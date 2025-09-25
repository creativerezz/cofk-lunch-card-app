"""
School Cafeteria NFC Payment System - Main Flask Application
"""

import os
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_cors import CORS
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from dotenv import load_dotenv
import json

# Import backend modules
from backend.models import db, init_db, Student, Card, MenuItem, Transaction, TransactionItem, Operator, SystemLog, CardStatus, TransactionType
from backend.nfc_service import get_nfc_service

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__, 
           template_folder='frontend/templates',
           static_folder='frontend/static')

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///database/cafeteria.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
CORS(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Initialize database
init_db(app)

# Initialize NFC service
nfc_service = get_nfc_service(os.getenv('NFC_ENCRYPTION_KEY'))

@login_manager.user_loader
def load_user(user_id):
    return Operator.query.get(int(user_id))

# ==================== Authentication Routes ====================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page and authentication"""
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        username = data.get('username')
        password = data.get('password')
        
        operator = Operator.query.filter_by(username=username).first()
        
        if operator and operator.check_password(password):
            login_user(operator)
            operator.last_login = datetime.utcnow()
            db.session.commit()
            
            # Log the login
            log = SystemLog(
                operator_id=operator.id,
                action='login',
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string
            )
            db.session.add(log)
            db.session.commit()
            
            if request.is_json:
                return jsonify({'success': True, 'redirect': url_for('dashboard')})
            return redirect(url_for('dashboard'))
        
        if request.is_json:
            return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
        flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Logout current user"""
    logout_user()
    return redirect(url_for('login'))

# ==================== Dashboard Routes ====================

@app.route('/')
@login_required
def dashboard():
    """Main dashboard"""
    # Get statistics
    total_students = Student.query.count()
    active_cards = Card.query.filter_by(status=CardStatus.ACTIVE.value).count()
    today = datetime.now().date()
    today_transactions = Transaction.query.filter(
        db.func.date(Transaction.created_at) == today
    ).count()
    today_revenue = db.session.query(db.func.sum(Transaction.amount)).filter(
        db.func.date(Transaction.created_at) == today,
        Transaction.transaction_type == TransactionType.PURCHASE.value
    ).scalar() or 0
    
    return render_template('dashboard.html',
                         total_students=total_students,
                         active_cards=active_cards,
                         today_transactions=today_transactions,
                         today_revenue=today_revenue)

@app.route('/pos')
@login_required
def pos():
    """Point of Sale interface"""
    menu_items = MenuItem.query.filter_by(is_available=True).all()
    categories = db.session.query(MenuItem.category).distinct().all()
    return render_template('pos.html', menu_items=menu_items, categories=[c[0] for c in categories if c[0]])

# ==================== NFC Card API Routes ====================

@app.route('/api/card/scan', methods=['POST'])
@login_required
def scan_card():
    """Scan NFC card and get information"""
    try:
        # Connect to reader if not connected
        if not nfc_service.reader:
            nfc_service.connect_reader()
        
        # Wait for card (timeout 10 seconds)
        card_uid = nfc_service.wait_for_card(timeout=10)
        
        if not card_uid:
            return jsonify({'success': False, 'error': 'No card detected'}), 404
        
        # Check if card is registered
        card = Card.query.filter_by(card_uid=card_uid).first()
        
        if not card:
            # New unregistered card
            return jsonify({
                'success': True,
                'card_uid': card_uid,
                'registered': False,
                'message': 'Unregistered card detected'
            })
        
        # Get card data
        card_data = nfc_service.read_card(card_uid)
        
        # Get student information
        student = card.student
        
        return jsonify({
            'success': True,
            'card_uid': card_uid,
            'registered': True,
            'balance': float(card.balance),
            'student': {
                'id': student.id,
                'name': student.full_name,
                'student_id': student.student_id,
                'grade': student.grade
            } if student else None,
            'status': card.status,
            'from_cache': card_data.get('from_cache', False) if card_data else False
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/card/register', methods=['POST'])
@login_required
def register_card():
    """Register a new NFC card to a student"""
    try:
        data = request.get_json()
        card_uid = data.get('card_uid')
        student_id = data.get('student_id')
        initial_balance = Decimal(str(data.get('initial_balance', 0)))
        
        # Check if card already exists
        existing_card = Card.query.filter_by(card_uid=card_uid).first()
        if existing_card:
            return jsonify({'success': False, 'error': 'Card already registered'}), 400
        
        # Get or create student
        student = Student.query.get(student_id)
        if not student:
            return jsonify({'success': False, 'error': 'Student not found'}), 404
        
        # Create new card
        card = Card(
            card_uid=card_uid,
            student_id=student.id,
            balance=initial_balance,
            status=CardStatus.ACTIVE.value
        )
        
        # Set PIN if provided
        if data.get('pin'):
            card.set_pin(data['pin'])
        
        db.session.add(card)
        
        # Write to physical card
        success = nfc_service.write_card(card_uid, initial_balance, student.student_id)
        
        if initial_balance > 0:
            # Create initial load transaction
            transaction = Transaction(
                transaction_id=str(uuid.uuid4()),
                card_id=card.id,
                student_id=student.id,
                operator_id=current_user.id,
                transaction_type=TransactionType.LOAD_FUNDS.value,
                amount=initial_balance,
                balance_before=0,
                balance_after=initial_balance,
                description='Initial card registration'
            )
            db.session.add(transaction)
        
        # Log the action
        log = SystemLog(
            operator_id=current_user.id,
            action='register_card',
            entity_type='card',
            entity_id=card.id,
            details={'card_uid': card_uid, 'student_id': student_id}
        )
        db.session.add(log)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Card registered successfully',
            'card_written': success
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/card/load', methods=['POST'])
@login_required
def load_funds():
    """Load funds onto a card"""
    try:
        data = request.get_json()
        card_uid = data.get('card_uid')
        amount = Decimal(str(data.get('amount')))
        
        if amount <= 0:
            return jsonify({'success': False, 'error': 'Invalid amount'}), 400
        
        # Get card
        card = Card.query.filter_by(card_uid=card_uid).first()
        if not card:
            return jsonify({'success': False, 'error': 'Card not found'}), 404
        
        # Check card status
        if card.status != CardStatus.ACTIVE.value:
            return jsonify({'success': False, 'error': f'Card is {card.status}'}), 400
        
        # Update balance
        balance_before = card.balance
        card.add_funds(amount)
        
        # Write to physical card
        nfc_service.write_card(card_uid, card.balance, card.student.student_id if card.student else None)
        
        # Create transaction
        transaction = Transaction(
            transaction_id=str(uuid.uuid4()),
            card_id=card.id,
            student_id=card.student_id,
            operator_id=current_user.id,
            transaction_type=TransactionType.LOAD_FUNDS.value,
            amount=amount,
            balance_before=balance_before,
            balance_after=card.balance,
            description=data.get('description', 'Funds loaded')
        )
        db.session.add(transaction)
        
        # Log the action
        log = SystemLog(
            operator_id=current_user.id,
            action='load_funds',
            entity_type='card',
            entity_id=card.id,
            details={'amount': float(amount)}
        )
        db.session.add(log)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'new_balance': float(card.balance),
            'transaction_id': transaction.transaction_id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== Transaction API Routes ====================

@app.route('/api/transaction/purchase', methods=['POST'])
@login_required
def process_purchase():
    """Process a purchase transaction"""
    try:
        data = request.get_json()
        card_uid = data.get('card_uid')
        items = data.get('items', [])  # [{menu_item_id: x, quantity: y}, ...]
        
        if not items:
            return jsonify({'success': False, 'error': 'No items selected'}), 400
        
        # Get card
        card = Card.query.filter_by(card_uid=card_uid).first()
        if not card:
            return jsonify({'success': False, 'error': 'Card not found'}), 404
        
        # Check card status
        if card.status != CardStatus.ACTIVE.value:
            return jsonify({'success': False, 'error': f'Card is {card.status}'}), 400
        
        # Calculate total
        total_amount = Decimal('0')
        transaction_items = []
        
        for item in items:
            menu_item = MenuItem.query.get(item['menu_item_id'])
            if not menu_item:
                continue
            
            quantity = item.get('quantity', 1)
            item_total = menu_item.price * quantity
            total_amount += item_total
            
            transaction_items.append({
                'menu_item': menu_item,
                'quantity': quantity,
                'unit_price': menu_item.price,
                'total_price': item_total
            })
        
        # Check balance
        if card.balance < total_amount:
            return jsonify({
                'success': False, 
                'error': 'Insufficient balance',
                'balance': float(card.balance),
                'required': float(total_amount)
            }), 400
        
        # Process payment
        balance_before = card.balance
        card.deduct_funds(total_amount)
        
        # Write to physical card
        nfc_service.write_card(card_uid, card.balance, card.student.student_id if card.student else None)
        
        # Create transaction
        transaction = Transaction(
            transaction_id=str(uuid.uuid4()),
            card_id=card.id,
            student_id=card.student_id,
            operator_id=current_user.id,
            transaction_type=TransactionType.PURCHASE.value,
            amount=total_amount,
            balance_before=balance_before,
            balance_after=card.balance,
            description='Cafeteria purchase'
        )
        db.session.add(transaction)
        db.session.flush()  # Get transaction ID
        
        # Create transaction items
        for item_data in transaction_items:
            trans_item = TransactionItem(
                transaction_id=transaction.id,
                menu_item_id=item_data['menu_item'].id,
                quantity=item_data['quantity'],
                unit_price=item_data['unit_price'],
                total_price=item_data['total_price']
            )
            db.session.add(trans_item)
        
        # Check for low balance alert
        if card.student and card.balance < card.student.low_balance_threshold:
            # TODO: Send notification (email/SMS)
            pass
        
        # Log the action
        log = SystemLog(
            operator_id=current_user.id,
            action='process_purchase',
            entity_type='transaction',
            entity_id=transaction.id,
            details={'amount': float(total_amount), 'items': len(items)}
        )
        db.session.add(log)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'transaction_id': transaction.transaction_id,
            'amount': float(total_amount),
            'new_balance': float(card.balance),
            'low_balance_warning': card.balance < 10
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/transaction/refund', methods=['POST'])
@login_required
def process_refund():
    """Process a refund"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        data = request.get_json()
        transaction_id = data.get('transaction_id')
        
        # Get original transaction
        original = Transaction.query.filter_by(transaction_id=transaction_id).first()
        if not original:
            return jsonify({'success': False, 'error': 'Transaction not found'}), 404
        
        # Check if already refunded
        if original.transaction_type == TransactionType.REFUND.value:
            return jsonify({'success': False, 'error': 'Transaction is already a refund'}), 400
        
        card = original.card
        
        # Process refund
        balance_before = card.balance
        card.add_funds(original.amount)
        
        # Write to physical card
        nfc_service.write_card(card.card_uid, card.balance, card.student.student_id if card.student else None)
        
        # Create refund transaction
        refund = Transaction(
            transaction_id=str(uuid.uuid4()),
            card_id=card.id,
            student_id=card.student_id,
            operator_id=current_user.id,
            transaction_type=TransactionType.REFUND.value,
            amount=original.amount,
            balance_before=balance_before,
            balance_after=card.balance,
            description=f'Refund for transaction {transaction_id}'
        )
        db.session.add(refund)
        
        # Log the action
        log = SystemLog(
            operator_id=current_user.id,
            action='process_refund',
            entity_type='transaction',
            entity_id=refund.id,
            details={'original_transaction': transaction_id, 'amount': float(original.amount)}
        )
        db.session.add(log)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'refund_id': refund.transaction_id,
            'amount': float(original.amount),
            'new_balance': float(card.balance)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== Student Management Routes ====================

@app.route('/students')
@login_required
def students():
    """Student management page"""
    all_students = Student.query.order_by(Student.last_name, Student.first_name).all()
    return render_template('students.html', students=all_students)

@app.route('/api/student', methods=['POST'])
@login_required
def create_student():
    """Create new student"""
    try:
        data = request.get_json()
        
        # Check if student ID already exists
        existing = Student.query.filter_by(student_id=data['student_id']).first()
        if existing:
            return jsonify({'success': False, 'error': 'Student ID already exists'}), 400
        
        student = Student(
            student_id=data['student_id'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            grade=data.get('grade'),
            email=data.get('email'),
            parent_email=data.get('parent_email'),
            parent_phone=data.get('parent_phone'),
            low_balance_threshold=Decimal(str(data.get('low_balance_threshold', 10)))
        )
        
        db.session.add(student)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'student_id': student.id,
            'message': 'Student created successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== Menu Management Routes ====================

@app.route('/menu')
@login_required
def menu_management():
    """Menu management page"""
    menu_items = MenuItem.query.order_by(MenuItem.category, MenuItem.name).all()
    return render_template('menu.html', menu_items=menu_items)

@app.route('/api/menu', methods=['POST'])
@login_required
def create_menu_item():
    """Create new menu item"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        data = request.get_json()
        
        menu_item = MenuItem(
            name=data['name'],
            description=data.get('description'),
            category=data.get('category'),
            price=Decimal(str(data['price'])),
            is_available=data.get('is_available', True),
            stock_quantity=data.get('stock_quantity'),
            image_url=data.get('image_url'),
            nutritional_info=data.get('nutritional_info')
        )
        
        db.session.add(menu_item)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'item_id': menu_item.id,
            'message': 'Menu item created successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/menu/<int:item_id>', methods=['PUT'])
@login_required
def update_menu_item(item_id):
    """Update menu item"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        menu_item = MenuItem.query.get(item_id)
        if not menu_item:
            return jsonify({'success': False, 'error': 'Item not found'}), 404
        
        data = request.get_json()
        
        if 'name' in data:
            menu_item.name = data['name']
        if 'description' in data:
            menu_item.description = data['description']
        if 'category' in data:
            menu_item.category = data['category']
        if 'price' in data:
            menu_item.price = Decimal(str(data['price']))
        if 'is_available' in data:
            menu_item.is_available = data['is_available']
        if 'stock_quantity' in data:
            menu_item.stock_quantity = data['stock_quantity']
        
        menu_item.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Menu item updated'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== Reports Routes ====================

@app.route('/reports')
@login_required
def reports():
    """Reports page"""
    return render_template('reports.html')

@app.route('/api/reports/daily', methods=['GET'])
@login_required
def daily_report():
    """Get daily transaction report"""
    date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    date = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    # Get transactions for the day
    transactions = Transaction.query.filter(
        db.func.date(Transaction.created_at) == date
    ).all()
    
    # Calculate totals
    total_sales = sum(t.amount for t in transactions if t.transaction_type == TransactionType.PURCHASE.value)
    total_loads = sum(t.amount for t in transactions if t.transaction_type == TransactionType.LOAD_FUNDS.value)
    total_refunds = sum(t.amount for t in transactions if t.transaction_type == TransactionType.REFUND.value)
    
    # Get popular items
    popular_items = db.session.query(
        MenuItem.name,
        db.func.sum(TransactionItem.quantity).label('total_quantity'),
        db.func.sum(TransactionItem.total_price).label('total_revenue')
    ).join(
        TransactionItem, MenuItem.id == TransactionItem.menu_item_id
    ).join(
        Transaction, Transaction.id == TransactionItem.transaction_id
    ).filter(
        db.func.date(Transaction.created_at) == date,
        Transaction.transaction_type == TransactionType.PURCHASE.value
    ).group_by(
        MenuItem.id, MenuItem.name
    ).order_by(
        db.func.sum(TransactionItem.quantity).desc()
    ).limit(10).all()
    
    return jsonify({
        'date': date_str,
        'total_transactions': len(transactions),
        'total_sales': float(total_sales),
        'total_loads': float(total_loads),
        'total_refunds': float(total_refunds),
        'net_revenue': float(total_sales - total_refunds),
        'popular_items': [
            {
                'name': item.name,
                'quantity': item.total_quantity,
                'revenue': float(item.total_revenue)
            }
            for item in popular_items
        ]
    })

@app.route('/api/reports/student/<int:student_id>', methods=['GET'])
@login_required
def student_report(student_id):
    """Get student transaction history"""
    student = Student.query.get(student_id)
    if not student:
        return jsonify({'error': 'Student not found'}), 404
    
    # Get date range
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = Transaction.query.filter_by(student_id=student_id)
    
    if start_date:
        query = query.filter(Transaction.created_at >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(Transaction.created_at <= datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1))
    
    transactions = query.order_by(Transaction.created_at.desc()).limit(100).all()
    
    return jsonify({
        'student': {
            'id': student.id,
            'name': student.full_name,
            'student_id': student.student_id,
            'current_balance': float(student.current_balance)
        },
        'transactions': [
            {
                'id': t.transaction_id,
                'date': t.created_at.isoformat(),
                'type': t.transaction_type,
                'amount': float(t.amount),
                'balance_after': float(t.balance_after),
                'description': t.description
            }
            for t in transactions
        ]
    })

# ==================== Offline Sync Routes ====================

@app.route('/api/sync/pending', methods=['GET'])
@login_required
def get_pending_sync():
    """Get pending offline transactions"""
    pending = nfc_service.get_pending_transactions()
    return jsonify({
        'count': len(pending),
        'transactions': pending
    })

@app.route('/api/sync/process', methods=['POST'])
@login_required
def process_sync():
    """Process pending offline transactions"""
    try:
        pending = nfc_service.get_pending_transactions()
        synced = 0
        errors = []
        
        for trans in pending:
            try:
                # Process based on transaction type
                card = Card.query.filter_by(card_uid=trans['card_uid']).first()
                if not card:
                    errors.append(f"Card {trans['card_uid']} not found")
                    continue
                
                if trans['transaction_type'] == 'purchase':
                    # Process offline purchase
                    card.deduct_funds(trans['amount'])
                elif trans['transaction_type'] == 'load':
                    # Process offline load
                    card.add_funds(trans['amount'])
                
                # Create transaction record
                transaction = Transaction(
                    transaction_id=str(uuid.uuid4()),
                    card_id=card.id,
                    student_id=card.student_id,
                    operator_id=current_user.id,
                    transaction_type=trans['transaction_type'],
                    amount=trans['amount'],
                    description=f"Offline transaction synced from {trans['timestamp']}"
                )
                db.session.add(transaction)
                
                # Mark as synced
                nfc_service.mark_transaction_synced(trans['id'])
                synced += 1
                
            except Exception as e:
                errors.append(f"Error syncing transaction {trans['id']}: {str(e)}")
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'synced': synced,
            'errors': errors
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== Error Handlers ====================

@app.errorhandler(404)
def not_found(error):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Not found'}), 404
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error'}), 500
    return render_template('500.html'), 500

# ==================== Main ====================

if __name__ == '__main__':
    # Create database directory if it doesn't exist
    os.makedirs('database', exist_ok=True)
    
    # Run the app
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=os.getenv('FLASK_ENV') == 'development'
    )
"""
Database models for School Cafeteria NFC Payment System
"""

from datetime import datetime
from decimal import Decimal
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import event
import enum

db = SQLAlchemy()

class UserRole(enum.Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"

class TransactionType(enum.Enum):
    LOAD_FUNDS = "load_funds"
    PURCHASE = "purchase"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"

class CardStatus(enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    LOST = "lost"
    EXPIRED = "expired"

class Student(db.Model):
    """Student model - represents a student in the system"""
    __tablename__ = 'students'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), unique=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    grade = db.Column(db.String(10))
    email = db.Column(db.String(120))
    parent_email = db.Column(db.String(120))
    parent_phone = db.Column(db.String(20))
    low_balance_threshold = db.Column(db.Numeric(10, 2), default=10.00)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    cards = db.relationship('Card', backref='student', lazy='dynamic')
    transactions = db.relationship('Transaction', backref='student', lazy='dynamic')
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def active_card(self):
        return self.cards.filter_by(status=CardStatus.ACTIVE.value).first()
    
    @property
    def current_balance(self):
        card = self.active_card
        return card.balance if card else Decimal('0.00')

class Card(db.Model):
    """NFC Card model - represents physical NFC cards"""
    __tablename__ = 'cards'
    
    id = db.Column(db.Integer, primary_key=True)
    card_uid = db.Column(db.String(50), unique=True, nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    balance = db.Column(db.Numeric(10, 2), default=0.00, nullable=False)
    status = db.Column(db.String(20), default=CardStatus.ACTIVE.value)
    pin_hash = db.Column(db.String(255))  # Optional PIN for security
    issued_date = db.Column(db.DateTime, default=datetime.utcnow)
    expiry_date = db.Column(db.DateTime)
    last_used = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def set_pin(self, pin):
        """Set PIN for the card"""
        if pin:
            self.pin_hash = generate_password_hash(str(pin))
    
    def verify_pin(self, pin):
        """Verify PIN"""
        if not self.pin_hash:
            return True  # No PIN set
        return check_password_hash(self.pin_hash, str(pin))
    
    def add_funds(self, amount):
        """Add funds to the card"""
        self.balance += Decimal(str(amount))
        self.last_used = datetime.utcnow()
        return self.balance
    
    def deduct_funds(self, amount):
        """Deduct funds from the card"""
        amount = Decimal(str(amount))
        if self.balance >= amount:
            self.balance -= amount
            self.last_used = datetime.utcnow()
            return True
        return False

class MenuItem(db.Model):
    """Menu items available in the cafeteria"""
    __tablename__ = 'menu_items'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))  # breakfast, lunch, snack, drink
    price = db.Column(db.Numeric(10, 2), nullable=False)
    is_available = db.Column(db.Boolean, default=True)
    stock_quantity = db.Column(db.Integer)  # Optional stock tracking
    image_url = db.Column(db.String(255))
    nutritional_info = db.Column(db.JSON)  # Store calories, allergens, etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    transaction_items = db.relationship('TransactionItem', backref='menu_item', lazy='dynamic')

class Transaction(db.Model):
    """Transaction records for all financial activities"""
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.String(50), unique=True, nullable=False)
    card_id = db.Column(db.Integer, db.ForeignKey('cards.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    operator_id = db.Column(db.Integer, db.ForeignKey('operators.id'))
    transaction_type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    balance_before = db.Column(db.Numeric(10, 2))
    balance_after = db.Column(db.Numeric(10, 2))
    description = db.Column(db.Text)
    is_synced = db.Column(db.Boolean, default=False)  # For offline sync
    synced_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    card = db.relationship('Card', backref='transactions')
    operator = db.relationship('Operator', backref='transactions')
    items = db.relationship('TransactionItem', backref='transaction', lazy='dynamic')

class TransactionItem(db.Model):
    """Items purchased in a transaction"""
    __tablename__ = 'transaction_items'
    
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=False)
    menu_item_id = db.Column(db.Integer, db.ForeignKey('menu_items.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    total_price = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Operator(db.Model, UserMixin):
    """Operator/Admin users who manage the system"""
    __tablename__ = 'operators'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    role = db.Column(db.String(20), default=UserRole.OPERATOR.value)
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    @property
    def is_admin(self):
        return self.role == UserRole.ADMIN.value

class SystemLog(db.Model):
    """System activity logs for auditing"""
    __tablename__ = 'system_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    operator_id = db.Column(db.Integer, db.ForeignKey('operators.id'))
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50))  # card, student, menu_item, etc.
    entity_id = db.Column(db.Integer)
    details = db.Column(db.JSON)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    operator = db.relationship('Operator', backref='logs')

class OfflineTransaction(db.Model):
    """Store offline transactions for later sync"""
    __tablename__ = 'offline_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    local_id = db.Column(db.String(50), unique=True, nullable=False)
    card_uid = db.Column(db.String(50), nullable=False)
    transaction_data = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    synced = db.Column(db.Boolean, default=False)
    synced_at = db.Column(db.DateTime)
    sync_error = db.Column(db.Text)

# Database initialization helper
def init_db(app):
    """Initialize database with the Flask app"""
    db.init_app(app)
    with app.app_context():
        db.create_all()
        
        # Create default admin if not exists
        admin = Operator.query.filter_by(username='admin').first()
        if not admin:
            admin = Operator(
                username='admin',
                email='admin@school.edu',
                first_name='System',
                last_name='Administrator',
                role=UserRole.ADMIN.value
            )
            admin.set_password('admin123')  # Change this in production!
            db.session.add(admin)
            db.session.commit()
            print("Default admin user created: admin/admin123")

#!/usr/bin/env python3
"""
Setup script for School Cafeteria NFC Payment System
"""

import os
import sys
from decimal import Decimal
from datetime import datetime

# Add project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from backend.models import db, Student, MenuItem, Operator, UserRole

def create_sample_data():
    """Create sample data for testing"""
    with app.app_context():
        # Create sample students
        students = [
            {"student_id": "S001", "first_name": "John", "last_name": "Doe", "grade": "10", 
             "email": "john.doe@school.edu", "parent_email": "parent.doe@email.com"},
            {"student_id": "S002", "first_name": "Jane", "last_name": "Smith", "grade": "11", 
             "email": "jane.smith@school.edu", "parent_email": "parent.smith@email.com"},
            {"student_id": "S003", "first_name": "Bob", "last_name": "Johnson", "grade": "9", 
             "email": "bob.johnson@school.edu", "parent_email": "parent.johnson@email.com"},
            {"student_id": "S004", "first_name": "Alice", "last_name": "Williams", "grade": "12", 
             "email": "alice.williams@school.edu", "parent_email": "parent.williams@email.com"},
            {"student_id": "S005", "first_name": "Charlie", "last_name": "Brown", "grade": "10", 
             "email": "charlie.brown@school.edu", "parent_email": "parent.brown@email.com"},
        ]
        
        for s in students:
            existing = Student.query.filter_by(student_id=s["student_id"]).first()
            if not existing:
                student = Student(**s)
                db.session.add(student)
        
        # Create sample menu items
        menu_items = [
            # Breakfast items
            {"name": "Pancakes", "description": "Stack of 3 pancakes with syrup", 
             "category": "breakfast", "price": Decimal("4.50"), "is_available": True},
            {"name": "French Toast", "description": "Two slices with powdered sugar", 
             "category": "breakfast", "price": Decimal("3.75"), "is_available": True},
            {"name": "Scrambled Eggs", "description": "With toast and hash browns", 
             "category": "breakfast", "price": Decimal("5.00"), "is_available": True},
            {"name": "Breakfast Burrito", "description": "Eggs, cheese, and sausage", 
             "category": "breakfast", "price": Decimal("4.25"), "is_available": True},
            
            # Lunch items
            {"name": "Hamburger", "description": "Beef patty with lettuce and tomato", 
             "category": "lunch", "price": Decimal("6.50"), "is_available": True},
            {"name": "Cheeseburger", "description": "Hamburger with cheese", 
             "category": "lunch", "price": Decimal("7.00"), "is_available": True},
            {"name": "Chicken Sandwich", "description": "Grilled chicken breast", 
             "category": "lunch", "price": Decimal("6.75"), "is_available": True},
            {"name": "Pizza Slice", "description": "Cheese or pepperoni", 
             "category": "lunch", "price": Decimal("3.50"), "is_available": True},
            {"name": "Caesar Salad", "description": "Fresh romaine with croutons", 
             "category": "lunch", "price": Decimal("5.50"), "is_available": True},
            {"name": "Pasta Bowl", "description": "Spaghetti with marinara sauce", 
             "category": "lunch", "price": Decimal("5.75"), "is_available": True},
            
            # Snacks
            {"name": "Apple", "description": "Fresh fruit", 
             "category": "snack", "price": Decimal("1.00"), "is_available": True},
            {"name": "Banana", "description": "Fresh fruit", 
             "category": "snack", "price": Decimal("0.75"), "is_available": True},
            {"name": "Chips", "description": "Individual bag", 
             "category": "snack", "price": Decimal("1.50"), "is_available": True},
            {"name": "Cookie", "description": "Chocolate chip", 
             "category": "snack", "price": Decimal("1.25"), "is_available": True},
            {"name": "Granola Bar", "description": "Healthy snack", 
             "category": "snack", "price": Decimal("1.75"), "is_available": True},
            
            # Drinks
            {"name": "Water Bottle", "description": "16 oz", 
             "category": "drink", "price": Decimal("1.00"), "is_available": True},
            {"name": "Juice Box", "description": "Apple or orange", 
             "category": "drink", "price": Decimal("1.50"), "is_available": True},
            {"name": "Milk", "description": "Regular or chocolate", 
             "category": "drink", "price": Decimal("1.25"), "is_available": True},
            {"name": "Soda", "description": "Coke, Sprite, or Fanta", 
             "category": "drink", "price": Decimal("2.00"), "is_available": True},
            {"name": "Sports Drink", "description": "Gatorade", 
             "category": "drink", "price": Decimal("2.50"), "is_available": True},
        ]
        
        for item in menu_items:
            existing = MenuItem.query.filter_by(name=item["name"]).first()
            if not existing:
                menu_item = MenuItem(**item)
                db.session.add(menu_item)
        
        # Create additional operator account
        operator = Operator.query.filter_by(username='operator').first()
        if not operator:
            operator = Operator(
                username='operator',
                email='operator@school.edu',
                first_name='Test',
                last_name='Operator',
                role=UserRole.OPERATOR.value
            )
            operator.set_password('operator123')
            db.session.add(operator)
        
        db.session.commit()
        print("✅ Sample data created successfully!")

def main():
    """Main setup function"""
    print("=" * 50)
    print("School Cafeteria NFC Payment System Setup")
    print("=" * 50)
    
    # Create database directory
    os.makedirs('database', exist_ok=True)
    
    # Initialize database
    print("\n1. Initializing database...")
    with app.app_context():
        db.create_all()
        print("✅ Database initialized")
    
    # Create sample data
    print("\n2. Creating sample data...")
    create_sample_data()
    
    # Print access information
    print("\n" + "=" * 50)
    print("Setup Complete!")
    print("=" * 50)
    print("\nAccess Information:")
    print("-" * 30)
    print("Admin Login:")
    print("  Username: admin")
    print("  Password: admin123")
    print("\nOperator Login:")
    print("  Username: operator")
    print("  Password: operator123")
    print("\nTo start the server:")
    print("  python app.py")
    print("\nThen access: http://localhost:5000")
    print("=" * 50)

if __name__ == "__main__":
    main()
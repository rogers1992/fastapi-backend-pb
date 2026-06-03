"""
Import seed data into the database
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, engine
from app.models.product import Product, Category, Supplier
from app.models.customer import Customer, Loyalty
from app.models.inventory import InventoryItem, Warehouse
from app.models.user import User, Role
from app.core.security import get_password_hash
from datetime import datetime

def import_seed_data():
    """Import all seed data into the database"""
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    # Create session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Load seed files
        with open('products_seed.json', 'r', encoding='utf-8') as f:
            products_data = json.load(f)
        
        with open('customers_seed.json', 'r', encoding='utf-8') as f:
            customers_data = json.load(f)
        
        with open('inventory_seed.json', 'r', encoding='utf-8') as f:
            inventory_data = json.load(f)
        
        # Insert products
        print(f"Inserting {len(products_data)} products...")
        for product_data in products_data:
            product = Product(**product_data)
            db.add(product)
        db.commit()
        print(f"✓ Products inserted")
        
        # Insert customers with loyalty
        print(f"Inserting {len(customers_data)} customers...")
        for customer_data in customers_data:
            # Create loyalty record
            loyalty = Loyalty(points=0, tier='bronze')
            db.add(loyalty)
            db.flush()
            
            # Create customer
            customer = Customer(
                **customer_data,
                loyalty_id=loyalty.id
            )
            db.add(customer)
        db.commit()
        print(f"✓ Customers inserted")
        
        # Insert inventory items
        print(f"Inserting {len(inventory_data)} inventory items...")
        for inventory_item_data in inventory_data:
            item = InventoryItem(**inventory_item_data)
            db.add(item)
        db.commit()
        print(f"✓ Inventory items inserted")
        
        print("\n✓ All seed data imported successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"✗ Error importing seed data: {e}")
        raise
    finally:
        db.close()

if __name__ == '__main__':
    import_seed_data()

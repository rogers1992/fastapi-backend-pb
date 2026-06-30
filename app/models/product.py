from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base

class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"))
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    sku = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    barcode = Column(String(100), unique=True, index=True)
    unit_price = Column(Numeric(10, 2), nullable=False)
    weight = Column(Numeric(8, 2))
    dimensions = Column(JSONB)
    image_url = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    category = relationship("Category", back_populates="products")
    supplier = relationship("Supplier", back_populates="products")
    inventory_items = relationship("InventoryItem", back_populates="product")
    sale_items = relationship("SaleItem", back_populates="product")

class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    parent_id = Column(Integer, ForeignKey("categories.id"))
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    products = relationship("Product", back_populates="category")

class Supplier(Base):
    __tablename__ = "suppliers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    contact_info = Column(JSONB)
    address = Column(Text)
    email = Column(String(100))
    phone = Column(String(20))
    website = Column(String(200))
    payment_terms = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    products = relationship("Product", back_populates="supplier")

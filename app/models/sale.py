from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Numeric, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base

class Sale(Base):
    __tablename__ = "sales"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=True)
    payment_method = Column(String(50), nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=False)
    tax_amount = Column(Numeric(10, 2), default=0)
    status = Column(String(20), nullable=False, default='completed')
    sale_date = Column(DateTime, server_default=func.now())
    notes = Column(Text)
    
    # Relationships
    customer = relationship("Customer", back_populates="sales")
    user = relationship("User", back_populates="sales")
    warehouse = relationship("Warehouse", back_populates="sales")
    sale_items = relationship("SaleItem", back_populates="sale")

    @property
    def items(self):
        return self.sale_items

    @property
    def warehouse_name(self):
        return self.warehouse.name if self.warehouse else None

class SaleItem(Base):
    __tablename__ = "sale_items"
    
    id = Column(Integer, primary_key=True, index=True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    discount = Column(Numeric(10, 2), default=0)
    total_price = Column(Numeric(10, 2), nullable=False)
    notes = Column(Text)
    
    # Relationships
    sale = relationship("Sale", back_populates="sale_items")
    product = relationship("Product", back_populates="sale_items")

    @property
    def product_name(self) -> str:
        return self.product.name if self.product else f"Producto #{self.product_id}"

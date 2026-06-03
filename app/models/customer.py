from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Date, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base

class Customer(Base):
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True, index=True)
    loyalty_id = Column(Integer, ForeignKey("loyalty.id"))
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    email = Column(String(100), unique=True, index=True)
    phone = Column(String(20))
    address = Column(Text)
    date_of_birth = Column(Date)
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    sales = relationship("Sale", back_populates="customer")

class Loyalty(Base):
    __tablename__ = "loyalty"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), unique=True)
    points = Column(Integer, default=0)
    tier = Column(String(20), default='bronze')
    last_updated = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())

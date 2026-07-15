from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Date, Numeric, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"))
    status = Column(String(20), nullable=False, default="pending")
    total_amount = Column(Numeric(10, 2), default=0)
    order_date = Column(DateTime, server_default=func.now())
    expected_date = Column(Date)
    received_date = Column(Date)
    created_by = Column(Integer, ForeignKey("users.id"))
    notes = Column(Text)

    # Relationships
    supplier = relationship("Supplier", back_populates="orders")
    warehouse = relationship("Warehouse", back_populates="orders")
    user = relationship("User", back_populates="orders")
    order_items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

    @property
    def items(self):
        return self.order_items


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_cost = Column(Numeric(10, 2), nullable=False)
    total_price = Column(Numeric(10, 2), nullable=False)
    received_quantity = Column(Integer, default=0)
    notes = Column(Text)

    # Relationships
    order = relationship("Order", back_populates="order_items")
    product = relationship("Product", back_populates="order_items")

    @property
    def product_name(self) -> str:
        return self.product.name if self.product else f"Producto #{self.product_id}"
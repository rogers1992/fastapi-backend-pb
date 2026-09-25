from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Numeric, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class ExpenseCategory(Base):
    __tablename__ = "expense_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(String(255))
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    expenses = relationship("Expense", back_populates="category")


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("expense_categories.id"), nullable=False)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    description = Column(String(500))
    expense_date = Column(DateTime, server_default=func.now())
    payment_method = Column(String(50), default="efectivo")
    is_recurring = Column(Boolean, default=False)
    recorded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    category = relationship("ExpenseCategory", back_populates="expenses")
    warehouse = relationship("Warehouse", back_populates="expenses")
    user = relationship("User", back_populates="expenses")

    @property
    def category_name(self):
        return self.category.name if self.category else None

    @property
    def warehouse_name(self):
        return self.warehouse.name if self.warehouse else None

    @property
    def recorded_by_name(self):
        if self.user:
            return f"{self.user.first_name} {self.user.last_name}".strip()
        return None

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Numeric, Text, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base
import enum

class CashRegisterStatus(enum.Enum):
    open = "open"
    closed = "closed"

class MovementType(enum.Enum):
    ingreso = "ingreso"
    egreso = "egreso"

class CashRegister(Base):
    __tablename__ = "cash_registers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    
    sessions = relationship("CashSession", back_populates="register")
    warehouse = relationship("Warehouse", back_populates="cash_registers")

class CashSession(Base):
    __tablename__ = "cash_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    register_id = Column(Integer, ForeignKey("cash_registers.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    closed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    opening_amount = Column(Numeric(10, 2), nullable=False, default=0)
    closing_amount = Column(Numeric(10, 2), nullable=True)
    expected_amount = Column(Numeric(10, 2), nullable=True)
    discrepancy = Column(Numeric(10, 2), nullable=True)
    opening_notes = Column(Text)
    closing_notes = Column(Text)
    opened_at = Column(DateTime, server_default=func.now())
    closed_at = Column(DateTime, nullable=True)
    status = Column(SAEnum(CashRegisterStatus), nullable=False, default=CashRegisterStatus.open)
    
    register = relationship("CashRegister", back_populates="sessions")
    user = relationship("User", foreign_keys=[user_id], backref="opened_sessions")
    closed_by_user = relationship("User", foreign_keys=[closed_by_user_id], backref="closed_sessions")
    movements = relationship("CashMovement", back_populates="session", cascade="all, delete-orphan")
    sales = relationship("Sale", back_populates="cash_session")

class CashMovement(Base):
    __tablename__ = "cash_movements"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("cash_sessions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(SAEnum(MovementType), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    reason = Column(String(200), nullable=False)
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    
    session = relationship("CashSession", back_populates="movements")
    user = relationship("User", backref="cash_movements")

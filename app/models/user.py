from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from typing import List
from ..database import Base
from .associations import user_warehouses

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, ForeignKey("roles.id"))
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    phone = Column(String(20))
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    role = relationship("Role", back_populates="users", lazy="joined")
    sales = relationship("Sale", back_populates="user")
    orders = relationship("Order", back_populates="user")
    warehouses = relationship(
        "Warehouse",
        secondary=user_warehouses,
        back_populates="users",
        lazy="joined"
    )

    @property
    def warehouse_ids(self) -> List[int]:
        return [w.id for w in self.warehouses] if self.warehouses else []

class Role(Base):
    __tablename__ = "roles"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    permissions = Column(JSONB, default=dict)
    description = Column(Text)
    is_system = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    
    users = relationship("User", back_populates="role")

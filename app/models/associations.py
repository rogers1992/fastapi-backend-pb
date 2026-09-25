from sqlalchemy import Table, Column, Integer, ForeignKey
from ..database import Base

user_warehouses = Table(
    "user_warehouses",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("warehouse_id", Integer, ForeignKey("warehouses.id", ondelete="CASCADE"), primary_key=True),
)

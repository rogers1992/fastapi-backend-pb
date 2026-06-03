from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from decimal import Decimal

class InventoryItemBase(BaseModel):
    product_id: int
    warehouse_id: int
    quantity: int
    min_stock_level: Optional[int] = 0
    max_stock_level: Optional[int] = None
    location: Optional[str] = None

class InventoryItemCreate(InventoryItemBase):
    pass

class InventoryItemUpdate(BaseModel):
    quantity: Optional[int] = None
    min_stock_level: Optional[int] = None
    max_stock_level: Optional[int] = None
    location: Optional[str] = None

class InventoryItemResponse(InventoryItemBase):
    id: int
    reserved_quantity: int
    last_updated: datetime
    
    class Config:
        from_attributes = True

class InventoryTransfer(BaseModel):
    product_id: int
    from_warehouse_id: int
    to_warehouse_id: int
    quantity: int

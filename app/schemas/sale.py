from pydantic import BaseModel

from . import BaseSchema
from datetime import datetime
from typing import List, Optional
from decimal import Decimal

class SaleItemBase(BaseSchema):
    product_id: int
    quantity: int
    unit_price: Decimal
    discount: Optional[Decimal] = 0

class SaleItemCreate(SaleItemBase):
    pass

class SaleItemResponse(SaleItemBase):
    id: int
    sale_id: int
    product_name: str
    total_price: Decimal
    
    class Config:
        from_attributes = True

class SaleBase(BaseSchema):
    customer_id: int
    warehouse_id: Optional[int] = None
    payment_method: str
    notes: Optional[str] = None

class SaleCreate(SaleBase):
    items: List[SaleItemCreate]

class SaleUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None

class SaleResponse(SaleBase):
    id: int
    user_id: int
    warehouse_name: Optional[str] = None
    total_amount: Decimal
    tax_amount: Decimal
    status: str
    sale_date: datetime
    items: List[SaleItemResponse] = []

    class Config:
        from_attributes = True

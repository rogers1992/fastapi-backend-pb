from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
from decimal import Decimal

class SaleItemBase(BaseModel):
    product_id: int
    quantity: int
    unit_price: Decimal
    discount: Optional[Decimal] = 0

class SaleItemCreate(SaleItemBase):
    pass

class SaleItemResponse(SaleItemBase):
    id: int
    sale_id: int
    total_price: Decimal
    
    class Config:
        from_attributes = True

class SaleBase(BaseModel):
    customer_id: int
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
    total_amount: Decimal
    tax_amount: Decimal
    status: str
    sale_date: datetime
    items: List[SaleItemResponse] = []
    
    class Config:
        from_attributes = True

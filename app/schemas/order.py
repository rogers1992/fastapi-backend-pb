from pydantic import BaseModel
from datetime import datetime, date
from typing import List, Optional
from decimal import Decimal


class OrderItemBase(BaseModel):
    product_id: int
    quantity: int
    unit_cost: Decimal


class OrderItemCreate(OrderItemBase):
    pass


class OrderItemResponse(OrderItemBase):
    id: int
    order_id: int
    product_name: str
    total_price: Decimal
    received_quantity: int

    class Config:
        from_attributes = True


class OrderBase(BaseModel):
    supplier_id: int
    warehouse_id: int
    expected_date: Optional[date] = None
    notes: Optional[str] = None


class OrderCreate(OrderBase):
    items: List[OrderItemCreate]


class OrderUpdate(BaseModel):
    notes: Optional[str] = None


class OrderResponse(OrderBase):
    id: int
    created_by: int
    status: str
    total_amount: Decimal
    order_date: datetime
    received_date: Optional[date] = None
    items: List[OrderItemResponse] = []

    class Config:
        from_attributes = True
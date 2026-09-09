from pydantic import BaseModel, Field
from . import BaseSchema
from datetime import datetime
from typing import List, Optional
from decimal import Decimal

class CashRegisterBase(BaseSchema):
    name: str
    warehouse_id: Optional[int] = None

class CashRegisterCreate(CashRegisterBase):
    pass

class CashRegisterUpdate(BaseModel):
    name: Optional[str] = None
    warehouse_id: Optional[int] = None
    is_active: Optional[bool] = None

class CashRegisterResponse(CashRegisterBase):
    id: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class CashMovementBase(BaseSchema):
    type: str
    amount: Decimal
    reason: str
    notes: Optional[str] = None

class CashMovementCreate(CashMovementBase):
    session_id: Optional[int] = None

class CashMovementResponse(CashMovementBase):
    id: int
    session_id: int
    user_id: int
    created_at: datetime
    warehouse_name: Optional[str] = None
    
    class Config:
        from_attributes = True

class CashSessionOpen(BaseSchema):
    register_id: int
    opening_amount: Decimal = Field(ge=0)
    notes: Optional[str] = None

class CashSessionClose(BaseModel):
    closing_amount: Decimal = Field(ge=0)
    notes: Optional[str] = None

class CashSessionResponse(BaseSchema):
    id: int
    register_id: int
    warehouse_id: Optional[int] = None
    warehouse_name: Optional[str] = None
    user_id: int
    opening_amount: Decimal
    closing_amount: Optional[Decimal] = None
    expected_amount: Optional[Decimal] = None
    discrepancy: Optional[Decimal] = None
    opening_notes: Optional[str] = None
    closing_notes: Optional[str] = None
    opened_at: datetime
    closed_at: Optional[datetime] = None
    status: str
    sales_total: Decimal = Decimal(0)
    sales_count: int = 0
    cash_sales_total: Decimal = Decimal(0)
    movements: List[CashMovementResponse] = []
    
    class Config:
        from_attributes = True


class WarehouseCajaSummary(BaseModel):
    warehouse_id: int
    warehouse_name: str
    register_id: Optional[int] = None
    register_name: Optional[str] = None
    session: Optional[CashSessionResponse] = None

class CashSessionSummary(BaseSchema):
    session: CashSessionResponse
    sales_by_payment: dict = {}
    total_movements_in: Decimal = Decimal(0)
    total_movements_out: Decimal = Decimal(0)

from pydantic import BaseModel
from . import BaseSchema
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional


class ExpenseCategoryResponse(BaseSchema):
    id: int
    name: str
    description: Optional[str] = None
    sort_order: int
    is_active: bool


class ExpenseCreate(BaseSchema):
    category_id: int
    warehouse_id: Optional[int] = None
    amount: Decimal
    description: Optional[str] = None
    expense_date: Optional[datetime] = None
    payment_method: str = "efectivo"
    is_recurring: bool = False
    notes: Optional[str] = None


class ExpenseUpdate(BaseModel):
    category_id: Optional[int] = None
    warehouse_id: Optional[int] = None
    amount: Optional[Decimal] = None
    description: Optional[str] = None
    expense_date: Optional[datetime] = None
    payment_method: Optional[str] = None
    is_recurring: Optional[bool] = None
    notes: Optional[str] = None


class ExpenseResponse(BaseSchema):
    id: int
    category_id: int
    category_name: Optional[str] = None
    warehouse_id: Optional[int] = None
    warehouse_name: Optional[str] = None
    amount: Decimal
    description: Optional[str] = None
    expense_date: Optional[datetime] = None
    payment_method: str
    is_recurring: bool
    recorded_by: int
    recorded_by_name: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


class ExpenseSummary(BaseSchema):
    category_name: str
    total: float
    count: int


class IncomeStatementResponse(BaseSchema):
    warehouse_id: Optional[int] = None
    warehouse_name: Optional[str] = None
    period_start: str
    period_end: str
    revenue: float
    cogs: float
    gross_profit: float
    gross_margin_pct: float
    expenses: List[ExpenseSummary]
    total_expenses: float
    net_profit: float
    net_margin_pct: float

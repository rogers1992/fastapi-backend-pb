"""Dashboard endpoints — KPI tiles and chart series.

All endpoints require the `reports.read` permission (pre-registered in
`app/schemas/role.py` and seeded for the `admin` and `gerente` roles).
"""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.dependencies import get_user_timezone, require_permission
from ..database import get_db
from ..models.user import User
from ..schemas.dashboard import (
    DashboardSummary,
    InventoryStatusSummary,
    PaymentMethodRow,
    SalesTrendPoint,
    TopCustomerRow,
    TopProductRow,
)
from ..services.report_service import (
    dashboard_summary,
    inventory_status,
    payment_method_breakdown,
    sales_trend,
    top_customers,
    top_products,
)

router = APIRouter()


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    warehouse_id: Optional[list[int]] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports", "read")),
    tz: str = Depends(get_user_timezone),
):
    return dashboard_summary(db, current_user, tz=tz, warehouse_id=warehouse_id)


@router.get("/sales-trend", response_model=List[SalesTrendPoint])
async def get_sales_trend(
    period: str = Query("daily", pattern="^(daily|weekly|monthly)$"),
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    warehouse_id: Optional[list[int]] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports", "read")),
    tz: str = Depends(get_user_timezone),
):
    return sales_trend(db, current_user, period=period, from_date=from_date, to_date=to_date, warehouse_id=warehouse_id, tz=tz)


@router.get("/inventory-status", response_model=InventoryStatusSummary)
async def get_inventory_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports", "read")),
):
    return inventory_status(db)


@router.get("/top-products", response_model=List[TopProductRow])
async def get_top_products(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    warehouse_id: Optional[list[int]] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports", "read")),
):
    return top_products(db, current_user, from_date=from_date, to_date=to_date, warehouse_id=warehouse_id, limit=limit)


@router.get("/top-customers", response_model=List[TopCustomerRow])
async def get_top_customers(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports", "read")),
):
    return top_customers(db, from_date=from_date, to_date=to_date, limit=limit)


@router.get("/payment-methods", response_model=List[PaymentMethodRow])
async def get_payment_method_breakdown(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    warehouse_id: Optional[list[int]] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports", "read")),
):
    return payment_method_breakdown(db, current_user, from_date=from_date, to_date=to_date, warehouse_id=warehouse_id)
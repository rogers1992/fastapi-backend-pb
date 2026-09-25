"""Reports endpoints — detailed tabular reports with CSV export.

All endpoints require the `reports.read` permission. CSV export uses only
Python stdlib `csv` + FastAPI `StreamingResponse`; no extra dependencies.
"""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..core.dependencies import require_permission
from ..database import get_db
from ..models.user import User
from ..schemas.report import (
    CustomerReportRow,
    InventoryReportRow,
    ProductReportRow,
    ProfitSummaryRow,
    PurchaseReportRow,
    SalesReportRow,
)
from ..services.report_service import (
    ABC_REPORT_HEADERS,
    CUSTOMERS_REPORT_HEADERS,
    INVENTORY_REPORT_HEADERS,
    PROFIT_REPORT_HEADERS,
    PROFIT_SUMMARY_REPORT_HEADERS,
    PRODUCTS_REPORT_HEADERS,
    PURCHASES_REPORT_HEADERS,
    SALES_REPORT_HEADERS,
    SELLERS_REPORT_HEADERS,
    SLOW_MOVING_REPORT_HEADERS,
    abc_report,
    customers_report,
    inventory_report,
    products_report,
    profit_report,
    profit_summary_report,
    purchases_report,
    rows_to_csv_response,
    sales_report,
    sellers_report,
    slow_moving_report,
)

router = APIRouter()


def _maybe_csv(rows, headers, filename, fmt):
    if fmt == "csv":
        return rows_to_csv_response(rows, headers, filename=filename)
    return rows


@router.get("/sales")
async def get_sales_report(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    seller_id: Optional[int] = Query(None),
    customer_id: Optional[int] = Query(None),
    warehouse_id: Optional[list[int]] = Query(None),
    format: str = Query("json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports", "read")),
):
    rows = sales_report(
        db, current_user,
        from_date=from_date, to_date=to_date,
        seller_id=seller_id, customer_id=customer_id,
        warehouse_id=warehouse_id,
    )
    return _maybe_csv(rows, SALES_REPORT_HEADERS, "sales_report.csv", format) \
        if format == "csv" else JSONResponse(content=rows)


@router.get("/inventory")
async def get_inventory_report(
    format: str = Query("json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports", "read")),
):
    rows = inventory_report(db, current_user)
    if format == "csv":
        return rows_to_csv_response(rows, INVENTORY_REPORT_HEADERS, "inventory_report.csv")
    return JSONResponse(content=rows)


@router.get("/purchases")
async def get_purchases_report(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    status: Optional[str] = Query(None),
    format: str = Query("json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports", "read")),
):
    rows = purchases_report(db, from_date=from_date, to_date=to_date, status=status)
    if format == "csv":
        return rows_to_csv_response(rows, PURCHASES_REPORT_HEADERS, "purchases_report.csv")
    return JSONResponse(content=rows)


@router.get("/customers")
async def get_customers_report(
    format: str = Query("json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports", "read")),
):
    rows = customers_report(db)
    if format == "csv":
        return rows_to_csv_response(rows, CUSTOMERS_REPORT_HEADERS, "customers_report.csv")
    return JSONResponse(content=rows)


@router.get("/products")
async def get_products_report(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    format: str = Query("json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports", "read")),
):
    rows = products_report(db, current_user, from_date=from_date, to_date=to_date)
    if format == "csv":
        return rows_to_csv_response(rows, PRODUCTS_REPORT_HEADERS, "products_report.csv")
    return JSONResponse(content=rows)


@router.get("/profit")
async def get_profit_report(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    warehouse_id: Optional[list[int]] = Query(None),
    format: str = Query("json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports", "read")),
):
    rows = profit_report(db, current_user, from_date=from_date, to_date=to_date, warehouse_id=warehouse_id)
    if format == "csv":
        return rows_to_csv_response(rows, PROFIT_REPORT_HEADERS, "profit_report.csv")
    return JSONResponse(content=rows)


@router.get("/profit-summary")
async def get_profit_summary_report(
    period: str = Query("daily", pattern="^(daily|weekly|monthly)$"),
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    warehouse_id: Optional[list[int]] = Query(None),
    format: str = Query("json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports", "read")),
):
    rows = profit_summary_report(db, current_user, period=period, from_date=from_date, to_date=to_date, warehouse_id=warehouse_id)
    if format == "csv":
        return rows_to_csv_response(rows, PROFIT_SUMMARY_REPORT_HEADERS, "profit_summary_report.csv")
    return JSONResponse(content=rows)


@router.get("/abc")
async def get_abc_report(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    format: str = Query("json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports", "read")),
):
    rows = abc_report(db, current_user, from_date=from_date, to_date=to_date)
    if format == "csv":
        return rows_to_csv_response(rows, ABC_REPORT_HEADERS, "abc_report.csv")
    return JSONResponse(content=rows)


@router.get("/slow-moving")
async def get_slow_moving_report(
    threshold_days: int = Query(90, ge=1, le=3650),
    format: str = Query("json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports", "read")),
):
    rows = slow_moving_report(db, threshold_days=threshold_days)
    if format == "csv":
        return rows_to_csv_response(rows, SLOW_MOVING_REPORT_HEADERS, "slow_moving_report.csv")
    return JSONResponse(content=rows)


@router.get("/sellers")
async def get_sellers_report(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    format: str = Query("json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports", "read")),
):
    rows = sellers_report(db, current_user, from_date=from_date, to_date=to_date)
    if format == "csv":
        return rows_to_csv_response(rows, SELLERS_REPORT_HEADERS, "sellers_report.csv")
    return JSONResponse(content=rows)


@router.get("/export")
async def export_report(
    report: str = Query(..., pattern="^(sales|inventory|purchases|customers|products|profit|profit-summary|abc|slow-moving|sellers)$"),
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    seller_id: Optional[int] = Query(None),
    customer_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    threshold_days: Optional[int] = Query(None, ge=1, le=3650),
    period: Optional[str] = Query(None),
    warehouse_id: Optional[list[int]] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports", "read")),
):
    """Generic CSV download. Returns a `text/csv` StreamingResponse."""
    table = {
        "sales": (sales_report, SALES_REPORT_HEADERS, "sales_report.csv"),
        "inventory": (inventory_report, INVENTORY_REPORT_HEADERS, "inventory_report.csv"),
        "purchases": (purchases_report, PURCHASES_REPORT_HEADERS, "purchases_report.csv"),
        "customers": (customers_report, CUSTOMERS_REPORT_HEADERS, "customers_report.csv"),
        "products": (products_report, PRODUCTS_REPORT_HEADERS, "products_report.csv"),
        "profit": (profit_report, PROFIT_REPORT_HEADERS, "profit_report.csv"),
        "profit-summary": (profit_summary_report, PROFIT_SUMMARY_REPORT_HEADERS, "profit_summary_report.csv"),
        "abc": (abc_report, ABC_REPORT_HEADERS, "abc_report.csv"),
        "slow-moving": (slow_moving_report, SLOW_MOVING_REPORT_HEADERS, "slow_moving_report.csv"),
        "sellers": (sellers_report, SELLERS_REPORT_HEADERS, "sellers_report.csv"),
    }
    if report not in table:
        raise HTTPException(status_code=400, detail="Unknown report type")

    fn, headers, filename = table[report]

    if report == "sales":
        rows = fn(db, current_user, from_date=from_date, to_date=to_date, seller_id=seller_id, customer_id=customer_id, warehouse_id=warehouse_id)
    elif report in ("products", "abc", "sellers"):
        rows = fn(db, current_user, from_date=from_date, to_date=to_date)
    elif report == "profit":
        rows = fn(db, current_user, from_date=from_date, to_date=to_date, warehouse_id=warehouse_id)
    elif report == "profit-summary":
        rows = fn(db, current_user, period=period or "daily", from_date=from_date, to_date=to_date, warehouse_id=warehouse_id)
    elif report == "slow-moving":
        rows = fn(db, threshold_days=threshold_days if threshold_days is not None else 90)
    elif report == "purchases":
        rows = fn(db, from_date=from_date, to_date=to_date, status=status)
    elif report == "inventory":
        rows = fn(db, current_user)
    else:
        rows = fn(db)

    return rows_to_csv_response(rows, headers, filename=filename)
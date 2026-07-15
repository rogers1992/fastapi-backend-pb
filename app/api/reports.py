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
    PurchaseReportRow,
    SalesReportRow,
)
from ..services.report_service import (
    CUSTOMERS_REPORT_HEADERS,
    INVENTORY_REPORT_HEADERS,
    PRODUCTS_REPORT_HEADERS,
    PURCHASES_REPORT_HEADERS,
    SALES_REPORT_HEADERS,
    customers_report,
    inventory_report,
    products_report,
    purchases_report,
    rows_to_csv_response,
    sales_report,
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
    format: str = Query("json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports", "read")),
):
    rows = sales_report(
        db, current_user,
        from_date=from_date, to_date=to_date,
        seller_id=seller_id, customer_id=customer_id,
    )
    return _maybe_csv(rows, SALES_REPORT_HEADERS, "sales_report.csv", format) \
        if format == "csv" else JSONResponse(content=rows)


@router.get("/inventory")
async def get_inventory_report(
    format: str = Query("json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports", "read")),
):
    rows = inventory_report(db)
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


@router.get("/export")
async def export_report(
    report: str = Query(..., pattern="^(sales|inventory|purchases|customers|products)$"),
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    seller_id: Optional[int] = Query(None),
    customer_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
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
    }
    if report not in table:
        raise HTTPException(status_code=400, detail="Unknown report type")

    fn, headers, filename = table[report]

    if report == "sales":
        rows = fn(db, current_user, from_date=from_date, to_date=to_date, seller_id=seller_id, customer_id=customer_id)
    elif report == "products":
        rows = fn(db, current_user, from_date=from_date, to_date=to_date)
    elif report == "purchases":
        rows = fn(db, from_date=from_date, to_date=to_date, status=status)
    else:
        rows = fn(db)

    return rows_to_csv_response(rows, headers, filename=filename)
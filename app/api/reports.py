"""Reports endpoints — detailed tabular reports with CSV, XLSX, and PDF export.

All endpoints require the `reports.read` permission.
"""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..core.dependencies import require_permission
from ..database import get_db
from ..models.user import User
from ..models.inventory import Warehouse
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
    sales_report,
    sellers_report,
    slow_moving_report,
)
from ..services.report_export import (
    rows_to_csv_response_enhanced,
    rows_to_xlsx_response,
    rows_to_pdf_response,
)

router = APIRouter()


def _get_warehouse_names(db: Session, warehouse_ids: Optional[List[int]]) -> Optional[List[str]]:
    """Get warehouse names for report description."""
    if not warehouse_ids:
        return None
    warehouses = db.query(Warehouse).filter(Warehouse.id.in_(warehouse_ids)).all()
    return [w.name for w in warehouses]


def _export_report(
    rows,
    headers,
    filename_base: str,
    report_type: str,
    fmt: str,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    warehouse_names: Optional[List[str]] = None,
):
    """Export report in requested format."""
    if fmt == "csv":
        return rows_to_csv_response_enhanced(
            rows, headers,
            filename=f"{filename_base}.csv",
            report_type=report_type,
            from_date=from_date,
            to_date=to_date,
            warehouse_names=warehouse_names,
        )
    elif fmt == "xlsx":
        return rows_to_xlsx_response(
            rows, headers,
            filename=f"{filename_base}.xlsx",
            report_type=report_type,
            from_date=from_date,
            to_date=to_date,
            warehouse_names=warehouse_names,
        )
    elif fmt == "pdf":
        return rows_to_pdf_response(
            rows, headers,
            filename=f"{filename_base}.pdf",
            report_type=report_type,
            from_date=from_date,
            to_date=to_date,
            warehouse_names=warehouse_names,
        )
    return JSONResponse(content=rows)


@router.get("/sales")
async def get_sales_report(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    seller_id: Optional[int] = Query(None),
    customer_id: Optional[int] = Query(None),
    warehouse_id: Optional[list[int]] = Query(None),
    format: str = Query("json", pattern="^(json|csv|xlsx|pdf)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports", "read")),
):
    rows = sales_report(
        db, current_user,
        from_date=from_date, to_date=to_date,
        seller_id=seller_id, customer_id=customer_id,
        warehouse_id=warehouse_id,
    )
    if format != "json":
        warehouse_names = _get_warehouse_names(db, warehouse_id)
        return _export_report(
            rows, SALES_REPORT_HEADERS, "reporte_ventas", "sales", format,
            from_date, to_date, warehouse_names,
        )
    return JSONResponse(content=rows)


@router.get("/inventory")
async def get_inventory_report(
    format: str = Query("json", pattern="^(json|csv|xlsx|pdf)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports", "read")),
):
    rows = inventory_report(db, current_user)
    if format != "json":
        return _export_report(
            rows, INVENTORY_REPORT_HEADERS, "reporte_inventario", "inventory", format,
        )
    return JSONResponse(content=rows)


@router.get("/purchases")
async def get_purchases_report(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    status: Optional[str] = Query(None),
    format: str = Query("json", pattern="^(json|csv|xlsx|pdf)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports", "read")),
):
    rows = purchases_report(db, from_date=from_date, to_date=to_date, status=status)
    if format != "json":
        return _export_report(
            rows, PURCHASES_REPORT_HEADERS, "reporte_compras", "purchases", format,
            from_date, to_date,
        )
    return JSONResponse(content=rows)


@router.get("/customers")
async def get_customers_report(
    format: str = Query("json", pattern="^(json|csv|xlsx|pdf)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports", "read")),
):
    rows = customers_report(db)
    if format != "json":
        return _export_report(
            rows, CUSTOMERS_REPORT_HEADERS, "reporte_clientes", "customers", format,
        )
    return JSONResponse(content=rows)


@router.get("/products")
async def get_products_report(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    format: str = Query("json", pattern="^(json|csv|xlsx|pdf)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports", "read")),
):
    rows = products_report(db, current_user, from_date=from_date, to_date=to_date)
    if format != "json":
        return _export_report(
            rows, PRODUCTS_REPORT_HEADERS, "reporte_productos", "products", format,
            from_date, to_date,
        )
    return JSONResponse(content=rows)


@router.get("/profit")
async def get_profit_report(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    warehouse_id: Optional[list[int]] = Query(None),
    format: str = Query("json", pattern="^(json|csv|xlsx|pdf)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports", "read")),
):
    rows = profit_report(db, current_user, from_date=from_date, to_date=to_date, warehouse_id=warehouse_id)
    if format != "json":
        warehouse_names = _get_warehouse_names(db, warehouse_id)
        return _export_report(
            rows, PROFIT_REPORT_HEADERS, "reporte_rentabilidad", "profit", format,
            from_date, to_date, warehouse_names,
        )
    return JSONResponse(content=rows)


@router.get("/profit-summary")
async def get_profit_summary_report(
    period: str = Query("daily", pattern="^(daily|weekly|monthly)$"),
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    warehouse_id: Optional[list[int]] = Query(None),
    format: str = Query("json", pattern="^(json|csv|xlsx|pdf)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports", "read")),
):
    rows = profit_summary_report(db, current_user, period=period, from_date=from_date, to_date=to_date, warehouse_id=warehouse_id)
    if format != "json":
        warehouse_names = _get_warehouse_names(db, warehouse_id)
        return _export_report(
            rows, PROFIT_SUMMARY_REPORT_HEADERS, "reporte_resumen_ganancia", "profit-summary", format,
            from_date, to_date, warehouse_names,
        )
    return JSONResponse(content=rows)


@router.get("/abc")
async def get_abc_report(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    format: str = Query("json", pattern="^(json|csv|xlsx|pdf)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports", "read")),
):
    rows = abc_report(db, current_user, from_date=from_date, to_date=to_date)
    if format != "json":
        return _export_report(
            rows, ABC_REPORT_HEADERS, "reporte_abc", "abc", format,
            from_date, to_date,
        )
    return JSONResponse(content=rows)


@router.get("/slow-moving")
async def get_slow_moving_report(
    threshold_days: int = Query(90, ge=1, le=3650),
    format: str = Query("json", pattern="^(json|csv|xlsx|pdf)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports", "read")),
):
    rows = slow_moving_report(db, threshold_days=threshold_days)
    if format != "json":
        return _export_report(
            rows, SLOW_MOVING_REPORT_HEADERS, "reporte_lento", "slow-moving", format,
        )
    return JSONResponse(content=rows)


@router.get("/sellers")
async def get_sellers_report(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    format: str = Query("json", pattern="^(json|csv|xlsx|pdf)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports", "read")),
):
    rows = sellers_report(db, current_user, from_date=from_date, to_date=to_date)
    if format != "json":
        return _export_report(
            rows, SELLERS_REPORT_HEADERS, "reporte_vendedores", "sellers", format,
            from_date, to_date,
        )
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
    format: str = Query("csv", pattern="^(csv|xlsx|pdf)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports", "read")),
):
    """Generic export endpoint supporting CSV, XLSX, and PDF formats."""
    table = {
        "sales": (sales_report, SALES_REPORT_HEADERS, "reporte_ventas"),
        "inventory": (inventory_report, INVENTORY_REPORT_HEADERS, "reporte_inventario"),
        "purchases": (purchases_report, PURCHASES_REPORT_HEADERS, "reporte_compras"),
        "customers": (customers_report, CUSTOMERS_REPORT_HEADERS, "reporte_clientes"),
        "products": (products_report, PRODUCTS_REPORT_HEADERS, "reporte_productos"),
        "profit": (profit_report, PROFIT_REPORT_HEADERS, "reporte_rentabilidad"),
        "profit-summary": (profit_summary_report, PROFIT_SUMMARY_REPORT_HEADERS, "reporte_resumen_ganancia"),
        "abc": (abc_report, ABC_REPORT_HEADERS, "reporte_abc"),
        "slow-moving": (slow_moving_report, SLOW_MOVING_REPORT_HEADERS, "reporte_lento"),
        "sellers": (sellers_report, SELLERS_REPORT_HEADERS, "reporte_vendedores"),
    }
    if report not in table:
        raise HTTPException(status_code=400, detail="Unknown report type")

    fn, headers, filename_base = table[report]
    warehouse_names = _get_warehouse_names(db, warehouse_id)

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

    return _export_report(
        rows, headers, filename_base, report, format,
        from_date, to_date, warehouse_names,
    )
"""
Centralized aggregate queries and CSV export helpers for the reports
and dashboard modules. Keeping these queries out of the API routers
makes them reusable and easier to reason about.

Every sales-derived method applies the "vendedor" restriction: a user
whose role name is "vendedor" only sees their own sales (`Sale.user_id ==
current_user.id`). This mirrors the filter in `app/api/sales.py` and is
applied defensively even though vendedor currently lacks the
`reports.read` permission.
"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Iterable, List, Optional, Sequence, Tuple

from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.customer import Customer, Loyalty
from ..models.inventory import InventoryItem, Warehouse
from ..models.order import Order, OrderItem
from ..models.product import Category, Product, Supplier
from ..models.sale import Sale, SaleItem
from ..models.user import Role, User


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _apply_sales_visibility(query, user: User):
    """Restrict a Sale query to what `user` is allowed to see.

    Vendedor only ever sees their own sales. Every other role sees all.
    """
    role: Optional[Role] = getattr(user, "role", None)
    role_name = role.name if role else None
    if role_name == "vendedor":
        query = query.filter(Sale.user_id == user.id)
    return query


def _coerce_range(
    from_date: Optional[date], to_date: Optional[date]
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Normalize a date range to datetimes spanning full days."""
    from_dt = datetime.combine(from_date, datetime.min.time()) if from_date else None
    to_dt = None
    if to_date:
        to_dt = datetime.combine(to_date + timedelta(days=1), datetime.min.time())
    return from_dt, to_dt


def _safe_dec(value) -> Decimal:
    """Coerce a SQLAlchemy scalar to a non-null Decimal.

    Internal helper for dashboard Pydantic response models (which handle
    Decimal natively). For JSON-returning report rows use `_row_num` —
    JSONResponse cannot serialize Decimal.
    """
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _row_num(value) -> float:
    """Coerce a SQLAlchemy scalar to float for JSON-serializable row dicts.

    FastAPI's `JSONResponse` cannot serialize `Decimal`; every numeric
    value that will bubble up via `reports.py`'s `JSONResponse(content=...)`
    must be a primitive. Use this in the tabular report row builders.
    """
    if value is None:
        return 0.0
    return float(value)


# --------------------------------------------------------------------------- #
# Dashboard: summary
# --------------------------------------------------------------------------- #
def dashboard_summary(db: Session, user: User) -> dict:
    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # Monday
    month_start = today.replace(day=1)

    today_start = datetime.combine(today, datetime.min.time())
    today_end = today_start + timedelta(days=1)
    month_start_dt = datetime.combine(month_start, datetime.min.time())
    month_end_dt = datetime.combine(
        (month_start.replace(month=month_start.month + 1) if month_start.month < 12 else month_start.replace(year=month_start.year + 1, month=1)),
        datetime.min.time(),
    )
    week_start_dt = datetime.combine(week_start, datetime.min.time())
    week_end_dt = week_start_dt + timedelta(days=7)

    base = db.query(Sale).filter(Sale.status == "completed")

    def _revenue(start, end) -> Tuple[Decimal, int]:
        q = _apply_sales_visibility(base, user).filter(Sale.sale_date >= start, Sale.sale_date < end)
        row = q.with_entities(
            func.coalesce(func.sum(Sale.total_amount), 0),
            func.count(Sale.id),
        ).first()
        return _safe_dec(row[0]), int(row[1] or 0)

    rev_today, sales_today = _revenue(today_start, today_end)
    rev_week, _ = _revenue(week_start_dt, week_end_dt)
    rev_month, sales_month = _revenue(month_start_dt, month_end_dt)

    tax_month_row = (
        _apply_sales_visibility(base, user)
        .filter(Sale.sale_date >= month_start_dt, Sale.sale_date < month_end_dt)
        .with_entities(func.coalesce(func.sum(Sale.tax_amount), 0))
        .first()
    )
    tax_month = _safe_dec(tax_month_row[0])

    avg_ticket = rev_month / sales_month if sales_month else Decimal("0")

    low_stock_count = (
        db.query(InventoryItem)
        .filter(InventoryItem.min_stock_level.isnot(None))
        .filter(InventoryItem.quantity <= InventoryItem.min_stock_level)
        .count()
    )
    pending_po_count = db.query(Order).filter(Order.status == "pending").count()
    active_customers = db.query(Customer).filter(Customer.is_active == 1).count()
    active_products = db.query(Product).filter(Product.is_active.is_(True)).count()

    # Top-selling product (last 30 days by revenue)
    since = datetime.combine(today - timedelta(days=30), datetime.min.time())
    top_prod_row = (
        db.query(
            Product.name,
            func.coalesce(func.sum(SaleItem.total_price), 0),
        )
        .join(Product, Product.id == SaleItem.product_id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(Sale.status == "completed")
        .filter(Sale.sale_date >= since)
    )
    top_prod_row = _apply_sales_visibility(top_prod_row, user)
    top_prod_row = top_prod_row.group_by(Product.name).order_by(func.sum(SaleItem.total_price).desc()).first()
    top_product_name = top_prod_row[0] if top_prod_row else None
    top_product_revenue = _safe_dec(top_prod_row[1]) if top_prod_row else None

    return {
        "revenue_today": rev_today,
        "revenue_week": rev_week,
        "revenue_month": rev_month,
        "sales_count_today": sales_today,
        "sales_count_month": sales_month,
        "avg_ticket": avg_ticket,
        "tax_collected_month": tax_month,
        "low_stock_count": low_stock_count,
        "pending_po_count": pending_po_count,
        "active_customers": active_customers,
        "active_products": active_products,
        "top_product_name": top_product_name,
        "top_product_revenue": top_product_revenue,
    }


# --------------------------------------------------------------------------- #
# Dashboard: sales trend
# --------------------------------------------------------------------------- #
def sales_trend(
    db: Session,
    user: User,
    period: str = "daily",
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
) -> List[dict]:
    """Return a time series of revenue + sales count grouped by period."""
    period = (period or "daily").lower()
    if period not in {"daily", "weekly", "monthly"}:
        period = "daily"

    from_dt, to_dt = _coerce_range(from_date, to_date)
    if from_dt is None:
        from_dt = datetime.combine(date.today() - timedelta(days=29), datetime.min.time())
    if to_dt is None:
        to_dt = datetime.combine(date.today() + timedelta(days=1), datetime.min.time())

    if period == "daily":
        bucket = func.date_trunc("day", Sale.sale_date)
    elif period == "weekly":
        bucket = func.date_trunc("week", Sale.sale_date)
    else:
        bucket = func.date_trunc("month", Sale.sale_date)

    q = (
        db.query(
            bucket.label("bucket"),
            func.coalesce(func.sum(Sale.total_amount), 0).label("revenue"),
            func.count(Sale.id).label("sales_count"),
        )
        .filter(Sale.status == "completed")
        .filter(Sale.sale_date >= from_dt, Sale.sale_date < to_dt)
    )
    q = _apply_sales_visibility(q, user)
    rows = q.group_by("bucket").order_by("bucket").all()

    return [
        {
            "date_label": (r[0].date().isoformat() if hasattr(r[0], "date") else str(r[0])),
            "revenue": _safe_dec(r[1]),
            "sales_count": int(r[2] or 0),
        }
        for r in rows
    ]


# --------------------------------------------------------------------------- #
# Dashboard: inventory status
# --------------------------------------------------------------------------- #
def inventory_status(db: Session) -> dict:
    total_qty_row = db.query(func.coalesce(func.sum(InventoryItem.quantity), 0)).first()
    total_qty = int(total_qty_row[0] or 0)

    # Stock value at unit_price (sum quantity * product.unit_price)
    total_value_row = (
        db.query(func.coalesce(func.sum(InventoryItem.quantity * Product.unit_price), 0))
        .join(Product, Product.id == InventoryItem.product_id)
        .first()
    )
    total_value = _safe_dec(total_value_row[0])

    low_stock_items = (
        db.query(InventoryItem, Product, Warehouse)
        .join(Product, Product.id == InventoryItem.product_id)
        .join(Warehouse, Warehouse.id == InventoryItem.warehouse_id)
        .filter(InventoryItem.min_stock_level.isnot(None))
        .filter(InventoryItem.quantity <= InventoryItem.min_stock_level)
        .order_by((InventoryItem.quantity - InventoryItem.min_stock_level).asc())
        .all()
    )

    out_of_stock_count = sum(1 for inv, _, _ in low_stock_items if inv.quantity <= 0)

    by_warehouse_rows = (
        db.query(
            Warehouse.id,
            Warehouse.name,
            func.coalesce(func.sum(InventoryItem.quantity), 0),
            func.count(InventoryItem.id),
        )
        .join(InventoryItem, InventoryItem.warehouse_id == Warehouse.id)
        .group_by(Warehouse.id, Warehouse.name)
        .order_by(Warehouse.name)
        .all()
    )

    return {
        "total_quantity": total_qty,
        "total_value": total_value,
        "low_stock_count": len(low_stock_items),
        "out_of_stock_count": out_of_stock_count,
        "by_warehouse": [
            {
                "warehouse_id": int(r[0]),
                "warehouse_name": r[1],
                "quantity": int(r[2] or 0),
                "items": int(r[3] or 0),
            }
            for r in by_warehouse_rows
        ],
        "low_stock_items": [
            {
                "product_id": inv.product_id,
                "product_name": prod.name,
                "sku": prod.sku,
                "warehouse_id": inv.warehouse_id,
                "warehouse_name": wh.name,
                "quantity": inv.quantity,
                "min_stock_level": inv.min_stock_level or 0,
                "is_low_stock": True,
                "is_out_of_stock": inv.quantity <= 0,
            }
            for inv, prod, wh in low_stock_items
        ],
    }


# --------------------------------------------------------------------------- #
# Dashboard: top products / customers / payment methods
# --------------------------------------------------------------------------- #
def top_products(
    db: Session,
    user: User,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    limit: int = 10,
) -> List[dict]:
    from_dt, to_dt = _coerce_range(from_date, to_date)
    q = (
        db.query(
            Product.id,
            Product.name,
            Product.sku,
            func.coalesce(func.sum(SaleItem.quantity), 0).label("qty_sold"),
            func.coalesce(func.sum(SaleItem.total_price), 0).label("revenue"),
        )
        .join(Product, Product.id == SaleItem.product_id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(Sale.status == "completed")
    )
    if from_dt is not None:
        q = q.filter(Sale.sale_date >= from_dt)
    if to_dt is not None:
        q = q.filter(Sale.sale_date < to_dt)
    q = _apply_sales_visibility(q, user)
    rows = q.group_by(Product.id, Product.name, Product.sku).order_by(
        func.sum(SaleItem.total_price).desc()
    ).limit(limit).all()

    return [
        {
            "product_id": int(r[0]),
            "name": r[1],
            "sku": r[2],
            "qty_sold": int(r[3] or 0),
            "revenue": _safe_dec(r[4]),
        }
        for r in rows
    ]


def top_customers(
    db: Session,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    limit: int = 10,
) -> List[dict]:
    from_dt, to_dt = _coerce_range(from_date, to_date)
    q = (
        db.query(
            Customer.id,
            Customer.first_name,
            Customer.last_name,
            func.count(Sale.id).label("orders"),
            func.coalesce(func.sum(Sale.total_amount), 0).label("spent"),
            Loyalty.tier,
        )
        .join(Sale, Sale.customer_id == Customer.id)
        .outerjoin(Loyalty, Loyalty.customer_id == Customer.id)
        .filter(Sale.status == "completed")
    )
    if from_dt is not None:
        q = q.filter(Sale.sale_date >= from_dt)
    if to_dt is not None:
        q = q.filter(Sale.sale_date < to_dt)
    rows = (
        q.group_by(
            Customer.id, Customer.first_name, Customer.last_name, Loyalty.tier
        )
        .order_by(func.sum(Sale.total_amount).desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "customer_id": int(r[0]),
            "name": f"{r[1]} {r[2]}".strip(),
            "orders": int(r[3] or 0),
            "total_spent": _safe_dec(r[4]),
            "tier": r[5],
        }
        for r in rows
    ]


def payment_method_breakdown(
    db: Session,
    user: User,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
) -> List[dict]:
    from_dt, to_dt = _coerce_range(from_date, to_date)
    q = (
        db.query(
            Sale.payment_method,
            func.count(Sale.id),
            func.coalesce(func.sum(Sale.total_amount), 0),
        )
        .filter(Sale.status == "completed")
    )
    if from_dt is not None:
        q = q.filter(Sale.sale_date >= from_dt)
    if to_dt is not None:
        q = q.filter(Sale.sale_date < to_dt)
    q = _apply_sales_visibility(q, user)
    rows = q.group_by(Sale.payment_method).order_by(func.sum(Sale.total_amount).desc()).all()
    return [
        {"payment_method": r[0], "count": int(r[1] or 0), "total": _safe_dec(r[2])}
        for r in rows
    ]


# --------------------------------------------------------------------------- #
# Tabular reports
# --------------------------------------------------------------------------- #
def sales_report(
    db: Session,
    user: User,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    seller_id: Optional[int] = None,
    customer_id: Optional[int] = None,
) -> List[dict]:
    from_dt, to_dt = _coerce_range(from_date, to_date)
    q = (
        db.query(
            Sale.id,
            Sale.sale_date,
            Customer.id,
            Customer.first_name,
            Customer.last_name,
            User.id,
            User.first_name,
            User.last_name,
            Sale.payment_method,
            Sale.status,
            func.count(SaleItem.id),
            func.coalesce(func.sum(SaleItem.quantity), 0),
            func.coalesce(func.sum(SaleItem.total_price), 0),
            Sale.tax_amount,
            Sale.total_amount,
        )
        .join(SaleItem, SaleItem.sale_id == Sale.id)
        .outerjoin(Customer, Customer.id == Sale.customer_id)
        .outerjoin(User, User.id == Sale.user_id)
        .filter(Sale.status == "completed")
    )
    if from_dt is not None:
        q = q.filter(Sale.sale_date >= from_dt)
    if to_dt is not None:
        q = q.filter(Sale.sale_date < to_dt)
    if seller_id is not None:
        q = q.filter(Sale.user_id == seller_id)
    if customer_id is not None:
        q = q.filter(Sale.customer_id == customer_id)
    q = _apply_sales_visibility(q, user)
    rows = q.group_by(
        Sale.id, Sale.sale_date, Customer.id, Customer.first_name, Customer.last_name,
        User.id, User.first_name, User.last_name, Sale.payment_method, Sale.status,
        Sale.tax_amount, Sale.total_amount,
    ).order_by(Sale.sale_date.desc()).all()

    return [
        {
            "sale_id": int(r[0]),
            "sale_date": r[1].isoformat() if r[1] else None,
            "customer_id": r[2],
            "customer_name": (f"{r[3]} {r[4]}".strip() if r[3] else None),
            "seller_id": r[5],
            "seller_name": (f"{r[6]} {r[7]}".strip() if r[6] else None),
            "payment_method": r[8],
            "status": r[9],
            "items_count": int(r[10] or 0),
            "units_sold": int(r[11] or 0),
            "subtotal": _row_num(r[12]),
            "tax_amount": _row_num(r[13]),
            "total_amount": _row_num(r[14]),
        }
        for r in rows
    ]


def inventory_report(db: Session) -> List[dict]:
    rows = (
        db.query(
            InventoryItem, Product, Category, Warehouse,
        )
        .join(Product, Product.id == InventoryItem.product_id)
        .outerjoin(Category, Category.id == Product.category_id)
        .join(Warehouse, Warehouse.id == InventoryItem.warehouse_id)
        .order_by(Product.name.asc())
        .all()
    )

    return [
        {
            "product_id": inv.product_id,
            "name": prod.name,
            "sku": prod.sku,
            "category_id": cat.id if cat else None,
            "category_name": cat.name if cat else None,
            "warehouse_id": inv.warehouse_id,
            "warehouse_name": wh.name,
            "quantity": inv.quantity,
            "reserved_quantity": inv.reserved_quantity,
            "min_stock_level": inv.min_stock_level or 0,
            "max_stock_level": inv.max_stock_level,
            "unit_price": float(prod.unit_price or 0),
            "stock_value": float((prod.unit_price or 0) * inv.quantity),
            "is_low_stock": inv.min_stock_level is not None and inv.quantity <= inv.min_stock_level,
            "is_out_of_stock": inv.quantity <= 0,
        }
        for inv, prod, cat, wh in rows
    ]


def purchases_report(
    db: Session,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    status: Optional[str] = None,
) -> List[dict]:
    from_dt, to_dt = _coerce_range(from_date, to_date)
    q = (
        db.query(
            Order.id,
            Order.order_date,
            Supplier.id,
            Supplier.name,
            Warehouse.id,
            Warehouse.name,
            Order.status,
            func.count(OrderItem.id),
            func.coalesce(func.sum(OrderItem.quantity), 0),
            Order.total_amount,
        )
        .join(OrderItem, OrderItem.order_id == Order.id)
        .outerjoin(Supplier, Supplier.id == Order.supplier_id)
        .outerjoin(Warehouse, Warehouse.id == Order.warehouse_id)
    )
    if from_dt is not None:
        q = q.filter(Order.order_date >= from_dt)
    if to_dt is not None:
        q = q.filter(Order.order_date < to_dt)
    if status:
        q = q.filter(Order.status == status)
    rows = (
        q.group_by(
            Order.id, Order.order_date, Supplier.id, Supplier.name,
            Warehouse.id, Warehouse.name, Order.status, Order.total_amount,
        )
        .order_by(Order.order_date.desc())
        .all()
    )

    return [
        {
            "order_id": int(r[0]),
            "order_date": r[1].isoformat() if r[1] else None,
            "supplier_id": r[2],
            "supplier_name": r[3],
            "warehouse_id": r[4],
            "warehouse_name": r[5],
            "status": r[6],
            "items_count": int(r[7] or 0),
            "units_ordered": int(r[8] or 0),
            "total_amount": _row_num(r[9]),
        }
        for r in rows
    ]


def customers_report(db: Session) -> List[dict]:
    rows = (
        db.query(
            Customer.id,
            Customer.first_name,
            Customer.last_name,
            Customer.email,
            Customer.phone,
            Customer.is_active,
            Loyalty.tier,
            Loyalty.points,
            func.count(Sale.id),
            func.coalesce(func.sum(Sale.total_amount), 0),
            func.max(Sale.sale_date),
        )
        .outerjoin(Sale, Sale.customer_id == Customer.id)
        .outerjoin(Loyalty, Loyalty.customer_id == Customer.id)
        .group_by(
            Customer.id, Customer.first_name, Customer.last_name, Customer.email,
            Customer.phone, Customer.is_active, Loyalty.tier, Loyalty.points,
        )
        .order_by(func.sum(Sale.total_amount).desc())
        .all()
    )

    return [
        {
            "customer_id": int(r[0]),
            "name": f"{r[1]} {r[2]}".strip(),
            "email": r[3],
            "phone": r[4],
            "is_active": int(r[5] or 0),
            "loyalty_tier": r[6],
            "loyalty_points": int(r[7] or 0) if r[7] is not None else None,
            "orders": int(r[8] or 0),
            "total_spent": _row_num(r[9]),
            "last_sale_date": r[10].isoformat() if r[10] else None,
        }
        for r in rows
    ]


def products_report(
    db: Session,
    user: User,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
) -> List[dict]:
    from_dt, to_dt = _coerce_range(from_date, to_date)
    # Per-product aggregate joined to inventory sum
    inv_subq = (
        db.query(
            InventoryItem.product_id,
            func.coalesce(func.sum(InventoryItem.quantity), 0).label("stock"),
        )
        .group_by(InventoryItem.product_id)
        .subquery()
    )

    sales_q = (
        db.query(
            SaleItem.product_id,
            func.coalesce(func.sum(SaleItem.quantity), 0).label("units_sold"),
            func.coalesce(func.sum(SaleItem.total_price), 0).label("revenue"),
        )
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(Sale.status == "completed")
    )
    if from_dt is not None:
        sales_q = sales_q.filter(Sale.sale_date >= from_dt)
    if to_dt is not None:
        sales_q = sales_q.filter(Sale.sale_date < to_dt)
    sales_q = _apply_sales_visibility(sales_q, user)
    sales_subq = sales_q.group_by(SaleItem.product_id).subquery()

    rows = (
        db.query(
            Product.id, Product.name, Product.sku, Product.category_id,
            Category.name, Product.unit_price, Product.is_active,
            func.coalesce(sales_subq.c.units_sold, 0),
            func.coalesce(sales_subq.c.revenue, 0),
            func.coalesce(inv_subq.c.stock, 0),
        )
        .outerjoin(sales_subq, sales_subq.c.product_id == Product.id)
        .outerjoin(inv_subq, inv_subq.c.product_id == Product.id)
        .outerjoin(Category, Category.id == Product.category_id)
        .order_by(func.coalesce(sales_subq.c.revenue, 0).desc())
        .all()
    )

    return [
        {
            "product_id": int(r[0]),
            "name": r[1],
            "sku": r[2],
            "category_id": r[3],
            "category_name": r[4],
            "unit_price": float(r[5] or 0),
            "is_active": bool(r[6]),
            "units_sold": int(r[7] or 0),
            "revenue": _row_num(r[8]),
            "stock_quantity": int(r[9] or 0),
        }
        for r in rows
    ]


# --------------------------------------------------------------------------- #
# CSV export
# --------------------------------------------------------------------------- #
def rows_to_csv_response(
    rows: Sequence[dict],
    headers: Sequence[str],
    filename: str = "report.csv",
) -> StreamingResponse:
    """Serialize a list of dicts to a CSV `StreamingResponse`."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([row.get(h, "") for h in headers])
    buffer.seek(0)

    def _iter() -> Iterable[bytes]:
        chunk = buffer.read(8192)
        while chunk:
            yield chunk.encode("utf-8")
            chunk = buffer.read(8192)

    return StreamingResponse(
        _iter(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


SALES_REPORT_HEADERS = [
    "sale_id", "sale_date", "customer_id", "customer_name", "seller_id",
    "seller_name", "payment_method", "status", "items_count", "units_sold",
    "subtotal", "tax_amount", "total_amount",
]
INVENTORY_REPORT_HEADERS = [
    "product_id", "name", "sku", "category_id", "category_name",
    "warehouse_id", "warehouse_name", "quantity", "reserved_quantity",
    "min_stock_level", "max_stock_level", "unit_price", "stock_value",
    "is_low_stock", "is_out_of_stock",
]
PURCHASES_REPORT_HEADERS = [
    "order_id", "order_date", "supplier_id", "supplier_name",
    "warehouse_id", "warehouse_name", "status", "items_count",
    "units_ordered", "total_amount",
]
CUSTOMERS_REPORT_HEADERS = [
    "customer_id", "name", "email", "phone", "is_active", "loyalty_tier",
    "loyalty_points", "orders", "total_spent", "last_sale_date",
]
PRODUCTS_REPORT_HEADERS = [
    "product_id", "name", "sku", "category_id", "category_name",
    "unit_price", "is_active", "units_sold", "revenue", "stock_quantity",
]
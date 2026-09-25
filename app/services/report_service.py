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
from datetime import date, datetime, timedelta, timezone as tz_module
from decimal import Decimal
from typing import Iterable, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from fastapi.responses import StreamingResponse
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..models.customer import Customer, Loyalty
from ..models.inventory import InventoryItem, Warehouse
from ..models.order import Order, OrderItem
from ..models.product import Category, Product, Supplier
from ..models.sale import Sale, SaleItem
from ..models.user import Role, User


# Roles allowed to see product cost data (purchase-side financials).
_COST_VISIBILITY_ROLES = {"admin", "gerente"}


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


def _row_num_or_none(value) -> Optional[float]:
    """Coerce a SQLAlchemy scalar to float or None for JSON-serializable row dicts."""
    if value is None:
        return None
    return float(value)


# --------------------------------------------------------------------------- #
# Dashboard: summary
# --------------------------------------------------------------------------- #
def dashboard_summary(db: Session, user: User, tz: str = "America/La_Paz", warehouse_id: Optional[list[int]] = None) -> dict:
    """Compute all KPI tiles for the dashboard.

    Timezone-aware: "today", "this week", and "this month" are computed in
    the user's local timezone so KPIs reflect the correct local day.

    Optimized: consolidates 11 sequential queries into 3 round-trips.
    """
    user_tz = ZoneInfo(tz)
    now_local = datetime.now(tz_module.utc).astimezone(user_tz)
    today = now_local.date()
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

    # Convert boundaries to UTC for DB queries
    today_start_utc = today_start.replace(tzinfo=user_tz).astimezone(tz_module.utc).replace(tzinfo=None)
    today_end_utc = today_end.replace(tzinfo=user_tz).astimezone(tz_module.utc).replace(tzinfo=None)
    month_start_utc = month_start_dt.replace(tzinfo=user_tz).astimezone(tz_module.utc).replace(tzinfo=None)
    month_end_utc = month_end_dt.replace(tzinfo=user_tz).astimezone(tz_module.utc).replace(tzinfo=None)
    week_start_utc = week_start_dt.replace(tzinfo=user_tz).astimezone(tz_module.utc).replace(tzinfo=None)
    week_end_utc = week_end_dt.replace(tzinfo=user_tz).astimezone(tz_module.utc).replace(tzinfo=None)

    base = db.query(Sale).filter(Sale.status == "completed")
    if warehouse_id:
        base = base.filter(Sale.warehouse_id.in_(warehouse_id))
    base = _apply_sales_visibility(base, user)

    # --- Query 1: Revenue metrics (today/week/month) + tax in ONE round-trip ---
    revenue_row = base.with_entities(
        func.coalesce(func.sum(case((Sale.sale_date >= today_start_utc, Sale.total_amount))), 0),
        func.count(case((Sale.sale_date >= today_start_utc, Sale.id))),
        func.coalesce(func.sum(case((Sale.sale_date >= week_start_utc, Sale.total_amount))), 0),
        func.coalesce(func.sum(case((Sale.sale_date >= month_start_utc, Sale.total_amount))), 0),
        func.count(case((Sale.sale_date >= month_start_utc, Sale.id))),
        func.coalesce(func.sum(case((Sale.sale_date >= month_start_utc, Sale.tax_amount))), 0),
    ).filter(
        Sale.sale_date >= month_start_utc,  # Earliest boundary (month scope)
        Sale.sale_date < today_end_utc,
    ).first()

    rev_today = _safe_dec(revenue_row[0])
    sales_today = int(revenue_row[1] or 0)
    rev_week = _safe_dec(revenue_row[2])
    rev_month = _safe_dec(revenue_row[3])
    sales_month = int(revenue_row[4] or 0)
    tax_month = _safe_dec(revenue_row[5])

    avg_ticket = rev_month / sales_month if sales_month else Decimal("0")

    # --- Query 2: COGS (today & month) using window function instead of correlated subquery ---
    latest_cost_cte = (
        db.query(
            OrderItem.product_id,
            OrderItem.unit_cost,
            func.row_number().over(
                partition_by=OrderItem.product_id,
                order_by=Order.received_date.desc(),
            ).label("rn"),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.status == "received")
        .filter(Order.received_date.isnot(None))
        .subquery()
    )

    cogs_base = (
        db.query(SaleItem)
        .select_from(SaleItem)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .outerjoin(latest_cost_cte, latest_cost_cte.c.product_id == SaleItem.product_id)
        .filter(latest_cost_cte.c.rn == 1)
        .filter(Sale.status == "completed")
        .filter(Sale.sale_date >= month_start_utc, Sale.sale_date < today_end_utc)
    )
    if warehouse_id:
        cogs_base = cogs_base.filter(Sale.warehouse_id.in_(warehouse_id))
    cogs_base = _apply_sales_visibility(cogs_base, user)

    cogs_row = cogs_base.with_entities(
        func.coalesce(func.sum(case((Sale.sale_date >= today_start_utc, SaleItem.quantity * latest_cost_cte.c.unit_cost))), 0),
        func.coalesce(func.sum(case((Sale.sale_date >= month_start_utc, SaleItem.quantity * latest_cost_cte.c.unit_cost))), 0),
    ).first()

    cogs_today = _safe_dec(cogs_row[0])
    cogs_month = _safe_dec(cogs_row[1])
    gross_profit_today = rev_today - cogs_today
    gross_profit_month = rev_month - cogs_month
    margin_pct_month = (gross_profit_month / rev_month * 100) if rev_month else Decimal("0")

    # --- Query 3: Counts (low stock, pending POs, active customers, active products) in ONE round-trip ---
    low_stock_subq = db.query(func.count(InventoryItem.id)).filter(
        InventoryItem.min_stock_level.isnot(None),
        InventoryItem.quantity <= InventoryItem.min_stock_level,
    ).as_scalar()
    pending_po_subq = db.query(func.count(Order.id)).filter(Order.status == "pending").as_scalar()
    active_cust_subq = db.query(func.count(Customer.id)).filter(Customer.is_active == 1).as_scalar()
    active_prod_subq = db.query(func.count(Product.id)).filter(Product.is_active.is_(True)).as_scalar()

    counts_row = db.query(low_stock_subq, pending_po_subq, active_cust_subq, active_prod_subq).first()
    low_stock_count = int(counts_row[0] or 0)
    pending_po_count = int(counts_row[1] or 0)
    active_customers = int(counts_row[2] or 0)
    active_products = int(counts_row[3] or 0)

    # --- Query 4: Top-selling product (last 30 days by revenue) ---
    since = datetime.combine(today - timedelta(days=30), datetime.min.time())
    since_utc = since.replace(tzinfo=user_tz).astimezone(tz_module.utc).replace(tzinfo=None)
    top_prod_row = (
        db.query(
            Product.name,
            func.coalesce(func.sum(SaleItem.total_price), 0),
        )
        .join(Product, Product.id == SaleItem.product_id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(Sale.status == "completed")
        .filter(Sale.sale_date >= since_utc)
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
        "gross_profit_today": gross_profit_today,
        "gross_profit_month": gross_profit_month,
        "cogs_month": cogs_month,
        "margin_pct_month": margin_pct_month,
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
    warehouse_id: Optional[list[int]] = None,
    tz: str = "America/La_Paz",
) -> List[dict]:
    """Return a time series of revenue + sales count grouped by period.

    Timezone-aware: day/week/month boundaries are computed in the user's
    local timezone so charts reflect the correct local day.
    """
    period = (period or "daily").lower()
    if period not in {"daily", "weekly", "monthly"}:
        period = "daily"

    user_tz = ZoneInfo(tz)
    now_local = datetime.now(tz_module.utc).astimezone(user_tz)

    from_dt, to_dt = _coerce_range(from_date, to_date)
    if from_dt is None:
        from_dt = datetime.combine(now_local.date() - timedelta(days=29), datetime.min.time())
    if to_dt is None:
        to_dt = datetime.combine(now_local.date() + timedelta(days=1), datetime.min.time())

    # Convert range boundaries to UTC for the DB query
    from_utc = from_dt.replace(tzinfo=user_tz).astimezone(tz_module.utc).replace(tzinfo=None)
    to_utc = to_dt.replace(tzinfo=user_tz).astimezone(tz_module.utc).replace(tzinfo=None)

    if period == "daily":
        # Truncate in user's timezone, then convert result back for display
        bucket = func.timezone("UTC", func.date_trunc("day", func.timezone(tz, Sale.sale_date)))
    elif period == "weekly":
        bucket = func.timezone("UTC", func.date_trunc("week", func.timezone(tz, Sale.sale_date)))
    else:
        bucket = func.timezone("UTC", func.date_trunc("month", func.timezone(tz, Sale.sale_date)))

    q = (
        db.query(
            bucket.label("bucket"),
            func.coalesce(func.sum(Sale.total_amount), 0).label("revenue"),
            func.count(Sale.id).label("sales_count"),
        )
        .filter(Sale.status == "completed")
        .filter(Sale.sale_date >= from_utc, Sale.sale_date < to_utc)
    )
    if warehouse_id:
        q = q.filter(Sale.warehouse_id.in_(warehouse_id))
    q = _apply_sales_visibility(q, user)
    rows = q.group_by("bucket").order_by("bucket").all()

    return [
        {
            "date_label": r[0].strftime("%Y-%m-%d") if hasattr(r[0], "strftime") else str(r[0])[:10],
            "revenue": _safe_dec(r[1]),
            "sales_count": int(r[2] or 0),
        }
        for r in rows
    ]


# --------------------------------------------------------------------------- #
# Dashboard: inventory status
# --------------------------------------------------------------------------- #
def inventory_status(db: Session) -> dict:
    # Query 1: Combined total quantity + total value (both scan inventory_items)
    totals = db.query(
        func.coalesce(func.sum(InventoryItem.quantity), 0),
        func.coalesce(func.sum(InventoryItem.quantity * Product.unit_price), 0),
    ).join(Product, Product.id == InventoryItem.product_id).first()
    total_qty = int(totals[0] or 0)
    total_value = _safe_dec(totals[1])

    # Query 2: Low stock items with out_of_stock_count computed in SQL
    low_stock_rows = (
        db.query(
            InventoryItem.id,
            InventoryItem.product_id,
            InventoryItem.warehouse_id,
            InventoryItem.quantity,
            InventoryItem.min_stock_level,
            Product.name,
            Product.sku,
            Warehouse.name,
        )
        .join(Product, Product.id == InventoryItem.product_id)
        .join(Warehouse, Warehouse.id == InventoryItem.warehouse_id)
        .filter(InventoryItem.min_stock_level.isnot(None))
        .filter(InventoryItem.quantity <= InventoryItem.min_stock_level)
        .order_by((InventoryItem.quantity - InventoryItem.min_stock_level).asc())
        .all()
    )

    out_of_stock_count = sum(1 for row in low_stock_rows if row.quantity <= 0)

    # Query 3: By-warehouse breakdown
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
        "low_stock_count": len(low_stock_rows),
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
                "product_id": row.product_id,
                "product_name": row.name,
                "sku": row.sku,
                "warehouse_id": row.warehouse_id,
                "warehouse_name": row[7],
                "quantity": row.quantity,
                "min_stock_level": row.min_stock_level or 0,
                "is_low_stock": True,
                "is_out_of_stock": row.quantity <= 0,
            }
            for row in low_stock_rows
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
    warehouse_id: Optional[list[int]] = None,
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
    if warehouse_id:
        q = q.filter(Sale.warehouse_id.in_(warehouse_id))
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
    warehouse_id: Optional[list[int]] = None,
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
    if warehouse_id:
        q = q.filter(Sale.warehouse_id.in_(warehouse_id))
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
    warehouse_id: Optional[list[int]] = None,
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
            Warehouse.id,
            Warehouse.name,
        )
        .join(SaleItem, SaleItem.sale_id == Sale.id)
        .outerjoin(Customer, Customer.id == Sale.customer_id)
        .outerjoin(User, User.id == Sale.user_id)
        .outerjoin(Warehouse, Warehouse.id == Sale.warehouse_id)
        .filter(Sale.status == "completed")
    )
    if warehouse_id:
        q = q.filter(Sale.warehouse_id.in_(warehouse_id))
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
        Sale.tax_amount, Sale.total_amount, Warehouse.id, Warehouse.name,
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
            "warehouse_name": r[16],
        }
        for r in rows
    ]


_COST_VISIBILITY_ROLES = {"admin", "gerente"}


def _latest_cost_cte(db: Session):
    """Pre-computed latest received unit_cost per product using window function.

    Returns a subquery with columns: product_id, unit_cost, rn
    Use with: .outerjoin(cte, cte.c.product_id == X).filter(cte.c.rn == 1)
    """
    return (
        db.query(
            OrderItem.product_id,
            OrderItem.unit_cost,
            func.row_number().over(
                partition_by=OrderItem.product_id,
                order_by=Order.received_date.desc(),
            ).label("rn"),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.status == "received")
        .filter(Order.received_date.isnot(None))
        .subquery()
    )


def inventory_report(db: Session, user: User) -> List[dict]:
    cost_cte = _latest_cost_cte(db)
    cost_subq = (
        select(cost_cte.c.unit_cost)
        .where(cost_cte.c.product_id == Product.id)
        .where(cost_cte.c.rn == 1)
        .scalar_subquery()
    )
    can_see_cost = bool(user.role) and user.role.name in _COST_VISIBILITY_ROLES

    rows = (
        db.query(
            InventoryItem, Product, Category, Warehouse,
            cost_subq.label("current_cost"),
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
            "unit_cost": _row_num_or_none(current_cost) if can_see_cost else None,
            "stock_value_at_cost": _row_num_or_none(current_cost * inv.quantity) if (can_see_cost and current_cost is not None) else None,
            "is_low_stock": inv.min_stock_level is not None and inv.quantity <= inv.min_stock_level,
            "is_out_of_stock": inv.quantity <= 0,
        }
        for inv, prod, cat, wh, current_cost in rows
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


def profit_report(
    db: Session,
    user: User,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    warehouse_id: Optional[list[int]] = None,
) -> List[dict]:
    """Per-product gross profit using historical COGS.

    COGS per sale item is inferred from the most recent received Order's
    unit_cost for that product, scoped to purchases received at or before
    the sale date. Products with sales but no recorded purchases report
    COGS=0 (margin=100%, flagged in UI as needing cost data).
    """
    from_dt, to_dt = _coerce_range(from_date, to_date)

    # Pre-computed latest unit_cost per product (window function, O(N) instead of O(N*M))
    cost_cte = _latest_cost_cte(db)
    cost_subq = (
        select(cost_cte.c.unit_cost)
        .where(cost_cte.c.product_id == SaleItem.product_id)
        .where(cost_cte.c.rn == 1)
        .scalar_subquery()
    )

    q = (
        db.query(
            Product.id,
            Product.name,
            Product.sku,
            func.coalesce(func.sum(SaleItem.quantity), 0),
            func.coalesce(func.sum(SaleItem.total_price), 0),
            func.coalesce(func.sum(SaleItem.quantity * cost_subq), 0),
        )
        .join(SaleItem, SaleItem.product_id == Product.id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(Sale.status == "completed")
    )
    if warehouse_id:
        q = q.filter(Sale.warehouse_id.in_(warehouse_id))
    if from_dt is not None:
        q = q.filter(Sale.sale_date >= from_dt)
    if to_dt is not None:
        q = q.filter(Sale.sale_date < to_dt)
    q = _apply_sales_visibility(q, user)
    rows = q.group_by(Product.id, Product.name, Product.sku).all()

    return [
        {
            "product_id": int(r[0]),
            "name": r[1],
            "sku": r[2],
            "units_sold": int(r[3] or 0),
            "revenue": _row_num(r[4]),
            "cogs": _row_num(r[5]),
            "gross_profit": _row_num((r[4] or 0) - (r[5] or 0)),
            "margin_pct": _row_num(
                (((r[4] or 0) - (r[5] or 0)) / r[4] * 100) if r[4] else 0.0
            ),
        }
        for r in rows
    ]


def profit_summary_report(
    db: Session,
    user: User,
    period: str = "daily",
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    warehouse_id: Optional[list[int]] = None,
) -> List[dict]:
    """Time-series gross profit summary grouped by day/week/month.

    Uses the same historical COGS logic as profit_report(): the latest
    received purchase order unit_cost at or before each sale date.
    """
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

    # Pre-computed latest unit_cost per product (window function, O(N) instead of O(N*M))
    cost_cte = _latest_cost_cte(db)
    cost_subq = (
        select(cost_cte.c.unit_cost)
        .where(cost_cte.c.product_id == SaleItem.product_id)
        .where(cost_cte.c.rn == 1)
        .scalar_subquery()
    )

    q = (
        db.query(
            bucket.label("bucket"),
            func.coalesce(func.sum(SaleItem.total_price), 0),
            func.coalesce(func.sum(SaleItem.quantity * cost_subq), 0),
            func.count(Sale.id),
        )
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(Sale.status == "completed")
        .filter(Sale.sale_date >= from_dt, Sale.sale_date < to_dt)
    )
    if warehouse_id:
        q = q.filter(Sale.warehouse_id.in_(warehouse_id))
    q = _apply_sales_visibility(q, user)
    rows = q.group_by("bucket").order_by("bucket").all()

    return [
        {
            "period_label": (r[0].date().isoformat() if hasattr(r[0], "date") else str(r[0])),
            "revenue": _row_num(r[1]),
            "cogs": _row_num(r[2]),
            "gross_profit": _row_num((r[1] or 0) - (r[2] or 0)),
            "margin_pct": _row_num(
                (((r[1] or 0) - (r[2] or 0)) / r[1] * 100) if r[1] else 0.0
            ),
            "sales_count": int(r[3] or 0),
        }
        for r in rows
    ]


def abc_report(
    db: Session,
    user: User,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
) -> List[dict]:
    """ABC classification by revenue contribution (Pareto).

    A: cumulative revenue <= 80% of total.
    B: cumulative revenue <= 95% of total.
    C: remainder (bottom 5%).
    """
    from_dt, to_dt = _coerce_range(from_date, to_date)
    q = (
        db.query(
            Product.id,
            Product.name,
            Product.sku,
            func.coalesce(func.sum(SaleItem.quantity), 0),
            func.coalesce(func.sum(SaleItem.total_price), 0),
        )
        .join(SaleItem, SaleItem.product_id == Product.id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(Sale.status == "completed")
    )
    if from_dt is not None:
        q = q.filter(Sale.sale_date >= from_dt)
    if to_dt is not None:
        q = q.filter(Sale.sale_date < to_dt)
    q = _apply_sales_visibility(q, user)
    rows = (
        q.group_by(Product.id, Product.name, Product.sku)
        .order_by(func.sum(SaleItem.total_price).desc())
        .all()
    )

    # Compute total revenue first to derive percentages.
    total_revenue = sum((r[4] or 0) for r in rows)
    cumulative = Decimal("0")
    out: List[dict] = []
    for r in rows:
        product_id = int(r[0])
        name = r[1]
        sku = r[2]
        units_sold = int(r[3] or 0)
        revenue = _safe_dec(r[4])
        revenue_pct = (revenue / total_revenue * 100) if total_revenue else Decimal("0")
        cumulative += revenue
        cumulative_pct = (cumulative / total_revenue * 100) if total_revenue else Decimal("0")
        if cumulative_pct <= Decimal("80"):
            abc_class = "A"
        elif cumulative_pct <= Decimal("95"):
            abc_class = "B"
        else:
            abc_class = "C"
        out.append({
            "product_id": product_id,
            "name": name,
            "sku": sku,
            "revenue": _row_num(revenue),
            "revenue_pct": _row_num(revenue_pct),
            "cumulative_pct": _row_num(cumulative_pct),
            "abc_class": abc_class,
            "units_sold": units_sold,
        })
    return out


def slow_moving_report(
    db: Session,
    threshold_days: int = 90,
) -> List[dict]:
    """Inventory rows with stock but no (or stale) sales activity.

    A product+warehouse row is slow-moving if either it has never been sold
    (last_sale_date IS NULL) or `days_since_last_sale >= threshold_days`.
    No vendedor visibility filter — this is pure inventory data.
    """
    today = date.today()

    last_sale_subq = (
        db.query(
            SaleItem.product_id,
            func.max(Sale.sale_date).label("last_sale_date"),
        )
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(Sale.status == "completed")
        .group_by(SaleItem.product_id)
        .subquery()
    )

    rows = (
        db.query(
            InventoryItem.product_id,
            Product.name,
            Product.sku,
            Category.name,
            Warehouse.name,
            InventoryItem.quantity,
            last_sale_subq.c.last_sale_date,
            Product.unit_price,
        )
        .join(Product, Product.id == InventoryItem.product_id)
        .outerjoin(Category, Category.id == Product.category_id)
        .join(Warehouse, Warehouse.id == InventoryItem.warehouse_id)
        .outerjoin(last_sale_subq, last_sale_subq.c.product_id == InventoryItem.product_id)
        .filter(InventoryItem.quantity > 0)
        .order_by(Product.name.asc())
        .all()
    )

    out: List[dict] = []
    threshold_delta = timedelta(days=threshold_days)
    for r in rows:
        last_sale = r[6]
        days_since: Optional[int] = None
        if last_sale is not None:
            days_since = (today - last_sale.date()).days if hasattr(last_sale, "date") else (today - last_sale).days

        is_slow = last_sale is None or days_since is None or days_since >= threshold_days
        if not is_slow:
            continue

        qty = int(r[5] or 0)
        unit_price = float(r[7] or 0)
        out.append({
            "product_id": int(r[0]),
            "name": r[1],
            "sku": r[2],
            "category_name": r[3],
            "warehouse_name": r[4],
            "quantity": qty,
            "last_sale_date": last_sale.isoformat() if last_sale else None,
            "days_since_last_sale": days_since,
            "stock_value": _row_num(qty * unit_price),
        })
    return out


def sellers_report(
    db: Session,
    user: User,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
) -> List[dict]:
    """Per-seller aggregate: sales_count, units_sold, revenue, avg_ticket, tax.

    Only users with at least 1 sale in range appear (Q2 decision). A
    vendedor user only ever sees their own row (Q6 defensive filter).
    """
    from_dt, to_dt = _coerce_range(from_date, to_date)

    # Pre-aggregate quantities per sale so the JOIN does not multiply
    # Sale.total_amount / Sale.tax_amount across multiple items.
    items_subq = (
        db.query(
            SaleItem.sale_id,
            func.coalesce(func.sum(SaleItem.quantity), 0).label("total_qty"),
        )
        .group_by(SaleItem.sale_id)
        .subquery()
    )

    q = (
        db.query(
            User.id,
            User.first_name,
            User.last_name,
            Role.name,
            func.count(Sale.id),
            func.coalesce(func.sum(items_subq.c.total_qty), 0),
            func.coalesce(func.sum(Sale.total_amount), 0),
            func.coalesce(func.sum(Sale.tax_amount), 0),
        )
        .join(Sale, Sale.user_id == User.id)
        .outerjoin(Role, Role.id == User.role_id)
        .outerjoin(items_subq, items_subq.c.sale_id == Sale.id)
        .filter(Sale.status == "completed")
    )
    if from_dt is not None:
        q = q.filter(Sale.sale_date >= from_dt)
    if to_dt is not None:
        q = q.filter(Sale.sale_date < to_dt)
    q = _apply_sales_visibility(q, user)
    rows = (
        q.group_by(User.id, User.first_name, User.last_name, Role.name)
        .having(func.count(Sale.id) >= 1)
        .order_by(func.sum(Sale.total_amount).desc())
        .all()
    )

    return [
        {
            "seller_id": int(r[0]),
            "seller_name": f"{r[1]} {r[2]}".strip(),
            "role_name": r[3],
            "sales_count": int(r[4] or 0),
            "units_sold": int(r[5] or 0),
            "revenue": _row_num(r[6]),
            "avg_ticket": _row_num((r[6] or 0) / r[4]) if r[4] else 0.0,
            "tax_collected": _row_num(r[7]),
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
    "subtotal", "tax_amount", "total_amount", "warehouse_name",
]
INVENTORY_REPORT_HEADERS = [
    "product_id", "name", "sku", "category_id", "category_name",
    "warehouse_id", "warehouse_name", "quantity", "reserved_quantity",
    "min_stock_level", "max_stock_level", "unit_price", "stock_value",
    "unit_cost", "stock_value_at_cost",
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
PROFIT_REPORT_HEADERS = [
    "product_id", "name", "sku", "units_sold", "revenue",
    "cogs", "gross_profit", "margin_pct",
]
PROFIT_SUMMARY_REPORT_HEADERS = [
    "period_label", "revenue", "cogs", "gross_profit",
    "margin_pct", "sales_count",
]
ABC_REPORT_HEADERS = [
    "product_id", "name", "sku", "revenue", "revenue_pct",
    "cumulative_pct", "abc_class", "units_sold",
]
SLOW_MOVING_REPORT_HEADERS = [
    "product_id", "name", "sku", "category_name", "warehouse_name",
    "quantity", "last_sale_date", "days_since_last_sale", "stock_value",
]
SELLERS_REPORT_HEADERS = [
    "seller_id", "seller_name", "role_name", "sales_count",
    "units_sold", "revenue", "avg_ticket", "tax_collected",
]
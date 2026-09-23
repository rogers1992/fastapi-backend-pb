"""Expenses endpoints -- CRUD for operating expenses and income statement generation.

Endpoints require the `expenses` permission resource.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload, joinedload

from ..core.dependencies import require_permission, get_user_timezone
from ..database import get_db
from ..models.expense import Expense, ExpenseCategory
from ..models.sale import Sale, SaleItem
from ..models.order import Order, OrderItem
from ..models.user import User, Role
from ..schemas.expense import (
    ExpenseCategoryResponse, ExpenseCreate, ExpenseUpdate, ExpenseResponse,
    ExpenseSummary, IncomeStatementResponse,
)

router = APIRouter()


def _get_user_warehouse_ids(user: User) -> Optional[List[int]]:
    if user.role and user.role.name == "admin":
        return None
    return [w.id for w in user.warehouses] if user.warehouses else []


# --------------------------------------------------------------------------- #
# Categories
# --------------------------------------------------------------------------- #
@router.get("/categories", response_model=List[ExpenseCategoryResponse])
async def list_categories(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("expenses", "read")),
):
    cats = (
        db.query(ExpenseCategory)
        .filter(ExpenseCategory.is_active == True)
        .order_by(ExpenseCategory.sort_order)
        .all()
    )
    return cats


# --------------------------------------------------------------------------- #
# CRUD Expenses
# --------------------------------------------------------------------------- #
@router.get("", response_model=List[ExpenseResponse])
async def list_expenses(
    skip: int = 0,
    limit: int = 100,
    warehouse_id: Optional[int] = None,
    category_id: Optional[int] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    is_recurring: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("expenses", "read")),
):
    query = db.query(Expense).options(
        joinedload(Expense.category),
        joinedload(Expense.warehouse),
        joinedload(Expense.user),
    )

    # Scope: admin sees all, others see only their warehouse's expenses
    user_warehouse_ids = _get_user_warehouse_ids(current_user)
    if user_warehouse_ids:
        query = query.filter(
            (Expense.warehouse_id.in_(user_warehouse_ids)) | (Expense.warehouse_id.is_(None))
        )

    if warehouse_id is not None:
        query = query.filter(Expense.warehouse_id == warehouse_id)
    if category_id is not None:
        query = query.filter(Expense.category_id == category_id)
    if is_recurring is not None:
        query = query.filter(Expense.is_recurring == is_recurring)
    if from_date is not None:
        query = query.filter(Expense.expense_date >= datetime.combine(from_date, datetime.min.time()))
    if to_date is not None:
        query = query.filter(Expense.expense_date < datetime.combine(to_date + timedelta(days=1), datetime.min.time()))

    expenses = (
        query.order_by(Expense.expense_date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return expenses


@router.post("", response_model=ExpenseResponse)
async def create_expense(
    data: ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("expenses", "create")),
):
    category = db.query(ExpenseCategory).filter(ExpenseCategory.id == data.category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Categoria de gasto no encontrada")

    if data.warehouse_id:
        user_warehouse_ids = _get_user_warehouse_ids(current_user)
        if user_warehouse_ids and data.warehouse_id not in user_warehouse_ids:
            raise HTTPException(
                status_code=403,
                detail="No tienes permisos para registrar gastos en este almacen.",
            )

    expense = Expense(
        category_id=data.category_id,
        warehouse_id=data.warehouse_id,
        amount=data.amount,
        description=data.description,
        expense_date=data.expense_date or datetime.utcnow(),
        payment_method=data.payment_method,
        is_recurring=data.is_recurring,
        recorded_by=current_user.id,
        notes=data.notes,
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)

    # Eagerly load relationships for response
    expense = (
        db.query(Expense)
        .options(
            joinedload(Expense.category),
            joinedload(Expense.warehouse),
            joinedload(Expense.user),
        )
        .filter(Expense.id == expense.id)
        .first()
    )
    return expense


@router.put("/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    expense_id: int,
    data: ExpenseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("expenses", "update")),
):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")

    if data.category_id is not None:
        category = db.query(ExpenseCategory).filter(ExpenseCategory.id == data.category_id).first()
        if not category:
            raise HTTPException(status_code=404, detail="Categoria de gasto no encontrada")
        expense.category_id = data.category_id

    if data.warehouse_id is not None:
        expense.warehouse_id = data.warehouse_id
    if data.amount is not None:
        expense.amount = data.amount
    if data.description is not None:
        expense.description = data.description
    if data.expense_date is not None:
        expense.expense_date = data.expense_date
    if data.payment_method is not None:
        expense.payment_method = data.payment_method
    if data.is_recurring is not None:
        expense.is_recurring = data.is_recurring
    if data.notes is not None:
        expense.notes = data.notes

    db.commit()
    db.refresh(expense)

    expense = (
        db.query(Expense)
        .options(
            joinedload(Expense.category),
            joinedload(Expense.warehouse),
            joinedload(Expense.user),
        )
        .filter(Expense.id == expense.id)
        .first()
    )
    return expense


@router.delete("/{expense_id}")
async def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("expenses", "delete")),
):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")

    db.delete(expense)
    db.commit()
    return {"detail": "Gasto eliminado"}


# --------------------------------------------------------------------------- #
# Income Statement
# --------------------------------------------------------------------------- #
def _latest_cost_cte(db: Session):
    """Pre-computed latest received unit_cost per product."""
    from ..models.order import Order as PO, OrderItem as POItem
    return (
        db.query(
            POItem.product_id,
            POItem.unit_cost,
            func.row_number().over(
                partition_by=POItem.product_id,
                order_by=PO.received_date.desc(),
            ).label("rn"),
        )
        .join(PO, PO.id == POItem.order_id)
        .filter(PO.status == "received")
        .filter(PO.received_date.isnot(None))
        .subquery()
    )


@router.get("/income-statement", response_model=IncomeStatementResponse)
async def income_statement(
    warehouse_id: Optional[int] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("expenses", "read")),
):
    # Default to current month if no dates provided
    today = date.today()
    if from_date is None:
        from_date = today.replace(day=1)
    if to_date is None:
        if today.month == 12:
            to_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            to_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

    from_dt = datetime.combine(from_date, datetime.min.time())
    to_dt = datetime.combine(to_date + timedelta(days=1), datetime.min.time())

    # --- Revenue ---
    revenue_query = (
        db.query(func.coalesce(func.sum(Sale.total_amount), 0))
        .filter(Sale.status == "completed")
        .filter(Sale.sale_date >= from_dt, Sale.sale_date < to_dt)
    )
    if warehouse_id is not None:
        revenue_query = revenue_query.filter(Sale.warehouse_id == warehouse_id)
    revenue = Decimal(str(revenue_query.scalar()))

    # --- COGS ---
    cost_cte = _latest_cost_cte(db)
    cogs_query = (
        db.query(func.coalesce(func.sum(SaleItem.quantity * cost_cte.c.unit_cost), 0))
        .select_from(SaleItem)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .outerjoin(cost_cte, cost_cte.c.product_id == SaleItem.product_id)
        .filter(cost_cte.c.rn == 1)
        .filter(Sale.status == "completed")
        .filter(Sale.sale_date >= from_dt, Sale.sale_date < to_dt)
    )
    if warehouse_id is not None:
        cogs_query = cogs_query.filter(Sale.warehouse_id == warehouse_id)
    cogs = Decimal(str(cogs_query.scalar()))

    gross_profit = revenue - cogs
    gross_margin_pct = (gross_profit / revenue * 100) if revenue else Decimal("0")

    # --- Expenses ---
    expense_query = (
        db.query(
            ExpenseCategory.name,
            func.coalesce(func.sum(Expense.amount), 0),
            func.count(Expense.id),
        )
        .join(ExpenseCategory, ExpenseCategory.id == Expense.category_id)
        .filter(Expense.expense_date >= from_dt, Expense.expense_date < to_dt)
    )
    if warehouse_id is not None:
        expense_query = expense_query.filter(
            (Expense.warehouse_id == warehouse_id) | (Expense.warehouse_id.is_(None))
        )
    expense_rows = (
        expense_query
        .group_by(ExpenseCategory.name, ExpenseCategory.sort_order)
        .order_by(ExpenseCategory.sort_order)
        .all()
    )

    expenses_list = []
    total_expenses = Decimal("0")
    for name, total, count in expense_rows:
        total_dec = Decimal(str(total))
        total_expenses += total_dec
        expenses_list.append(
            ExpenseSummary(category_name=name, total=float(total_dec), count=int(count))
        )

    net_profit = gross_profit - total_expenses
    net_margin_pct = (net_profit / revenue * 100) if revenue else Decimal("0")

    # Warehouse name
    warehouse_name = None
    if warehouse_id is not None:
        from ..models.inventory import Warehouse
        wh = db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
        warehouse_name = wh.name if wh else None

    return IncomeStatementResponse(
        warehouse_id=warehouse_id,
        warehouse_name=warehouse_name,
        period_start=from_date.isoformat(),
        period_end=to_date.isoformat(),
        revenue=float(revenue),
        cogs=float(cogs),
        gross_profit=float(gross_profit),
        gross_margin_pct=float(gross_margin_pct.quantize(Decimal("0.1"))),
        expenses=expenses_list,
        total_expenses=float(total_expenses),
        net_profit=float(net_profit),
        net_margin_pct=float(net_margin_pct.quantize(Decimal("0.1"))),
    )

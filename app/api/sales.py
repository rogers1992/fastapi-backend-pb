from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy import func
from datetime import datetime, timedelta, timezone as tz_module
from zoneinfo import ZoneInfo, available_timezones
from typing import List
from ..database import get_db
from ..models.sale import Sale, SaleItem
from ..models.product import Product
from ..models.inventory import InventoryItem, Warehouse
from ..schemas.sale import SaleCreate, SaleResponse
from ..core.dependencies import get_current_user, require_permission
from ..models.user import User
from ..services.notification_service import NotificationService
from ..config import settings
from decimal import Decimal

router = APIRouter()

_DEFAULT_TZ = "America/La_Paz"
_VALID_TIMEZONES = available_timezones()


def _get_user_timezone(tz: str = Header(default=_DEFAULT_TZ, alias="X-Timezone")) -> str:
    """Extract and validate the user's timezone from the request header."""
    if tz in _VALID_TIMEZONES:
        return tz
    return _DEFAULT_TZ


def _check_low_stock_after_sale(
    db: Session,
    inventory: InventoryItem,
    product_name: str | None = None,
    warehouse_name: str | None = None,
) -> None:
    """
    After a sale reduces inventory, alert staff if the item is now at or
    below its minimum stock level.
    """
    if inventory.min_stock_level is None:
        return
    if inventory.quantity > inventory.min_stock_level:
        return

    if product_name is None:
        product = db.query(Product).filter(Product.id == inventory.product_id).first()
        product_name = product.name if product else f"Producto #{inventory.product_id}"

    if warehouse_name is None:
        warehouse = db.query(Warehouse).filter(Warehouse.id == inventory.warehouse_id).first()
        warehouse_name = warehouse.name if warehouse else f"Almacen #{inventory.warehouse_id}"

    NotificationService.notify_users_with_permission(
        db,
        resource="inventory",
        action="read",
        type="low_stock",
        title="Stock bajo tras venta",
        message=(
            f"{product_name} quedo con {inventory.quantity} unidades "
            f"en {warehouse_name} tras una venta "
            f"(minimo: {inventory.min_stock_level})."
        ),
        data={
            "product_id": inventory.product_id,
            "warehouse_id": inventory.warehouse_id,
            "warehouse_name": warehouse_name,
            "quantity": inventory.quantity,
            "min_stock_level": inventory.min_stock_level,
        },
    )


def _apply_vendedor_filter(query, current_user: User, tz: str):
    """Apply vendedor restrictions: own sales only, today in user's timezone."""
    user_tz = ZoneInfo(tz)
    today_local = datetime.now(tz_module.utc).astimezone(user_tz).date()
    today_start_utc = (
        datetime.combine(today_local, datetime.min.time())
        .replace(tzinfo=user_tz)
        .astimezone(tz_module.utc)
        .replace(tzinfo=None)
    )
    today_end_utc = today_start_utc + timedelta(days=1)
    return query.filter(
        Sale.user_id == current_user.id,
        Sale.sale_date >= today_start_utc,
        Sale.sale_date < today_end_utc,
    )


@router.get("", response_model=List[SaleResponse])
async def get_sales(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("sales", "read")),
    tz: str = Depends(_get_user_timezone),
):
    query = db.query(Sale)

    if current_user.role and current_user.role.name == "vendedor":
        query = _apply_vendedor_filter(query, current_user, tz)

    sales = (
        query.options(
            selectinload(Sale.sale_items).joinedload(SaleItem.product)
        )
        .order_by(Sale.sale_date.desc())
        .offset(skip).limit(limit).all()
    )
    return sales


@router.get("/{sale_id}", response_model=SaleResponse)
async def get_sale(
    sale_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("sales", "read")),
    tz: str = Depends(_get_user_timezone),
):
    query = db.query(Sale).filter(Sale.id == sale_id)

    if current_user.role and current_user.role.name == "vendedor":
        query = _apply_vendedor_filter(query, current_user, tz)

    sale = query.options(
        selectinload(Sale.sale_items).joinedload(SaleItem.product)
    ).first()
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    return sale


@router.post("", response_model=SaleResponse)
async def create_sale(
    sale: SaleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("sales", "create")),
):
    total_amount = Decimal(0)
    tax_rate = Decimal(str(settings.TAX_RATE))

    warehouse_id = sale.warehouse_id

    db_sale = Sale(
        customer_id=sale.customer_id,
        user_id=current_user.id,
        warehouse_id=warehouse_id,
        payment_method=sale.payment_method,
        notes=sale.notes,
        total_amount=0,
        tax_amount=0,
    )
    db.add(db_sale)
    db.flush()

    # Pre-fetch warehouse ONCE (same for all items)
    warehouse_name = "General"
    if warehouse_id:
        warehouse = db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
        warehouse_name = warehouse.name if warehouse else "General"

    # Pre-fetch all products in ONE query
    product_ids = [item.product_id for item in sale.items]
    products = {p.id: p for p in db.query(Product).filter(Product.id.in_(product_ids)).all()}

    # Pre-fetch all inventory items for this warehouse in ONE query
    inv_map: dict[tuple[int, int], InventoryItem] = {}
    if warehouse_id:
        inv_rows = db.query(InventoryItem).filter(
            InventoryItem.product_id.in_(product_ids),
            InventoryItem.warehouse_id == warehouse_id,
        ).all()
        inv_map = {(i.product_id, i.warehouse_id): i for i in inv_rows}

    affected_inventory: List[InventoryItem] = []
    items_count = 0

    for item_data in sale.items:
        product = products.get(item_data.product_id)
        product_name = product.name if product else f"Producto #{item_data.product_id}"

        if warehouse_id:
            inventory = inv_map.get((item_data.product_id, warehouse_id))

            if not inventory or inventory.quantity < item_data.quantity:
                available = inventory.quantity if inventory else 0
                db.rollback()
                raise HTTPException(
                    status_code=400,
                    detail=f"Stock insuficiente para {product_name} en {warehouse_name} (disponible: {available}, solicitado: {item_data.quantity})",
                )
        else:
            inventories = (
                db.query(InventoryItem)
                .filter(
                    InventoryItem.product_id == item_data.product_id,
                    InventoryItem.quantity > 0,
                )
                .order_by(InventoryItem.quantity.desc())
                .all()
            )
            total_available = sum(inv.quantity for inv in inventories)
            if total_available < item_data.quantity:
                db.rollback()
                raise HTTPException(
                    status_code=400,
                    detail=f"Stock insuficiente para {product_name} (disponible: {total_available}, solicitado: {item_data.quantity})",
                )

            remaining = item_data.quantity
            for inv in inventories:
                deduct = min(inv.quantity, remaining)
                inv.quantity -= deduct
                remaining -= deduct
                if inv not in affected_inventory:
                    affected_inventory.append(inv)
                if remaining == 0:
                    break

        item_total = (item_data.unit_price * item_data.quantity) - item_data.discount
        total_amount += item_total
        items_count += item_data.quantity

        sale_item = SaleItem(
            sale_id=db_sale.id,
            product_id=item_data.product_id,
            quantity=item_data.quantity,
            unit_price=item_data.unit_price,
            discount=item_data.discount,
            total_price=item_total,
        )
        db.add(sale_item)

        if warehouse_id:
            inventory.quantity -= item_data.quantity
            if inventory not in affected_inventory:
                affected_inventory.append(inventory)

    tax_amount = total_amount * tax_rate
    db_sale.total_amount = total_amount + tax_amount
    db_sale.tax_amount = tax_amount

    db.commit()
    db.refresh(db_sale)

    # --- Notifications (after commit so the sale exists) ---
    # 1) Alert users with sales:read about the new sale.
    NotificationService.notify_users_with_permission(
        db,
        resource="sales",
        action="read",
        type="new_sale",
        title="Nueva venta registrada",
        message=(
            f"Venta #{db_sale.id} por ${db_sale.total_amount:.2f} "
            f"({items_count} articulos, {sale.payment_method})."
        ),
        data={
            "sale_id": db_sale.id,
            "total_amount": float(db_sale.total_amount),
            "payment_method": sale.payment_method,
        },
    )

    # 2) Low-stock alerts for any inventory that dropped to/below min.
    for inv in affected_inventory:
        db.refresh(inv)
        _check_low_stock_after_sale(db, inv, product_name, warehouse_name)

    return db_sale

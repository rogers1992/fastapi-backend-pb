from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models.sale import Sale, SaleItem
from ..models.product import Product
from ..models.inventory import InventoryItem, Warehouse
from ..schemas.sale import SaleCreate, SaleResponse
from ..core.dependencies import get_current_user, require_permission
from ..models.user import User
from ..services.notification_service import NotificationService
from decimal import Decimal

router = APIRouter()


def _check_low_stock_after_sale(db: Session, inventory: InventoryItem) -> None:
    """
    After a sale reduces inventory, alert staff if the item is now at or
    below its minimum stock level.
    """
    if inventory.min_stock_level is None:
        return
    if inventory.quantity > inventory.min_stock_level:
        return

    product = db.query(Product).filter(Product.id == inventory.product_id).first()
    product_name = product.name if product else f"Producto #{inventory.product_id}"

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


@router.get("/", response_model=List[SaleResponse])
async def get_sales(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("sales", "read")),
):
    sales = db.query(Sale).order_by(Sale.sale_date.desc()).offset(skip).limit(limit).all()
    return sales


@router.get("/{sale_id}", response_model=SaleResponse)
async def get_sale(
    sale_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("sales", "read")),
):
    sale = db.query(Sale).filter(Sale.id == sale_id).first()
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    return sale


@router.post("/", response_model=SaleResponse)
async def create_sale(
    sale: SaleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("sales", "create")),
):
    total_amount = Decimal(0)
    tax_rate = Decimal(0.16)

    db_sale = Sale(
        customer_id=sale.customer_id,
        user_id=current_user.id,
        payment_method=sale.payment_method,
        notes=sale.notes,
        total_amount=0,
        tax_amount=0,
    )
    db.add(db_sale)
    db.flush()

    affected_inventory: List[InventoryItem] = []
    items_count = 0

    for item_data in sale.items:
        inventory = db.query(InventoryItem).filter(
            InventoryItem.product_id == item_data.product_id,
        ).first()

        if not inventory or inventory.quantity < item_data.quantity:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient inventory for product {item_data.product_id}",
            )

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

        inventory.quantity -= item_data.quantity
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
        _check_low_stock_after_sale(db, inv)

    return db_sale

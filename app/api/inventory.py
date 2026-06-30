from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from ..database import get_db
from ..models.inventory import InventoryItem, Warehouse
from ..models.product import Product
from ..schemas.inventory import InventoryItemCreate, InventoryItemResponse, InventoryItemUpdate, InventoryTransfer
from ..core.dependencies import get_current_user, require_permission
from ..models.user import User
from ..services.notification_service import NotificationService

router = APIRouter()


def _check_low_stock(db: Session, item: InventoryItem) -> None:
    """
    If the given inventory item is at or below its min_stock_level, fan out
    a low_stock notification to every active user with inventory:read.
    Idempotent-ish: we don't deduplicate here, so repeated saves at low stock
    will produce repeated notifications. Acceptable for an MVP alert system.
    """
    if item.min_stock_level is None:
        return
    if item.quantity > item.min_stock_level:
        return

    product = db.query(Product).filter(Product.id == item.product_id).first()
    product_name = product.name if product else f"Producto #{item.product_id}"

    warehouse = db.query(Warehouse).filter(Warehouse.id == item.warehouse_id).first()
    warehouse_name = warehouse.name if warehouse else f"Almacen #{item.warehouse_id}"

    NotificationService.notify_users_with_permission(
        db,
        resource="inventory",
        action="read",
        type="low_stock",
        title="Stock bajo",
        message=(
            f"{product_name} tiene {item.quantity} unidades "
            f"en {warehouse_name} (minimo: {item.min_stock_level})."
        ),
        data={
            "product_id": item.product_id,
            "warehouse_id": item.warehouse_id,
            "warehouse_name": warehouse_name,
            "quantity": item.quantity,
            "min_stock_level": item.min_stock_level,
        },
    )


@router.get("/", response_model=List[InventoryItemResponse])
async def get_inventory(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory", "read")),
):
    inventory = db.query(InventoryItem).offset(skip).limit(limit).all()
    return inventory


@router.get("/warehouse/{warehouse_id}", response_model=List[InventoryItemResponse])
async def get_inventory_by_warehouse(
    warehouse_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory", "read")),
):
    inventory = db.query(InventoryItem).filter(InventoryItem.warehouse_id == warehouse_id).all()
    return inventory


@router.post("/", response_model=InventoryItemResponse)
async def create_inventory_item(
    item: InventoryItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory", "create")),
):
    existing = db.query(InventoryItem).filter(
        InventoryItem.product_id == item.product_id,
        InventoryItem.warehouse_id == item.warehouse_id,
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Inventory item already exists for this product and warehouse")

    db_item = InventoryItem(**item.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    _check_low_stock(db, db_item)
    return db_item


@router.put("/{item_id}", response_model=InventoryItemResponse)
async def update_inventory_item(
    item_id: int,
    item: InventoryItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory", "update")),
):
    db_item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Inventory item not found")

    update_data = item.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_item, key, value)

    db.commit()
    db.refresh(db_item)
    _check_low_stock(db, db_item)
    return db_item


@router.post("/transfer", response_model=dict)
async def transfer_inventory(
    transfer: InventoryTransfer,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory", "update")),
):
    source_item = db.query(InventoryItem).filter(
        InventoryItem.product_id == transfer.product_id,
        InventoryItem.warehouse_id == transfer.from_warehouse_id,
    ).first()

    if not source_item:
        raise HTTPException(status_code=404, detail="Source inventory item not found")

    if source_item.quantity < transfer.quantity:
        raise HTTPException(status_code=400, detail="Insufficient quantity for transfer")

    dest_item = db.query(InventoryItem).filter(
        InventoryItem.product_id == transfer.product_id,
        InventoryItem.warehouse_id == transfer.to_warehouse_id,
    ).first()

    if not dest_item:
        dest_item = InventoryItem(
            product_id=transfer.product_id,
            warehouse_id=transfer.to_warehouse_id,
            quantity=0,
        )
        db.add(dest_item)

    source_item.quantity -= transfer.quantity
    dest_item.quantity += transfer.quantity

    db.commit()
    db.refresh(source_item)
    if source_item is not dest_item:
        db.refresh(dest_item)
    _check_low_stock(db, source_item)
    if source_item is not dest_item:
        _check_low_stock(db, dest_item)
    return {"message": "Transfer completed successfully"}


@router.get("/low-stock", response_model=List[InventoryItemResponse])
async def get_low_stock_items(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory", "read")),
):
    items = (
        db.query(InventoryItem)
        .filter(InventoryItem.quantity <= InventoryItem.min_stock_level)
        .all()
    )
    return items


@router.get("/summary")
async def get_inventory_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory", "read")),
):
    total_items = db.query(InventoryItem).count()
    total_warehouses = (
        db.query(Warehouse).filter(Warehouse.is_active == True).count()
    )
    low_stock_count = (
        db.query(InventoryItem)
        .filter(InventoryItem.quantity <= InventoryItem.min_stock_level)
        .count()
    )
    total_quantity = 0
    result = db.query(func.sum(InventoryItem.quantity)).scalar()
    if result is not None:
        total_quantity = int(result)
    return {
        "total_items": total_items,
        "total_warehouses": total_warehouses,
        "low_stock_count": low_stock_count,
        "total_quantity": total_quantity,
    }

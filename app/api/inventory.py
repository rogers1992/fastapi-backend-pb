from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models.inventory import InventoryItem, Warehouse
from ..schemas.inventory import InventoryItemCreate, InventoryItemResponse, InventoryItemUpdate, InventoryTransfer
from ..core.dependencies import get_current_user, require_permission
from ..models.user import User

router = APIRouter()


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
    return {"message": "Transfer completed successfully"}

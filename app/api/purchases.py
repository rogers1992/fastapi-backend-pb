from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload, joinedload
from typing import List, Optional
from decimal import Decimal
from datetime import date

from ..database import get_db
from ..models.order import Order, OrderItem
from ..models.product import Product, Supplier
from ..models.inventory import InventoryItem, Warehouse
from ..schemas.order import OrderCreate, OrderUpdate, OrderResponse
from ..core.dependencies import require_permission
from ..models.user import User
from ..services.notification_service import NotificationService

router = APIRouter()


@router.get("/", response_model=List[OrderResponse])
async def get_purchases(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    supplier_id: Optional[int] = None,
    warehouse_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("purchases", "read")),
):
    query = db.query(Order)

    if status:
        query = query.filter(Order.status == status)
    if supplier_id:
        query = query.filter(Order.supplier_id == supplier_id)
    if warehouse_id:
        query = query.filter(Order.warehouse_id == warehouse_id)

    orders = (
        query.options(
            selectinload(Order.order_items).joinedload(OrderItem.product)
        )
        .order_by(Order.order_date.desc())
        .offset(skip).limit(limit).all()
    )
    return orders


@router.get("/{order_id}", response_model=OrderResponse)
async def get_purchase(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("purchases", "read")),
):
    order = db.query(Order).options(
        selectinload(Order.order_items).joinedload(OrderItem.product)
    ).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return order


@router.post("/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_purchase(
    order: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("purchases", "create")),
):
    # Validate supplier
    if not order.supplier_id:
        raise HTTPException(status_code=400, detail="supplier_id (proveedor) es requerido")
    supplier = db.query(Supplier).filter(Supplier.id == order.supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=400, detail="supplier_id no existe")

    # Validate warehouse
    warehouse = db.query(Warehouse).filter(Warehouse.id == order.warehouse_id).first()
    if not warehouse:
        raise HTTPException(status_code=400, detail="Invalid warehouse_id")

    if not order.items:
        raise HTTPException(status_code=400, detail="Order must have at least one item")

    total_amount = Decimal(0)

    db_order = Order(
        supplier_id=order.supplier_id,
        warehouse_id=order.warehouse_id,
        created_by=current_user.id,
        status="pending",
        total_amount=0,
        expected_date=order.expected_date,
        notes=order.notes,
    )
    db.add(db_order)
    db.flush()

    for item_data in order.items:
        product = db.query(Product).filter(Product.id == item_data.product_id).first()
        if not product:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail=f"Invalid product_id {item_data.product_id}",
            )
        if item_data.quantity <= 0:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail=f"Quantity must be positive for product {item_data.product_id}",
            )

        item_total = item_data.unit_cost * item_data.quantity
        total_amount += item_total

        order_item = OrderItem(
            order_id=db_order.id,
            product_id=item_data.product_id,
            quantity=item_data.quantity,
            unit_cost=item_data.unit_cost,
            total_price=item_total,
            received_quantity=0,
        )
        db.add(order_item)

    db_order.total_amount = total_amount
    db.commit()
    db.refresh(db_order)

    # Notify users with purchases:read that a new pending order was created
    NotificationService.notify_users_with_permission(
        db,
        resource="purchases",
        action="read",
        type="new_purchase",
        title="Nueva orden de compra registrada",
        message=(
            f"Orden de compra #{db_order.id} creada "
            f"({len(order.items)} articulos, Bs{total_amount:.2f})."
        ),
        data={
            "order_id": db_order.id,
            "total_amount": float(total_amount),
            "supplier_id": order.supplier_id,
        },
    )

    return db_order


@router.patch("/{order_id}/receive", response_model=OrderResponse)
async def receive_purchase(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("purchases", "update")),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    if order.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Order is already {order.status}; only pending orders can be received",
        )

    affected_inventory: List[InventoryItem] = []

    for item in order.order_items:
        inventory = (
            db.query(InventoryItem)
            .filter(
                InventoryItem.product_id == item.product_id,
                InventoryItem.warehouse_id == order.warehouse_id,
            )
            .first()
        )
        if not inventory:
            inventory = InventoryItem(
                product_id=item.product_id,
                warehouse_id=order.warehouse_id,
                quantity=0,
            )
            db.add(inventory)
            db.flush()

        inventory.quantity += item.quantity
        item.received_quantity = item.quantity
        affected_inventory.append(inventory)

    order.status = "received"
    order.received_date = date.today()

    db.commit()
    db.refresh(order)

    # Notify inventory watchers that stock arrived
    NotificationService.notify_users_with_permission(
        db,
        resource="inventory",
        action="read",
        type="stock_received",
        title="Stock recibido",
        message=(
            f"Orden de compra #{order.id} recibida: "
            f"{len(order.order_items)} productos agregados al inventario."
        ),
        data={
            "order_id": order.id,
            "warehouse_id": order.warehouse_id,
        },
    )

    return order


@router.patch("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_purchase(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("purchases", "update")),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    if order.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel order that is already {order.status}",
        )

    order.status = "cancelled"
    db.commit()
    db.refresh(order)
    return order


@router.patch("/{order_id}", response_model=OrderResponse)
async def update_purchase(
    order_id: int,
    update: OrderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("purchases", "update")),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    update_data = update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(order, key, value)
    db.commit()
    db.refresh(order)
    return order


@router.delete("/{order_id}")
async def delete_purchase(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("purchases", "delete")),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    if order.status != "pending":
        raise HTTPException(
            status_code=400,
            detail="Only pending orders can be deleted",
        )

    db.delete(order)
    db.commit()
    return {"message": f"Purchase order #{order_id} deleted"}
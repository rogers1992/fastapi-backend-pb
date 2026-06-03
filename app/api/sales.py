from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models.sale import Sale, SaleItem
from ..models.product import Product
from ..models.inventory import InventoryItem
from ..schemas.sale import SaleCreate, SaleResponse
from ..core.dependencies import get_current_user, require_permission
from ..models.user import User
from decimal import Decimal

router = APIRouter()


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

    tax_amount = total_amount * tax_rate
    db_sale.total_amount = total_amount + tax_amount
    db_sale.tax_amount = tax_amount

    db.commit()
    db.refresh(db_sale)
    return db_sale

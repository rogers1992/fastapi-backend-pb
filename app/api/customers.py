from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import List, Optional
from ..database import get_db
from ..models.customer import Customer, Loyalty
from ..models.sale import Sale
from ..schemas.customer import (
    CustomerCreate, CustomerUpdate, CustomerResponse,
    LoyaltyResponse, LoyaltyUpdate, LoyaltyAdjust,
)
from ..core.dependencies import get_current_user, require_permission
from ..models.user import User

router = APIRouter()


@router.get("/")
async def get_customers(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=1000),
    search: Optional[str] = None,
    email: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("customers", "read")),
):
    query = db.query(Customer)

    if is_active is not None:
        query = query.filter(Customer.is_active == int(is_active))
    else:
        query = query.filter(Customer.is_active == 1)

    if search:
        query = query.filter(
            or_(
                Customer.first_name.ilike(f"%{search}%"),
                Customer.last_name.ilike(f"%{search}%"),
                Customer.email.ilike(f"%{search}%"),
                Customer.phone.ilike(f"%{search}%"),
            )
        )

    if email:
        query = query.filter(Customer.email.ilike(f"%{email}%"))

    total = query.with_entities(func.count(Customer.id)).scalar()
    customers = query.offset(skip).limit(limit).all()

    return {
        "items": customers,
        "total_items": total,
        "current_page": (skip // limit) + 1,
        "page_size": limit,
        "total_pages": (total + limit - 1) // limit if limit > 0 else 0,
    }


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("customers", "read")),
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.post("/", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    customer: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("customers", "create")),
):
    existing = db.query(Customer).filter(
        Customer.email == customer.email
    ).filter(Customer.email.isnot(None)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    db_customer = Customer(
        **customer.model_dump(),
        is_active=1,
    )
    db.add(db_customer)
    db.flush()

    loyalty = Loyalty(points=0, tier='bronze', customer_id=db_customer.id)
    db.add(loyalty)

    db.commit()
    db.refresh(db_customer)
    return db_customer


@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: int,
    customer: CustomerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("customers", "update")),
):
    db_customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not db_customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    if customer.email and customer.email != db_customer.email:
        existing = db.query(Customer).filter(
            Customer.email == customer.email,
            Customer.id != customer_id,
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

    update_data = customer.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_customer, key, value)

    db.commit()
    db.refresh(db_customer)
    return db_customer


@router.patch("/{customer_id}/toggle-active", response_model=CustomerResponse)
async def toggle_customer_active(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("customers", "update")),
):
    db_customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not db_customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    db_customer.is_active = 0 if db_customer.is_active else 1
    db.commit()
    db.refresh(db_customer)
    return db_customer


@router.delete("/{customer_id}")
async def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("customers", "delete")),
):
    db_customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not db_customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    if db_customer.loyalty:
        db.delete(db_customer.loyalty)

    db.delete(db_customer)
    db.commit()
    return {"message": "Customer deleted successfully"}


@router.get("/{customer_id}/loyalty", response_model=LoyaltyResponse)
async def get_customer_loyalty(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("customers", "read")),
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    if not customer.loyalty:
        raise HTTPException(status_code=404, detail="Loyalty record not found")
    return customer.loyalty


@router.patch("/{customer_id}/loyalty", response_model=LoyaltyResponse)
async def update_customer_loyalty(
    customer_id: int,
    loyalty_data: LoyaltyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("customers", "update")),
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    if not customer.loyalty:
        raise HTTPException(status_code=404, detail="Loyalty record not found")

    update_data = loyalty_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(customer.loyalty, key, value)

    from sqlalchemy.sql import func
    customer.loyalty.last_updated = func.now()

    db.commit()
    db.refresh(customer.loyalty)
    return customer.loyalty


@router.post("/{customer_id}/loyalty/adjust", response_model=LoyaltyResponse)
async def adjust_customer_loyalty(
    customer_id: int,
    adjust_data: LoyaltyAdjust,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("customers", "update")),
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    if not customer.loyalty:
        raise HTTPException(status_code=404, detail="Loyalty record not found")

    customer.loyalty.points += adjust_data.points_change
    if customer.loyalty.points < 0:
        customer.loyalty.points = 0

    if customer.loyalty.points >= 1000:
        customer.loyalty.tier = 'gold'
    elif customer.loyalty.points >= 500:
        customer.loyalty.tier = 'silver'
    else:
        customer.loyalty.tier = 'bronze'

    from sqlalchemy.sql import func
    customer.loyalty.last_updated = func.now()

    db.commit()
    db.refresh(customer.loyalty)
    return customer.loyalty


@router.get("/{customer_id}/sales", response_model=List[dict])
async def get_customer_sales(
    customer_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("sales", "read")),
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    sales = (
        db.query(Sale)
        .filter(Sale.customer_id == customer_id)
        .order_by(Sale.sale_date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": sale.id,
            "customer_id": sale.customer_id,
            "user_id": sale.user_id,
            "payment_method": sale.payment_method,
            "total_amount": float(sale.total_amount),
            "tax_amount": float(sale.tax_amount),
            "notes": sale.notes,
            "sale_date": sale.sale_date.isoformat() if sale.sale_date else None,
        }
        for sale in sales
    ]

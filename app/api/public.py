from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, asc
from typing import List, Optional
from ..database import get_db
from ..models.product import Product, ProductImage, Category
from ..models.inventory import InventoryItem
from ..models.contact import ContactMessage
from ..schemas.product import ProductResponse
from ..schemas.category import CategoryResponse
from pydantic import BaseModel

router = APIRouter()


class ContactMessageCreate(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    subject: Optional[str] = None
    message: str

    class Config:
        from_attributes = True


class ContactMessageResponse(ContactMessageCreate):
    id: int
    is_read: bool
    created_at: str

    class Config:
        from_attributes = True


class PaginatedProductsResponse(BaseModel):
    items: List[dict]
    total: int
    page: int
    page_size: int
    total_pages: int


@router.get("/products", response_model=PaginatedProductsResponse)
async def get_public_products(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(20, ge=1, le=1000, description="Items per page"),
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    search: Optional[str] = Query(None, description="Search in name and description"),
    sort_by: Optional[str] = Query("created_at", description="Sort field: name, price, created_at"),
    order: Optional[str] = Query("desc", description="Sort order: asc or desc"),
    db: Session = Depends(get_db)
):
    """Get active products for public site with pagination and filters"""
    query = db.query(Product).options(
        joinedload(Product.inventory_items),
        joinedload(Product.images),
        joinedload(Product.category)
    ).filter(Product.is_active == True)
    
    if category_id is not None:
        query = query.filter(Product.category_id == category_id)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Product.name.ilike(search_term)) | (Product.description.ilike(search_term))
        )
    
    sort_column = Product.created_at
    if sort_by == "name":
        sort_column = Product.name
    elif sort_by == "price":
        sort_column = Product.unit_price
    
    if order == "asc":
        query = query.order_by(asc(sort_column))
    else:
        query = query.order_by(desc(sort_column))
    
    total = query.count()
    products = query.offset(skip).limit(limit).all()
    
    items = []
    for product in products:
        total_stock = sum(
            (item.quantity - item.reserved_quantity)
            for item in product.inventory_items
        )
        product_dict = {
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "unit_price": float(product.unit_price) if product.unit_price else 0,
            "sku": product.sku,
            "barcode": product.barcode,
            "category_id": product.category_id,
            "category_name": product.category.name if product.category else None,
            "image_url": product.image_url,
            "is_active": product.is_active,
            "stock": total_stock,
            "in_stock": total_stock > 0,
            "created_at": product.created_at.isoformat() if product.created_at else None,
            "images": [
                {
                    "id": img.id,
                    "product_id": img.product_id,
                    "image_url": img.image_url,
                    "is_primary": img.is_primary,
                    "sort_order": img.sort_order
                }
                for img in product.images
            ]
        }
        items.append(product_dict)
    
    page = (skip // limit) + 1
    total_pages = (total + limit - 1) // limit if limit > 0 else 0
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": limit,
        "total_pages": total_pages
    }


@router.get("/products/{product_id}")
async def get_public_product(product_id: int, db: Session = Depends(get_db)):
    """Get single product details for public site"""
    product = db.query(Product).options(
        joinedload(Product.inventory_items),
        joinedload(Product.images),
        joinedload(Product.category)
    ).filter(
        Product.id == product_id,
        Product.is_active == True
    ).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    total_stock = sum(
        (item.quantity - item.reserved_quantity)
        for item in product.inventory_items
    )
    product_dict = {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "unit_price": float(product.unit_price) if product.unit_price else 0,
        "sku": product.sku,
        "barcode": product.barcode,
        "category_id": product.category_id,
        "category_name": product.category.name if product.category else None,
        "image_url": product.image_url,
        "is_active": product.is_active,
        "stock": total_stock,
        "in_stock": total_stock > 0,
        "created_at": product.created_at.isoformat() if product.created_at else None,
        "images": [
            {
                "id": img.id,
                "product_id": img.product_id,
                "image_url": img.image_url,
                "is_primary": img.is_primary,
                "sort_order": img.sort_order
            }
            for img in product.images
        ]
    }
    
    return product_dict


@router.get("/categories", response_model=List[CategoryResponse])
async def get_public_categories(db: Session = Depends(get_db)):
    """Get all categories for public site"""
    categories = db.query(Category).all()
    return categories


@router.get("/categories/{category_id}", response_model=CategoryResponse)
async def get_public_category(category_id: int, db: Session = Depends(get_db)):
    """Get single category for public site"""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@router.post("/contact", response_model=ContactMessageResponse)
async def submit_contact_form(
    contact_data: ContactMessageCreate,
    db: Session = Depends(get_db)
):
    """Submit contact form message"""
    new_message = ContactMessage(
        name=contact_data.name,
        email=contact_data.email,
        phone=contact_data.phone,
        subject=contact_data.subject,
        message=contact_data.message
    )
    
    db.add(new_message)
    db.commit()
    db.refresh(new_message)
    
    return {
        "id": new_message.id,
        "name": new_message.name,
        "email": new_message.email,
        "phone": new_message.phone,
        "subject": new_message.subject,
        "message": new_message.message,
        "is_read": new_message.is_read,
        "created_at": new_message.created_at.isoformat() if new_message.created_at else None
    }

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from decimal import Decimal
import time
from pathlib import Path
from ..database import get_db
from ..models.product import Product, Category, Supplier, ProductImage
from ..models.order import Order, OrderItem
from ..schemas.product import ProductCreate, ProductResponse, ProductUpdate, ProductImageCreate, ProductImageResponse
from ..core.dependencies import require_permission
from ..models.user import User
from ..config import settings
from ..supabase import get_supabase
from ..services.image_service import compress_image, get_compressed_filename

from sqlalchemy import func, select
from ..services.image_service import ALLOWED_IMAGE_TYPES, ALLOWED_IMAGE_EXTS

router = APIRouter()


# Roles allowed to see product cost data (purchase-side financials).
_COST_VISIBILITY_ROLES = {"admin", "gerente"}


def _user_can_see_cost(user: User) -> bool:
    return bool(user.role) and user.role.name in _COST_VISIBILITY_ROLES


def _latest_cost_cte(db: Session):
    """Pre-computed latest received unit_cost per product using window function."""
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


def _latest_cost_subquery(db: Session):
    """Latest received OrderItem.unit_cost per product (non-correlated CTE)."""
    cte = _latest_cost_cte(db)
    return (
        select(cte.c.unit_cost)
        .where(cte.c.product_id == Product.id)
        .where(cte.c.rn == 1)
        .scalar_subquery()
    )


def _row_num_or_none(value) -> Optional[float]:
    if value is None:
        return None
    return float(value)



def _delete_supabase_image(image_url: str | None) -> None:
    if not image_url or "supabase.co" not in image_url:
        return
    try:
        path = image_url.split("/objects/")[1].split("?")[0]
        if path.startswith("paraiso_biker/"):
            path = path[len("paraiso_biker/"):]
        get_supabase().storage.from_("paraiso_biker").remove([path])
    except Exception:
        pass


@router.get("")
async def get_products(
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("products", "read")),
):
    cost_subq = _latest_cost_subquery(db)
    from sqlalchemy.orm import joinedload
    query = db.query(Product, cost_subq.label("current_cost")).options(joinedload(Product.images))
    if not include_inactive:
        query = query.filter(Product.is_active == True)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            Product.name.ilike(search_pattern) |
            Product.sku.ilike(search_pattern) |
            Product.barcode.ilike(search_pattern)
        )

    total = query.with_entities(func.count(Product.id)).scalar()
    rows = query.offset(skip).limit(limit).all()

    can_see_cost = _user_can_see_cost(current_user)
    items = []
    for product, current_cost in rows:
        images_data = []
        for img in product.images:
            images_data.append({
                "id": img.id,
                "product_id": img.product_id,
                "image_url": img.image_url,
                "is_primary": img.is_primary,
                "sort_order": img.sort_order,
                "created_at": img.created_at,
            })
        
        items.append({
            "id": product.id,
            "name": product.name,
            "sku": product.sku,
            "barcode": product.barcode,
            "description": product.description,
            "unit_price": product.unit_price,
            "weight": product.weight,
            "image_url": product.image_url,
            "category_id": product.category_id,
            "supplier_id": product.supplier_id,
            "is_active": product.is_active,
            "created_at": product.created_at,
            "updated_at": product.updated_at,
            "current_cost": _row_num_or_none(current_cost) if can_see_cost else None,
            "images": images_data,
        })

    return {
        "items": items,
        "total_items": total,
        "current_page": (skip // limit) + 1,
        "page_size": limit,
        "total_pages": (total + limit - 1) // limit if limit > 0 else 0,
    }



@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("products", "read")),
):
    cost_subq = _latest_cost_subquery(db)
    from sqlalchemy.orm import joinedload
    row = (
        db.query(Product, cost_subq.label("current_cost"))
        .options(joinedload(Product.images))
        .filter(
            Product.id == product_id,
            Product.is_active == True,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    product, current_cost = row
    can_see_cost = _user_can_see_cost(current_user)
    
    images_data = []
    for img in product.images:
        images_data.append({
            "id": img.id,
            "product_id": img.product_id,
            "image_url": img.image_url,
            "is_primary": img.is_primary,
            "sort_order": img.sort_order,
            "created_at": img.created_at,
        })
    
    return {
        "id": product.id,
        "name": product.name,
        "sku": product.sku,
        "barcode": product.barcode,
        "description": product.description,
        "unit_price": product.unit_price,
        "weight": product.weight,
        "image_url": product.image_url,
        "category_id": product.category_id,
        "supplier_id": product.supplier_id,
        "is_active": product.is_active,
        "created_at": product.created_at,
        "updated_at": product.updated_at,
        "current_cost": _row_num_or_none(current_cost) if can_see_cost else None,
        "images": images_data,
    }


@router.get("/barcode/{barcode}", response_model=ProductResponse)
async def get_product_by_barcode(
    barcode: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("products", "read")),
):
    cost_subq = _latest_cost_subquery(db)
    from sqlalchemy.orm import joinedload
    row = (
        db.query(Product, cost_subq.label("current_cost"))
        .options(joinedload(Product.images))
        .filter(
            Product.barcode == barcode,
            Product.is_active == True,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    product, current_cost = row
    can_see_cost = _user_can_see_cost(current_user)
    
    images_data = []
    for img in product.images:
        images_data.append({
            "id": img.id,
            "product_id": img.product_id,
            "image_url": img.image_url,
            "is_primary": img.is_primary,
            "sort_order": img.sort_order,
            "created_at": img.created_at,
        })
    
    return {
        "id": product.id,
        "name": product.name,
        "sku": product.sku,
        "barcode": product.barcode,
        "description": product.description,
        "unit_price": product.unit_price,
        "weight": product.weight,
        "image_url": product.image_url,
        "category_id": product.category_id,
        "supplier_id": product.supplier_id,
        "is_active": product.is_active,
        "created_at": product.created_at,
        "updated_at": product.updated_at,
        "current_cost": _row_num_or_none(current_cost) if can_see_cost else None,
        "images": images_data,
    }


@router.post("", response_model=ProductResponse)
async def create_product(
    product: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("products", "create")),
):
    db_product = Product(**product.model_dump())
    db.add(db_product)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El producto con el SKU o Codigo de Barras ya existe."
        )
    db.refresh(db_product)
    return db_product


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    product: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("products", "update")),
):
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = product.model_dump(exclude_unset=True)
    if "image_url" in update_data:
        new_url = update_data["image_url"]
        old_url = db_product.image_url
        if old_url and old_url != new_url:
            _delete_supabase_image(old_url)
    for key, value in update_data.items():
        setattr(db_product, key, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El producto con el SKU o Codigo de Barras ya existe."
        )
    db.refresh(db_product)
    return db_product


@router.delete("/{product_id}")
async def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("products", "delete")),
):
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")

    _delete_supabase_image(db_product.image_url)

    db_product.is_active = False
    db.commit()
    return {"message": "Product deleted successfully"}


@router.post("/{product_id}/image")
async def upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("products", "update")),
):
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Validate content type
    ctype = (file.content_type or "").lower()
    if ctype not in ALLOWED_IMAGE_TYPES:
        ext = Path(file.filename or "").suffix.lower()
        if ext not in ALLOWED_IMAGE_EXTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo debe ser una imagen (jpg, png, webp o gif).",
            )

    # Read bytes with size guard
    contents = await file.read()
    if len(contents) > settings.MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La imagen excede el tamano maximo permitido ({settings.MAX_IMAGE_SIZE_BYTES // (1024 * 1024)} MB).",
        )
    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo esta vacio.",
        )

    # Compress and convert to WebP
    try:
        contents = compress_image(
            contents,
            max_width=settings.IMAGE_MAX_WIDTH,
            webp_quality=settings.IMAGE_WEBP_QUALITY,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo procesar la imagen.",
        )

    # Build filename (always .webp)
    path = get_compressed_filename(db_product.sku, int(time.time()), folder="products")

    # Delete old image from Supabase (if exists)
    _delete_supabase_image(db_product.image_url)

    # Upload to Supabase Storage
    supabase = get_supabase()
    supabase.storage.from_("paraiso_biker").upload(
        path,
        contents,
        {"content-type": "image/webp", "upsert": "true"},
    )

    # Get public URL
    image_url = supabase.storage.from_("paraiso_biker").get_public_url(path)
    db_product.image_url = image_url
    db.commit()
    db.refresh(db_product)
    return {"image_url": db_product.image_url}


@router.delete("/{product_id}/image")
async def delete_product_image(
    product_id: int,
    current_user: User = Depends(require_permission("products", "update")),
    db: Session = Depends(get_db),
):
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")

    if not db_product.image_url:
        return {"message": "El producto no tiene imagen."}

    # Delete from Supabase Storage
    _delete_supabase_image(db_product.image_url)

    db_product.image_url = None
    db.commit()
    return {"message": "Imagen eliminada exitosamente."}


# Product Images CRUD Endpoints

@router.get("/{product_id}/images", response_model=List[ProductImageResponse])
async def get_product_images(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("products", "read")),
):
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    images = db.query(ProductImage).filter(
        ProductImage.product_id == product_id
    ).order_by(ProductImage.sort_order, ProductImage.id).all()
    
    return images


@router.post("/{product_id}/images", response_model=ProductImageResponse)
async def upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    is_primary: bool = False,
    sort_order: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("products", "update")),
):
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Validate content type
    ctype = (file.content_type or "").lower()
    if ctype not in ALLOWED_IMAGE_TYPES:
        ext = Path(file.filename or "").suffix.lower()
        if ext not in ALLOWED_IMAGE_EXTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo debe ser una imagen (jpg, png, webp o gif).",
            )

    # Read bytes with size guard
    contents = await file.read()
    if len(contents) > settings.MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La imagen excede el tamano maximo permitido ({settings.MAX_IMAGE_SIZE_BYTES // (1024 * 1024)} MB).",
        )
    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo esta vacio.",
        )

    # Compress and convert to WebP
    try:
        contents = compress_image(
            contents,
            max_width=settings.IMAGE_MAX_WIDTH,
            webp_quality=settings.IMAGE_WEBP_QUALITY,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo procesar la imagen.",
        )

    # Build filename
    timestamp = int(time.time())
    path = get_compressed_filename(db_product.sku, timestamp, folder="products")

    # If this is marked as primary, unset other primary images
    if is_primary:
        db.query(ProductImage).filter(
            ProductImage.product_id == product_id,
            ProductImage.is_primary == True
        ).update({"is_primary": False})

    # Upload to Supabase Storage
    supabase = get_supabase()
    supabase.storage.from_("paraiso_biker").upload(
        path,
        contents,
        {"content-type": "image/webp", "upsert": "true"},
    )

    # Get public URL
    image_url = supabase.storage.from_("paraiso_biker").get_public_url(path)
    
    # Create ProductImage record
    new_image = ProductImage(
        product_id=product_id,
        image_url=image_url,
        is_primary=is_primary,
        sort_order=sort_order,
    )
    db.add(new_image)
    
    # Update main product image_url if this is the first image or is primary
    if not db_product.image_url or is_primary:
        db_product.image_url = image_url
    
    db.commit()
    db.refresh(new_image)
    
    return new_image


@router.put("/{product_id}/images/{image_id}", response_model=ProductImageResponse)
async def update_product_image(
    product_id: int,
    image_id: int,
    is_primary: Optional[bool] = None,
    sort_order: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("products", "update")),
):
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    image = db.query(ProductImage).filter(
        ProductImage.id == image_id,
        ProductImage.product_id == product_id
    ).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    if is_primary is not None:
        if is_primary:
            # Unset other primary images
            db.query(ProductImage).filter(
                ProductImage.product_id == product_id,
                ProductImage.is_primary == True,
                ProductImage.id != image_id
            ).update({"is_primary": False})
            image.is_primary = True
            # Update main product image
            db_product.image_url = image.image_url
        else:
            image.is_primary = False
    
    if sort_order is not None:
        image.sort_order = sort_order
    
    db.commit()
    db.refresh(image)
    
    return image


@router.delete("/{product_id}/images/{image_id}")
async def delete_product_image_v2(
    product_id: int,
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("products", "update")),
):
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    image = db.query(ProductImage).filter(
        ProductImage.id == image_id,
        ProductImage.product_id == product_id
    ).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Delete from Supabase
    _delete_supabase_image(image.image_url)
    
    # If this was the primary image, set another image as primary
    if image.is_primary:
        other_image = db.query(ProductImage).filter(
            ProductImage.product_id == product_id,
            ProductImage.id != image_id
        ).order_by(ProductImage.sort_order, ProductImage.id).first()
        
        if other_image:
            other_image.is_primary = True
            db_product.image_url = other_image.image_url
        else:
            db_product.image_url = None
    
    db.delete(image)
    db.commit()
    
    return {"message": "Imagen eliminada exitosamente."}

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List
import time
from pathlib import Path
from ..database import get_db
from ..models.product import Product, Category, Supplier
from ..schemas.product import ProductCreate, ProductResponse, ProductUpdate
from ..core.dependencies import require_permission
from ..models.user import User
from ..config import settings
from ..supabase import get_supabase
from ..services.image_service import compress_image, get_compressed_filename

from sqlalchemy import func
from ..services.image_service import ALLOWED_IMAGE_TYPES, ALLOWED_IMAGE_EXTS

router = APIRouter()


@router.get("/")
async def get_products(
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("products", "read")),
):
    query = db.query(Product).filter(Product.is_active == True)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            Product.name.ilike(search_pattern) |
            Product.sku.ilike(search_pattern) |
            Product.barcode.ilike(search_pattern)
        )

    total = query.with_entities(func.count(Product.id)).scalar()
    products = query.offset(skip).limit(limit).all()

    return {
        "items": products,
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
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/barcode/{barcode}", response_model=ProductResponse)
async def get_product_by_barcode(
    barcode: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("products", "read")),
):
    product = db.query(Product).filter(Product.barcode == barcode).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("/", response_model=ProductResponse)
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
    if db_product.image_url and "supabase.co" in db_product.image_url:
        try:
            old_path = db_product.image_url.split("/objects/")[1].split("?")[0]
            if old_path.startswith("paraiso_biker/"):
                old_path = old_path[len("paraiso_biker/"):]
            get_supabase().storage.from_("paraiso_biker").remove([old_path])
        except Exception:
            pass

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
    if "supabase.co" in db_product.image_url:
        try:
            path = db_product.image_url.split("/objects/")[1].split("?")[0]
            if path.startswith("paraiso_biker/"):
                path = path[len("paraiso_biker/"):]
            get_supabase().storage.from_("paraiso_biker").remove([path])
        except Exception:
            pass

    db_product.image_url = None
    db.commit()
    return {"message": "Imagen eliminada exitosamente."}

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from decimal import Decimal

class ProductImageBase(BaseModel):
    is_primary: Optional[bool] = False
    sort_order: Optional[int] = 0

class ProductImageCreate(ProductImageBase):
    pass

class ProductImageResponse(ProductImageBase):
    id: int
    product_id: int
    image_url: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class ProductBase(BaseModel):
    name: str
    sku: str = ""
    barcode: Optional[str] = None
    description: Optional[str] = None
    unit_price: Decimal
    weight: Optional[Decimal] = None
    image_url: Optional[str] = None
    category_id: int
    supplier_id: Optional[int] = None

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    barcode: Optional[str] = None
    description: Optional[str] = None
    unit_price: Optional[Decimal] = None
    weight: Optional[Decimal] = None
    image_url: Optional[str] = None
    category_id: Optional[int] = None
    supplier_id: Optional[int] = None
    is_active: Optional[bool] = None

class ProductResponse(ProductBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    current_cost: Optional[Decimal] = None
    images: Optional[List[ProductImageResponse]] = []
    
    class Config:
        from_attributes = True

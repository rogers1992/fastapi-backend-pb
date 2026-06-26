from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class WarehouseBase(BaseModel):
    name: str
    location: Optional[str] = None
    contact_info: Optional[dict] = None


class WarehouseCreate(WarehouseBase):
    pass


class WarehouseUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    contact_info: Optional[dict] = None
    is_active: Optional[bool] = None


class WarehouseResponse(WarehouseBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

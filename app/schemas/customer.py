from pydantic import EmailStr

from . import BaseSchema
from datetime import datetime, date
from typing import Optional

class CustomerBase(BaseSchema):
    first_name: str
    last_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    date_of_birth: Optional[date] = None

class CustomerCreate(CustomerBase):
    pass

class CustomerUpdate(BaseSchema):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    date_of_birth: Optional[date] = None

class LoyaltyResponse(BaseSchema):
    id: int
    points: int
    tier: str
    last_updated: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class CustomerResponse(CustomerBase):
    id: int
    is_active: int
    created_at: datetime
    loyalty: Optional[LoyaltyResponse] = None
    
    class Config:
        from_attributes = True

class LoyaltyUpdate(BaseSchema):
    points: Optional[int] = None
    tier: Optional[str] = None

class LoyaltyAdjust(BaseSchema):
    points_change: int
    reason: Optional[str] = None

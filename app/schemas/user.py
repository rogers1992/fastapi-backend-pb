from pydantic import EmailStr, Field

from . import BaseSchema
from datetime import datetime
from typing import Optional, List, Dict
from .role import RoleResponse


class UserBase(BaseSchema):
    username: str
    email: EmailStr
    first_name: str
    last_name: str
    phone: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(min_length=6)
    role_id: int
    warehouse_ids: Optional[List[int]] = None


class UserUpdate(BaseSchema):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    role_id: Optional[int] = None
    warehouse_ids: Optional[List[int]] = None


class UserPasswordReset(BaseSchema):
    new_password: str = Field(min_length=6)


class UserToggleActive(BaseSchema):
    is_active: bool


class UserResponse(UserBase):
    id: int
    role_id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserWithRoleResponse(UserBase):
    id: int
    role_id: int
    role: Optional[RoleResponse] = None
    is_active: bool
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    warehouse_ids: List[int] = []

    class Config:
        from_attributes = True


class UserLogin(BaseSchema):
    username: str
    password: str


class Token(BaseSchema):
    access_token: str
    token_type: str
    user: UserWithRoleResponse


class TokenData(BaseSchema):
    username: Optional[str] = None
    role: Optional[str] = None
    permissions: Optional[Dict[str, List[str]]] = None

from datetime import datetime, timezone
from pydantic import BaseModel, model_serializer


class BaseSchema(BaseModel):
    """Base schema with UTC datetime serialization.

    All schemas should inherit from this instead of BaseModel to ensure
    all datetime fields serialize with explicit UTC timezone (Z suffix).
    """

    @model_serializer(mode='wrap')
    def serialize_model(self, handler):
        data = handler(self)
        for key, value in data.items():
            if isinstance(value, str):
                try:
                    dt = datetime.fromisoformat(value)
                    if dt.tzinfo is None:
                        data[key] = dt.replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')
                except (ValueError, TypeError):
                    pass
        return data


from .user import (
    UserCreate, UserUpdate, UserResponse, UserWithRoleResponse,
    UserLogin, UserPasswordReset, UserToggleActive, Token, TokenData,
)
from .role import RoleCreate, RoleUpdate, RoleResponse, PermissionMap
from .product import ProductCreate, ProductResponse, ProductUpdate
from .inventory import InventoryItemCreate, InventoryItemResponse, InventoryItemUpdate, InventoryTransfer
from .sale import SaleCreate, SaleResponse, SaleItemCreate, SaleItemResponse
from .customer import CustomerCreate, CustomerResponse, CustomerUpdate


__all__ = [
    'UserCreate', 'UserUpdate', 'UserResponse', 'UserWithRoleResponse',
    'UserLogin', 'UserPasswordReset', 'UserToggleActive', 'Token', 'TokenData',
    'RoleCreate', 'RoleUpdate', 'RoleResponse', 'PermissionMap',
    'ProductCreate', 'ProductResponse', 'ProductUpdate',
    'InventoryItemCreate', 'InventoryItemResponse', 'InventoryItemUpdate', 'InventoryTransfer',
    'SaleCreate', 'SaleResponse', 'SaleItemCreate', 'SaleItemResponse',
    'CustomerCreate', 'CustomerResponse', 'CustomerUpdate',
    'BaseSchema',
]

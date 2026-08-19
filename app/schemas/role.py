from pydantic import field_validator

from . import BaseSchema
from datetime import datetime
from typing import Optional, List, Dict


VALID_RESOURCES = ["products", "inventory", "sales", "purchases", "customers", "users", "roles", "reports", "categories", "suppliers"]
VALID_ACTIONS = ["read", "create", "update", "delete"]


class PermissionMap(BaseSchema):
    permissions: Dict[str, List[str]] = {}

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, v: Dict[str, List[str]]) -> Dict[str, List[str]]:
        for resource, actions in v.items():
            if resource not in VALID_RESOURCES:
                raise ValueError(f"Invalid resource: {resource}. Must be one of {VALID_RESOURCES}")
            for action in actions:
                if action not in VALID_ACTIONS:
                    raise ValueError(f"Invalid action: {action}. Must be one of {VALID_ACTIONS}")
        return v


class RoleBase(BaseSchema):
    name: str
    description: Optional[str] = None


class RoleCreate(RoleBase, PermissionMap):
    pass


class RoleUpdate(BaseSchema):
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[Dict[str, List[str]]] = None

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, v):
        if v is None:
            return v
        for resource, actions in v.items():
            if resource not in VALID_RESOURCES:
                raise ValueError(f"Invalid resource: {resource}. Must be one of {VALID_RESOURCES}")
            for action in actions:
                if action not in VALID_ACTIONS:
                    raise ValueError(f"Invalid action: {action}. Must be one of {VALID_ACTIONS}")
        return v


class RoleResponse(BaseSchema):
    id: int
    name: str
    description: Optional[str] = None
    permissions: Dict[str, List[str]] = {}
    is_system: bool
    created_at: datetime

    class Config:
        from_attributes = True

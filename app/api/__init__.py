from fastapi import APIRouter
from .auth import router as auth_router
from .users import router as users_router
from .roles import router as roles_router
from .products import router as products_router
from .inventory import router as inventory_router
from .sales import router as sales_router
from .customers import router as customers_router

__all__ = [
    'auth_router', 'users_router', 'roles_router',
    'products_router', 'inventory_router', 'sales_router', 'customers_router',
]

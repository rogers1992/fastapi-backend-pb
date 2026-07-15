from pydantic import BaseModel
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


class SalesReportRow(BaseModel):
    sale_id: int
    sale_date: datetime
    customer_id: Optional[int]
    customer_name: Optional[str]
    seller_id: Optional[int]
    seller_name: Optional[str]
    payment_method: str
    status: str
    items_count: Optional[int]
    units_sold: Optional[int]
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal


class InventoryReportRow(BaseModel):
    product_id: int
    name: str
    sku: Optional[str]
    category_id: Optional[int]
    category_name: Optional[str]
    warehouse_id: int
    warehouse_name: str
    quantity: int
    reserved_quantity: int
    min_stock_level: int
    max_stock_level: Optional[int]
    unit_price: Decimal
    stock_value: Decimal
    is_low_stock: bool
    is_out_of_stock: bool


class PurchaseReportRow(BaseModel):
    order_id: int
    order_date: datetime
    supplier_id: Optional[int]
    supplier_name: Optional[str]
    warehouse_id: Optional[int]
    warehouse_name: Optional[str]
    status: str
    items_count: int
    units_ordered: int
    total_amount: Decimal


class CustomerReportRow(BaseModel):
    customer_id: int
    name: str
    email: Optional[str]
    phone: Optional[str]
    is_active: int
    loyalty_tier: Optional[str]
    loyalty_points: Optional[int]
    orders: int
    total_spent: Decimal
    last_sale_date: Optional[datetime]


class ProductReportRow(BaseModel):
    product_id: int
    name: str
    sku: Optional[str]
    category_id: Optional[int]
    category_name: Optional[str]
    unit_price: Decimal
    is_active: bool
    units_sold: int
    revenue: Decimal
    stock_quantity: int
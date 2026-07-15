from pydantic import BaseModel
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional


class DashboardSummary(BaseModel):
    revenue_today: Decimal
    revenue_week: Decimal
    revenue_month: Decimal
    sales_count_today: int
    sales_count_month: int
    avg_ticket: Decimal
    tax_collected_month: Decimal
    low_stock_count: int
    pending_po_count: int
    active_customers: int
    active_products: int
    top_product_name: Optional[str]
    top_product_revenue: Optional[Decimal]


class SalesTrendPoint(BaseModel):
    date_label: str
    revenue: Decimal
    sales_count: int


class WarehouseStatusRow(BaseModel):
    warehouse_id: int
    warehouse_name: str
    quantity: int
    items: int


class InventoryStatusItem(BaseModel):
    product_id: int
    product_name: str
    sku: Optional[str]
    warehouse_id: int
    warehouse_name: str
    quantity: int
    min_stock_level: int
    is_low_stock: bool
    is_out_of_stock: bool


class InventoryStatusSummary(BaseModel):
    total_quantity: int
    total_value: Decimal
    low_stock_count: int
    out_of_stock_count: int
    by_warehouse: List[WarehouseStatusRow]
    low_stock_items: List[InventoryStatusItem]


class TopProductRow(BaseModel):
    product_id: int
    name: str
    sku: Optional[str]
    qty_sold: int
    revenue: Decimal


class TopCustomerRow(BaseModel):
    customer_id: int
    name: str
    orders: int
    total_spent: Decimal
    tier: Optional[str]


class PaymentMethodRow(BaseModel):
    payment_method: str
    count: int
    total: Decimal
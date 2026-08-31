-- Migration 008: Add performance indexes for frequently queried columns
-- Reduces query execution time for list endpoints with filtering/sorting

-- Purchases (orders) filtering and sorting
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_supplier_id ON orders(supplier_id);
CREATE INDEX IF NOT EXISTS idx_orders_warehouse_id ON orders(warehouse_id);
CREATE INDEX IF NOT EXISTS idx_orders_order_date ON orders(order_date DESC);

-- Order items (for JOIN optimization)
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product_id ON order_items(product_id);

-- Sales filtering and sorting
CREATE INDEX IF NOT EXISTS idx_sales_status ON sales(status);
CREATE INDEX IF NOT EXISTS idx_sales_customer_id ON sales(customer_id);
CREATE INDEX IF NOT EXISTS idx_sales_user_id ON sales(user_id);
CREATE INDEX IF NOT EXISTS idx_sales_sale_date ON sales(sale_date DESC);
CREATE INDEX IF NOT EXISTS idx_sales_warehouse_id ON sales(warehouse_id);

-- Sale items (for JOIN optimization)
CREATE INDEX IF NOT EXISTS idx_sale_items_sale_id ON sale_items(sale_id);
CREATE INDEX IF NOT EXISTS idx_sale_items_product_id ON sale_items(product_id);

-- Customers filtering
CREATE INDEX IF NOT EXISTS idx_customers_is_active ON customers(is_active);

-- Products filtering
CREATE INDEX IF NOT EXISTS idx_products_is_active ON products(is_active);
CREATE INDEX IF NOT EXISTS idx_products_category_id ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_supplier_id ON products(supplier_id);

-- Inventory filtering
CREATE INDEX IF NOT EXISTS idx_inventory_product_id ON inventory_items(product_id);
CREATE INDEX IF NOT EXISTS idx_inventory_warehouse_id ON inventory_items(warehouse_id);

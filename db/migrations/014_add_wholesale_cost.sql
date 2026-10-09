-- Add wholesale cost to products
ALTER TABLE products ADD COLUMN IF NOT EXISTS wholesale_cost_price NUMERIC(10,2);

-- Copy existing cost_price as default for wholesale_cost_price
-- UPDATE products SET wholesale_cost_price = cost_price WHERE wholesale_cost_price IS NULL;

-- Add wholesale flag to warehouses
ALTER TABLE warehouses ADD COLUMN IF NOT EXISTS is_wholesale BOOLEAN DEFAULT FALSE;

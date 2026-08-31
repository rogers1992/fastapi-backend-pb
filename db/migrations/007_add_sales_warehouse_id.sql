-- Migration 007: Add warehouse_id to sales table
-- Links each sale to the warehouse where it was made.
-- Enables per-warehouse inventory validation and reporting.

-- Add warehouse_id column (nullable so existing sales are unaffected)
ALTER TABLE sales ADD COLUMN IF NOT EXISTS warehouse_id INTEGER REFERENCES warehouses(id);

-- Add index for faster lookups and joins
CREATE INDEX IF NOT EXISTS idx_sales_warehouse ON sales(warehouse_id);

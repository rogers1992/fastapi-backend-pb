-- Migration: Add total_amount to orders and rename order_items.unit_price → unit_cost
-- Date: 2026-07-10
-- Description: Supports the Compras (Purchases) module. total_amount enables
--   querying/reporting without aggregating items. Renaming unit_price to
--   unit_cost disambiguates purchase cost from the product selling price.

-- 1. Add total_amount column to orders table
ALTER TABLE orders ADD COLUMN IF NOT EXISTS total_amount DECIMAL(10,2) DEFAULT 0;

-- 2. Rename order_items.unit_price → unit_cost (idempotent: check current state)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'order_items' AND column_name = 'unit_price'
    ) THEN
        ALTER TABLE order_items RENAME COLUMN unit_price TO unit_cost;
    END IF;
END $$;
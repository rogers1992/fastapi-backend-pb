-- Migration: Add user_warehouses junction table for many-to-many relationship
-- Allows assigning multiple warehouses to users (e.g., vendedores with sales permissions)

CREATE TABLE IF NOT EXISTS user_warehouses (
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    warehouse_id INTEGER REFERENCES warehouses(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, warehouse_id)
);

CREATE INDEX IF NOT EXISTS idx_user_warehouses_user ON user_warehouses(user_id);
CREATE INDEX IF NOT EXISTS idx_user_warehouses_warehouse ON user_warehouses(warehouse_id);

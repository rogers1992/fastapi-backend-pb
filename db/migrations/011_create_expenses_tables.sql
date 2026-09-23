-- Migration 011: Create expense_categories and expenses tables
-- Tracks business operating expenses (rent, utilities, salaries, etc.)
-- and supports per-warehouse and global income statement generation.

CREATE TABLE IF NOT EXISTS expense_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description VARCHAR(255),
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS expenses (
    id SERIAL PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES expense_categories(id),
    warehouse_id INTEGER REFERENCES warehouses(id),
    amount NUMERIC(10,2) NOT NULL,
    description VARCHAR(500),
    expense_date TIMESTAMP DEFAULT NOW(),
    payment_method VARCHAR(50) DEFAULT 'efectivo',
    is_recurring BOOLEAN DEFAULT FALSE,
    recorded_by INTEGER NOT NULL REFERENCES users(id),
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(expense_date);
CREATE INDEX IF NOT EXISTS idx_expenses_warehouse ON expenses(warehouse_id);
CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category_id);
CREATE INDEX IF NOT EXISTS idx_expenses_recurring ON expenses(is_recurring);

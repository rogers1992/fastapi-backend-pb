-- ============================================
-- ============================================
-- Paraiso Biker Database Schema
-- ============================================

-- 1. Roles Table
CREATE TABLE roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    permissions JSONB DEFAULT '{}'::jsonb,
    description TEXT,
    is_system BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Users Table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    role_id INTEGER REFERENCES roles(id),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    phone VARCHAR(20),
    is_active BOOLEAN DEFAULT true,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Warehouses Table
CREATE TABLE warehouses (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    location TEXT,
    contact_info JSONB,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Categories Table
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    parent_id INTEGER REFERENCES categories(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. Suppliers Table
CREATE TABLE suppliers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    contact_info JSONB,
    address TEXT,
    email VARCHAR(100),
    phone VARCHAR(20),
    website VARCHAR(200),
    payment_terms VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. Products Table
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    category_id INTEGER REFERENCES categories(id),
    supplier_id INTEGER REFERENCES suppliers(id),
    sku VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    barcode VARCHAR(100) UNIQUE,
    unit_price DECIMAL(10,2) NOT NULL,
    weight DECIMAL(8,2),
    dimensions JSONB,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. Inventory Items Table
CREATE TABLE inventory_items (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id),
    warehouse_id INTEGER REFERENCES warehouses(id),
    quantity INTEGER NOT NULL DEFAULT 0,
    reserved_quantity INTEGER NOT NULL DEFAULT 0,
    min_stock_level INTEGER DEFAULT 0,
    max_stock_level INTEGER,
    location VARCHAR(100),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(product_id, warehouse_id)
);

-- 8. Customers Table
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE,
    phone VARCHAR(20),
    address TEXT,
    date_of_birth DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 9. Loyalty Table
CREATE TABLE loyalty (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    points INTEGER DEFAULT 0,
    tier VARCHAR(20) DEFAULT 'bronze',
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add loyalty_id to customers
ALTER TABLE customers ADD COLUMN loyalty_id INTEGER REFERENCES loyalty(id);

-- 10. Sales Table
CREATE TABLE sales (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    user_id INTEGER REFERENCES users(id),
    payment_method VARCHAR(50) NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL,
    tax_amount DECIMAL(10,2) DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'completed',
    sale_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

-- 11. Sale Items Table
CREATE TABLE sale_items (
    id SERIAL PRIMARY KEY,
    sale_id INTEGER REFERENCES sales(id),
    product_id INTEGER REFERENCES products(id),
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    discount DECIMAL(10,2) DEFAULT 0,
    total_price DECIMAL(10,2) NOT NULL,
    notes TEXT
);

-- 12. Orders Table (Purchase Orders)
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    supplier_id INTEGER REFERENCES suppliers(id),
    warehouse_id INTEGER REFERENCES warehouses(id),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expected_date DATE,
    received_date DATE,
    created_by INTEGER REFERENCES users(id),
    notes TEXT
);

-- 13. Order Items Table
CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    product_id INTEGER REFERENCES products(id),
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    total_price DECIMAL(10,2) NOT NULL,
    received_quantity INTEGER DEFAULT 0,
    notes TEXT
);

-- 14. Payments Table
CREATE TABLE payments (
    id SERIAL PRIMARY KEY,
    sale_id INTEGER REFERENCES sales(id),
    method VARCHAR(50) NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    transaction_id VARCHAR(200),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    processed_at TIMESTAMP,
    notes TEXT
);

-- 15. Audit Trail Table
CREATE TABLE audit_trail (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(50) NOT NULL,
    table_name VARCHAR(50) NOT NULL,
    record_id INTEGER,
    old_values JSONB,
    new_values JSONB,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- SEED DATA
-- ============================================

-- Roles
INSERT INTO roles (name, permissions, description, is_system) VALUES
('admin', '{"products": ["read", "create", "update", "delete"], "inventory": ["read", "create", "update", "delete"], "sales": ["read", "create", "update", "delete"], "customers": ["read", "create", "update", "delete"], "users": ["read", "create", "update", "delete"], "roles": ["read", "create", "update", "delete"], "reports": ["read", "create"]}', 'Administrador con acceso completo', true),
('gerente', '{"products": ["read", "create", "update"], "inventory": ["read", "create", "update"], "sales": ["read", "create", "update"], "customers": ["read", "create", "update"], "users": ["read"], "reports": ["read", "create"]}', 'Gerente de tienda', true),
('vendedor', '{"products": ["read"], "inventory": ["read"], "sales": ["read", "create"], "customers": ["read", "create"]}', 'Vendedor', true),
('almacen', '{"products": ["read"], "inventory": ["read", "update"]}', 'Personal de almacén', true);

-- Admin User (password: admin123 - hashed with bcrypt)
INSERT INTO users (role_id, username, email, password_hash, first_name, last_name, phone) VALUES
(1, 'admin', 'admin@paraisobiker.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYzS3MebAJu', 'Administrador', 'Sistema', '+52 555 000 0000');

-- Warehouses
INSERT INTO warehouses (name, location, contact_info) VALUES
('Principal', 'Tienda Centro', '{"phone": "+52 555 100 0000", "email": "principal@paraisobiker.com"}'),
('Secundario', 'Almacén Norte', '{"phone": "+52 555 200 0000", "email": "secundario@paraisobiker.com"}');

-- Categories
INSERT INTO categories (name, description) VALUES
('Cadenas', 'Cadenas y componentes de transmisión'),
('Frenos', 'Sistemas de frenos y pastillas'),
('Neumáticos', 'Llantas y cámaras de aire'),
('Transmisión', 'Cambios y engranajes'),
('Accesorios', 'Accesorios y componentes adicionales'),
('Herramientas', 'Herramientas y mantenimiento');

-- Suppliers (6 suppliers)
INSERT INTO suppliers (name, contact_info, address, email, phone, payment_terms) VALUES
('Shimano México', '{"contact": "Carlos Ruiz"}', 'Ciudad de México', 'ventas@shimano.mx', '+52 555 300 0000', '30 días'),
('Tektro Latinoamérica', '{"contact": "María López"}', 'Guadalajara', 'contacto@tektro.mx', '+52 333 400 0000', 'Contado'),
('Michelin Deportes', '{"contact": "Juan Pérez"}', 'Monterrey', 'ventas@michelin.mx', '+52 818 500 0000', '45 días'),
('SRAM Components', '{"contact": "Ana García"}', 'Puebla', 'ventas@sram.mx', '+52 222 600 0000', '30 días'),
('Park Tools', '{"contact": "Roberto Díaz"}', 'Tijuana', 'ventas@parktool.mx', '+52 664 700 0000', 'Contado'),
('Continental Tires', '{"contact": "Luis Hernández"}', 'Mérida', 'ventas@continental.mx', '+52 999 800 0000', '60 días');

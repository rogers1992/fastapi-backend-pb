-- Migration 012: Seed expense categories
-- Predefined categories for business operating expenses.

INSERT INTO expense_categories (name, description, sort_order) VALUES
('Alquiler', 'Alquiler de local comercial', 1),
('Servicios', 'Luz, agua, internet, telefono', 2),
('Sueldos', 'Sueldos y cargas sociales', 3),
('Transporte', 'Transporte y logistica', 4),
('Mantenimiento', 'Reparaciones y mantenimiento', 5),
('Impuestos', 'Impuestos y tasas', 6),
('Suministros', 'Suministros de oficina', 7),
('Marketing', 'Publicidad y marketing', 8),
('Otros', 'Otros gastos operacionales', 9)
ON CONFLICT (name) DO NOTHING;

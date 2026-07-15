-- Migration: Add "Cliente General" customer for POS walk-in sales
-- Date: 2026-07-08
-- Description: Insert a default "Cliente General" customer if it doesn't exist

INSERT INTO customers (first_name, last_name, email, phone)
SELECT 'Cliente', 'General', 'general@paraisobiker.com', ''
WHERE NOT EXISTS (
  SELECT 1 FROM customers WHERE first_name = 'Cliente' AND last_name = 'General'
);

-- Migration: Add is_active to customers table
-- Date: 2026-07-09
-- Description: Soft-delete support for customers

ALTER TABLE customers ADD COLUMN IF NOT EXISTS is_active INTEGER DEFAULT 1 NOT NULL;

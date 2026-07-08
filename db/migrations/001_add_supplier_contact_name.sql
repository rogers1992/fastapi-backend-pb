-- Migration: Flatten contact_info JSONB into contact_name column
-- Date: 2026-07-08
-- Description: Add contact_name column to suppliers table and migrate data from contact_info JSONB

-- Add contact_name column if it doesn't exist
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS contact_name VARCHAR(200);

-- Migrate existing data from contact_info JSONB
-- The JSONB stores contact name under "contact" key: {"contact": "Carlos Ruiz"}
UPDATE suppliers
SET contact_name = contact_info->>'contact'
WHERE contact_info IS NOT NULL
  AND contact_info->>'contact' IS NOT NULL
  AND (contact_name IS NULL OR contact_name = '');

-- After verification, optionally drop the JSONB column:
-- ALTER TABLE suppliers DROP COLUMN contact_info;

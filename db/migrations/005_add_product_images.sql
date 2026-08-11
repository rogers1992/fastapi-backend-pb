-- Migration 005: Add product_images table for multiple product images
-- This allows products to have multiple images with a primary image concept

-- Create product_images table
CREATE TABLE IF NOT EXISTS product_images (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    image_url VARCHAR(255) NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add index for faster lookups by product_id
CREATE INDEX IF NOT EXISTS idx_product_imaidx_product_images_product_idges_product_id ON product_images(product_id);

-- Migrate existing product image_url to product_images as primary image
INSERT INTO product_images (product_id, image_url, is_primary, sort_order)
SELECT id, image_url, TRUE, 0
FROM products
WHERE image_url IS NOT NULL
AND NOT EXISTS (
    SELECT 1 FROM product_images WHERE product_images.product_id = products.id
);

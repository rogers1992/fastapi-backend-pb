#!/usr/bin/env python3
"""
Manual migration script: add warehouse_id column to sales table.

Usage:
    python scripts/migrate_sales_warehouse.py

This connects to the Neon DB using the same DATABASE_URL from app/config
and runs the ALTER TABLE directly, with verbose output for debugging.
"""

import sys
import os

# Ensure backend root is on the path so we can import app.config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text


def run_migration(database_url: str) -> None:
    engine = create_engine(database_url)

    print("=" * 60)
    print("Migration: Add warehouse_id to sales table")
    print("=" * 60)

    with engine.connect() as conn:
        # --- 1. Check if the sales table exists ---
        result = conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_name = 'sales'"
            )
        )
        table_exists = result.scalar()
        print(f"[INFO] sales table exists: {table_exists > 0}")
        if table_exists == 0:
            print("[WARN] sales table does not exist — skipping")
            return

        # --- 2. Check if warehouse_id column already exists ---
        result = conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_name = 'sales' AND column_name = 'warehouse_id'"
            )
        )
        column_exists = result.scalar()
        print(f"[INFO] warehouse_id column exists: {column_exists > 0}")
        if column_exists > 0:
            print("[OK] Column already present — nothing to do")
            return

        # --- 3. Check if the warehouses table exists (FK target) ---
        result = conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_name = 'warehouses'"
            )
        )
        warehouses_exist = result.scalar()
        print(f"[INFO] warehouses table exists: {warehouses_exist > 0}")

        # --- 4. Run ALTER TABLE ---
        if warehouses_exist:
            sql = (
                "ALTER TABLE sales "
                "ADD COLUMN warehouse_id INTEGER REFERENCES warehouses(id)"
            )
        else:
            sql = (
                "ALTER TABLE sales "
                "ADD COLUMN warehouse_id INTEGER"
            )

        print(f"[SQL]  {sql}")
        conn.execute(text(sql))
        conn.commit()
        print("[OK] ALTER TABLE executed and committed")

        # --- 5. Verify ---
        result = conn.execute(
            text(
                "SELECT column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_name = 'sales' AND column_name = 'warehouse_id'"
            )
        )
        row = result.fetchone()
        if row:
            col_name, data_type, nullable = row
            print(f"[OK] Verified: column_name={col_name}, data_type={data_type}, is_nullable={nullable}")
        else:
            print("[ERROR] Column verification FAILED — column not found after ALTER")

    print("=" * 60)


if __name__ == "__main__":
    from app.config import settings
    run_migration(settings.DATABASE_URL)

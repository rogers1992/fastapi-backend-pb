"""
Hard-delete all active products that have no received purchase orders (no current_cost).

Execution order (FK-safe):
  1. inventory_items  (stock records)
  2. order_items      (from pending orders)
  3. sale_items       (sale line items)
  4. products         (the products themselves)

Rolls back on any error. Prints counts before/after.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine

with engine.connect() as conn:
    trans = conn.begin()
    try:
        # Identify target products
        target_sql = """
            SELECT p.id, p.sku, p.name
            FROM products p
            WHERE p.is_active = true
              AND NOT EXISTS (
                  SELECT 1 FROM order_items oi
                  JOIN orders o ON o.id = oi.order_id
                  WHERE oi.product_id = p.id
                    AND o.status = 'received'
                    AND o.received_date IS NOT NULL
              )
        """
        targets = conn.execute(text(target_sql)).fetchall()
        count = len(targets)
        print(f"Products to delete: {count}")
        if count == 0:
            print("Nothing to delete.")
            trans.rollback()
            sys.exit(0)

        # Build IN clause
        ids = [r[0] for r in targets]
        placeholders = ",".join([str(i) for i in ids])

        # Step 1: Delete inventory_items
        r1 = conn.execute(text(f"DELETE FROM inventory_items WHERE product_id IN ({placeholders})"))
        print(f"  inventory_items deleted: {r1.rowcount}")

        # Step 2: Delete order_items
        r2 = conn.execute(text(f"DELETE FROM order_items WHERE product_id IN ({placeholders})"))
        print(f"  order_items deleted: {r2.rowcount}")

        # Step 3: Delete sale_items
        r3 = conn.execute(text(f"DELETE FROM sale_items WHERE product_id IN ({placeholders})"))
        print(f"  sale_items deleted: {r3.rowcount}")

        # Step 4: Delete products
        r4 = conn.execute(text(f"DELETE FROM products WHERE id IN ({placeholders})"))
        print(f"  products deleted: {r4.rowcount}")

        # Verify
        remaining = conn.execute(text("""
            SELECT COUNT(*) FROM products p
            WHERE p.is_active = true
              AND NOT EXISTS (
                  SELECT 1 FROM order_items oi
                  JOIN orders o ON o.id = oi.order_id
                  WHERE oi.product_id = p.id
                    AND o.status = 'received'
                    AND o.received_date IS NOT NULL
              )
        """)).scalar()
        print(f"\nRemaining products without cost: {remaining}")

        if remaining == 0:
            trans.commit()
            print("Committed successfully.")
        else:
            print("ERROR: Some products still without cost. Rolling back.")
            trans.rollback()

    except Exception as e:
        print(f"\nError: {e}")
        trans.rollback()
        print("Rolled back.")
        raise

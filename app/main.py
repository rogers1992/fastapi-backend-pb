from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from sqlalchemy import text
import traceback
from .config import settings
from .api import auth, products, inventory, sales, purchases, customers, users, roles, categories, suppliers, warehouses, notifications, reports, dashboard
from .database import engine, Base


def _ensure_column(table: str, column: str, sql_type: str, conn) -> None:
    """
    Add a column to an existing table if it does not already exist.
    Uses information_schema so it works regardless of the DB search_path
    (important for Neon and other hosted PostgreSQL services).
    """
    result = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column},
    )
    if result.scalar() > 0:
        return  # already present
    conn.execute(
        text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {sql_type}")
    )
    conn.commit()


def _ensure_products_image_url_column() -> None:
    """
    Backfill the products.image_url column on DBs that predate it.

    Base.metadata.create_all() only creates missing TABLES, never new
    columns on existing tables. The Product model declares image_url; if the
    live products table is from an older deploy, SELECT products.image_url
    fails with "column does not exist" -> HTTP 500 on /products (+collateral
    damage to /inventory via the frontend Promise.all).

    Run an idempotent ALTER before create_all. Guarded by to_regclass so a
    brand-new (column-less AND table-less) DB does not raise on ALTER of a
    nonexistent table -- create_all will build it WITH the column.
    Safe to run on every boot: IF NOT EXISTS makes it a no-op when present.
    """
    try:
        with engine.connect() as conn:
            _ensure_column("products", "image_url", "VARCHAR(255)", conn)
    except Exception:
        traceback.print_exc()


def _ensure_customer_is_active_column() -> None:
    """
    Backfill the customers.is_active column on DBs that predate it.
    Same pattern as _ensure_products_image_url_column().
    """
    try:
        with engine.connect() as conn:
            _ensure_column("customers", "is_active", "INTEGER DEFAULT 1 NOT NULL", conn)
    except Exception:
        traceback.print_exc()


def _ensure_orders_total_amount_column() -> None:
    """
    Backfill the orders.total_amount column on DBs that predate it.
    Matches the pattern used for the image_url and is_active backfills.
    """
    try:
        with engine.connect() as conn:
            _ensure_column("orders", "total_amount", "DECIMAL(10,2) DEFAULT 0", conn)
    except Exception:
        traceback.print_exc()


def _ensure_sales_warehouse_id_column() -> None:
    """
    Backfill the sales.warehouse_id column on DBs that predate it.
    """
    try:
        with engine.connect() as conn:
            _ensure_column("sales", "warehouse_id", "INTEGER REFERENCES warehouses(id)", conn)
    except Exception:
        traceback.print_exc()


_ensure_products_image_url_column()
_ensure_customer_is_active_column()
_ensure_orders_total_amount_column()
_ensure_sales_warehouse_id_column()
Base.metadata.create_all(bind=engine)

# Ensure the upload directory exists before mounting StaticFiles.
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

if settings.SEED_DEFAULTS:
    from .database import SessionLocal
    from .seed import seed_defaults
    db = SessionLocal()
    try:
        seed_defaults(db)
    except Exception as e:
        print(f"[seed] error: {e}")
    finally:
        db.close()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(roles.router, prefix="/api/roles", tags=["Roles"])
app.include_router(categories.router, prefix="/api/categories", tags=["Categories"])
app.include_router(suppliers.router, prefix="/api/suppliers", tags=["Suppliers"])
app.include_router(products.router, prefix="/api/products", tags=["Products"])
app.include_router(inventory.router, prefix="/api/inventory", tags=["Inventory"])
app.include_router(warehouses.router, prefix="/api/warehouses", tags=["Warehouses"])
app.include_router(sales.router, prefix="/api/sales", tags=["Sales"])
app.include_router(purchases.router, prefix="/api/purchases", tags=["Purchases"])
app.include_router(customers.router, prefix="/api/customers", tags=["Customers"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["Notifications"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])

# Serve uploaded product images (and any future uploads) as static files.
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


@app.get("/")
async def root():
    return {"message": "Paraiso Biker API", "version": settings.VERSION}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}

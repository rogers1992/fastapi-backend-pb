# Paraiso Biker - Backend API

FastAPI backend for Paraiso Biker Inventory & Sales Management System.

## Quick Start

One-command setup using the included startup script:

```bash
./start.sh
```

This starts PostgreSQL, creates the virtual environment, installs dependencies, seeds data, and launches the API server.

## Setup (Manual)

### 1. Start Database (Docker)

```bash
docker-compose up -d
```

Wait 30 seconds for database initialization.

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run Database Migrations

The database schema is automatically created when you start the API.

### 5. Import Seed Data

```bash
# Generate seed data
python scripts/seed_data.py

# Import into database
python scripts/import_seed_data.py
```

### 6. Start API Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Documentation

Once running, access:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

## Default Credentials

- **Username:** admin
- **Password:** admin123

## Architecture

- **Framework:** FastAPI 0.109.0 (Python 3.12)
- **ORM:** SQLAlchemy 2.0 with PostgreSQL 14
- **Auth:** JWT Bearer tokens (HS256), 24h expiry
- **Password hashing:** bcrypt via passlib
- **Validation:** Pydantic v2 schemas
- **Database:** PostgreSQL via Docker, schema initialized by `db/init.sql`

### Request Flow

```
Client → FastAPI Router → Permission Check → Service/Logic → SQLAlchemy → PostgreSQL
```

## Authentication & Authorization

### JWT Flow

1. Client sends `POST /api/auth/login` with `{ username, password }`
2. Server validates credentials, returns JWT with claims: `sub` (username), `role`, `permissions`
3. Client includes token in subsequent requests: `Authorization: Bearer <token>`

### RBAC Permission System

Roles store permissions as a JSONB map of `resource → actions`:

```json
{
  "products": ["read", "create", "update", "delete"],
  "inventory": ["read", "create"],
  "sales": ["read", "create"]
}
```

**Valid resources:** `products`, `inventory`, `sales`, `customers`, `users`, `roles`, `reports`
**Valid actions:** `read`, `create`, `update`, `delete`

### System Roles

| Role | Products | Inventory | Sales | Customers | Users | Roles | Reports |
|---|---|---|---|---|---|---|---|
| **admin** | CRUD | CRUD | CRUD | CRUD | CRUD | CRUD | read, create |
| **gerente** | read, create, update | read, create, update | read, create, update | read, create, update | read | -- | read, create |
| **vendedor** | read | read | read, create | read, create | -- | -- | -- |
| **almacen** | read | read, update | -- | -- | -- | -- | -- |

## API Endpoints

### Authentication
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/login` | No | User login, returns JWT |
| POST | `/api/auth/logout` | No | Logout (client-side only) |
| GET | `/api/auth/me` | Yes | Get current user info |

### Users
| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/api/users/` | `users.read` | List users (search, filter by role/active) |
| GET | `/api/users/{id}` | `users.read` | Get user by ID |
| POST | `/api/users/` | `users.create` | Create user |
| PUT | `/api/users/{id}` | `users.update` | Update user |
| PATCH | `/api/users/{id}/toggle-active` | `users.update` | Enable/disable user |
| POST | `/api/users/{id}/reset-password` | `users.update` | Reset user password |

### Roles
| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/api/roles/` | `roles.read` | List all roles |
| GET | `/api/roles/{id}` | `roles.read` | Get role by ID |
| POST | `/api/roles/` | `roles.create` | Create role |
| PUT | `/api/roles/{id}` | `roles.update` | Update role |
| DELETE | `/api/roles/{id}` | `roles.delete` | Delete role (non-system, no assigned users) |

### Products
| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/api/products/` | `products.read` | List active products |
| GET | `/api/products/{id}` | `products.read` | Get product by ID |
| GET | `/api/products/barcode/{barcode}` | `products.read` | Get product by barcode |
| POST | `/api/products/` | `products.create` | Create product |
| PUT | `/api/products/{id}` | `products.update` | Update product |
| DELETE | `/api/products/{id}` | `products.delete` | Soft-delete (sets `is_active=false`) |

### Inventory
| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/api/inventory/` | `inventory.read` | List inventory items |
| GET | `/api/inventory/warehouse/{warehouse_id}` | `inventory.read` | List by warehouse |
| POST | `/api/inventory/` | `inventory.create` | Add inventory item |
| PUT | `/api/inventory/{id}` | `inventory.update` | Update inventory item |
| POST | `/api/inventory/transfer` | `inventory.update` | Transfer stock between warehouses |

### Sales
| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/api/sales/` | `sales.read` | List all sales (newest first) |
| GET | `/api/sales/{id}` | `sales.read` | Get sale details |
| POST | `/api/sales/` | `sales.create` | Create sale (auto 16% tax, decrements inventory) |

### Customers
| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/api/customers/` | `customers.read` | List all customers |
| GET | `/api/customers/{id}` | `customers.read` | Get customer by ID |
| POST | `/api/customers/` | `customers.create` | Create customer (auto-creates loyalty record) |
| PUT | `/api/customers/{id}` | `customers.update` | Update customer |
| DELETE | `/api/customers/{id}` | `customers.delete` | Hard-delete customer |

## Database Schema

15 tables defined in `db/init.sql`:

| Table | Description | Key Relationships |
|---|---|---|
| `roles` | User roles with JSONB permissions | -- |
| `users` | System users | `role_id → roles` |
| `warehouses` | Storage locations | -- |
| `categories` | Product categories (hierarchical) | `parent_id → categories` |
| `suppliers` | Product suppliers | -- |
| `products` | Bicycle parts/accessories | `category_id → categories`, `supplier_id → suppliers` |
| `inventory_items` | Stock per product per warehouse | `product_id → products`, `warehouse_id → warehouses` |
| `customers` | Store customers | `loyalty_id → loyalty` |
| `loyalty` | Customer loyalty points/tiers | `customer_id → customers` |
| `sales` | Sales transactions | `customer_id → customers`, `user_id → users` |
| `sale_items` | Line items in a sale | `sale_id → sales`, `product_id → products` |
| `orders` | Purchase orders to suppliers | `supplier_id → suppliers`, `warehouse_id → warehouses` |
| `order_items` | Line items in a purchase order | `order_id → orders`, `product_id → products` |
| `payments` | Payment records | `sale_id → sales` |
| `audit_trail` | Change tracking log | `user_id → users` |

> **Note:** `orders`, `order_items`, `payments`, and `audit_trail` tables exist in the schema but don't have API endpoints yet.

## Testing

### Postman Collection

Import the included Postman collection for API testing:

1. Open Postman → **Import**
2. Select `testing/ParaisoBiker_API.postman_collection.json`
3. Import the environment: `testing/ParaisoBiker_ENV.postman_environment.json`
4. Select the **Paraiso Biker - Local** environment in Postman
5. Run **Auth → Login** first — the token is auto-saved for subsequent requests

### Automated Tests

```bash
pytest
```

> Tests directory (`tests/`) exists but no tests are written yet.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PROJECT_NAME` | `Paraiso Biker API` | Project name |
| `VERSION` | `1.0.0` | API version |
| `DEBUG` | `True` | Debug mode |
| `DATABASE_URL` | `postgresql://postgres:paraiso2026secure@localhost:5432/paraiso_biker` | PostgreSQL connection string |
| `SECRET_KEY` | *(hardcoded default)* | JWT signing key |
| `ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Token expiry (24 hours) |
| `BACKEND_CORS_ORIGINS` | `localhost:3000, :3001, :5173, :8080` | Allowed CORS origins |

## Development

```bash
# Run with auto-reload
uvicorn app.main:app --reload

# Connect to database
docker exec -it paraiso_biker_db psql -U postgres -d paraiso_biker
```

## Project Structure

```
backend/
├── app/
│   ├── api/              # API route handlers (7 routers)
│   ├── core/             # Security, auth dependencies
│   ├── models/           # SQLAlchemy ORM models (10 classes)
│   ├── schemas/          # Pydantic request/response schemas
│   ├── services/         # Business logic layer
│   ├── main.py           # FastAPI app entry point
│   ├── config.py         # Settings (pydantic-settings)
│   └── database.py       # SQLAlchemy engine & session
├── db/
│   └── init.sql          # Database schema + seed data
├── scripts/
│   ├── seed_data.py      # Generate fake seed data (Faker)
│   └── import_seed_data.py  # Import seed data into DB
├── testing/              # Postman collections
│   ├── ParaisoBiker_API.postman_collection.json
│   └── ParaisoBiker_ENV.postman_environment.json
├── tests/                # Automated tests (empty)
├── docker-compose.yml    # PostgreSQL service
├── requirements.txt      # Python dependencies
├── start.sh              # One-command startup script
└── .env                  # Environment variables (not tracked by git)
```

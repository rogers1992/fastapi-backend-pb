"""
Comprehensive seed data with CHRONOLOGICAL date ordering.

All purchases (received orders) are dated BEFORE all sales.
This ensures the profit report's historical COGS subquery always finds a cost.

Creates:
- 9 categories, 6 suppliers, 3 warehouses
- 334 products (realistic motorcycle/bike parts)
- 50 customers
- 50 purchase orders (40 received + 10 pending) with ~250 order items
  - Received orders: day -120 to day -15 (all BEFORE any sale)
  - Pending orders: today
- ~1000 inventory items across 3 warehouses
- 100 completed sales with ~350 sale items
  - All sales: day -14 to day -1 (all AFTER latest purchase)
- 3 test users (vendedor_test, almacen_test, gerente_test)

Idempotent: wipes existing seed data first, then recreates.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
from datetime import date, timedelta, datetime
from decimal import Decimal

from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from app.database import engine
from app.models.product import Product, Category, Supplier
from app.models.inventory import InventoryItem, Warehouse
from app.models.order import Order, OrderItem
from app.models.sale import Sale, SaleItem
from app.models.customer import Customer, Loyalty
from app.models.user import User, Role
from app.core.security import get_password_hash

random.seed(42)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

# --------------------------------------------------------------------------- #
# Data pools
# --------------------------------------------------------------------------- #
FIRST_NAMES = [
    "Carlos", "Maria", "Juan", "Ana", "Pedro", "Laura", "Diego", "Sofia",
    "Miguel", "Carmen", "Jose", "Rosa", "Luis", "Elena", "Fernando", "Patricia",
    "Ricardo", "Gabriela", "Andres", "Valentina", "Roberto", "Isabella",
    "Manuel", "Camila", "Jorge", "Daniela", "Rafael", "Lucia", "Francisco", "Andrea",
]
LAST_NAMES = [
    "Garcia", "Rodriguez", "Martinez", "Lopez", "Gonzalez", "Hernandez",
    "Perez", "Sanchez", "Ramirez", "Torres", "Flores", "Rivera", "Gomez",
    "Diaz", "Cruz", "Morales", "Reyes", "Gutierrez", "Ortiz", "Ramos",
    "Vargas", "Castillo", "Mendoza", "Jimenez", "Ruiz", "Alvarez", "Romero",
    "Medina", "Herrera", "Aguilar", "Vega", "Castro", "Delgado", "Navarro",
]
STREETS = [
    "Av. Principal", "Calle Central", "Blvd. Industrial", "Av. Libertad",
    "Calle Comercio", "Av. Bolivar", "Calle Junin", "Av. Heroines",
    "Calle Santa Cruz", "Av. America", "Calle Cochabamba", "Av. Banzer",
]
CITIES = ["Santa Cruz", "La Paz", "Cochabamba", "Oruro", "Sucre", "Tarija", "Potosi", "Beni", "Pando"]

CATEGORY_NAMES = {
    1: "Cadenas y Transmision",
    2: "Frenos",
    3: "Neumaticos y Camaras",
    4: "Cambios y Desviadores",
    5: "Accesorios",
    6: "Herramientas",
    7: "Motores y Componentes",
    8: "Suspension",
    9: "Sistema Electrico",
}

PRODUCT_TEMPLATES = {
    1: [
        ("Cadena Shimano HG{v} {speed}v", [53, 71, 81], ["7", "8", "9", "10", "11"]),
        ("Cadena SRAM PC{v}", [451, 951, 1031, 1130], []),
        ("Cadena KMC X{v}", [9, 10, 11, 12], []),
        ("Cassette Shimano {speed}v {range}", ["7", "8", "9", "10", "11"], ["11-28T", "11-32T", "11-34T", "12-25T"]),
        ("Plato Shimano FC-{v}", ["M311", "M410", "M610", "M710"], []),
        ("Pinon Libre {v}v", ["7", "8", "9", "10"], []),
        ("Eje de Cadena Reforzado {v}mm", ["1/2", "5/8"], []),
        ("Tensor de Cadena Ajustable", [], []),
    ],
    2: [
        ("Pastillas Tektro E{v}", ["10.11", "10.12", "10.15", "10.16"], []),
        ("Pastillas Shimano {v}", ["B01S", "B03S", "G04S", "L03A"], []),
        ("Disco Freno {size}mm {type}", ["140", "160", "180", "203"], ["Centerlock", "6-Bolt"]),
        ("Cable Freno Acero Inox {v}mm", ["1.5", "1.6", "1.8"], []),
        ("Pinzas Freno V-Brake {v}", ["T410", "T420", "M510"], []),
        ("Manguera Freno Hidraulico {v}mm", ["800", "1000", "1200", "1500"], []),
        ("Bomba Freno Shimano {v}", ["MT200", "MT400", "MT500"], []),
        ("Liquido Freno DOT {v}", ["4", "5.1"], []),
    ],
    3: [
        ("Neumatico MTB {size}x{width}", ["26", "27.5", "29"], ["1.95", "2.10", "2.25", "2.35"]),
        ("Neumatico Ruta 700x{width}c", ["23", "25", "28", "32"], []),
        ("Camara {size} {valve}", ["26", "27.5", "29", "700c"], ["Presta", "Schrader"]),
        ("Neumatico Urbano {size}x{width}", ["26", "27.5"], ["1.50", "1.75", "1.95"]),
        ("Cinta Rin {v}mm", ["17", "19", "21", "23"], []),
        ("Valvula Extension Presta {v}mm", ["40", "60", "80"], []),
    ],
    4: [
        ("Cambio Trasero Shimano {v}", ["Tourney", "Altus", "Alivio", "Deore", "SLX"], []),
        ("Cambio Delantero Shimano {v}", ["Tourney", "Altus", "Alivio", "Deore"], []),
        ("Palanca Cambio {v}", ["SL-M310", "SL-M410", "SL-M610", "SL-M710"], []),
        ("Desviador SRAM X{v}", ["3", "4", "5", "7"], []),
        ("Cable Cambio Acero {v}mm", ["1.1", "1.2"], []),
        ("Funda Cable Cambio {v}mm", ["1500", "1700", "2000", "2200"], []),
        ("Tija de Cambio {v}", ["Standard", "Clamp-on"], []),
    ],
    5: [
        ("Casco MTB {v}", ["Trail", "Enduro", "XC", "Downhill"], []),
        ("Luces LED {v}", ["Delantera 300lm", "Trasera 50lm", "Set Completo"], []),
        ("Portabidon {v}", ["Aluminio", "Carbono", "Plastico Reforzado"], []),
        ("Multiherramienta {v} funciones", ["11", "16", "19", "21"], []),
        ("Bomba Aire {v}", ["Mini Pie", "Mesa con Manometro", "CO2"], []),
        ("Guantes MTB {v}", ["Dedos Largos", "Dedos Cortos", "Gel"], []),
        ("Rodilleras {v}", ["Basicas", "Pro con Bisagra"], []),
        ("Mochila Hidratacion {v}L", ["2", "3", "5", "8"], []),
    ],
    6: [
        ("Llave Hexagonal {v}mm", ["2", "2.5", "3", "4", "5", "6", "8", "10"], []),
        ("Extractores Biela Shimano", [], []),
        ("Herramienta Cadena {v}", ["Simple", "Doble", "Triple"], []),
        ("Juego Llaves Allen {v}", ["9 piezas", "10 piezas", "12 piezas"], []),
        ("Torquimetro Profesional {v}Nm", ["2-24", "5-25"], []),
        ("Desmontables Neumatico {v}", ["Plastico", "Acero"], []),
        ("Llave de Radio {v}", ["10-15", "12-16"], []),
        ("Medidor de Cadena", [], []),
    ],
    7: [
        ("Piston Motor 2T {v}mm", ["47", "50", "52", "54", "56"], []),
        ("Anillos Piston {v}mm", ["47", "50", "52", "54"], []),
        ("Bielas Motor {v}cc", ["50", "110", "125", "150", "200"], []),
        ("Cilindro Motor 2T {v}cc", ["50", "110", "125", "150"], []),
        ("Empaquetadura Motor Completa {v}cc", ["110", "125", "150", "200"], []),
        ("Volano Magnetico {v}cc", ["110", "125", "150"], []),
        ("Cadena Distribucion {v}mm", ["420", "428", "520"], []),
        ("Filtro Aceite {v}", ["Universal", "Honda", "Yamaha", "Suzuki"], []),
    ],
    8: [
        ("Amortiguador Trasero {v}mm", ["300", "320", "340"], []),
        ("Horquilla Delantera {v}", ["Telescopica", "Invertida"], []),
        ("Retenedor Horquilla {v}mm", ["31", "33", "35", "37"], []),
        ("Buje Suspension {v}", ["Delantero", "Trasero"], []),
        ("Resorte Amortiguador {v}lb", ["400", "450", "500", "550"], []),
        ("Kit Reconstruccion Horquilla", [], []),
        ("Aceite Horquilla {v}W", ["5", "10", "15", "20"], []),
    ],
    9: [
        ("CDI Universal {v}cc", ["50", "110", "125", "150", "200"], []),
        ("Bobina Encendido {v}cc", ["110", "125", "150"], []),
        ("Estator/Magneto {v}cc", ["50", "110", "125", "150"], []),
        ("Regulador Rectificador {v}", ["4 Pines", "5 Pines", "6 Pines"], []),
        ("Bateria 12V {v}Ah", ["4", "5", "7", "9"], []),
        ("Faro Delantero LED {v}W", ["10", "20", "30", "50"], []),
        ("Direccionales LED {v}", ["Par Delantero", "Par Trasero", "Set Completo"], []),
        ("Switch Encendido {v}", ["Honda", "Yamaha", "Suzuki", "Universal"], []),
        ("Arnes Electrico {v}cc", ["110", "125", "150"], []),
    ],
}

COLORS = ["Negro", "Rojo", "Azul", "Plateado", "Verde", "Amarillo", "Blanco", "Gris"]
PRICE_RANGES = {
    1: (45, 350),
    2: (25, 450),
    3: (35, 550),
    4: (30, 600),
    5: (40, 950),
    6: (25, 380),
    7: (80, 2500),
    8: (120, 1800),
    9: (35, 650),
}


def generate_product_name(cat_id, idx):
    templates = PRODUCT_TEMPLATES.get(cat_id, [])
    if not templates:
        return f"Producto Categoria {cat_id} #{idx}"
    tmpl = templates[idx % len(templates)]
    name = tmpl[0]
    variants1 = tmpl[1] if tmpl[1] else [""]
    variants2 = tmpl[2] if tmpl[2] else [""]
    v1 = variants1[idx % len(variants1)]
    v2 = variants2[idx % len(variants2)] if variants2 else ""
    name = name.replace("{type}", v2) if "{type}" in name else name
    name = name.format(v=v1, speed=v1, size=v1, range=v1, width=v1, valve=v1)
    color = COLORS[idx % len(COLORS)]
    return f"{name} {color}"


# --------------------------------------------------------------------------- #
# Phase 0: Wipe existing seed data
# --------------------------------------------------------------------------- #
print("=" * 60)
print("Phase 0: Wiping existing seed data...")
print("=" * 60)

with engine.connect() as conn:
    trans = conn.begin()
    try:
        # Delete in FK-safe order
        conn.execute(text("DELETE FROM sale_items WHERE sale_id IN (SELECT id FROM sales WHERE notes LIKE 'Seed Sale%')"))
        conn.execute(text("DELETE FROM sales WHERE notes LIKE 'Seed Sale%'"))
        conn.execute(text("DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE notes LIKE 'Seed PO%')"))
        conn.execute(text("DELETE FROM orders WHERE notes LIKE 'Seed PO%'"))
        conn.execute(text("DELETE FROM inventory_items WHERE product_id IN (SELECT id FROM products WHERE sku LIKE 'PB-%')"))
        conn.execute(text("DELETE FROM products WHERE sku LIKE 'PB-%'"))
        conn.execute(text("DELETE FROM loyalty WHERE customer_id IN (SELECT id FROM customers WHERE email LIKE '%@test.com')"))
        conn.execute(text("DELETE FROM customers WHERE email LIKE '%@test.com'"))
        conn.execute(text("DELETE FROM users WHERE username IN ('vendedor_test', 'almacen_test', 'gerente_test')"))
        trans.commit()
        print("Existing seed data wiped.")
    except Exception as e:
        trans.rollback()
        print(f"Wipe error: {e}")
        raise

# --------------------------------------------------------------------------- #
# Phase 1: Categories, Suppliers, Warehouses
# --------------------------------------------------------------------------- #
print("\nPhase 1: Categories, Suppliers, Warehouses")
for cid in range(1, 10):
    if not db.query(Category).filter(Category.id == cid).first():
        db.add(Category(id=cid, name=CATEGORY_NAMES[cid], description=f"Categoria {cid}"))
db.commit()
print(f"  Categories: {len(CATEGORY_NAMES)} ready")

supplier_names = [
    "Shimano Mexico", "SRAM Distribucion", "Tektro Frenos MX",
    "KMC Cadenas", "Accesorios Bici MX", "Herramientas Pro",
]
for sid, name in enumerate(supplier_names, 1):
    if not db.query(Supplier).filter(Supplier.id == sid).first():
        db.add(Supplier(
            id=sid, name=name, contact_name=f"Contacto {name}",
            email=f"ventas@{name.lower().replace(' ', '')}.mx",
            phone=f"+52 55 {random.randint(1000,9999)} {random.randint(1000,9999)}",
            is_active=True,
        ))
db.commit()
print(f"  Suppliers: {len(supplier_names)} ready")

wh_data = [
    {"id": 1, "name": "Almacen Principal", "location": "Tienda Central"},
    {"id": 2, "name": "Almacen Secundario", "location": "Bodega Norte"},
    {"id": 3, "name": "Bodega Sur", "location": "Zona Industrial Sur"},
]
for wh in wh_data:
    if not db.query(Warehouse).filter(Warehouse.id == wh["id"]).first():
        db.add(Warehouse(**wh, is_active=True))
db.commit()
print(f"  Warehouses: {len(wh_data)} ready")

# --------------------------------------------------------------------------- #
# Phase 2: Products (334)
# --------------------------------------------------------------------------- #
print("\nPhase 2: Generating 334 products...")
product_ids = []
sku_counter = 0
for cat_id in range(1, 10):
    items_for_cat = max(30, 334 // 9)
    for i in range(items_for_cat):
        sku_counter += 1
        sku = f"PB-{cat_id:02d}-{sku_counter:04d}"
        existing = db.query(Product).filter(Product.sku == sku).first()
        if existing:
            product_ids.append(existing.id)
            continue
        name = generate_product_name(cat_id, i)
        price_min, price_max = PRICE_RANGES[cat_id]
        price = Decimal(str(round(random.uniform(price_min, price_max), 2)))
        barcode = f"7501{sku_counter:09d}"
        prod = Product(
            sku=sku, name=name, category_id=cat_id,
            supplier_id=random.randint(1, len(supplier_names)),
            unit_price=price, barcode=barcode,
            description=f"Producto de prueba: {name}",
            weight=round(random.uniform(0.05, 5.0), 2),
            is_active=True,
        )
        db.add(prod)
        db.flush()
        product_ids.append(prod.id)
    db.commit()
    print(f"  Category {cat_id}: {items_for_cat} products ({sku_counter} total)")
print(f"Total products: {len(product_ids)}")

# --------------------------------------------------------------------------- #
# Phase 3: Customers (50)
# --------------------------------------------------------------------------- #
print("\nPhase 3: Generating 50 customers...")
customer_ids = []
for i in range(50):
    first = FIRST_NAMES[i % len(FIRST_NAMES)]
    last = LAST_NAMES[i % len(LAST_NAMES)]
    email = f"{first.lower()}.{last.lower()}{i}@test.com"
    existing = db.query(Customer).filter(Customer.email == email).first()
    if existing:
        customer_ids.append(existing.id)
        continue
    cust = Customer(
        first_name=first, last_name=last, email=email,
        phone=f"+591 {random.randint(70000000, 79999999)}",
        address=f"{random.choice(STREETS)} #{random.randint(100,999)}, {random.choice(CITIES)}",
        date_of_birth=date(1970 + random.randint(0, 40), random.randint(1, 12), random.randint(1, 28)),
        is_active=1,
    )
    db.add(cust)
    db.flush()
    db.add(Loyalty(customer_id=cust.id, points=random.randint(0, 500), tier=random.choice(["bronze", "bronze", "bronze", "silver", "silver", "gold"])))
    customer_ids.append(cust.id)
db.commit()
print(f"Customers: {len(customer_ids)} created")

# --------------------------------------------------------------------------- #
# Phase 4: Purchase Orders (50: 40 received + 10 pending)
# CHRONOLOGICAL: received orders dated day -120 to day -15
# --------------------------------------------------------------------------- #
print("\nPhase 4: Generating 50 purchase orders...")
admin_user = db.query(User).filter(User.username == "admin").first()
creator_id = admin_user.id if admin_user else 1

products = db.query(Product.id, Product.unit_price).all()
product_price_map = {p[0]: float(p[1]) for p in products}

order_count = 0
for i in range(40):
    days_ago = random.randint(15, 120)  # 15-120 days ago (all BEFORE sales)
    order_date = date.today() - timedelta(days=days_ago + random.randint(5, 15))
    received_date = date.today() - timedelta(days=days_ago)
    notes = f"Seed PO Received #{i+1} (days_ago={days_ago})"
    existing = db.query(Order).filter(Order.notes == notes).first()
    if existing:
        order_count += 1
        continue
    order = Order(
        supplier_id=random.randint(1, len(supplier_names)),
        warehouse_id=random.randint(1, 3),
        status="received",
        total_amount=Decimal("0"),
        order_date=order_date,
        received_date=received_date,
        created_by=creator_id,
        notes=notes,
    )
    db.add(order)
    db.flush()

    num_items = random.randint(3, 8)
    chosen_products = random.sample(product_ids, min(num_items, len(product_ids)))
    total = Decimal("0")
    for pid in chosen_products:
        base_price = product_price_map.get(pid, 100)
        age_factor = 1.0 + (days_ago / 200)
        unit_cost = Decimal(str(round(base_price * random.uniform(0.30, 0.60) * age_factor, 2)))
        qty = random.randint(5, 50)
        total_price = unit_cost * qty
        total += total_price
        db.add(OrderItem(
            order_id=order.id, product_id=pid,
            quantity=qty, unit_cost=unit_cost,
            total_price=total_price, received_quantity=qty,
        ))
    order.total_amount = total
    order_count += 1
db.commit()
print(f"  Received orders: {order_count} (dated day -120 to -15)")

pending_count = 0
for i in range(10):
    notes = f"Seed PO Pending #{i+1}"
    existing = db.query(Order).filter(Order.notes == notes).first()
    if existing:
        pending_count += 1
        continue
    order = Order(
        supplier_id=random.randint(1, len(supplier_names)),
        warehouse_id=random.randint(1, 3),
        status="pending",
        total_amount=Decimal("0"),
        order_date=date.today(),
        expected_date=date.today() + timedelta(days=random.randint(7, 30)),
        created_by=creator_id,
        notes=notes,
    )
    db.add(order)
    db.flush()

    num_items = random.randint(2, 6)
    chosen_products = random.sample(product_ids, min(num_items, len(product_ids)))
    total = Decimal("0")
    for pid in chosen_products:
        base_price = product_price_map.get(pid, 100)
        unit_cost = Decimal(str(round(base_price * random.uniform(0.30, 0.60), 2)))
        qty = random.randint(10, 30)
        total_price = unit_cost * qty
        total += total_price
        db.add(OrderItem(
            order_id=order.id, product_id=pid,
            quantity=qty, unit_cost=unit_cost,
            total_price=total_price, received_quantity=0,
        ))
    order.total_amount = total
    pending_count += 1
db.commit()
print(f"  Pending orders: {pending_count}")
print(f"Total purchase orders: {order_count + pending_count}")

# --------------------------------------------------------------------------- #
# Phase 5: Inventory Items (~1000 across 3 warehouses)
# --------------------------------------------------------------------------- #
print("\nPhase 5: Generating ~1000 inventory items...")
inv_count = 0
products_for_all3 = product_ids[:332]
products_for_2wh = product_ids[332:]

for pid in products_for_all3:
    for wh_id in [1, 2, 3]:
        existing = db.query(InventoryItem).filter(
            InventoryItem.product_id == pid,
            InventoryItem.warehouse_id == wh_id,
        ).first()
        if existing:
            continue
        qty = random.randint(0, 200)
        min_stock = random.randint(5, 20)
        db.add(InventoryItem(
            product_id=pid, warehouse_id=wh_id,
            quantity=qty, reserved_quantity=random.randint(0, max(0, qty // 5)),
            min_stock_level=min_stock, max_stock_level=min_stock * random.randint(3, 8),
            location=f"{random.choice('ABCDE')}-{random.randint(1,20):02d}-{random.randint(1,50):02d}",
        ))
        inv_count += 1

for pid in products_for_2wh:
    for wh_id in random.sample([1, 2, 3], 2):
        existing = db.query(InventoryItem).filter(
            InventoryItem.product_id == pid,
            InventoryItem.warehouse_id == wh_id,
        ).first()
        if existing:
            continue
        qty = random.randint(0, 200)
        min_stock = random.randint(5, 20)
        db.add(InventoryItem(
            product_id=pid, warehouse_id=wh_id,
            quantity=qty, reserved_quantity=random.randint(0, max(0, qty // 5)),
            min_stock_level=min_stock, max_stock_level=min_stock * random.randint(3, 8),
            location=f"{random.choice('ABCDE')}-{random.randint(1,20):02d}-{random.randint(1,50):02d}",
        ))
        inv_count += 1

db.commit()
print(f"Inventory items: {inv_count} created")

# --------------------------------------------------------------------------- #
# Phase 6: Sales (100 completed)
# CHRONOLOGICAL: all sales dated day -14 to day -1 (AFTER all purchases)
# Only sell products that have at least 1 received purchase order
# --------------------------------------------------------------------------- #
print("\nPhase 6: Generating 100 sales (day -14 to -1, only products with cost)...")

# Get products from our seed (PB-*) that have at least 1 received order
products_with_cost_result = db.query(OrderItem.product_id).join(Order).join(Product).filter(
    Order.status == "received",
    Product.sku.like("PB-%"),
).distinct().all()
sellable_product_ids = [r[0] for r in products_with_cost_result]
print(f"  Products with purchase history: {len(sellable_product_ids)}")

vendedor_role = db.query(Role).filter(Role.name == "vendedor").first()
admin_role = db.query(Role).filter(Role.name == "admin").first()
seller_ids = []
if admin_user:
    seller_ids.append(admin_user.id)
if vendedor_role:
    vendedores = db.query(User).filter(User.role_id == vendedor_role.id, User.is_active == True).all()
    seller_ids.extend([u.id for u in vendedores])
gerente_role = db.query(Role).filter(Role.name == "gerente").first()
if gerente_role:
    gerentes = db.query(User).filter(User.role_id == gerente_role.id, User.is_active == True).all()
    seller_ids.extend([u.id for u in gerentes])
if not seller_ids:
    seller_ids = [creator_id]

payment_methods = ["efectivo"] * 60 + ["transferencia"] * 25 + ["tarjeta"] * 15
sale_count = 0

for i in range(100):
    days_ago = random.randint(1, 14)  # 1-14 days ago (AFTER all purchases)
    sale_date = datetime.combine(date.today() - timedelta(days=days_ago), datetime.min.time()) + timedelta(hours=random.randint(8, 20), minutes=random.randint(0, 59))
    notes = f"Seed Sale #{i+1}"
    existing = db.query(Sale).filter(Sale.notes == notes).first()
    if existing:
        sale_count += 1
        continue

    seller_id = random.choice(seller_ids)
    customer_id = random.choice(customer_ids)
    payment = random.choice(payment_methods)

    sale = Sale(
        customer_id=customer_id, user_id=seller_id,
        payment_method=payment, status="completed",
        total_amount=Decimal("0"), tax_amount=Decimal("0"),
        sale_date=sale_date, notes=notes,
    )
    db.add(sale)
    db.flush()

    num_items = random.randint(2, 5)
    chosen_products = random.sample(sellable_product_ids, min(num_items, len(sellable_product_ids)))
    total = Decimal("0")
    for pid in chosen_products:
        base_price = product_price_map.get(pid, 100)
        unit_price = Decimal(str(round(base_price, 2)))
        qty = random.randint(1, 5)
        discount_pct = random.choice([0, 0, 0, 0, 0, 5, 10, 15])
        discount = Decimal(str(round(float(unit_price) * qty * discount_pct / 100, 2)))
        total_price = unit_price * qty - discount
        total += total_price
        db.add(SaleItem(
            sale_id=sale.id, product_id=pid,
            quantity=qty, unit_price=unit_price,
            discount=discount, total_price=total_price,
        ))

    tax = total * Decimal("0.16")
    sale.total_amount = total
    sale.tax_amount = tax
    sale_count += 1
db.commit()
print(f"Sales: {sale_count} created (all dated AFTER purchases)")

# --------------------------------------------------------------------------- #
# Phase 7: Test Users
# --------------------------------------------------------------------------- #
print("\nPhase 7: Creating test users...")
vendedor_role = db.query(Role).filter(Role.name == "vendedor").first()
almacen_role = db.query(Role).filter(Role.name == "almacen").first()
gerente_role = db.query(Role).filter(Role.name == "gerente").first()

test_users = [
    {"username": "vendedor_test", "email": "vendedor@test.com", "first_name": "Juan", "last_name": "Vendedor", "phone": "+591 7777 0001", "role": vendedor_role, "password": "test123"},
    {"username": "almacen_test", "email": "almacen@test.com", "first_name": "Pedro", "last_name": "Almacen", "phone": "+591 7777 0002", "role": almacen_role, "password": "test123"},
    {"username": "gerente_test", "email": "gerente@test.com", "first_name": "Ana", "last_name": "Gerente", "phone": "+591 7777 0003", "role": gerente_role, "password": "test123"},
]

for u in test_users:
    if db.query(User).filter(User.username == u["username"]).first():
        print(f"  User '{u['username']}' exists, skipped")
    else:
        db.add(User(
            role_id=u["role"].id if u["role"] else None,
            username=u["username"],
            email=u["email"],
            password_hash=get_password_hash(u["password"]),
            first_name=u["first_name"],
            last_name=u["last_name"],
            phone=u["phone"],
            is_active=True,
        ))
        print(f"  + User '{u['username']}' created (role={u['role'].name if u['role'] else 'none'}, password={u['password']})")
db.commit()
print("Test users ready")

# --------------------------------------------------------------------------- #
# Summary
# --------------------------------------------------------------------------- #
total_products = db.query(Product).count()
total_customers = db.query(Customer).count()
total_orders = db.query(Order).count()
total_order_items = db.query(OrderItem).count()
total_inventory = db.query(InventoryItem).count()
total_sales = db.query(Sale).count()
total_sale_items = db.query(SaleItem).count()
total_users = db.query(User).count()

# Verify chronological integrity
bad_sales = db.query(SaleItem).join(Sale).join(OrderItem, SaleItem.product_id == OrderItem.product_id).join(Order).filter(
    Sale.status == "completed",
    Order.status == "received",
    Sale.sale_date < Order.received_date,
).distinct().count()

print("\n" + "=" * 60)
print("SEED COMPLETE - Data Summary")
print("=" * 60)
print(f"Categories:       {db.query(Category).count()}")
print(f"Suppliers:        {db.query(Supplier).count()}")
print(f"Warehouses:       {db.query(Warehouse).count()}")
print(f"Products:         {total_products}")
print(f"Customers:        {total_customers}")
print(f"Purchase Orders:  {total_orders} ({db.query(Order).filter(Order.status=='received').count()} received, {db.query(Order).filter(Order.status=='pending').count()} pending)")
print(f"Order Items:      {total_order_items}")
print(f"Inventory Items:  {total_inventory}")
print(f"Sales:            {total_sales}")
print(f"Sale Items:       {total_sale_items}")
print(f"Users:            {total_users}")
print()
print(f"Chronological check: {bad_sales} sales dated before their product's purchase")
print()
print("Test Users (password: test123):")
print("  - vendedor_test  (role: vendedor)")
print("  - almacen_test   (role: almacen)")
print("  - gerente_test   (role: gerente)")
print("  - admin          (password: admin123, role: admin)")
print()
print("Date ranges:")
print("  Purchases received: day -120 to day -15")
print("  Sales:              day -14 to day -1")
print("  Pending orders:     today")
print()
print("Cost visibility:")
print("  admin/gerente   -> current_cost shown")
print("  vendedor/almacen -> current_cost = null")
print("=" * 60)

db.close()

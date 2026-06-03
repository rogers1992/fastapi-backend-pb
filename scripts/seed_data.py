"""
Generate 100 sample products and 100 sample customers for Paraiso Biker
"""
import random
from faker import Faker
from datetime import datetime, date
import json

fake = Faker('es_MX')

# Product data generators
PRODUCT_NAMES = {
    1: ['Cadena Shimano HG71 9v', 'Cadena SRAM PC951', 'Cadena KMC X9', 'Cadena Shimano CN-HG53', 'Cadena Campagnolo 11v'],
    2: ['Pastillas Tektro E10.11', 'Pastillas Shimano B01S', 'Disco freno 160mm', 'Cable freno acero', 'Pinzas freno V-brake'],
    3: ['Neumático MTB 26x2.1', 'Neumático 700x25c', 'Cámara 26"', 'Cámara 700c', 'Neumático 27.5x2.25'],
    4: ['Cambio trasero Shimano', 'Cambio delantero', 'Desviador SRAM', 'Palanca cambios', 'Cassette 9v'],
    5: ['Casco protector', 'Luces LED', 'Portabidón', 'Multiherramienta', 'Bomba aire'],
    6: ['Llave hexagonal', 'Extractores biela', 'Herramienta cadena', 'Bombilla aire', 'Juego herramientas']
}

COLORS = ['Negro', 'Rojo', 'Azul', 'Plateado', 'Verde', 'Amarillo']

def generate_products(n=100):
    """Generate n random products"""
    products = []
    for i in range(n):
        category_id = random.randint(1, 6)
        name = random.choice(PRODUCT_NAMES[category_id])
        color = random.choice(COLORS)
        
        product = {
            'sku': f'SKU-{str(i+1).zfill(4)}',
            'barcode': f'750{random.randint(1000000000, 9999999999)}',
            'name': f'{name} {color}',
            'category_id': category_id,
            'supplier_id': random.randint(1, 6),
            'unit_price': round(random.uniform(15.0, 250.0), 2),
            'weight': round(random.uniform(0.1, 2.5), 2),
            'description': f'{name} de alta calidad para bicicleta. Color {color}.',
        }
        products.append(product)
    return products

def generate_customers(n=100):
    """Generate n random customers"""
    customers = []
    for i in range(n):
        customer = {
            'first_name': fake.first_name(),
            'last_name': fake.last_name(),
            'email': fake.email(),
            'phone': fake.phone_number(),
            'address': fake.address().replace('\n', ', '),
            'date_of_birth': fake.date_of_birth(minimum_age=18, maximum_age=70).strftime('%Y-%m-%d'),
        }
        customers.append(customer)
    return customers

def generate_inventory(n=100):
    """Generate inventory items for products"""
    inventory = []
    for i in range(n):
        item = {
            'product_id': i + 1,
            'warehouse_id': random.randint(1, 2),
            'quantity': random.randint(5, 100),
            'min_stock_level': random.randint(5, 20),
            'max_stock_level': random.randint(50, 200),
            'location': f'{random.choice(["A", "B", "C"])}-{random.randint(1, 20):02d}-{random.randint(1, 50):02d}'
        }
        inventory.append(item)
    return inventory

if __name__ == '__main__':
    print("Generating seed data...")
    
    products = generate_products(100)
    customers = generate_customers(100)
    inventory = generate_inventory(100)
    
    print(f"✓ Generated {len(products)} products")
    print(f"✓ Generated {len(customers)} customers")
    print(f"✓ Generated {len(inventory)} inventory items")
    
    # Save to JSON files
    with open('products_seed.json', 'w', encoding='utf-8') as f:
        json.dump(products, f, indent=2, ensure_ascii=False)
    
    with open('customers_seed.json', 'w', encoding='utf-8') as f:
        json.dump(customers, f, indent=2, ensure_ascii=False)
    
    with open('inventory_seed.json', 'w', encoding='utf-8') as f:
        json.dump(inventory, f, indent=2, ensure_ascii=False)
    
    print("\n✓ Seed data saved to JSON files")
    print("\nTo import into database, run:")
    print("  python import_seed_data.py")

"""
Generate seed data for categories and suppliers for Paraiso Biker
"""
import json


def generate_categories():
    """Generate 6 categories matching seed_data.py category_ids"""
    categories = [
        {
            'id': 1,
            'name': 'Cadenas y Transmisión',
            'description': 'Cadenas, cassettes, platos y componentes de transmisión para bicicletas',
        },
        {
            'id': 2,
            'name': 'Frenos',
            'description': 'Pastillas, discos, cables y sistemas de frenado',
        },
        {
            'id': 3,
            'name': 'Neumáticos y Cámaras',
            'description': 'Neumáticos, cámaras y accesorios para ruedas',
        },
        {
            'id': 4,
            'name': 'Cambios y Desviadores',
            'description': 'Cambios traseros, desviadores delanteros, palancas y cassettes',
        },
        {
            'id': 5,
            'name': 'Accesorios',
            'description': 'Cascos, luces, portabidones, multiherramientas y bombas de aire',
        },
        {
            'id': 6,
            'name': 'Herramientas',
            'description': 'Llaves, extractores, herramientas de cadena y juegos completos',
        },
    ]
    return categories


def generate_suppliers():
    """Generate 6 suppliers matching seed_data.py supplier_ids"""
    suppliers = [
        {
            'id': 1,
            'name': 'Shimano México',
            'email': 'ventas@shimano.mx',
            'phone': '+52 55 1234 5678',
            'address': 'Av. Industrial 456, CDMX',
            'website': 'https://shimano.mx',
            'payment_terms': 'Net 30',
            'contact_info': {'contact_name': 'Carlos Mendoza', 'position': 'Gerente de Ventas'},
            'is_active': True,
        },
        {
            'id': 2,
            'name': 'SRAM Distribución',
            'email': 'pedidos@sram-distribucion.com',
            'phone': '+52 33 2345 6789',
            'address': 'Calle Comercio 789, Guadalajara',
            'website': 'https://sram-distribucion.com',
            'payment_terms': 'Net 45',
            'contact_info': {'contact_name': 'Ana Rodríguez', 'position': 'Coordinadora Comercial'},
            'is_active': True,
        },
        {
            'id': 3,
            'name': 'Tektro Frenos MX',
            'email': 'info@tektro-frenos.mx',
            'phone': '+52 81 3456 7890',
            'address': 'Blvd. Tecnológico 123, Monterrey',
            'website': 'https://tektro-frenos.mx',
            'payment_terms': 'Net 30',
            'contact_info': {'contact_name': 'Roberto Silva', 'position': 'Director de Operaciones'},
            'is_active': True,
        },
        {
            'id': 4,
            'name': 'KMC Cadenas',
            'email': 'ventas@kmc-cadenas.com',
            'phone': '+52 55 4567 8901',
            'address': 'Parque Industrial Norte 45, CDMX',
            'website': 'https://kmc-cadenas.com',
            'payment_terms': 'Net 60',
            'contact_info': {'contact_name': 'Laura García', 'position': 'Ejecutiva de Cuentas'},
            'is_active': True,
        },
        {
            'id': 5,
            'name': 'Accesorios Bici MX',
            'email': 'contacto@accesoriosbicimx.com',
            'phone': '+52 222 5678 9012',
            'address': 'Av. Reforma 234, Puebla',
            'website': 'https://accesoriosbicimx.com',
            'payment_terms': 'Net 30',
            'contact_info': {'contact_name': 'Miguel Torres', 'position': 'Gerente General'},
            'is_active': True,
        },
        {
            'id': 6,
            'name': 'Herramientas Pro',
            'email': 'pedidos@herramientaspro.com',
            'phone': '+52 33 6789 0123',
            'address': 'Calle Herreros 567, Guadalajara',
            'website': 'https://herramientaspro.com',
            'payment_terms': 'Net 45',
            'contact_info': {'contact_name': 'Patricia López', 'position': 'Jefa de Ventas'},
            'is_active': True,
        },
    ]
    return suppliers


if __name__ == '__main__':
    print("Generating categories and suppliers seed data...")
    
    categories = generate_categories()
    suppliers = generate_suppliers()
    
    print(f"✓ Generated {len(categories)} categories")
    print(f"✓ Generated {len(suppliers)} suppliers")
    
    # Save to JSON files
    with open('categories_seed.json', 'w', encoding='utf-8') as f:
        json.dump(categories, f, indent=2, ensure_ascii=False)
    
    with open('suppliers_seed.json', 'w', encoding='utf-8') as f:
        json.dump(suppliers, f, indent=2, ensure_ascii=False)
    
    print("\n✓ Seed data saved to JSON files")
    print("\nTo import into database, run:")
    print("  python import_seed_data.py")

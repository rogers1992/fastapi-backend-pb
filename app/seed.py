"""
Idempotent default seeding: roles + admin user.

Runs on app startup when settings.SEED_DEFAULTS is True (e.g. on Render).
Safe to re-run on every boot: each insert is guarded by an existence check,
so cold-start restarts never duplicate rows and never overwrite a password
that was changed later via the API/UI.
"""
from sqlalchemy.orm import Session
from .models.user import Role, User
from .core.security import get_password_hash


DEFAULT_ROLES = [
    ("admin", {
        "products": ["read", "create", "update", "delete"],
        "inventory": ["read", "create", "update", "delete"],
        "sales": ["read", "create", "update", "delete"],
        "customers": ["read", "create", "update", "delete"],
        "users": ["read", "create", "update", "delete"],
        "roles": ["read", "create", "update", "delete"],
        "reports": ["read", "create"],
    }, "Administrador con acceso completo", True),
    ("gerente", {
        "products": ["read", "create", "update"],
        "inventory": ["read", "create", "update"],
        "sales": ["read", "create", "update"],
        "customers": ["read", "create", "update"],
        "users": ["read"],
        "reports": ["read", "create"],
    }, "Gerente de tienda", True),
    ("vendedor", {
        "products": ["read"],
        "inventory": ["read"],
        "sales": ["read", "create"],
        "customers": ["read", "create"],
    }, "Vendedor", True),
    ("almacen", {
        "products": ["read"],
        "inventory": ["read", "update"],
    }, "Personal de almac\u00e9n", True),
]


def seed_defaults(db: Session) -> None:
    """Create default roles and admin user if missing. Idempotent."""
    role_map = {}

    for name, perms, description, is_system in DEFAULT_ROLES:
        existing = db.query(Role).filter(Role.name == name).first()
        if existing:
            role_map[name] = existing
            print(f"[seed] role '{name}' exists, skipped")
            continue
        role = Role(
            name=name,
            permissions=perms,
            description=description,
            is_system=is_system,
        )
        db.add(role)
        db.flush()
        role_map[name] = role
        print(f"[seed] + role '{name}' added")

    admin_role = role_map.get("admin") or db.query(Role).filter(Role.name == "admin").first()
    if db.query(User).filter(User.username == "admin").first():
        print("[seed] user 'admin' exists, skipped")
    else:
        db.add(User(
            role_id=admin_role.id if admin_role else None,
            username="admin",
            email="admin@paraisobiker.com",
            password_hash=get_password_hash("admin123"),
            first_name="Administrador",
            last_name="Sistema",
            phone="+52 555 000 0000",
        ))
        print("[seed] + user 'admin' created (password: admin123)")

    db.commit()
    print("[seed] done")

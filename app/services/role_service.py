from sqlalchemy.orm import Session
from typing import Optional, List
from ..models.user import Role
from ..schemas.role import RoleCreate, RoleUpdate


class RoleService:

    @staticmethod
    def get_roles(db: Session) -> List[Role]:
        return db.query(Role).order_by(Role.id).all()

    @staticmethod
    def get_role_by_id(db: Session, role_id: int) -> Optional[Role]:
        return db.query(Role).filter(Role.id == role_id).first()

    @staticmethod
    def get_role_by_name(db: Session, name: str) -> Optional[Role]:
        return db.query(Role).filter(Role.name == name).first()

    @staticmethod
    def create_role(db: Session, role_data: RoleCreate) -> Role:
        existing = db.query(Role).filter(Role.name == role_data.name).first()
        if existing:
            raise ValueError("Role name already exists")

        role = Role(
            name=role_data.name,
            description=role_data.description,
            permissions=role_data.permissions,
            is_system=False,
        )
        db.add(role)
        db.commit()
        db.refresh(role)
        return role

    @staticmethod
    def update_role(db: Session, role_id: int, role_data: RoleUpdate) -> Optional[Role]:
        role = db.query(Role).filter(Role.id == role_id).first()
        if not role:
            return None

        update_data = role_data.model_dump(exclude_unset=True)

        if "name" in update_data and role.is_system:
            raise ValueError("Cannot rename a system role")

        if "name" in update_data:
            existing = db.query(Role).filter(Role.name == update_data["name"], Role.id != role_id).first()
            if existing:
                raise ValueError("Role name already exists")

        for key, value in update_data.items():
            setattr(role, key, value)

        db.commit()
        db.refresh(role)
        return role

    @staticmethod
    def delete_role(db: Session, role_id: int) -> bool:
        role = db.query(Role).filter(Role.id == role_id).first()
        if not role:
            return None

        if role.is_system:
            raise ValueError("Cannot delete a system role")

        if role.users:
            raise ValueError("Cannot delete a role that has users assigned")

        db.delete(role)
        db.commit()
        return True

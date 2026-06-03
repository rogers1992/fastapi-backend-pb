from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, List
from ..models.user import User, Role
from ..schemas.user import UserCreate, UserUpdate
from ..core.security import get_password_hash, verify_password


class UserService:

    @staticmethod
    def get_users(db: Session, skip: int = 0, limit: int = 100, search: Optional[str] = None, role_id: Optional[int] = None, is_active: Optional[bool] = None) -> List[User]:
        query = db.query(User)
        if search:
            query = query.filter(
                or_(
                    User.username.ilike(f"%{search}%"),
                    User.first_name.ilike(f"%{search}%"),
                    User.last_name.ilike(f"%{search}%"),
                    User.email.ilike(f"%{search}%"),
                )
            )
        if role_id is not None:
            query = query.filter(User.role_id == role_id)
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        return query.order_by(User.id).offset(skip).limit(limit).all()

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def get_user_by_username(db: Session, username: str) -> Optional[User]:
        return db.query(User).filter(User.username == username).first()

    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        return db.query(User).filter(User.email == email).first()

    @staticmethod
    def create_user(db: Session, user_data: UserCreate) -> User:
        existing_username = db.query(User).filter(User.username == user_data.username).first()
        if existing_username:
            raise ValueError("Username already exists")

        existing_email = db.query(User).filter(User.email == user_data.email).first()
        if existing_email:
            raise ValueError("Email already exists")

        role = db.query(Role).filter(Role.id == user_data.role_id).first()
        if not role:
            raise ValueError("Role not found")

        user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=get_password_hash(user_data.password),
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            phone=user_data.phone,
            role_id=user_data.role_id,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def update_user(db: Session, user_id: int, user_data: UserUpdate) -> Optional[User]:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None

        update_data = user_data.model_dump(exclude_unset=True)

        if "email" in update_data:
            existing = db.query(User).filter(User.email == update_data["email"], User.id != user_id).first()
            if existing:
                raise ValueError("Email already in use")

        if "role_id" in update_data:
            role = db.query(Role).filter(Role.id == update_data["role_id"]).first()
            if not role:
                raise ValueError("Role not found")

        for key, value in update_data.items():
            setattr(user, key, value)

        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def toggle_active(db: Session, user_id: int, is_active: bool) -> Optional[User]:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        user.is_active = is_active
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def reset_password(db: Session, user_id: int, new_password: str) -> Optional[User]:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        user.password_hash = get_password_hash(new_password)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def update_last_login(db: Session, user_id: int):
        from sqlalchemy.sql import func
        db.query(User).filter(User.id == user_id).update({"last_login": func.now()})
        db.commit()

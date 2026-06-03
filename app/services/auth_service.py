from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from ..models.user import User
from ..schemas.user import UserLogin, UserWithRoleResponse
from ..core.security import verify_password, create_access_token
from .user_service import UserService


class AuthService:

    @staticmethod
    def authenticate(db: Session, credentials: UserLogin) -> Optional[dict]:
        user = UserService.get_user_by_username(db, credentials.username)

        if not user or not verify_password(credentials.password, user.password_hash):
            return None

        if not user.is_active:
            raise PermissionError("User account is disabled")

        permissions = user.role.permissions if user.role else {}

        access_token = create_access_token(data={
            "sub": user.username,
            "role": user.role.name if user.role else None,
            "permissions": permissions,
        })

        UserService.update_last_login(db, user.id)

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": UserWithRoleResponse.model_validate(user),
        }

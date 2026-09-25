from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from typing import List
from zoneinfo import available_timezones
from ..config import settings
from ..database import get_db
from ..models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

_DEFAULT_TZ = "America/La_Paz"
_VALID_TIMEZONES = available_timezones()


async def get_user_timezone(
    tz: str = Header(default=_DEFAULT_TZ, alias="X-Timezone"),
) -> str:
    """Extract and validate the user's timezone from the X-Timezone header.

    Falls back to America/La_Paz if the header is missing or contains an
    invalid IANA timezone identifier.
    """
    return tz if tz in _VALID_TIMEZONES else _DEFAULT_TZ


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    return user


def require_permission(resource: str, action: str):
    async def permission_checker(current_user: User = Depends(get_current_user)):
        if not current_user.role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No role assigned",
            )

        permissions = current_user.role.permissions or {}

        allowed_actions = permissions.get(resource, [])
        if action not in allowed_actions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {resource}.{action}",
            )

        return current_user

    return permission_checker


def require_role(*role_names: str):
    async def role_checker(current_user: User = Depends(get_current_user)):
        if not current_user.role or current_user.role.name not in role_names:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient role. Required: {', '.join(role_names)}",
            )

        return current_user

    return role_checker

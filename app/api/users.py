from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from ..database import get_db
from ..models.user import User
from ..schemas.user import (
    UserCreate, UserUpdate, UserWithRoleResponse,
    UserPasswordReset, UserToggleActive,
)
from ..core.dependencies import get_current_user, require_permission
from ..services.user_service import UserService

router = APIRouter()


@router.get("/", response_model=List[UserWithRoleResponse])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: Optional[str] = None,
    role_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "read")),
):
    return UserService.get_users(db, skip, limit, search, role_id, is_active)


@router.get("/{user_id}", response_model=UserWithRoleResponse)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "read")),
):
    user = UserService.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/", response_model=UserWithRoleResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "create")),
):
    try:
        return UserService.create_user(db, user_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{user_id}", response_model=UserWithRoleResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "update")),
):
    try:
        user = UserService.update_user(db, user_id, user_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/{user_id}/toggle-active", response_model=UserWithRoleResponse)
async def toggle_user_active(
    user_id: int,
    data: UserToggleActive,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "update")),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    user = UserService.toggle_active(db, user_id, data.is_active)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    data: UserPasswordReset,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "update")),
):
    user = UserService.reset_password(db, user_id, data.new_password)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "Password reset successfully"}

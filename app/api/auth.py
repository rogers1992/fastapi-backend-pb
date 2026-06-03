from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.user import User
from ..schemas.user import UserLogin, Token, UserWithRoleResponse
from ..core.dependencies import get_current_user
from ..services.auth_service import AuthService

router = APIRouter()


@router.post("/login", response_model=Token)
async def login(form_data: UserLogin, db: Session = Depends(get_db)):
    try:
        result = AuthService.authenticate(db, form_data)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return result


@router.post("/logout")
async def logout():
    return {"message": "Logout successful"}


@router.get("/me", response_model=UserWithRoleResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    return current_user

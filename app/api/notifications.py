from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models.user import User
from ..core.dependencies import get_current_user
from ..services.notification_service import NotificationService
from ..schemas.notification import (
    NotificationResponse,
    UnreadCountResponse,
    MessageResponse,
)

router = APIRouter()


@router.get("/", response_model=List[NotificationResponse])
async def list_notifications(
    unread_only: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return NotificationService.get_for_user(
        db, current_user.id, unread_only=unread_only, skip=skip, limit=limit
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = NotificationService.get_unread_count(db, current_user.id)
    return {"unread_count": count}


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notification = NotificationService.mark_read(db, notification_id, current_user.id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification


@router.patch("/mark-all-read", response_model=MessageResponse)
async def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = NotificationService.mark_all_read(db, current_user.id)
    return {"message": f"{count} notifications marked as read"}


@router.delete("/{notification_id}", response_model=MessageResponse, status_code=status.HTTP_200_OK)
async def delete_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = NotificationService.delete(db, notification_id, current_user.id)
    if result is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification deleted successfully"}

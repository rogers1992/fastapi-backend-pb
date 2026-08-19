from pydantic import BaseModel

from . import BaseSchema
from datetime import datetime
from typing import Optional, Any, Dict


class NotificationBase(BaseSchema):
    type: str
    title: str
    message: str
    data: Optional[Dict[str, Any]] = None


class NotificationCreate(NotificationBase):
    user_id: int


class NotificationResponse(NotificationBase):
    id: int
    user_id: int
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UnreadCountResponse(BaseSchema):
    unread_count: int


class MessageResponse(BaseSchema):
    message: str

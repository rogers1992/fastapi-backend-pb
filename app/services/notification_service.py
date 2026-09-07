from sqlalchemy.orm import Session
from typing import Optional, List, Any, Dict
from ..models.notification import Notification
from ..models.user import User
from ..models.user import Role
from ..schemas.notification import NotificationCreate


class NotificationService:

    @staticmethod
    def create(
        db: Session,
        user_id: int,
        type: str,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            data=data,
            is_read=False,
        )
        db.add(notification)
        return notification

    @staticmethod
    def get_for_user(
        db: Session,
        user_id: int,
        unread_only: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Notification]:
        query = db.query(Notification).filter(Notification.user_id == user_id)
        if unread_only:
            query = query.filter(Notification.is_read == False)  # noqa: E712
        return (
            query.order_by(Notification.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_unread_count(db: Session, user_id: int) -> int:
        return (
            db.query(Notification)
            .filter(
                Notification.user_id == user_id,
                Notification.is_read == False,  # noqa: E712
            )
            .count()
        )

    @staticmethod
    def mark_read(db: Session, notification_id: int, user_id: int) -> Optional[Notification]:
        notification = (
            db.query(Notification)
            .filter(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
            .first()
        )
        if not notification:
            return None
        notification.is_read = True
        db.commit()
        db.refresh(notification)
        return notification

    @staticmethod
    def mark_all_read(db: Session, user_id: int) -> int:
        result = (
            db.query(Notification)
            .filter(
                Notification.user_id == user_id,
                Notification.is_read == False,  # noqa: E712
            )
            .update({"is_read": True}, synchronize_session="fetch")
        )
        db.commit()
        return result

    @staticmethod
    def delete(db: Session, notification_id: int, user_id: int) -> bool:
        notification = (
            db.query(Notification)
            .filter(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
            .first()
        )
        if not notification:
            return None
        db.delete(notification)
        db.commit()
        return True

    # ---- Broadcast helpers (fan-out to many users) ----

    @staticmethod
    def notify_users_with_permission(
        db: Session,
        resource: str,
        action: str,
        type: str,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Create a notification for every active user whose role grants
        `resource.action`. Returns the number of notifications created.
        """
        users = (
            db.query(User)
            .join(User.role)
            .filter(
                User.is_active == True,
                Role.permissions.contains({resource: [action]}),
            )
            .all()
        )
        count = 0
        for user in users:
            NotificationService.create(db, user.id, type, title, message, data)
            count += 1
        db.commit()
        return count

    @staticmethod
    def notify_user(
        db: Session,
        user_id: int,
        type: str,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Notification:
        return NotificationService.create(
            db, user_id, type, title, message, data
        )

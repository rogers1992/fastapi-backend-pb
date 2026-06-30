from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String(50), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    data = Column(JSONB, nullable=True)
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    user = relationship("User", backref="notifications")

import enum
import uuid
from datetime import datetime

from sqlalchemy import String, Text, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class ActionResultStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Action(Base):
    __tablename__ = "actions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "prompt": self.prompt,
            "is_default": self.is_default,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ActionResult(Base):
    __tablename__ = "action_results"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    action_id: Mapped[str] = mapped_column(String, ForeignKey("actions.id", ondelete="CASCADE"))
    meeting_id: Mapped[str] = mapped_column(String, ForeignKey("meetings.id", ondelete="CASCADE"))
    status: Mapped[ActionResultStatus] = mapped_column(Enum(ActionResultStatus), default=ActionResultStatus.PENDING)
    result_text: Mapped[str] = mapped_column(Text, nullable=True)
    error: Mapped[str] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[str] = mapped_column(String, nullable=True)
    is_encrypted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "action_id": self.action_id,
            "meeting_id": self.meeting_id,
            "status": self.status.value,
            "result_text": self.result_text,
            "error": self.error,
            "celery_task_id": self.celery_task_id,
            "is_encrypted": bool(self.is_encrypted),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

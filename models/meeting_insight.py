import enum
import uuid
from datetime import datetime

from sqlalchemy import String, Text, Float, Integer, DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class InsightType(str, enum.Enum):
    DECISION = "decision"
    ACTION_ITEM = "action_item"
    OPEN_QUESTION = "open_question"


class InsightStatus(str, enum.Enum):
    OPEN = "open"
    COMPLETED = "completed"
    DISMISSED = "dismissed"


class MeetingInsight(Base):
    __tablename__ = "meeting_insights"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id: Mapped[str] = mapped_column(String, ForeignKey("meetings.id", ondelete="CASCADE"))
    insight_type: Mapped[InsightType] = mapped_column(Enum(InsightType), nullable=False)
    status: Mapped[InsightStatus] = mapped_column(Enum(InsightStatus), default=InsightStatus.OPEN)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    assignee: Mapped[str] = mapped_column(String, nullable=True)  # Speaker name
    source_start_time: Mapped[float] = mapped_column(Float, nullable=True)
    source_end_time: Mapped[float] = mapped_column(Float, nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "meeting_id": self.meeting_id,
            "insight_type": self.insight_type.value,
            "status": self.status.value,
            "content": self.content,
            "assignee": self.assignee,
            "source_start_time": self.source_start_time,
            "source_end_time": self.source_end_time,
            "order": self.order,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

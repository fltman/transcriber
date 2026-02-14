import uuid
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class VocabularyEntry(Base):
    __tablename__ = "vocabulary_entries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    term: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    frequency: Mapped[int] = mapped_column(Integer, default=1)
    source_meeting_id: Mapped[str] = mapped_column(String, ForeignKey("meetings.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "term": self.term,
            "frequency": self.frequency,
            "source_meeting_id": self.source_meeting_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

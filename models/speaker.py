import uuid

from sqlalchemy import String, Float, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Speaker(Base):
    __tablename__ = "speakers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id: Mapped[str] = mapped_column(String, ForeignKey("meetings.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String, nullable=False)  # SPEAKER_00
    display_name: Mapped[str] = mapped_column(String, nullable=True)  # "Anders"
    color: Mapped[str] = mapped_column(String, default="#6366f1")
    identified_by: Mapped[str] = mapped_column(String, nullable=True)  # intro_llm, manual, null
    confidence: Mapped[float] = mapped_column(Float, nullable=True)
    total_speaking_time: Mapped[float] = mapped_column(Float, default=0.0)
    segment_count: Mapped[int] = mapped_column(Integer, default=0)

    meeting = relationship("Meeting", back_populates="speakers")
    segments = relationship("Segment", back_populates="speaker")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "meeting_id": self.meeting_id,
            "label": self.label,
            "display_name": self.display_name,
            "color": self.color,
            "identified_by": self.identified_by,
            "confidence": self.confidence,
            "total_speaking_time": self.total_speaking_time,
            "segment_count": self.segment_count,
        }

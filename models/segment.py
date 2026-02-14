import uuid

from sqlalchemy import String, Float, Integer, Boolean, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Segment(Base):
    __tablename__ = "segments"
    __table_args__ = (
        Index("ix_segments_meeting_order", "meeting_id", "order"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id: Mapped[str] = mapped_column(String, ForeignKey("meetings.id", ondelete="CASCADE"))
    speaker_id: Mapped[str] = mapped_column(String, ForeignKey("speakers.id", ondelete="SET NULL"), nullable=True)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_edited: Mapped[bool] = mapped_column(Boolean, default=False)

    meeting = relationship("Meeting", back_populates="segments")
    speaker = relationship("Speaker", back_populates="segments")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "meeting_id": self.meeting_id,
            "speaker_id": self.speaker_id,
            "speaker_label": self.speaker.label if self.speaker else None,
            "speaker_name": self.speaker.display_name if self.speaker else None,
            "speaker_color": self.speaker.color if self.speaker else None,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "text": self.text,
            "original_text": self.original_text,
            "order": self.order,
            "is_edited": self.is_edited,
        }

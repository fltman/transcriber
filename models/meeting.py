import enum
import uuid
from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime, JSON, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class MeetingStatus(str, enum.Enum):
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[MeetingStatus] = mapped_column(Enum(MeetingStatus), default=MeetingStatus.UPLOADED)
    original_filename: Mapped[str] = mapped_column(String, nullable=True)
    audio_filepath: Mapped[str] = mapped_column(String, nullable=True)
    duration: Mapped[float] = mapped_column(Float, nullable=True)
    whisper_model: Mapped[str] = mapped_column(String, default="medium")
    min_speakers: Mapped[int] = mapped_column(Integer, nullable=True)
    max_speakers: Mapped[int] = mapped_column(Integer, nullable=True)
    intro_end_time: Mapped[float] = mapped_column(Float, nullable=True)
    raw_diarization: Mapped[dict] = mapped_column(JSON, nullable=True)
    raw_transcription: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    speakers = relationship("Speaker", back_populates="meeting", cascade="all, delete-orphan")
    segments = relationship("Segment", back_populates="meeting", cascade="all, delete-orphan", order_by="Segment.order")
    jobs = relationship("Job", back_populates="meeting", cascade="all, delete-orphan")

    def to_dict(self, include_segments=False):
        d = {
            "id": self.id,
            "title": self.title,
            "status": self.status.value,
            "original_filename": self.original_filename,
            "duration": self.duration,
            "whisper_model": self.whisper_model,
            "min_speakers": self.min_speakers,
            "max_speakers": self.max_speakers,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "speaker_count": len(self.speakers) if self.speakers else 0,
            "segment_count": len(self.segments) if self.segments else 0,
        }
        if include_segments:
            d["speakers"] = [s.to_dict() for s in self.speakers]
            d["segments"] = [s.to_dict() for s in self.segments]
        return d

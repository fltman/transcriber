import uuid
from datetime import datetime

import numpy as np
from sqlalchemy import String, Float, DateTime, LargeBinary, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class SpeakerProfile(Base):
    """Persistent voice profile that can be matched across meetings."""
    __tablename__ = "speaker_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    embedding: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)  # numpy array as bytes
    sample_count: Mapped[float] = mapped_column(Float, default=1.0)  # for running average
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_embedding(self) -> np.ndarray:
        return np.frombuffer(self.embedding, dtype=np.float32).copy()

    def set_embedding(self, emb: np.ndarray):
        self.embedding = emb.astype(np.float32).tobytes()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "sample_count": int(self.sample_count),
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

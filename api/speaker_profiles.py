import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Speaker, Segment
from models.speaker_profile import SpeakerProfile
from services.embedding_service import EmbeddingService
from services.diarization_service import DiarizationService

router = APIRouter(prefix="/api/speaker-profiles", tags=["speaker_profiles"])


class CreateProfileRequest(BaseModel):
    name: str
    notes: str | None = None


class UpdateProfileRequest(BaseModel):
    name: str | None = None
    notes: str | None = None


class SaveFromSpeakerRequest(BaseModel):
    speaker_id: str
    meeting_id: str
    name: str | None = None


@router.get("")
def list_profiles(db: Session = Depends(get_db)):
    profiles = db.query(SpeakerProfile).order_by(SpeakerProfile.name).all()
    return [p.to_dict() for p in profiles]


@router.get("/{profile_id}")
def get_profile(profile_id: str, db: Session = Depends(get_db)):
    profile = db.query(SpeakerProfile).filter(SpeakerProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(404, "Profile not found")
    return profile.to_dict()


@router.put("/{profile_id}")
def update_profile(profile_id: str, req: UpdateProfileRequest, db: Session = Depends(get_db)):
    profile = db.query(SpeakerProfile).filter(SpeakerProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(404, "Profile not found")
    if req.name is not None:
        profile.name = req.name.strip()[:200]
    if req.notes is not None:
        profile.notes = req.notes.strip()[:1000] if req.notes else None
    db.commit()
    return profile.to_dict()


@router.delete("/{profile_id}")
def delete_profile(profile_id: str, db: Session = Depends(get_db)):
    profile = db.query(SpeakerProfile).filter(SpeakerProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(404, "Profile not found")
    db.delete(profile)
    db.commit()
    return {"ok": True}


@router.post("/save-from-speaker")
def save_profile_from_speaker(req: SaveFromSpeakerRequest, db: Session = Depends(get_db)):
    """Create or update a voice profile from an identified speaker in a meeting.

    Extracts voice embedding from the speaker's audio segments and saves
    it as a persistent profile for future meeting matching.
    """
    from models import Meeting
    from config import get_meeting_path
    import subprocess
    import wave
    from pathlib import Path

    speaker = db.query(Speaker).filter(Speaker.id == req.speaker_id).first()
    if not speaker:
        raise HTTPException(404, "Speaker not found")

    meeting = db.query(Meeting).filter(Meeting.id == req.meeting_id).first()
    if not meeting or not meeting.audio_filepath:
        raise HTTPException(404, "Meeting or audio not found")

    # Get speaker's segments to extract audio
    segments = (
        db.query(Segment)
        .filter(Segment.speaker_id == req.speaker_id, Segment.meeting_id == req.meeting_id)
        .order_by(Segment.order)
        .all()
    )
    if not segments:
        raise HTTPException(400, "Speaker has no segments")

    # Extract representative audio clips (up to 30s total)
    embedding_service = EmbeddingService()
    meeting_path = get_meeting_path(req.meeting_id)
    temp_path = str(meeting_path / "profile_extract.wav")

    # Build ffmpeg filter to concatenate speaker segments (up to 30s)
    total_duration = 0.0
    filter_parts = []
    input_args = []
    seg_count = 0

    for seg in segments:
        if total_duration >= 30:
            break
        dur = min(seg.end_time - seg.start_time, 30 - total_duration)
        input_args.extend(["-ss", str(seg.start_time), "-t", str(dur), "-i", meeting.audio_filepath])
        filter_parts.append(f"[{seg_count}:a]")
        total_duration += dur
        seg_count += 1

    if seg_count == 0:
        raise HTTPException(400, "No valid audio segments for this speaker")

    # Concatenate and extract
    if seg_count == 1:
        filter_str = f"{filter_parts[0]}aresample=16000,aformat=sample_fmts=s16:channel_layouts=mono[out]"
    else:
        filter_str = "".join(filter_parts) + f"concat=n={seg_count}:v=0:a=1[cat];[cat]aresample=16000,aformat=sample_fmts=s16:channel_layouts=mono[out]"

    cmd = ["ffmpeg", "-y"] + input_args + ["-filter_complex", filter_str, "-map", "[out]", temp_path]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {result.stderr[:200]}")

        embedding = embedding_service.extract_embedding(temp_path)
    finally:
        Path(temp_path).unlink(missing_ok=True)

    profile_name = req.name or speaker.display_name or speaker.label

    # Check if a profile with this name exists — update its embedding (running average)
    existing = db.query(SpeakerProfile).filter(SpeakerProfile.name == profile_name).first()
    if existing:
        old_emb = existing.get_embedding()
        n = existing.sample_count
        # Running average: new_avg = (old_avg * n + new) / (n + 1)
        new_emb = (old_emb * n + embedding) / (n + 1)
        existing.set_embedding(new_emb)
        existing.sample_count = n + 1
        db.commit()
        return existing.to_dict()

    profile = SpeakerProfile(
        name=profile_name,
        notes=None,
    )
    profile.set_embedding(embedding)
    db.add(profile)
    db.commit()
    return profile.to_dict()

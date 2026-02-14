from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models import Speaker, Segment

router = APIRouter(prefix="/api/speakers", tags=["speakers"])


class UpdateSpeakerRequest(BaseModel):
    display_name: str | None = None
    color: str | None = None


class MergeSpeakersRequest(BaseModel):
    source_id: str
    target_id: str


@router.put("/{speaker_id}")
def update_speaker(speaker_id: str, req: UpdateSpeakerRequest, db: Session = Depends(get_db)):
    speaker = db.query(Speaker).filter(Speaker.id == speaker_id).first()
    if not speaker:
        raise HTTPException(404, "Speaker not found")

    if req.display_name is not None:
        speaker.display_name = req.display_name
        speaker.identified_by = "manual"
    if req.color is not None:
        speaker.color = req.color

    db.commit()
    return speaker.to_dict()


@router.post("/merge")
def merge_speakers(req: MergeSpeakersRequest, db: Session = Depends(get_db)):
    source = db.query(Speaker).filter(Speaker.id == req.source_id).first()
    target = db.query(Speaker).filter(Speaker.id == req.target_id).first()

    if not source or not target:
        raise HTTPException(404, "Speaker not found")
    if source.meeting_id != target.meeting_id:
        raise HTTPException(400, "Speakers must be from the same meeting")

    # Move all segments from source to target
    db.query(Segment).filter(Segment.speaker_id == source.id).update(
        {"speaker_id": target.id}, synchronize_session="fetch"
    )

    # Update target stats with single aggregated query
    stats = db.query(
        func.count(Segment.id),
        func.coalesce(func.sum(Segment.end_time - Segment.start_time), 0),
    ).filter(Segment.speaker_id == target.id).one()
    target.segment_count = stats[0]
    target.total_speaking_time = stats[1]

    # Delete source
    db.delete(source)
    db.commit()
    db.refresh(target)

    return target.to_dict()

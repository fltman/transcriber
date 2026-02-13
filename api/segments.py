from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Segment

router = APIRouter(prefix="/api", tags=["segments"])


class UpdateSegmentTextRequest(BaseModel):
    text: str


class UpdateSegmentSpeakerRequest(BaseModel):
    speaker_id: str


@router.get("/meetings/{meeting_id}/segments")
def list_segments(meeting_id: str, db: Session = Depends(get_db)):
    segments = (
        db.query(Segment)
        .filter(Segment.meeting_id == meeting_id)
        .order_by(Segment.order)
        .all()
    )
    return [s.to_dict() for s in segments]


@router.put("/segments/{segment_id}")
def update_segment_text(segment_id: str, req: UpdateSegmentTextRequest, db: Session = Depends(get_db)):
    segment = db.query(Segment).filter(Segment.id == segment_id).first()
    if not segment:
        raise HTTPException(404, "Segment not found")

    segment.text = req.text
    segment.is_edited = True
    db.commit()
    return segment.to_dict()


@router.put("/segments/{segment_id}/speaker")
def update_segment_speaker(segment_id: str, req: UpdateSegmentSpeakerRequest, db: Session = Depends(get_db)):
    segment = db.query(Segment).filter(Segment.id == segment_id).first()
    if not segment:
        raise HTTPException(404, "Segment not found")

    segment.speaker_id = req.speaker_id
    db.commit()
    return segment.to_dict()

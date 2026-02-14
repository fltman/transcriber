from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Meeting, Speaker, Segment

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/meetings/{meeting_id}/analytics")
def get_meeting_analytics(meeting_id: str, db: Session = Depends(get_db)):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(404, "Meeting not found")

    speakers = db.query(Speaker).filter(Speaker.meeting_id == meeting_id).all()
    segments = (
        db.query(Segment)
        .filter(Segment.meeting_id == meeting_id)
        .order_by(Segment.order)
        .all()
    )

    total_duration = meeting.duration or 0
    total_speaking = sum(s.total_speaking_time or 0 for s in speakers)

    speaker_data = []
    for spk in speakers:
        spk_segments = [s for s in segments if s.speaker_id == spk.id]
        timeline = [{"start": s.start_time, "end": s.end_time} for s in spk_segments]
        pct = (spk.total_speaking_time / total_speaking * 100) if total_speaking > 0 else 0

        speaker_data.append({
            "name": spk.display_name or spk.label,
            "color": spk.color,
            "speaking_time": round(spk.total_speaking_time or 0, 1),
            "segment_count": spk.segment_count or len(spk_segments),
            "percentage": round(pct, 1),
            "timeline": timeline,
        })

    # Sort by speaking time descending
    speaker_data.sort(key=lambda x: x["speaking_time"], reverse=True)

    silence_pct = ((total_duration - total_speaking) / total_duration * 100) if total_duration > 0 else 0

    return {
        "speakers": speaker_data,
        "total_duration": round(total_duration, 1),
        "total_speaking_time": round(total_speaking, 1),
        "silence_percentage": round(max(0, silence_pct), 1),
    }

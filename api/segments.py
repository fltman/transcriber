import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import Meeting, Segment

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["segments"])


class UpdateSegmentTextRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)


class UpdateSegmentSpeakerRequest(BaseModel):
    speaker_id: str


@router.get("/meetings/{meeting_id}/segments")
def list_segments(meeting_id: str, db: Session = Depends(get_db)):
    segments = (
        db.query(Segment)
        .options(joinedload(Segment.speaker))
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

    meeting = db.query(Meeting).filter(Meeting.id == segment.meeting_id).first()
    if meeting and meeting.is_encrypted:
        raise HTTPException(400, "Cannot edit segments while meeting is encrypted. Decrypt first.")

    old_text = segment.original_text or segment.text
    segment.text = req.text
    segment.is_edited = True
    db.commit()

    # Learn vocabulary from corrections
    _learn_from_correction(db, old_text, req.text, segment.meeting_id)

    return segment.to_dict()


@router.put("/segments/{segment_id}/speaker")
def update_segment_speaker(segment_id: str, req: UpdateSegmentSpeakerRequest, db: Session = Depends(get_db)):
    segment = db.query(Segment).filter(Segment.id == segment_id).first()
    if not segment:
        raise HTTPException(404, "Segment not found")

    meeting = db.query(Meeting).filter(Meeting.id == segment.meeting_id).first()
    if meeting and meeting.is_encrypted:
        raise HTTPException(400, "Cannot edit segments while meeting is encrypted. Decrypt first.")

    segment.speaker_id = req.speaker_id
    db.commit()
    return segment.to_dict()


def _learn_from_correction(db: Session, old_text: str, new_text: str, meeting_id: str):
    """Extract corrected words/phrases and save as vocabulary entries."""
    from models import VocabularyEntry

    if not old_text or not new_text or old_text.strip() == new_text.strip():
        return

    old_words = old_text.split()
    new_words = new_text.split()

    # Find words that differ (simple word-level diff)
    corrections = set()
    # Use difflib for proper alignment
    import difflib
    matcher = difflib.SequenceMatcher(None, old_words, new_words)
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "replace":
            # The new words are corrections of old words
            new_phrase = " ".join(new_words[j1:j2])
            old_phrase = " ".join(old_words[i1:i2])
            # Only learn if it looks like a real correction (not a total rewrite)
            if len(new_phrase) < 100 and abs(len(new_phrase) - len(old_phrase)) < len(old_phrase):
                corrections.add(new_phrase)
        elif op == "insert":
            new_phrase = " ".join(new_words[j1:j2])
            if len(new_phrase) < 100:
                corrections.add(new_phrase)

    for term in corrections:
        term = term.strip()
        if len(term) < 2:
            continue
        # Skip common words (only learn proper nouns, technical terms)
        if term.islower() and len(term) < 5:
            continue

        existing = db.query(VocabularyEntry).filter(VocabularyEntry.term == term).first()
        if existing:
            existing.frequency += 1
        else:
            entry = VocabularyEntry(
                term=term,
                source_meeting_id=meeting_id,
            )
            db.add(entry)

    try:
        db.commit()
    except Exception as e:
        log.debug(f"Vocabulary learning failed: {e}")
        db.rollback()

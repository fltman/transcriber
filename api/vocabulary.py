from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import VocabularyEntry

router = APIRouter(prefix="/api/vocabulary", tags=["vocabulary"])


@router.get("")
def list_vocabulary(db: Session = Depends(get_db)):
    entries = db.query(VocabularyEntry).order_by(VocabularyEntry.frequency.desc()).limit(200).all()
    return [e.to_dict() for e in entries]


@router.delete("/{entry_id}")
def delete_entry(entry_id: str, db: Session = Depends(get_db)):
    entry = db.query(VocabularyEntry).filter(VocabularyEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(404, "Entry not found")
    db.delete(entry)
    db.commit()
    return {"ok": True}


@router.get("/suggest")
def suggest_vocabulary(db: Session = Depends(get_db)):
    """Return top learned terms formatted as a vocabulary string for Whisper prompts."""
    entries = (
        db.query(VocabularyEntry)
        .filter(VocabularyEntry.frequency >= 2)
        .order_by(VocabularyEntry.frequency.desc())
        .limit(50)
        .all()
    )
    terms = [e.term for e in entries]
    return {"terms": terms, "text": ", ".join(terms)}

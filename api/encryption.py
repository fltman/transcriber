import base64

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.meeting import Meeting
from models.segment import Segment
from models.action import ActionResult
from services.encryption_service import EncryptionService

router = APIRouter(prefix="/api/meetings", tags=["encryption"])


class EncryptRequest(BaseModel):
    password: str
    include_versions: bool = False


class DecryptRequest(BaseModel):
    password: str


@router.post("/{meeting_id}/encrypt")
def encrypt_meeting(meeting_id: str, req: EncryptRequest, db: Session = Depends(get_db)):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    if meeting.is_encrypted:
        raise HTTPException(400, "Meeting is already encrypted")
    if not req.password:
        raise HTTPException(400, "Password is required")

    svc = EncryptionService
    salt = svc.generate_salt()
    salt_b64 = base64.b64encode(salt).decode()
    key = svc.derive_key(req.password, salt)
    verify_token = svc.make_verify_token(key)

    # Encrypt all segment texts
    segments = db.query(Segment).filter(Segment.meeting_id == meeting_id).all()
    for seg in segments:
        if seg.text:
            seg.text = svc.encrypt_text(seg.text, key)
        if seg.original_text:
            seg.original_text = svc.encrypt_text(seg.original_text, key)

    # Optionally encrypt action result texts
    if req.include_versions:
        results = db.query(ActionResult).filter(ActionResult.meeting_id == meeting_id).all()
        for r in results:
            if r.result_text:
                r.result_text = svc.encrypt_text(r.result_text, key)
                r.is_encrypted = True

    meeting.is_encrypted = True
    meeting.encryption_salt = salt_b64
    meeting.encryption_verify = verify_token

    db.commit()
    return meeting.to_dict(include_segments=True)


@router.post("/{meeting_id}/decrypt")
def decrypt_meeting(meeting_id: str, req: DecryptRequest, db: Session = Depends(get_db)):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    if not meeting.is_encrypted:
        raise HTTPException(400, "Meeting is not encrypted")

    svc = EncryptionService
    if not svc.check_password(req.password, meeting.encryption_salt, meeting.encryption_verify):
        raise HTTPException(403, "Wrong password")

    salt = base64.b64decode(meeting.encryption_salt)
    key = svc.derive_key(req.password, salt)

    # Decrypt all segment texts
    segments = db.query(Segment).filter(Segment.meeting_id == meeting_id).all()
    for seg in segments:
        if seg.text:
            seg.text = svc.decrypt_text(seg.text, key)
        if seg.original_text:
            seg.original_text = svc.decrypt_text(seg.original_text, key)

    # Decrypt action result texts
    results = db.query(ActionResult).filter(
        ActionResult.meeting_id == meeting_id,
        ActionResult.is_encrypted == True,
    ).all()
    for r in results:
        if r.result_text:
            r.result_text = svc.decrypt_text(r.result_text, key)
        r.is_encrypted = False

    meeting.is_encrypted = False
    meeting.encryption_salt = None
    meeting.encryption_verify = None

    db.commit()
    return meeting.to_dict(include_segments=True)

import re
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from pydantic import BaseModel

from sqlalchemy import func

from database import get_db
from models import Meeting, MeetingStatus, Speaker, Segment
from models.meeting import MeetingMode, RecordingStatus
from models.job import Job, JobType, JobStatus
from config import get_meeting_path
from tasks.process_meeting import process_meeting_task
from translations import get_translation

router = APIRouter(prefix="/api/meetings", tags=["meetings"])

# Upload constraints
MAX_UPLOAD_SIZE = 5 * 1024 * 1024 * 1024  # 5 GB
ALLOWED_EXTENSIONS = {".mp3", ".wav", ".mp4", ".m4a", ".webm", ".ogg", ".flac", ".aac", ".wma", ".mov", ".avi", ".mkv"}
MAX_TITLE_LENGTH = 500


@router.get("")
def list_meetings(db: Session = Depends(get_db)):
    speaker_counts = (
        db.query(Speaker.meeting_id, func.count().label("count"))
        .group_by(Speaker.meeting_id)
        .subquery()
    )
    segment_counts = (
        db.query(Segment.meeting_id, func.count().label("count"))
        .group_by(Segment.meeting_id)
        .subquery()
    )
    rows = (
        db.query(
            Meeting,
            func.coalesce(speaker_counts.c.count, 0),
            func.coalesce(segment_counts.c.count, 0),
        )
        .outerjoin(speaker_counts, Meeting.id == speaker_counts.c.meeting_id)
        .outerjoin(segment_counts, Meeting.id == segment_counts.c.meeting_id)
        .order_by(Meeting.created_at.desc())
        .all()
    )
    return [m.to_dict(speaker_count=sc, segment_count=sgc) for m, sc, sgc in rows]


@router.post("")
async def create_meeting(
    title: str = Form(...),
    file: UploadFile = File(...),
    min_speakers: int = Form(None),
    max_speakers: int = Form(None),
    vocabulary: str = Form(None),
    db: Session = Depends(get_db),
):
    # Validate title
    title = title.strip()[:MAX_TITLE_LENGTH]
    if not title:
        raise HTTPException(400, get_translation('errors.title_required'))

    # Validate file extension
    filename = file.filename or "upload.mp4"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            get_translation('errors.unsupported_file_type').format(ext=ext, extensions=', '.join(sorted(ALLOWED_EXTENSIONS))),
        )

    # Sanitize filename — strip path components and special characters
    safe_filename = re.sub(r'[^\w.\-]', '_', Path(filename).name)

    # Validate speaker counts
    if min_speakers is not None and min_speakers < 1:
        raise HTTPException(400, get_translation('errors.min_speakers_invalid'))
    if max_speakers is not None and max_speakers < 1:
        raise HTTPException(400, get_translation('errors.max_speakers_invalid'))
    if min_speakers and max_speakers and min_speakers > max_speakers:
        raise HTTPException(400, get_translation('errors.min_max_speakers_order'))

    # Use global default vocabulary if none provided
    from preferences import load_preferences
    effective_vocab = vocabulary.strip()[:2000] if vocabulary else None
    if not effective_vocab:
        prefs = load_preferences()
        default_vocab = prefs.get("default_vocabulary", "")
        if default_vocab:
            effective_vocab = default_vocab

    meeting = Meeting(
        title=title,
        original_filename=safe_filename,
        status=MeetingStatus.UPLOADED,
        min_speakers=min_speakers,
        max_speakers=max_speakers,
        vocabulary=effective_vocab,
    )
    db.add(meeting)
    db.flush()

    # Save uploaded file with size limit
    meeting_dir = get_meeting_path(meeting.id)
    upload_path = str(meeting_dir / f"original{ext}")

    total_size = 0
    with open(upload_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            total_size += len(chunk)
            if total_size > MAX_UPLOAD_SIZE:
                # Clean up partial file
                f.close()
                Path(upload_path).unlink(missing_ok=True)
                shutil.rmtree(meeting_dir, ignore_errors=True)
                db.rollback()
                raise HTTPException(413, get_translation('errors.file_too_large').format(max_gb=MAX_UPLOAD_SIZE // (1024**3)))
            f.write(chunk)

    meeting.audio_filepath = upload_path
    db.commit()

    return meeting.to_dict()


@router.get("/{meeting_id}")
def get_meeting(meeting_id: str, db: Session = Depends(get_db)):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(404, get_translation('errors.meeting_not_found'))
    return meeting.to_dict(include_segments=True)


@router.delete("/{meeting_id}")
def delete_meeting(meeting_id: str, db: Session = Depends(get_db)):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(404, get_translation('errors.meeting_not_found'))

    # Clean up files
    meeting_dir = get_meeting_path(meeting_id)
    if meeting_dir.exists():
        shutil.rmtree(meeting_dir)

    db.delete(meeting)
    db.commit()
    return {"ok": True}


@router.post("/{meeting_id}/process")
def start_processing(meeting_id: str, db: Session = Depends(get_db)):
    from sqlalchemy import update

    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(404, get_translation('errors.meeting_not_found'))

    if meeting.status == MeetingStatus.PROCESSING:
        raise HTTPException(400, get_translation('errors.already_processing'))

    # Atomic status transition to prevent duplicate processing
    rows = db.execute(
        update(Meeting)
        .where(Meeting.id == meeting_id)
        .where(Meeting.status != MeetingStatus.PROCESSING)
        .values(status=MeetingStatus.PROCESSING)
    )
    if rows.rowcount == 0:
        db.rollback()
        raise HTTPException(409, get_translation('errors.meeting_already_processing'))

    # Create job
    job = Job(
        meeting_id=meeting.id,
        job_type=JobType.PROCESS_MEETING,
        status=JobStatus.PENDING,
    )
    db.add(job)
    db.commit()

    # Queue task
    result = process_meeting_task.delay(meeting.id, job.id)
    job.celery_task_id = result.id
    db.commit()

    return job.to_dict()


class LiveMeetingRequest(BaseModel):
    title: str
    vocabulary: str | None = None


@router.post("/live")
def create_live_meeting(req: LiveMeetingRequest, db: Session = Depends(get_db)):
    # Use global default vocabulary if none provided
    from preferences import load_preferences
    effective_vocab = req.vocabulary.strip()[:2000] if req.vocabulary else None
    if not effective_vocab:
        prefs = load_preferences()
        default_vocab = prefs.get("default_vocabulary", "")
        if default_vocab:
            effective_vocab = default_vocab

    meeting = Meeting(
        title=req.title,
        status=MeetingStatus.RECORDING,
        mode=MeetingMode.LIVE.value,
        recording_status=RecordingStatus.RECORDING.value,
        vocabulary=effective_vocab,
    )
    db.add(meeting)
    db.commit()

    # Create meeting storage directory
    get_meeting_path(meeting.id)

    return meeting.to_dict()


@router.post("/{meeting_id}/rediarize")
def rediarize_meeting(meeting_id: str, db: Session = Depends(get_db)):
    """Re-run diarization without re-transcribing."""
    from sqlalchemy import update as sql_update
    from tasks.reprocess_task import rediarize_task

    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(404, get_translation('errors.meeting_not_found'))
    if meeting.status != MeetingStatus.UPLOADED:
        raise HTTPException(400, get_translation('errors.already_processing'))
    if not meeting.raw_transcription:
        raise HTTPException(400, get_translation('errors.no_transcription_data'))

    rows = db.execute(
        sql_update(Meeting)
        .where(Meeting.id == meeting_id)
        .where(Meeting.status != MeetingStatus.PROCESSING)
        .values(status=MeetingStatus.PROCESSING)
    )
    if rows.rowcount == 0:
        db.rollback()
        raise HTTPException(409, get_translation('errors.meeting_already_processing'))

    job = Job(
        meeting_id=meeting.id,
        job_type=JobType.REDIARIZE,
        status=JobStatus.PENDING,
    )
    db.add(job)
    db.commit()

    result = rediarize_task.delay(meeting.id, job.id)
    job.celery_task_id = result.id
    db.commit()
    return job.to_dict()


@router.post("/{meeting_id}/reidentify")
def reidentify_meeting(meeting_id: str, db: Session = Depends(get_db)):
    """Re-run speaker identification without re-transcribing or re-diarizing."""
    from sqlalchemy import update as sql_update
    from tasks.reprocess_task import reidentify_task

    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(404, get_translation('errors.meeting_not_found'))
    if meeting.status == MeetingStatus.PROCESSING:
        raise HTTPException(400, get_translation('errors.already_processing'))
    if not meeting.raw_transcription or not meeting.raw_diarization:
        raise HTTPException(400, get_translation('errors.no_transcription_diarization_data'))

    rows = db.execute(
        sql_update(Meeting)
        .where(Meeting.id == meeting_id)
        .where(Meeting.status != MeetingStatus.PROCESSING)
        .values(status=MeetingStatus.PROCESSING)
    )
    if rows.rowcount == 0:
        db.rollback()
        raise HTTPException(409, get_translation('errors.meeting_already_processing'))

    job = Job(
        meeting_id=meeting.id,
        job_type=JobType.REIDENTIFY,
        status=JobStatus.PENDING,
    )
    db.add(job)
    db.commit()

    result = reidentify_task.delay(meeting.id, job.id)
    job.celery_task_id = result.id
    db.commit()
    return job.to_dict()


@router.get("/{meeting_id}/jobs")
def list_jobs(meeting_id: str, db: Session = Depends(get_db)):
    jobs = db.query(Job).filter(Job.meeting_id == meeting_id).order_by(Job.created_at.desc()).all()
    return [j.to_dict() for j in jobs]

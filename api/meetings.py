import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from pydantic import BaseModel

from database import get_db
from models import Meeting, Job, MeetingStatus
from models.meeting import MeetingMode, RecordingStatus
from models.job import JobType, JobStatus
from config import get_meeting_path
from tasks.process_meeting import process_meeting_task

router = APIRouter(prefix="/api/meetings", tags=["meetings"])


@router.get("")
def list_meetings(db: Session = Depends(get_db)):
    meetings = db.query(Meeting).order_by(Meeting.created_at.desc()).all()
    return [m.to_dict() for m in meetings]


@router.post("")
async def create_meeting(
    title: str = Form(...),
    file: UploadFile = File(...),
    min_speakers: int = Form(None),
    max_speakers: int = Form(None),
    db: Session = Depends(get_db),
):
    meeting = Meeting(
        title=title,
        original_filename=file.filename,
        status=MeetingStatus.UPLOADED,
        min_speakers=min_speakers,
        max_speakers=max_speakers,
    )
    db.add(meeting)
    db.flush()

    # Save uploaded file
    meeting_dir = get_meeting_path(meeting.id)
    ext = Path(file.filename).suffix or ".mp4"
    upload_path = str(meeting_dir / f"original{ext}")

    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    meeting.audio_filepath = upload_path
    db.commit()

    return meeting.to_dict()


@router.get("/{meeting_id}")
def get_meeting(meeting_id: str, db: Session = Depends(get_db)):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    return meeting.to_dict(include_segments=True)


@router.delete("/{meeting_id}")
def delete_meeting(meeting_id: str, db: Session = Depends(get_db)):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(404, "Meeting not found")

    # Clean up files
    meeting_dir = get_meeting_path(meeting_id)
    if meeting_dir.exists():
        shutil.rmtree(meeting_dir)

    db.delete(meeting)
    db.commit()
    return {"ok": True}


@router.post("/{meeting_id}/process")
def start_processing(meeting_id: str, db: Session = Depends(get_db)):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(404, "Meeting not found")

    if meeting.status == MeetingStatus.PROCESSING:
        raise HTTPException(400, "Already processing")

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


@router.post("/live")
def create_live_meeting(req: LiveMeetingRequest, db: Session = Depends(get_db)):
    meeting = Meeting(
        title=req.title,
        status=MeetingStatus.RECORDING,
        mode=MeetingMode.LIVE.value,
        recording_status=RecordingStatus.RECORDING.value,
    )
    db.add(meeting)
    db.commit()

    # Create meeting storage directory
    get_meeting_path(meeting.id)

    return meeting.to_dict()


@router.get("/{meeting_id}/jobs")
def list_jobs(meeting_id: str, db: Session = Depends(get_db)):
    jobs = db.query(Job).filter(Job.meeting_id == meeting_id).order_by(Job.created_at.desc()).all()
    return [j.to_dict() for j in jobs]

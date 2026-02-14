from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Meeting, MeetingInsight, InsightStatus
from models.job import Job, JobType, JobStatus

router = APIRouter(prefix="/api", tags=["insights"])


class UpdateInsightRequest(BaseModel):
    status: str | None = None
    content: str | None = None
    assignee: str | None = None


@router.get("/meetings/{meeting_id}/insights")
def list_insights(meeting_id: str, db: Session = Depends(get_db)):
    insights = (
        db.query(MeetingInsight)
        .filter(MeetingInsight.meeting_id == meeting_id)
        .order_by(MeetingInsight.order)
        .all()
    )
    return [i.to_dict() for i in insights]


@router.post("/meetings/{meeting_id}/extract-insights")
def extract_insights(meeting_id: str, db: Session = Depends(get_db)):
    """Trigger LLM-based extraction of decisions, action items, and open questions."""
    from sqlalchemy import update as sql_update
    from tasks.insights_task import extract_insights_task

    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    if meeting.status.value != "completed":
        raise HTTPException(400, "Meeting must be completed first")

    job = Job(
        meeting_id=meeting.id,
        job_type=JobType.EXTRACT_INSIGHTS,
        status=JobStatus.PENDING,
    )
    db.add(job)
    db.commit()

    result = extract_insights_task.delay(meeting.id, job.id)
    job.celery_task_id = result.id
    db.commit()
    return job.to_dict()


@router.put("/insights/{insight_id}")
def update_insight(insight_id: str, req: UpdateInsightRequest, db: Session = Depends(get_db)):
    insight = db.query(MeetingInsight).filter(MeetingInsight.id == insight_id).first()
    if not insight:
        raise HTTPException(404, "Insight not found")

    if req.status is not None:
        try:
            insight.status = InsightStatus(req.status)
        except ValueError:
            raise HTTPException(400, f"Invalid status: {req.status}")
    if req.content is not None:
        insight.content = req.content.strip()[:2000]
    if req.assignee is not None:
        insight.assignee = req.assignee.strip()[:200] if req.assignee else None

    db.commit()
    return insight.to_dict()


@router.delete("/insights/{insight_id}")
def delete_insight(insight_id: str, db: Session = Depends(get_db)):
    insight = db.query(MeetingInsight).filter(MeetingInsight.id == insight_id).first()
    if not insight:
        raise HTTPException(404, "Insight not found")
    db.delete(insight)
    db.commit()
    return {"ok": True}

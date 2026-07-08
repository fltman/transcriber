import logging
from datetime import datetime

from .celery_app import celery_app
from .shared import publish_event
from database import SessionLocal
from models import Meeting, Segment, Speaker, MeetingInsight, InsightType
from models.job import Job, JobStatus
from services.llm_service import LLMService
from model_config import get_model_config
from translations import get_translation

log = logging.getLogger(__name__)

MAX_TRANSCRIPT_CHARS = 15000


@celery_app.task(bind=True, time_limit=180)
def extract_insights_task(self, meeting_id: str, job_id: str):
    """Extract decisions, action items, and open questions from a meeting transcript."""
    db = SessionLocal()

    try:
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        job = db.query(Job).filter(Job.id == job_id).first()
        if not meeting or not job:
            return {"error": "Meeting or Job not found"}

        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow()
        db.commit()

        # Build transcript
        segments = (
            db.query(Segment)
            .filter(Segment.meeting_id == meeting_id)
            .order_by(Segment.order)
            .all()
        )
        if not segments:
            raise ValueError("No transcript segments found")

        speakers = db.query(Speaker).filter(Speaker.meeting_id == meeting_id).all()
        speaker_map = {s.id: s.display_name or s.label for s in speakers}

        lines = []
        for seg in segments:
            speaker = speaker_map.get(seg.speaker_id, "Unknown") if seg.speaker_id else "Unknown"
            ts = f"{int(seg.start_time // 60)}:{int(seg.start_time % 60):02d}"
            lines.append(f"[{ts}] [{speaker}]: {seg.text}")

        transcript_text = "\n".join(lines)
        truncation_msg = get_translation('ui.transcription_truncated')
        if len(transcript_text) > MAX_TRANSCRIPT_CHARS:
            transcript_text = transcript_text[:MAX_TRANSCRIPT_CHARS] + f"\n\n[...{truncation_msg}...]"

        # Call LLM
        preset = get_model_config().get_model_for_task("actions")
        llm = LLMService(preset=preset)
        messages = [
            {"role": "system", "content": get_translation('prompts.insights_extraction')},
            {"role": "user", "content": f"Motestitel: {meeting.title}\n\nTranskribering:\n{transcript_text}"},
        ]

        response = llm._call(messages, max_tokens=4000)
        data = llm._parse_json(response)

        # Clear previous insights for this meeting
        db.query(MeetingInsight).filter(MeetingInsight.meeting_id == meeting_id).delete()

        order = 0
        for decision in data.get("decisions", []):
            db.add(MeetingInsight(
                meeting_id=meeting_id,
                insight_type=InsightType.DECISION,
                content=decision.get("content", ""),
                source_start_time=decision.get("timestamp"),
                order=order,
            ))
            order += 1

        for item in data.get("action_items", []):
            db.add(MeetingInsight(
                meeting_id=meeting_id,
                insight_type=InsightType.ACTION_ITEM,
                content=item.get("content", ""),
                assignee=item.get("assignee"),
                source_start_time=item.get("timestamp"),
                order=order,
            ))
            order += 1

        for question in data.get("open_questions", []):
            db.add(MeetingInsight(
                meeting_id=meeting_id,
                insight_type=InsightType.OPEN_QUESTION,
                content=question.get("content", ""),
                source_start_time=question.get("timestamp"),
                order=order,
            ))
            order += 1

        job.status = JobStatus.COMPLETED
        job.progress = 100
        job.current_step = "Klar!"
        job.completed_at = datetime.utcnow()
        db.commit()

        publish_event(meeting_id, {
            "type": "insights_completed",
            "count": order,
        })

        log.info(f"Extracted {order} insights from meeting {meeting_id}")
        return {"status": "completed", "count": order}

    except Exception as e:
        db.rollback()
        log.error(f"Insights extraction failed: {e}")
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = JobStatus.FAILED
                job.error = str(e)
                job.completed_at = datetime.utcnow()
                db.commit()
        except Exception:
            pass
        return {"error": str(e)}

    finally:
        db.close()

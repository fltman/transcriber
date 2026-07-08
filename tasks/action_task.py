import logging
from datetime import datetime

from .celery_app import celery_app
from .shared import publish_event
from database import SessionLocal
from models import Meeting, Segment, Speaker, Action, ActionResult, ActionResultStatus
from services.llm_service import LLMService
from model_config import get_model_config
from translations import get_translation

log = logging.getLogger(__name__)

MAX_TRANSCRIPT_CHARS = 15000


@celery_app.task(bind=True, time_limit=180)
def run_action_task(self, action_result_id: str):
    """Execute an action prompt against a meeting transcript."""
    db = SessionLocal()

    try:
        result = db.query(ActionResult).filter(ActionResult.id == action_result_id).first()
        if not result:
            return {"error": get_translation('errors.action_result_not_found')}

        action = db.query(Action).filter(Action.id == result.action_id).first()
        meeting = db.query(Meeting).filter(Meeting.id == result.meeting_id).first()
        if not action or not meeting:
            return {"error": get_translation('errors.action_not_found')}

        result.status = ActionResultStatus.RUNNING
        result.celery_task_id = self.request.id
        db.commit()

        publish_event(meeting.id, {
            "type": "action_running",
            "action_result_id": result.id,
            "action_id": action.id,
            "action_name": action.name,
        })

        # Build transcript text from segments
        segments = (
            db.query(Segment)
            .filter(Segment.meeting_id == meeting.id)
            .order_by(Segment.order)
            .all()
        )

        if not segments:
            raise ValueError(get_translation("errors.no_transcript_segments"))

        # Build speaker lookup
        speakers = db.query(Speaker).filter(Speaker.meeting_id == meeting.id).all()
        speaker_map = {s.id: s.display_name or s.label for s in speakers}

        lines = []
        for seg in segments:
            speaker = (
                speaker_map.get(seg.speaker_id, get_translation("common.unknown_speaker"))
                if seg.speaker_id
                else get_translation("common.unknown_speaker")
            )
            lines.append(f"[{speaker}]: {seg.text}")

        transcript_text = "\n".join(lines)
        if len(transcript_text) > MAX_TRANSCRIPT_CHARS:
            transcript_text = (
                transcript_text[:MAX_TRANSCRIPT_CHARS]
                + f"\n\n[...{get_translation('ui.transcription_truncated')}...]"
            )

        # Call LLM (with model preset for "actions" task)
        preset = get_model_config().get_model_for_task("actions")
        llm = LLMService(preset=preset)
        messages = [
            {
                "role": "system",
                "content": action.prompt,
            },
            {
                "role": "user",
                "content": (
                    f"{get_translation('ui.meeting')}: {meeting.title}\n\n"
                    f"{get_translation('labels.protocol_transcript')}:\n{transcript_text}"
                ),
            },
        ]

        llm_response = llm._call(messages, max_tokens=4000)

        result.status = ActionResultStatus.COMPLETED
        result.result_text = llm_response
        result.completed_at = datetime.utcnow()
        db.commit()

        publish_event(meeting.id, {
            "type": "action_completed",
            "action_result_id": result.id,
            "action_id": action.id,
            "action_name": action.name,
        })

        log.info(f"Action '{action.name}' completed for meeting {meeting.id}")
        return {"status": "completed", "action_result_id": result.id}

    except Exception as e:
        db.rollback()
        log.error(f"Action task failed: {e}")

        try:
            result = db.query(ActionResult).filter(ActionResult.id == action_result_id).first()
            if result:
                result.status = ActionResultStatus.FAILED
                result.error = str(e)
                result.completed_at = datetime.utcnow()
                db.commit()

                publish_event(result.meeting_id, {
                    "type": "action_failed",
                    "action_result_id": result.id,
                    "action_id": result.action_id,
                    "error": str(e),
                })
        except Exception:
            pass

        return {"status": "failed", "error": str(e)}

    finally:
        db.close()

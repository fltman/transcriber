import json
import logging

import redis

from config import settings
from models import Job, Meeting

log = logging.getLogger(__name__)

# Module-level Redis connection pool (reused across all publish calls)
_redis_pool = redis.ConnectionPool.from_url(settings.redis_url)


def update_progress(db, job: Job, meeting: Meeting, progress: float, step: str):
    """Update job progress and broadcast via Redis pub/sub."""
    job.progress = progress
    job.current_step = step
    db.commit()

    publish_event(meeting.id, {
        "type": "progress",
        "progress": progress,
        "step": step,
        "status": meeting.status.value,
    })


def publish_event(meeting_id: str, data: dict):
    """Publish an event to Redis pub/sub for a meeting."""
    r = redis.Redis(connection_pool=_redis_pool)
    r.publish(f"meeting:{meeting_id}", json.dumps(data))


def align_segments(whisper_segments: list[dict], diarization_segments: list[dict]) -> list[dict]:
    """
    Match whisper transcript segments to diarization speaker segments
    by maximum time overlap.
    """
    aligned = []
    for ws in whisper_segments:
        ws_start, ws_end = ws["start"], ws["end"]
        ws_mid = (ws_start + ws_end) / 2

        best_speaker = None
        best_overlap = 0

        for ds in diarization_segments:
            overlap_start = max(ws_start, ds["start"])
            overlap_end = min(ws_end, ds["end"])
            overlap = max(0, overlap_end - overlap_start)

            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = ds["speaker"]

        # Fallback: find speaker whose segment contains the midpoint
        if best_speaker is None:
            for ds in diarization_segments:
                if ds["start"] <= ws_mid <= ds["end"]:
                    best_speaker = ds["speaker"]
                    break

        aligned.append({
            "start": ws_start,
            "end": ws_end,
            "text": ws["text"],
            "speaker": best_speaker or "UNKNOWN",
        })

    return aligned

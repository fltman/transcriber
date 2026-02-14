from fastapi import APIRouter, Depends, Query
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from database import get_db

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search")
def search_segments(
    q: str = Query(..., min_length=1, max_length=200),
    db: Session = Depends(get_db),
):
    """Full-text search across all meeting segments.

    Uses PostgreSQL tsvector for efficient matching. Returns segments
    grouped by meeting with context (speaker name, timestamps).
    """
    # Use plainto_tsquery for safe user input (no special syntax needed)
    # Also fall back to ILIKE for partial word matching
    results = db.execute(
        sa_text("""
            SELECT
                s.id, s.meeting_id, s.start_time, s.end_time, s.text, s."order",
                m.title AS meeting_title,
                sp.display_name AS speaker_name,
                sp.color AS speaker_color,
                ts_rank(to_tsvector('simple', s.text), plainto_tsquery('simple', :q)) AS rank
            FROM segments s
            JOIN meetings m ON m.id = s.meeting_id
            LEFT JOIN speakers sp ON sp.id = s.speaker_id
            WHERE to_tsvector('simple', s.text) @@ plainto_tsquery('simple', :q)
               OR s.text ILIKE :like_q
            ORDER BY rank DESC, m.created_at DESC, s."order"
            LIMIT 100
        """),
        {"q": q, "like_q": f"%{q}%"},
    )

    rows = results.fetchall()

    # Group by meeting
    meetings_map: dict[str, dict] = {}
    for row in rows:
        mid = row.meeting_id
        if mid not in meetings_map:
            meetings_map[mid] = {
                "meeting_id": mid,
                "meeting_title": row.meeting_title,
                "segments": [],
            }
        meetings_map[mid]["segments"].append({
            "id": row.id,
            "start_time": row.start_time,
            "end_time": row.end_time,
            "text": row.text,
            "order": row.order,
            "speaker_name": row.speaker_name,
            "speaker_color": row.speaker_color,
        })

    return list(meetings_map.values())

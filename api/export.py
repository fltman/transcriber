from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse
from sqlalchemy.orm import Session

from database import get_db
from models import Meeting, Segment

router = APIRouter(prefix="/api/meetings", tags=["export"])


def format_srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def format_vtt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


@router.get("/{meeting_id}/export")
def export_meeting(
    meeting_id: str,
    format: str = "srt",
    db: Session = Depends(get_db),
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(404, "Meeting not found")

    segments = (
        db.query(Segment)
        .filter(Segment.meeting_id == meeting_id)
        .order_by(Segment.order)
        .all()
    )

    if format == "srt":
        return _export_srt(meeting, segments)
    elif format == "vtt":
        return _export_vtt(meeting, segments)
    elif format == "txt":
        return _export_txt(meeting, segments)
    elif format == "json":
        return _export_json(meeting, segments)
    else:
        raise HTTPException(400, f"Unknown format: {format}")


def _export_srt(meeting: Meeting, segments: list[Segment]) -> PlainTextResponse:
    lines = []
    for i, seg in enumerate(segments, 1):
        speaker = seg.speaker.display_name if seg.speaker else "Okand"
        lines.append(str(i))
        lines.append(f"{format_srt_time(seg.start_time)} --> {format_srt_time(seg.end_time)}")
        lines.append(f"[{speaker}] {seg.text}")
        lines.append("")

    content = "\n".join(lines)
    return PlainTextResponse(
        content,
        headers={
            "Content-Disposition": f'attachment; filename="{meeting.title}.srt"',
        },
    )


def _export_vtt(meeting: Meeting, segments: list[Segment]) -> PlainTextResponse:
    lines = ["WEBVTT", ""]
    for seg in segments:
        speaker = seg.speaker.display_name if seg.speaker else "Okand"
        lines.append(f"{format_vtt_time(seg.start_time)} --> {format_vtt_time(seg.end_time)}")
        lines.append(f"<v {speaker}>{seg.text}")
        lines.append("")

    content = "\n".join(lines)
    return PlainTextResponse(
        content,
        headers={
            "Content-Disposition": f'attachment; filename="{meeting.title}.vtt"',
        },
    )


def _export_txt(meeting: Meeting, segments: list[Segment]) -> PlainTextResponse:
    lines = []
    current_speaker = None
    for seg in segments:
        speaker = seg.speaker.display_name if seg.speaker else "Okand"
        if speaker != current_speaker:
            if lines:
                lines.append("")
            lines.append(f"{speaker}:")
            current_speaker = speaker
        lines.append(f"  {seg.text}")

    content = "\n".join(lines)
    return PlainTextResponse(
        content,
        headers={
            "Content-Disposition": f'attachment; filename="{meeting.title}.txt"',
        },
    )


def _export_json(meeting: Meeting, segments: list[Segment]) -> JSONResponse:
    data = {
        "meeting": {
            "title": meeting.title,
            "duration": meeting.duration,
        },
        "segments": [
            {
                "start": seg.start_time,
                "end": seg.end_time,
                "speaker": seg.speaker.display_name if seg.speaker else "Okand",
                "text": seg.text,
            }
            for seg in segments
        ],
    }
    return JSONResponse(
        data,
        headers={
            "Content-Disposition": f'attachment; filename="{meeting.title}.json"',
        },
    )

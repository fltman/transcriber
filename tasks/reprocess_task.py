from datetime import datetime

from .celery_app import celery_app
from .shared import update_progress, align_segments, publish_event
from database import SessionLocal
from models import Meeting, Speaker, Segment, Job, MeetingStatus
from models.job import JobStatus
from services.diarization_service import DiarizationService
from services.speaker_id_service import SpeakerIdService
from model_config import get_model_config


@celery_app.task(bind=True)
def rediarize_task(self, meeting_id: str, job_id: str):
    """Re-run diarization and speaker alignment without re-transcribing.

    Uses existing raw_transcription from the meeting, runs fresh diarization,
    and re-aligns. Preserves manually edited segment text.
    """
    db = SessionLocal()
    try:
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        job = db.query(Job).filter(Job.id == job_id).first()
        if not meeting or not job:
            return {"error": "Meeting or Job not found"}

        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow()
        meeting.status = MeetingStatus.PROCESSING
        db.commit()

        whisper_segments = meeting.raw_transcription
        if not whisper_segments:
            raise RuntimeError("No existing transcription found. Run full processing first.")

        audio_path = meeting.audio_filepath
        if not audio_path:
            raise RuntimeError("No audio file found.")

        analysis_preset = get_model_config().get_model_for_task("analysis")
        diarization_service = DiarizationService()
        speaker_id_service = SpeakerIdService(llm_preset=analysis_preset)

        # Step 1: Fresh diarization
        update_progress(db, job, meeting, 10, "Kör ny talaridentifiering...")
        diarization_segments = diarization_service.diarize(
            audio_path,
            min_speakers=meeting.min_speakers,
            max_speakers=meeting.max_speakers,
        )
        meeting.raw_diarization = diarization_segments
        db.commit()
        update_progress(db, job, meeting, 50, "Diarization klar")

        # Step 2: Re-align
        update_progress(db, job, meeting, 55, "Synkroniserar talare med text...")
        aligned = align_segments(whisper_segments, diarization_segments)

        # Step 3: Speaker identification
        update_progress(db, job, meeting, 65, "Identifierar talare...")
        speaker_labels = list(set(s["speaker"] for s in aligned if s["speaker"] != "UNKNOWN"))
        speaker_info = {}

        if speaker_id_service.has_intro(aligned):
            speaker_info = speaker_id_service.identify_speakers_model2(
                aligned, audio_path, diarization_segments
            )

        unidentified = [l for l in speaker_labels if l not in speaker_info]
        if unidentified:
            fallback = speaker_id_service.identify_speakers_model3(unidentified)
            offset = len(speaker_info)
            for i, (label, info) in enumerate(fallback.items()):
                if offset > 0:
                    info["name"] = f"Deltagare {offset + i + 1}"
                speaker_info[label] = info

        # Step 4: Collect edits, recreate speakers + segments
        update_progress(db, job, meeting, 85, "Sparar resultat...")
        _rebuild_speakers_and_segments(db, meeting, aligned, speaker_info, speaker_id_service)

        meeting.status = MeetingStatus.COMPLETED
        job.status = JobStatus.COMPLETED
        job.progress = 100
        job.current_step = "Klar!"
        job.completed_at = datetime.utcnow()
        db.commit()
        update_progress(db, job, meeting, 100, "Klar!")
        return {"status": "completed", "meeting_id": meeting_id}

    except Exception as e:
        db.rollback()
        _fail_job(db, meeting_id, job_id, str(e))
        return {"error": str(e)}
    finally:
        db.close()


@celery_app.task(bind=True)
def reidentify_task(self, meeting_id: str, job_id: str):
    """Re-run speaker identification without re-transcribing or re-diarizing.

    Uses existing raw_transcription and raw_diarization, re-aligns, and
    re-identifies speakers via LLM. Preserves edited segment text.
    """
    db = SessionLocal()
    try:
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        job = db.query(Job).filter(Job.id == job_id).first()
        if not meeting or not job:
            return {"error": "Meeting or Job not found"}

        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow()
        meeting.status = MeetingStatus.PROCESSING
        db.commit()

        whisper_segments = meeting.raw_transcription
        diarization_segments = meeting.raw_diarization
        if not whisper_segments or not diarization_segments:
            raise RuntimeError("No existing transcription/diarization found. Run full processing first.")

        audio_path = meeting.audio_filepath
        if not audio_path:
            raise RuntimeError("No audio file found.")

        analysis_preset = get_model_config().get_model_for_task("analysis")
        speaker_id_service = SpeakerIdService(llm_preset=analysis_preset)

        # Step 1: Re-align (uses existing data)
        update_progress(db, job, meeting, 20, "Synkroniserar talare med text...")
        aligned = align_segments(whisper_segments, diarization_segments)

        # Step 2: Re-identify speakers via LLM
        update_progress(db, job, meeting, 40, "Identifierar talare med AI...")
        speaker_labels = list(set(s["speaker"] for s in aligned if s["speaker"] != "UNKNOWN"))
        speaker_info = {}

        if speaker_id_service.has_intro(aligned):
            speaker_info = speaker_id_service.identify_speakers_model2(
                aligned, audio_path, diarization_segments
            )

        unidentified = [l for l in speaker_labels if l not in speaker_info]
        if unidentified:
            fallback = speaker_id_service.identify_speakers_model3(unidentified)
            offset = len(speaker_info)
            for i, (label, info) in enumerate(fallback.items()):
                if offset > 0:
                    info["name"] = f"Deltagare {offset + i + 1}"
                speaker_info[label] = info

        # Step 3: Rebuild
        update_progress(db, job, meeting, 80, "Sparar resultat...")
        _rebuild_speakers_and_segments(db, meeting, aligned, speaker_info, speaker_id_service)

        meeting.status = MeetingStatus.COMPLETED
        job.status = JobStatus.COMPLETED
        job.progress = 100
        job.current_step = "Klar!"
        job.completed_at = datetime.utcnow()
        db.commit()
        update_progress(db, job, meeting, 100, "Klar!")
        return {"status": "completed", "meeting_id": meeting_id}

    except Exception as e:
        db.rollback()
        _fail_job(db, meeting_id, job_id, str(e))
        return {"error": str(e)}
    finally:
        db.close()


def _rebuild_speakers_and_segments(db, meeting, aligned, speaker_info, speaker_id_service):
    """Shared logic: preserve edits, delete old data, create new speakers + segments."""
    EDIT_TIME_TOLERANCE = 1.5

    existing_segments = (
        db.query(Segment)
        .filter(Segment.meeting_id == meeting.id)
        .order_by(Segment.order)
        .all()
    )
    edited_segments = [
        {"start": s.start_time, "end": s.end_time, "text": s.text}
        for s in existing_segments if s.is_edited
    ]

    db.query(Segment).filter(Segment.meeting_id == meeting.id).delete()
    db.query(Speaker).filter(Speaker.meeting_id == meeting.id).delete()
    db.commit()

    speaker_map = {}
    for i, (label, info) in enumerate(sorted(speaker_info.items())):
        speaker = Speaker(
            meeting_id=meeting.id,
            label=label,
            display_name=info["name"],
            color=speaker_id_service.get_color(i),
            identified_by=info.get("identified_by"),
            confidence=info.get("confidence"),
        )
        db.add(speaker)
        db.flush()
        speaker_map[label] = speaker

    if any(s["speaker"] == "UNKNOWN" for s in aligned):
        unk = Speaker(
            meeting_id=meeting.id,
            label="UNKNOWN",
            display_name="Okand",
            color="#9ca3af",
        )
        db.add(unk)
        db.flush()
        speaker_map["UNKNOWN"] = unk

    for i, seg in enumerate(aligned):
        speaker = speaker_map.get(seg["speaker"])
        text = seg["text"]
        is_edited = False

        for edited in edited_segments:
            if (abs(seg["start"] - edited["start"]) < EDIT_TIME_TOLERANCE
                    and abs(seg["end"] - edited["end"]) < EDIT_TIME_TOLERANCE):
                text = edited["text"]
                is_edited = True
                break

        segment = Segment(
            meeting_id=meeting.id,
            speaker_id=speaker.id if speaker else None,
            start_time=seg["start"],
            end_time=seg["end"],
            text=text,
            original_text=seg["text"],
            order=i,
            is_edited=is_edited,
        )
        db.add(segment)

    for spk in speaker_map.values():
        segs = [s for s in aligned if s["speaker"] == spk.label]
        spk.segment_count = len(segs)
        spk.total_speaking_time = sum(s["end"] - s["start"] for s in segs)

    db.commit()


def _fail_job(db, meeting_id, job_id, error_msg):
    """Mark job and meeting as failed."""
    job = db.query(Job).filter(Job.id == job_id).first()
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if job:
        job.status = JobStatus.FAILED
        job.error = error_msg
        job.completed_at = datetime.utcnow()
    if meeting:
        meeting.status = MeetingStatus.FAILED
    db.commit()
    try:
        publish_event(meeting_id, {"type": "error", "error": error_msg})
    except Exception:
        pass

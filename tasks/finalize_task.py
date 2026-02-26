import json
from datetime import datetime

from .celery_app import celery_app
from .shared import update_progress, align_segments, publish_event
from database import SessionLocal
from models import Meeting, Speaker, Segment, Job, MeetingStatus
from models.meeting import RecordingStatus
from models.job import JobStatus
from services.audio_service import AudioService
from services.whisper_service import WhisperService
from services.diarization_service import DiarizationService
from services.speaker_id_service import SpeakerIdService
from config import get_meeting_path
from model_config import get_model_config


@celery_app.task(bind=True)
def finalize_live_task(self, meeting_id: str, job_id: str):
    """
    Final full-quality pipeline for live recording:
    Re-transcribe with medium model, full diarization, speaker ID.
    Preserves is_edited segments.
    """
    db = SessionLocal()

    try:
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        job = db.query(Job).filter(Job.id == job_id).first()

        if not meeting or not job:
            return {"error": "Meeting or Job not found"}

        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow()
        meeting.status = MeetingStatus.FINALIZING
        meeting.recording_status = RecordingStatus.FINALIZING.value
        db.commit()

        publish_event(meeting_id, {
            "type": "finalize_started",
            "message": "Finalizing transcription with high-quality model...",
        })

        meeting_path = get_meeting_path(meeting_id)
        audio_path = str(meeting_path / "audio.wav")
        meeting.audio_filepath = audio_path

        audio_service = AudioService()
        whisper_service = WhisperService()
        diarization_service = DiarizationService()
        analysis_preset = get_model_config().get_model_for_task("analysis")
        speaker_id_service = SpeakerIdService(llm_preset=analysis_preset)

        # Get duration
        update_progress(db, job, meeting, 5, "Beräknar ljudlängd...")
        duration = audio_service.get_duration(audio_path)
        meeting.duration = duration
        db.commit()

        # Step 1: Re-transcribe with medium (high-quality) model
        update_progress(db, job, meeting, 10, "Transkriberar med högkvalitetsmodell...")
        whisper_segments = whisper_service.transcribe(audio_path, vocabulary=meeting.vocabulary)
        meeting.raw_transcription = whisper_segments
        db.commit()
        update_progress(db, job, meeting, 40, "Transkribering klar")

        # Step 2: LLM intro analysis
        min_speakers = meeting.min_speakers
        max_speakers = meeting.max_speakers

        if not min_speakers:
            update_progress(db, job, meeting, 42, "Analyserar presentationsfas med AI...")
            from services.llm_service import LLMService
            llm = LLMService(preset=analysis_preset)

            intro_result = llm.analyze_intro_iteratively(whisper_segments)
            if intro_result["speaker_count"] > 0:
                min_speakers = intro_result["speaker_count"]
                max_speakers = max_speakers or min_speakers + 1
                meeting.intro_end_time = intro_result["intro_end_time"]

        # Step 3: Full diarization
        update_progress(db, job, meeting, 50, "Fullständig talaridentifiering...")
        diarization_segments = diarization_service.diarize(
            audio_path,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
        )
        meeting.raw_diarization = diarization_segments
        db.commit()
        update_progress(db, job, meeting, 70, "Diarization klar")

        # Step 4: Alignment
        update_progress(db, job, meeting, 72, "Synkroniserar talare med text...")
        aligned = align_segments(whisper_segments, diarization_segments)

        # Step 5: Speaker identification
        update_progress(db, job, meeting, 80, "Identifierar talare...")
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

        update_progress(db, job, meeting, 90, "Sparar slutgiltigt resultat...")

        # Step 6: Collect edited segments before cleanup
        existing_segments = (
            db.query(Segment)
            .filter(Segment.meeting_id == meeting_id)
            .order_by(Segment.order)
            .all()
        )
        edited_segments = [
            {"start": s.start_time, "end": s.end_time, "text": s.text}
            for s in existing_segments if s.is_edited
        ]

        # Delete old segments and speakers
        db.query(Segment).filter(Segment.meeting_id == meeting_id).delete()
        db.query(Speaker).filter(Speaker.meeting_id == meeting_id).delete()
        db.commit()

        # Create new speakers
        speaker_map = {}
        for i, (label, info) in enumerate(sorted(speaker_info.items())):
            speaker = Speaker(
                meeting_id=meeting_id,
                label=label,
                display_name=info["name"],
                color=speaker_id_service.get_color(i),
                identified_by=info.get("identified_by"),
                confidence=info.get("confidence"),
            )
            db.add(speaker)
            db.flush()
            speaker_map[label] = speaker

        # Handle UNKNOWN
        if any(s["speaker"] == "UNKNOWN" for s in aligned):
            unk = Speaker(
                meeting_id=meeting_id,
                label="UNKNOWN",
                display_name="Okand",
                color="#9ca3af",
            )
            db.add(unk)
            db.flush()
            speaker_map["UNKNOWN"] = unk

        # Create new segments, preserving edits
        EDIT_TIME_TOLERANCE = 1.5  # seconds — tolerates Whisper re-timing drift
        for i, seg in enumerate(aligned):
            speaker = speaker_map.get(seg["speaker"])
            text = seg["text"]
            is_edited = False

            # Check if this segment was edited (match by time-window tolerance)
            for edited in edited_segments:
                if (abs(seg["start"] - edited["start"]) < EDIT_TIME_TOLERANCE
                        and abs(seg["end"] - edited["end"]) < EDIT_TIME_TOLERANCE):
                    text = edited["text"]
                    is_edited = True
                    break

            segment = Segment(
                meeting_id=meeting_id,
                speaker_id=speaker.id if speaker else None,
                start_time=seg["start"],
                end_time=seg["end"],
                text=text,
                original_text=seg["text"],
                order=i,
                is_edited=is_edited,
            )
            db.add(segment)

        # Update speaker stats
        for spk in speaker_map.values():
            segs = [s for s in aligned if s["speaker"] == spk.label]
            spk.segment_count = len(segs)
            spk.total_speaking_time = sum(s["end"] - s["start"] for s in segs)

        # Mark complete
        meeting.status = MeetingStatus.COMPLETED
        meeting.recording_status = RecordingStatus.COMPLETE.value
        job.status = JobStatus.COMPLETED
        job.progress = 100
        job.current_step = "Klar!"
        job.completed_at = datetime.utcnow()
        db.commit()

        publish_event(meeting_id, {
            "type": "finalize_complete",
            "progress": 100,
            "step": "Klar!",
        })

        return {"status": "completed", "meeting_id": meeting_id}

    except Exception as e:
        import traceback, logging
        logging.getLogger(__name__).error(f"finalize_live_task failed: {e}\n{traceback.format_exc()}")
        db.rollback()
        job = db.query(Job).filter(Job.id == job_id).first()
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if job:
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.utcnow()
        if meeting:
            meeting.status = MeetingStatus.FAILED
        db.commit()

        try:
            publish_event(meeting_id, {"type": "error", "error": str(e)})
        except Exception:
            pass

        return {"error": str(e)}

    finally:
        db.close()

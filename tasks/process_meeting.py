import json
import logging
from datetime import datetime

log = logging.getLogger(__name__)

from celery.exceptions import SoftTimeLimitExceeded

from .celery_app import celery_app
from .shared import update_progress, align_segments, publish_event
from database import SessionLocal
from models import Meeting, Speaker, Segment, Job, MeetingStatus
from models.job import JobStatus, JobType
from services.audio_service import AudioService
from services.whisper_service import WhisperService
from services.diarization_service import DiarizationService
from services.speaker_id_service import SpeakerIdService
from model_config import get_model_config
from preferences import load_preferences


@celery_app.task(bind=True)
def process_meeting_task(self, meeting_id: str, job_id: str):
    """Main pipeline: audio extraction -> diarization -> transcription -> alignment -> speaker ID."""
    db = SessionLocal()

    try:
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        job = db.query(Job).filter(Job.id == job_id).first()

        if not meeting or not job:
            return {"error": "Meeting or Job not found"}

        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow()
        meeting.status = MeetingStatus.PROCESSING

        # Clean up previous results for reprocessing
        db.query(Segment).filter(Segment.meeting_id == meeting_id).delete()
        db.query(Speaker).filter(Speaker.meeting_id == meeting_id).delete()
        db.commit()

        audio_service = AudioService()
        whisper_service = WhisperService()
        diarization_service = DiarizationService()
        analysis_preset = get_model_config().get_model_for_task("analysis")
        speaker_id_service = SpeakerIdService(llm_preset=analysis_preset)

        # Step 1: Extract audio
        update_progress(db, job, meeting, 2, "Extraherar ljud...")
        audio_path = audio_service.extract_audio(
            meeting.audio_filepath, meeting.id
        )
        duration = audio_service.get_duration(audio_path)
        meeting.duration = duration
        meeting.audio_filepath = audio_path
        db.commit()
        update_progress(db, job, meeting, 5, "Ljud extraherat")

        # Step 2: Transcription (before diarization so LLM can count speakers)
        update_progress(db, job, meeting, 7, "Transkriberar med Whisper...")
        whisper_segments = whisper_service.transcribe(audio_path, vocabulary=meeting.vocabulary)
        meeting.raw_transcription = whisper_segments
        db.commit()
        update_progress(db, job, meeting, 35, "Transkribering klar")

        # Step 3: Iterative intro analysis - LLM reads chunks until intro is over
        min_speakers = meeting.min_speakers
        max_speakers = meeting.max_speakers

        if not min_speakers:
            update_progress(db, job, meeting, 37, "Analyserar presentationsfas med AI...")
            from services.llm_service import LLMService
            llm = LLMService(preset=analysis_preset)

            def on_llm_progress(step_text):
                update_progress(db, job, meeting, 38, step_text)

            intro_result = llm.analyze_intro_iteratively(
                whisper_segments,
                on_progress=on_llm_progress,
            )

            if intro_result["speaker_count"] > 0:
                min_speakers = intro_result["speaker_count"]
                max_speakers = max_speakers or min_speakers + 1
                meeting.intro_end_time = intro_result["intro_end_time"]
                names_str = ", ".join(intro_result["names"])
                update_progress(db, job, meeting, 40,
                    f"Hittade {min_speakers} deltagare ({names_str}), "
                    f"intro slutade vid {intro_result['intro_end_time']:.0f}s")

        # Step 4: Diarization (with speaker count from LLM)
        update_progress(db, job, meeting, 42, "Identifierar talare (diarization)...")
        diarization_segments = diarization_service.diarize(
            audio_path,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
        )
        meeting.raw_diarization = diarization_segments
        db.commit()
        update_progress(db, job, meeting, 65, "Diarization klar")

        # Step 5: Alignment
        update_progress(db, job, meeting, 67, "Synkroniserar talare med text...")
        aligned = align_segments(whisper_segments, diarization_segments)
        update_progress(db, job, meeting, 75, "Synkronisering klar")

        # Step 6: Speaker identification
        update_progress(db, job, meeting, 77, "Identifierar talare...")

        speaker_labels = list(set(s["speaker"] for s in aligned if s["speaker"] != "UNKNOWN"))
        speaker_info = {}

        if speaker_id_service.has_intro(aligned):
            update_progress(db, job, meeting, 80, "Analyserar presentationer med AI...")
            speaker_info = speaker_id_service.identify_speakers_model2(
                aligned, audio_path, diarization_segments
            )

        # Fill in any speakers not identified by Model 2
        unidentified = [l for l in speaker_labels if l not in speaker_info]
        if unidentified:
            fallback = speaker_id_service.identify_speakers_model3(unidentified)
            # Number fallback speakers starting after identified count
            offset = len(speaker_info)
            for i, (label, info) in enumerate(fallback.items()):
                if offset > 0:
                    info["name"] = f"Deltagare {offset + i + 1}"
                speaker_info[label] = info

        # Step 6b: Match against saved speaker profiles (if enabled)
        prefs = load_preferences()
        profiles = []
        if prefs.get("speaker_profiles_enabled", True):
            update_progress(db, job, meeting, 87, "Matchar mot sparade röstprofiler...")
            from models.speaker_profile import SpeakerProfile
            from services.embedding_service import EmbeddingService
            profiles = db.query(SpeakerProfile).all()
        if profiles:
            embedding_service = EmbeddingService()
            PROFILE_MATCH_THRESHOLD = 0.55

            for label, info in speaker_info.items():
                # Only try profile matching for speakers not already identified by intro/LLM
                if info.get("identified_by") == "intro_llm" and info.get("confidence", 0) > 0.7:
                    continue

                # Extract embedding for this speaker from their segments
                speaker_segs = [s for s in diarization_segments if s["speaker"] == label]
                if not speaker_segs:
                    continue

                # Use the longest segment for best embedding quality
                best_seg = max(speaker_segs, key=lambda s: s["end"] - s["start"])
                if best_seg["end"] - best_seg["start"] < 2.0:
                    continue

                try:
                    import subprocess, wave
                    from pathlib import Path

                    temp_spk = str(Path(audio_path).parent / f"profile_match_{label}.wav")
                    subprocess.run([
                        "ffmpeg", "-y",
                        "-ss", str(best_seg["start"]),
                        "-t", str(min(best_seg["end"] - best_seg["start"], 15)),
                        "-i", audio_path,
                        "-ar", "16000", "-ac", "1",
                        temp_spk,
                    ], capture_output=True, timeout=15)

                    emb = embedding_service.extract_embedding(temp_spk)
                    Path(temp_spk).unlink(missing_ok=True)

                    # Compare against all profiles
                    best_profile = None
                    best_sim = 0.0
                    for profile in profiles:
                        profile_emb = profile.get_embedding()
                        sim = embedding_service.cosine_similarity(emb, profile_emb)
                        if sim > best_sim:
                            best_sim = sim
                            best_profile = profile

                    if best_profile and best_sim >= PROFILE_MATCH_THRESHOLD:
                        info["name"] = best_profile.name
                        info["identified_by"] = "voice_profile"
                        info["confidence"] = round(best_sim, 3)
                except Exception as e:
                    log.debug(f"Profile matching failed for {label}: {e}")

        update_progress(db, job, meeting, 90, "Sparar resultat...")

        # Create speakers in DB
        speaker_map = {}  # label -> Speaker
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

        # Handle UNKNOWN speaker
        if any(s["speaker"] == "UNKNOWN" for s in aligned):
            unknown_speaker = Speaker(
                meeting_id=meeting.id,
                label="UNKNOWN",
                display_name="Okand",  # Swedish for "Unknown"
                color="#9ca3af",
            )
            db.add(unknown_speaker)
            db.flush()
            speaker_map["UNKNOWN"] = unknown_speaker

        # Create segments in DB
        for i, seg in enumerate(aligned):
            speaker = speaker_map.get(seg["speaker"])
            segment = Segment(
                meeting_id=meeting.id,
                speaker_id=speaker.id if speaker else None,
                start_time=seg["start"],
                end_time=seg["end"],
                text=seg["text"],
                original_text=seg["text"],
                order=i,
            )
            db.add(segment)

        # Update speaker stats
        for speaker in speaker_map.values():
            segs = [s for s in aligned if s["speaker"] == speaker.label]
            speaker.segment_count = len(segs)
            speaker.total_speaking_time = sum(s["end"] - s["start"] for s in segs)

        # Mark complete
        meeting.status = MeetingStatus.COMPLETED
        job.status = JobStatus.COMPLETED
        job.progress = 100
        job.current_step = "Klar!"
        job.completed_at = datetime.utcnow()
        db.commit()

        update_progress(db, job, meeting, 100, "Klar!")

        # Auto-extract insights (decisions, action items, open questions)
        try:
            from .insights_task import extract_insights_task
            insights_job = Job(
                meeting_id=meeting_id,
                job_type=JobType.EXTRACT_INSIGHTS,
                status=JobStatus.PENDING,
            )
            db.add(insights_job)
            db.commit()
            extract_insights_task.delay(meeting_id, str(insights_job.id))
            log.info(f"Queued automatic insights extraction for meeting {meeting_id}")
        except Exception as e:
            log.warning(f"Auto insights extraction failed to queue: {e}")

        return {"status": "completed", "meeting_id": meeting_id}

    except SoftTimeLimitExceeded:
        db.rollback()
        error_msg = "Task exceeded time limit (55 minutes). Try a shorter recording."
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
        return {"error": error_msg}

    except Exception as e:
        import traceback
        log.error(f"process_meeting_task failed: {e}\n{traceback.format_exc()}")
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

        # Publish error
        try:
            publish_event(meeting_id, {"type": "error", "error": str(e)})
        except Exception:
            pass

        return {"error": str(e)}

    finally:
        db.close()

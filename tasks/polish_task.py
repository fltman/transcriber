import logging
from datetime import datetime

from .celery_app import celery_app
from .shared import publish_event
from database import SessionLocal
from models import Meeting, Speaker, Segment, Job
from models.job import JobStatus
from model_config import get_model_config

log = logging.getLogger(__name__)

MIN_SEGMENTS_TO_KEEP = 2  # Speakers with fewer segments get merged


@celery_app.task(bind=True)
def polish_pass_task(self, meeting_id: str, job_id: str, pass_number: int):
    """
    Lightweight polish: merge tiny speakers + LLM naming.
    No audio re-clustering — keeps the live session's speaker assignments intact.
    """
    db = SessionLocal()
    start_time = datetime.utcnow()

    try:
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        job = db.query(Job).filter(Job.id == job_id).first()

        if not meeting or not job:
            return {"error": "Meeting or Job not found"}

        job.status = JobStatus.RUNNING
        job.started_at = start_time
        db.commit()

        publish_event(meeting_id, {
            "type": "polish_started",
            "pass_number": pass_number,
        })

        # --- Step 1: Merge tiny speakers into nearest larger speaker ---
        speakers = db.query(Speaker).filter(Speaker.meeting_id == meeting_id).all()
        segments = (
            db.query(Segment)
            .filter(Segment.meeting_id == meeting_id)
            .order_by(Segment.order)
            .all()
        )

        if not segments:
            job.status = JobStatus.COMPLETED
            job.progress = 100
            job.completed_at = datetime.utcnow()
            db.commit()
            return {"status": "completed", "pass_number": pass_number, "note": "no segments"}

        # Count segments per speaker
        spk_segments: dict[str, list] = {}  # speaker_id -> [segment, ...]
        for seg in segments:
            if seg.speaker_id not in spk_segments:
                spk_segments[seg.speaker_id] = []
            spk_segments[seg.speaker_id].append(seg)

        large_speakers = {sid: segs for sid, segs in spk_segments.items()
                          if len(segs) >= MIN_SEGMENTS_TO_KEEP}
        small_speakers = {sid: segs for sid, segs in spk_segments.items()
                          if len(segs) < MIN_SEGMENTS_TO_KEEP}

        merged_count = 0
        if small_speakers and large_speakers:
            # Build time midpoints for large speakers (average of their segments)
            large_midpoints = {}
            for sid, segs in large_speakers.items():
                mids = [((s.start_time or 0) + (s.end_time or 0)) / 2 for s in segs]
                large_midpoints[sid] = mids

            for small_sid, small_segs in small_speakers.items():
                # Find nearest large speaker by time proximity
                for seg in small_segs:
                    seg_mid = ((seg.start_time or 0) + (seg.end_time or 0)) / 2
                    best_sid = None
                    best_dist = float("inf")
                    for large_sid, mids in large_midpoints.items():
                        for mid in mids:
                            dist = abs(seg_mid - mid)
                            if dist < best_dist:
                                best_dist = dist
                                best_sid = large_sid
                    if best_sid:
                        seg.speaker_id = best_sid
                        merged_count += 1

            db.flush()

            # Delete now-empty speakers
            for small_sid in small_speakers:
                remaining = db.query(Segment).filter(
                    Segment.speaker_id == small_sid
                ).count()
                if remaining == 0:
                    spk = db.query(Speaker).filter(Speaker.id == small_sid).first()
                    if spk:
                        db.delete(spk)

            db.commit()
            if merged_count:
                log.info(f"Polish: merged {merged_count} segments from "
                         f"{len(small_speakers)} tiny speakers")

        # Refresh speakers list after merge
        speakers = db.query(Speaker).filter(Speaker.meeting_id == meeting_id).all()
        segments = (
            db.query(Segment)
            .filter(Segment.meeting_id == meeting_id)
            .order_by(Segment.order)
            .all()
        )

        # Rebuild speaker_texts
        speaker_texts: dict[str, list[str]] = {}
        for seg in segments:
            if seg.speaker_id not in speaker_texts:
                speaker_texts[seg.speaker_id] = []
            speaker_texts[seg.speaker_id].append(seg.text)

        # --- Step 2: LLM naming for ALL speakers ---
        from services.llm_service import LLMService
        live_preset = get_model_config().get_model_for_task("live")
        llm = LLMService(preset=live_preset)

        speaker_blocks = []
        for spk in speakers:
            texts = speaker_texts.get(spk.id, [])
            if not texts:
                continue
            combined = " ".join(texts)
            if len(combined) > 800:
                combined = combined[:800] + "..."
            speaker_blocks.append(f"[{spk.label}] ({len(texts)} segment): {combined}")

        speaker_names = {}
        if speaker_blocks:
            prompt = (
                "Du analyserar en transkribering fran ett mote med "
                f"{len(speaker_blocks)} deltagare. "
                "Varje talare har en etikett (Speaker 1, Speaker 2, osv). "
                "Identifiera VARJE talares namn baserat pa:\n"
                "- Presentationer: 'jag heter...', 'jag ar...', 'mitt namn ar...'\n"
                "- Nar andra tilltalar dem vid namn\n"
                "- Ledtradar i vad de sager om sig sjalva\n\n"
                + "\n\n".join(speaker_blocks)
                + "\n\nVIKTIGT:\n"
                "- Varje talare MASTE fa ett UNIKT namn\n"
                "- Om du inte kan identifiera ett namn, anvand 'Deltagare N' "
                "(t.ex. 'Deltagare 1', 'Deltagare 2')\n"
                "- Anvand ALDRIG 'Speaker N' som namn\n"
                "- Ge ALLA talare ett namn, inte bara nagra\n\n"
                "Svara ENBART med JSON:\n"
                '{"speakers": [{"label": "Speaker 1", "name": "Fornamn"}, '
                '{"label": "Speaker 2", "name": "Fornamn"}]}'
            )

            try:
                response = llm._call([{"role": "user", "content": prompt}], max_tokens=500)
                data = llm._parse_json(response)
                speaker_names = {
                    s["label"]: s["name"]
                    for s in data.get("speakers", [])
                    if s.get("label") and s.get("name")
                }
                log.info(f"Polish LLM identified: {speaker_names}")
            except Exception as e:
                log.warning(f"Polish LLM failed: {e}")

        # Update speaker display names and stats
        for spk in speakers:
            name = speaker_names.get(spk.label)
            if name:
                spk.display_name = name
                spk.identified_by = "polish_llm"
                spk.confidence = 0.7
            segs_for_spk = [s for s in segments if s.speaker_id == spk.id]
            spk.segment_count = len(segs_for_spk)
            spk.total_speaking_time = sum(
                (s.end_time or 0) - (s.start_time or 0) for s in segs_for_spk
            )

        # Record polish history
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        history = meeting.polish_history or []
        history.append({
            "pass": pass_number,
            "duration_seconds": elapsed,
            "speaker_count": len(speakers),
            "names_found": len(speaker_names),
            "merged_segments": merged_count,
            "timestamp": datetime.utcnow().isoformat(),
        })
        meeting.polish_history = history

        job = db.query(Job).filter(Job.id == job_id).first()
        job.status = JobStatus.COMPLETED
        job.progress = 100
        job.completed_at = datetime.utcnow()
        db.commit()

        # Build response from fresh DB state
        updated_segments = [
            s.to_dict() for s in
            db.query(Segment).filter(Segment.meeting_id == meeting_id).order_by(Segment.order).all()
        ]
        updated_speakers = [
            spk.to_dict() for spk in
            db.query(Speaker).filter(Speaker.meeting_id == meeting_id).all()
        ]

        publish_event(meeting_id, {
            "type": "polish_complete",
            "pass_number": pass_number,
            "segments": updated_segments,
            "speakers": updated_speakers,
        })

        log.info(f"Polish pass {pass_number} completed in {elapsed:.1f}s")
        return {"status": "completed", "pass_number": pass_number}

    except Exception as e:
        db.rollback()
        log.error(f"Polish pass failed: {e}", exc_info=True)
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = JobStatus.FAILED
                job.error = str(e)
                job.completed_at = datetime.utcnow()
                db.commit()
        except Exception:
            pass

        try:
            publish_event(meeting_id, {"type": "error", "error": f"Polish pass failed: {e}"})
        except Exception:
            pass

        return {"error": str(e)}

    finally:
        db.close()

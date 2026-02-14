import asyncio
import json
import re
import subprocess
import wave
from pathlib import Path

import numpy as np
import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from config import settings, get_meeting_path
from database import SessionLocal
from models import Meeting, Speaker, Segment, MeetingStatus
from models.meeting import RecordingStatus
from model_config import get_model_config
from services.whisper_service import WhisperService
from services.embedding_service import EmbeddingService
from tasks.shared import publish_event

router = APIRouter()

SAMPLE_RATE = 16000
SPEAKER_THRESHOLD = settings.live_speaker_threshold
MIN_SEGMENT_DURATION = settings.live_min_segment_duration

# Speaker colors palette (same as speaker_id_service)
SPEAKER_COLORS = [
    "#6366f1", "#ec4899", "#10b981", "#f59e0b", "#3b82f6",
    "#ef4444", "#8b5cf6", "#14b8a6", "#f97316", "#06b6d4",
]


class LiveTranscriptionSession:
    """Handles live transcription with simple provisional speaker assignment.

    Speaker ID here is intentionally simple (centroid + threshold).
    The real speaker identification happens in polish passes (pyannote + LLM).
    """

    def __init__(self, meeting_id: str, meeting_path: Path, whisper_model_path: str | None = None):
        self.meeting_id = meeting_id
        self.meeting_path = meeting_path
        self.whisper_model_path = whisper_model_path
        self.audio_path = str(meeting_path / "audio.wav")
        self.pcm_path = str(meeting_path / "audio.raw")
        self.total_pcm_samples = 0
        self.speaker_centroids: dict[str, np.ndarray] = {}  # label -> centroid embedding
        self.segment_counter = 0
        self.total_audio_seconds = 0.0
        self.whisper_service = WhisperService()
        self.embedding_service = EmbeddingService()
        self._emitted_words: list[str] = []  # Rolling buffer for Whisper prompt context
        self._pcm_file = open(self.pcm_path, "wb")
        self._all_pcm = bytearray()

        # Polish scheduling
        self.last_polish_time = 0.0
        self.last_polish_duration = 0.0
        self.polish_count = 0

    def close(self):
        """Close PCM file and write final WAV."""
        if self._pcm_file:
            self._pcm_file.close()
            self._pcm_file = None
        self._write_wav(self.audio_path, bytes(self._all_pcm))
        try:
            Path(self.pcm_path).unlink(missing_ok=True)
        except Exception:
            pass

    async def process_chunk(self, webm_bytes: bytes, loop: asyncio.AbstractEventLoop) -> list[dict]:
        """Process a WebM/Opus chunk: convert, transcribe, identify speaker.

        Each chunk covers a distinct time range (no overlap).
        Previous transcription text is passed as Whisper prompt for continuity.
        """
        # 1. Convert WebM/Opus to 16kHz mono PCM
        pcm_data = await loop.run_in_executor(None, self._convert_webm_to_pcm, webm_bytes)
        if not pcm_data:
            return []

        # 2. Append PCM to raw file and accumulator
        if self._pcm_file:
            self._pcm_file.write(pcm_data)
            self._pcm_file.flush()
        self._all_pcm.extend(pcm_data)
        self.total_pcm_samples += len(pcm_data) // 2
        chunk_seconds = len(pcm_data) / (SAMPLE_RATE * 2)
        chunk_start_time = self.total_audio_seconds
        self.total_audio_seconds += chunk_seconds

        # 3. Silence detection (raised threshold to avoid Whisper hallucinations)
        rms = self._compute_rms(pcm_data)
        if rms < 500:
            print(f"[Live WS] Skipping silent chunk at {chunk_start_time:.1f}s (RMS={rms:.0f})")
            return []

        # 4. Write chunk as WAV
        temp_wav = str(self.meeting_path / f"chunk_{self.segment_counter}.wav")
        self._write_wav(temp_wav, pcm_data)

        # 5. Build prompt from previous transcription for Whisper context
        prompt = " ".join(self._emitted_words[-30:]) if self._emitted_words else None

        # 6. Transcribe
        try:
            raw_segments = await loop.run_in_executor(
                None, self.whisper_service.transcribe_chunk, temp_wav, self.whisper_model_path, prompt
            )
        except Exception as e:
            print(f"Whisper chunk error: {e}")
            raw_segments = []

        # 7. Adjust timestamps, filter hallucinations, collect segments
        new_segments = []
        for seg in raw_segments:
            text = seg["text"].strip()
            if not text:
                continue
            # Filter Whisper special tokens / hallucinations
            if self._is_hallucination(text):
                print(f"[Live WS] Filtered hallucination: {text!r}")
                continue
            new_segments.append({
                "start": round(seg["start"] + chunk_start_time, 3),
                "end": round(seg["end"] + chunk_start_time, 3),
                "text": text,
            })

        # 8. Speaker embedding per segment (simple centroid matching)
        results = []
        for seg in new_segments:
            speaker_label = await self._identify_speaker(
                seg, pcm_data, chunk_start_time, chunk_seconds, loop
            )
            self.segment_counter += 1
            self._record_emitted(seg["text"])
            results.append({
                "start_time": seg["start"],
                "end_time": seg["end"],
                "text": seg["text"],
                "speaker_label": speaker_label,
                "order": self.segment_counter,
            })

        # Clean up temp file
        try:
            Path(temp_wav).unlink(missing_ok=True)
            Path(temp_wav + ".json").unlink(missing_ok=True)
        except Exception:
            pass

        return results

    def _convert_webm_to_pcm(self, webm_bytes: bytes) -> bytes:
        """Convert WebM/Opus bytes to 16kHz mono PCM via FFmpeg."""
        try:
            proc = subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", "pipe:0",
                    "-vn",
                    "-acodec", "pcm_s16le",
                    "-ar", str(SAMPLE_RATE),
                    "-ac", "1",
                    "-f", "wav",
                    "pipe:1",
                ],
                input=webm_bytes,
                capture_output=True,
                timeout=30,
            )
            if proc.returncode != 0:
                print(f"[Live WS] FFmpeg failed (rc={proc.returncode}): {proc.stderr[:200]}")
                return b""
            raw = proc.stdout
            if len(raw) > 44:
                pcm = raw[44:]  # Strip WAV header
                print(f"[Live WS] FFmpeg converted {len(webm_bytes)}B WebM → {len(pcm)}B PCM ({len(pcm)/(SAMPLE_RATE*2):.1f}s)")
                return pcm
            print(f"[Live WS] FFmpeg output too small: {len(raw)} bytes")
            return b""
        except Exception as e:
            print(f"[Live WS] FFmpeg exception: {e}")
            return b""

    @staticmethod
    def _compute_rms(pcm_data: bytes) -> float:
        """Compute RMS amplitude of 16-bit PCM data."""
        if len(pcm_data) < 2:
            return 0.0
        samples = np.frombuffer(pcm_data, dtype=np.int16)
        return float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))

    def _write_wav(self, path: str, pcm_data: bytes):
        """Write PCM data to a WAV file."""
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(pcm_data)

    def _record_emitted(self, text: str):
        """Add emitted text to the rolling word buffer."""
        words = text.split()
        self._emitted_words.extend(words)
        if len(self._emitted_words) > 60:
            self._emitted_words = self._emitted_words[-60:]

    @staticmethod
    def _is_hallucination(text: str) -> bool:
        """Detect Whisper hallucinations and special token leaks."""
        # Whisper special tokens: <|nospeech|>, <|34.00|>, <|Påsk>, etc.
        if "<|" in text or "|>" in text:
            return True
        # Strip all special tokens and check if anything real remains
        cleaned = re.sub(r"<\|[^|]*\|?>", "", text).strip()
        if not cleaned:
            return True
        # Very short garbage (1-2 chars)
        if len(cleaned) <= 2:
            return True
        return False

    async def _identify_speaker(
        self, seg: dict, chunk_pcm: bytes, chunk_start: float,
        chunk_seconds: float, loop: asyncio.AbstractEventLoop
    ) -> str:
        """Simple provisional speaker ID using centroid + cosine similarity.

        This is intentionally basic — polish passes with pyannote handle
        the real speaker identification.
        """
        seg_duration = seg["end"] - seg["start"]
        if seg_duration < MIN_SEGMENT_DURATION:
            if self.speaker_centroids:
                return list(self.speaker_centroids.keys())[-1]
            return "Speaker 1"

        # Extract segment PCM from chunk
        seg_start_in_chunk = seg["start"] - chunk_start
        seg_end_in_chunk = seg["end"] - chunk_start
        sample_start = max(0, int(seg_start_in_chunk * SAMPLE_RATE) * 2)
        sample_end = min(len(chunk_pcm), int(seg_end_in_chunk * SAMPLE_RATE) * 2)

        if sample_end - sample_start < SAMPLE_RATE * 2:  # Less than 1s
            if self.speaker_centroids:
                return list(self.speaker_centroids.keys())[-1]
            return "Speaker 1"

        seg_pcm = chunk_pcm[sample_start:sample_end]
        temp_path = str(self.meeting_path / f"spk_tmp_{self.segment_counter}.wav")
        self._write_wav(temp_path, seg_pcm)

        try:
            embedding = await loop.run_in_executor(
                None, self.embedding_service.extract_embedding, temp_path
            )
        except Exception as e:
            print(f"[Live WS] Speaker embedding failed: {e}")
            if self.speaker_centroids:
                return list(self.speaker_centroids.keys())[-1]
            return "Speaker 1"
        finally:
            Path(temp_path).unlink(missing_ok=True)

        # Compare against existing centroids
        best_label = None
        best_sim = 0.0
        for label, centroid in self.speaker_centroids.items():
            sim = self.embedding_service.cosine_similarity(embedding, centroid)
            if sim > best_sim:
                best_sim = sim
                best_label = label

        print(f"[Live WS] Speaker: best={best_label} sim={best_sim:.3f} threshold={SPEAKER_THRESHOLD}")

        if best_label and best_sim >= SPEAKER_THRESHOLD:
            # Update centroid — more aggressive adaptation to handle
            # voice variation within a speaker (quiet vs loud, etc.)
            old = self.speaker_centroids[best_label]
            self.speaker_centroids[best_label] = (old * 0.7 + embedding * 0.3)
            return best_label

        # New speaker
        new_idx = len(self.speaker_centroids) + 1
        new_label = f"Speaker {new_idx}"
        self.speaker_centroids[new_label] = embedding
        return new_label

    def should_polish(self) -> bool:
        """Schedule: 1, 2, 3, 4, 5 min, then every 5 min."""
        t = self.total_audio_seconds
        if t < 60:
            return False
        if self.polish_count < 5:
            target = (self.polish_count + 1) * 60
        else:
            target = 5 * 60 + (self.polish_count - 4) * 5 * 60
        return t >= target

    def mark_polish_scheduled(self):
        self.last_polish_time = self.total_audio_seconds
        self.polish_count += 1


@router.websocket("/ws/live/{meeting_id}")
async def live_websocket(websocket: WebSocket, meeting_id: str):
    await websocket.accept()

    loop = asyncio.get_event_loop()

    # Subscribe to Redis pub/sub for polish/finalize results
    r = aioredis.from_url(settings.redis_url)
    pubsub = r.pubsub()
    await pubsub.subscribe(f"meeting:{meeting_id}")

    # Verify meeting exists and is in live mode
    db = SessionLocal()
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting or meeting.mode != "live":
        await websocket.close(code=4000, reason="Meeting not found or not in live mode")
        db.close()
        return

    meeting_path = get_meeting_path(meeting_id)
    # Get whisper model for live transcription from presets
    live_whisper = get_model_config().get_model_for_task("live_transcription")
    live_whisper_model = live_whisper.get("model_path") if live_whisper else None
    session = LiveTranscriptionSession(meeting_id, meeting_path, whisper_model_path=live_whisper_model)

    async def relay_redis():
        """Forward Redis pub/sub messages (polish/finalize results) to WS client."""
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    if data.get("type") in (
                        "polish_started", "polish_complete",
                        "finalize_started", "finalize_complete",
                        "progress", "error",
                    ):
                        await websocket.send_json(data)
        except Exception:
            pass

    relay_task = asyncio.create_task(relay_redis())

    try:
        while True:
            message = await websocket.receive()

            if "bytes" in message and message["bytes"]:
                chunk_bytes = message["bytes"]
                print(f"[Live WS] Received audio chunk: {len(chunk_bytes)} bytes")
                segments = await session.process_chunk(chunk_bytes, loop)

                # Persist segments and send to client
                for seg_data in segments:
                    # Retry loop: polish pass may delete/recreate speakers
                    # concurrently, causing transient FK violations
                    segment = None
                    speaker = None
                    for attempt in range(3):
                        try:
                            speaker = _get_or_create_speaker(
                                db, meeting_id, seg_data["speaker_label"]
                            )
                            segment = Segment(
                                meeting_id=meeting_id,
                                speaker_id=speaker.id,
                                start_time=seg_data["start_time"],
                                end_time=seg_data["end_time"],
                                text=seg_data["text"],
                                original_text=seg_data["text"],
                                order=seg_data["order"],
                            )
                            db.add(segment)
                            db.commit()
                            break
                        except Exception as e:
                            db.rollback()
                            if attempt < 2:
                                print(f"[Live WS] DB retry {attempt+1}/3: {e}")
                                continue
                            # Last attempt failed — skip this segment
                            print(f"[Live WS] DB failed after 3 retries, skipping segment: {e}")
                            segment = None
                            break

                    if segment and speaker:
                        await websocket.send_json({
                            "type": "live_segment",
                            "segment": {
                                "id": segment.id,
                                "start_time": seg_data["start_time"],
                                "end_time": seg_data["end_time"],
                                "text": seg_data["text"],
                                "speaker_id": speaker.id,
                                "speaker_label": speaker.label,
                                "speaker_name": speaker.display_name,
                                "speaker_color": speaker.color,
                                "order": seg_data["order"],
                                "is_edited": False,
                            },
                        })

                # Update meeting duration (resilient to concurrent modifications)
                try:
                    db.expire(meeting)
                    meeting.duration = session.total_audio_seconds
                    db.commit()
                except Exception:
                    db.rollback()

                # Write current WAV snapshot for polish tasks
                if session.total_audio_seconds > 0:
                    session._write_wav(session.audio_path, bytes(session._all_pcm))

                # Check if polish pass should run (pyannote handles real speaker ID)
                if session.should_polish():
                    session.mark_polish_scheduled()
                    _schedule_polish(db, meeting_id, session.polish_count)

            elif "text" in message and message["text"]:
                try:
                    cmd = json.loads(message["text"])
                except json.JSONDecodeError:
                    continue

                if cmd.get("type") == "stop_recording":
                    session.close()
                    meeting.status = MeetingStatus.FINALIZING
                    meeting.recording_status = RecordingStatus.STOPPED.value
                    db.commit()
                    _schedule_finalize(db, meeting_id)
                    await websocket.send_json({
                        "type": "finalize_started",
                        "message": "Finalizing transcription...",
                    })

                elif cmd.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"Live WS error: {e}")
    finally:
        session.close()
        relay_task.cancel()
        await pubsub.unsubscribe(f"meeting:{meeting_id}")
        await r.aclose()
        db.close()


def _get_or_create_speaker(db, meeting_id: str, label: str) -> Speaker:
    """Get existing speaker by label or create a new one.

    Expires cached objects first so we always see the latest DB state
    (polish passes may have deleted/recreated speakers).
    """
    db.expire_all()
    speaker = (
        db.query(Speaker)
        .filter(Speaker.meeting_id == meeting_id, Speaker.label == label)
        .first()
    )
    if speaker:
        return speaker

    idx = db.query(Speaker).filter(Speaker.meeting_id == meeting_id).count()
    speaker = Speaker(
        meeting_id=meeting_id,
        label=label,
        display_name=label,
        color=SPEAKER_COLORS[idx % len(SPEAKER_COLORS)],
    )
    db.add(speaker)
    db.flush()
    return speaker


def _schedule_polish(db, meeting_id: str, pass_number: int):
    """Schedule a polish pass Celery task."""
    from models.job import Job, JobType, JobStatus
    from tasks.polish_task import polish_pass_task

    job = Job(
        meeting_id=meeting_id,
        job_type=JobType.POLISH_PASS,
        status=JobStatus.PENDING,
    )
    db.add(job)
    db.commit()

    result = polish_pass_task.delay(meeting_id, job.id, pass_number)
    job.celery_task_id = result.id
    db.commit()


def _schedule_finalize(db, meeting_id: str):
    """Schedule a finalize Celery task."""
    from models.job import Job, JobType, JobStatus
    from tasks.finalize_task import finalize_live_task

    job = Job(
        meeting_id=meeting_id,
        job_type=JobType.FINALIZE_LIVE,
        status=JobStatus.PENDING,
    )
    db.add(job)
    db.commit()

    result = finalize_live_task.delay(meeting_id, job.id)
    job.celery_task_id = result.id
    db.commit()

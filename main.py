import shutil
from pathlib import Path

import redis
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from config import settings as _settings
from database import init_db, seed_default_actions, recover_stale_jobs, get_db, engine
from models import Meeting
from api import meetings, speakers, segments, export, websocket, live_websocket, actions, model_settings, encryption

app = FastAPI(title="Transcriber")

_default_origins = ["http://localhost:5174", "http://localhost:5175", "http://127.0.0.1:5174", "http://127.0.0.1:5175"]
_cors_origins = [x.strip() for x in _settings.cors_origins.split(",") if x.strip()] if _settings.cors_origins else _default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(meetings.router)
app.include_router(speakers.router)
app.include_router(segments.router)
app.include_router(export.router)
app.include_router(websocket.router)
app.include_router(live_websocket.router)
app.include_router(actions.router)
app.include_router(model_settings.router)
app.include_router(encryption.router)


@app.on_event("startup")
def startup():
    init_db()
    seed_default_actions()
    recover_stale_jobs()
    import logging
    _log = logging.getLogger(__name__)
    if not _settings.hf_auth_token or _settings.hf_auth_token == "hf_your_token_here":
        _log.warning("HF_AUTH_TOKEN not set — speaker diarization will fail. "
                     "Set it in .env (get one at https://huggingface.co/settings/tokens)")


@app.get("/api/meetings/{meeting_id}/audio")
def stream_audio(meeting_id: str, db: Session = Depends(get_db)):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting or not meeting.audio_filepath:
        raise HTTPException(404, "Audio not found")

    path = Path(meeting.audio_filepath)
    if not path.exists():
        raise HTTPException(404, "Audio file not found")

    return FileResponse(
        path,
        media_type="audio/wav",
        headers={"Accept-Ranges": "bytes"},
    )


@app.get("/api/health")
def health():
    checks = {}

    # Database
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    # Redis
    try:
        r = redis.Redis.from_url(_settings.redis_url)
        r.ping()
        r.close()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    # Whisper CLI
    whisper_path = Path(_settings.whisper_cli_path)
    checks["whisper_cli"] = "ok" if whisper_path.exists() else f"missing: {whisper_path}"

    # Disk space
    storage_path = Path(_settings.storage_path)
    storage_path.mkdir(parents=True, exist_ok=True)
    disk = shutil.disk_usage(storage_path)
    free_gb = disk.free / (1024 ** 3)
    checks["disk_free_gb"] = round(free_gb, 1)
    if free_gb < 1:
        checks["disk"] = "warning: less than 1 GB free"

    all_ok = all(
        v == "ok" for k, v in checks.items()
        if k not in ("disk_free_gb",)
    )
    return {"status": "ok" if all_ok else "degraded", **checks}


@app.get("/api/settings")
def get_settings():
    return {
        "llm_provider": _settings.llm_provider,
        "openrouter_model": _settings.openrouter_model,
        "ollama_model": _settings.ollama_model,
        "ollama_base_url": _settings.ollama_base_url,
    }

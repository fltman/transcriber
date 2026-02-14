from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from config import settings as _settings
from database import init_db, seed_default_actions, get_db
from models import Meeting
from api import meetings, speakers, segments, export, websocket, live_websocket, actions, model_settings, encryption

app = FastAPI(title="Transcriber")

_default_origins = ["http://localhost:5174", "http://localhost:5175", "http://127.0.0.1:5174", "http://127.0.0.1:5175"]
_cors_origins = _settings.cors_origins.split(",") if _settings.cors_origins else _default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
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
    if not _settings.hf_auth_token or _settings.hf_auth_token == "hf_your_token_here":
        print("WARNING: HF_AUTH_TOKEN not set — speaker diarization will fail. "
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
    return {"status": "ok"}


@app.get("/api/settings")
def get_settings():
    return {
        "llm_provider": _settings.llm_provider,
        "openrouter_model": _settings.openrouter_model,
        "ollama_model": _settings.ollama_model,
        "ollama_base_url": _settings.ollama_base_url,
    }

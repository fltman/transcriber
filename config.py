from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://transcriber:transcriber@localhost:5433/transcriber"
    redis_url: str = "redis://localhost:6380/0"
    llm_provider: str = "openrouter"  # "openrouter" or "ollama"
    openrouter_api_key: str = ""
    openrouter_model: str = "anthropic/claude-sonnet-4"
    openrouter_base_url: str = "https://openrouter.ai/api/v1/"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:1b"
    whisper_cli_path: str = "../whisper.cpp/build/bin/whisper-cli"
    whisper_model_path: str = "./models/kb_whisper_ggml_medium.bin"
    whisper_small_model_path: str = "./models/kb_whisper_ggml_small.bin"
    backend: str = "torch"
    torch_diarization_model: str = "pyannote/speaker-diarization-3.1"
    mlx_diarization_model: str = "mlx-community/diar_sortformer_4spk-v1-fp16"
    listen_host: str = "localhost"
    proxy_host: str = "localhost"
    api_port: int = 8082
    storage_path: str = "./storage"
    hf_auth_token: str = ""
    cors_origins: str = ""  # Comma-separated, e.g. "http://localhost:3000,http://myapp.com"

    # Live mode settings
    live_chunk_overlap_seconds: float = 2.5
    live_speaker_threshold: float = 0.45
    live_min_segment_duration: float = 2.0

    class Config:
        env_file = ".env"


settings = Settings()

# Warn about missing critical config at import time
import logging as _logging
_config_log = _logging.getLogger(__name__)
if settings.backend.strip().lower() == "torch" and not settings.hf_auth_token:
    _config_log.warning("HF_AUTH_TOKEN is not set — speaker diarization will not work")
if settings.llm_provider == "openrouter" and not settings.openrouter_api_key:
    _config_log.warning("OPENROUTER_API_KEY is not set — LLM features will fail")


def get_storage_path() -> Path:
    p = Path(settings.storage_path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_meeting_path(meeting_id: str) -> Path:
    p = get_storage_path() / meeting_id
    p.mkdir(parents=True, exist_ok=True)
    return p

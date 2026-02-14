from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://transcriber:transcriber@localhost:5433/transcriber"
    redis_url: str = "redis://localhost:6380/0"
    llm_provider: str = "openrouter"  # "openrouter" or "ollama"
    openrouter_api_key: str = ""
    openrouter_model: str = "anthropic/claude-sonnet-4"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:1b"
    whisper_cli_path: str = "/Users/andersbj/Projekt/whisper.cpp/build/bin/whisper-cli"
    whisper_model_path: str = "/Users/andersbj/Projekt/whisper-flow/models/kb_whisper_ggml_medium.bin"
    whisper_small_model_path: str = "/Users/andersbj/Projekt/whisper-flow/models/kb_whisper_ggml_small.bin"
    storage_path: str = "/Users/andersbj/Projekt/transcriber/storage"
    hf_auth_token: str = ""

    # Live mode settings
    live_chunk_overlap_seconds: float = 2.5
    live_speaker_threshold: float = 0.45
    live_min_segment_duration: float = 2.0

    class Config:
        env_file = ".env"


settings = Settings()


def get_storage_path() -> Path:
    p = Path(settings.storage_path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_meeting_path(meeting_id: str) -> Path:
    p = get_storage_path() / meeting_id
    p.mkdir(parents=True, exist_ok=True)
    return p

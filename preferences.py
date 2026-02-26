"""Simple JSON-file preferences for global settings."""
import json
from pathlib import Path

PREFS_PATH = Path("preferences.json")

DEFAULTS = {
    "default_vocabulary": "",
    "speaker_profiles_enabled": True,
    "hf_auth_token": "",
    "openrouter_api_key": "",
}

# Keys that should never be sent to the frontend in full
_SECRET_KEYS = {"hf_auth_token", "openrouter_api_key"}


def load_preferences() -> dict:
    if PREFS_PATH.exists():
        try:
            with open(PREFS_PATH) as f:
                data = json.load(f)
            # Merge with defaults for any missing keys
            return {**DEFAULTS, **data}
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULTS)


def save_preferences(prefs: dict):
    with open(PREFS_PATH, "w") as f:
        json.dump(prefs, f, indent=2, ensure_ascii=False)


def get_public_preferences() -> dict:
    """Return preferences with secrets masked for the frontend."""
    prefs = load_preferences()
    result = {}
    for k, v in prefs.items():
        if k in _SECRET_KEYS:
            result[k] = _mask(v) if v else ""
        else:
            result[k] = v
    return result


def _mask(value: str) -> str:
    """Show first 4 and last 4 chars of a secret."""
    if len(value) <= 10:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


def get_secret(key: str) -> str:
    """Get a secret value, checking preferences then env vars."""
    import os
    # Environment variable takes precedence
    env_val = os.environ.get(key.upper(), "")
    if env_val and env_val != f"hf_your_token_here":
        return env_val
    # Fall back to preferences
    prefs = load_preferences()
    return prefs.get(key, "")

"""Simple JSON-file preferences for global settings."""
import json
from pathlib import Path

PREFS_PATH = Path("preferences.json")

DEFAULTS = {
    "default_vocabulary": "",
    "speaker_profiles_enabled": True,
}


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

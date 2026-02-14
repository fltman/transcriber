"""Model configuration manager.

Loads preset definitions from model_presets/ folder and persists
per-task model assignments in storage/settings.json.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from config import get_storage_path

log = logging.getLogger(__name__)

PRESETS_DIR = Path(__file__).parent / "model_presets"

TASK_DEFAULTS = {
    "actions": "ollama-qwen3-8b",
    "analysis": "ollama-qwen3-8b",
    "live": "ollama-qwen3-8b",
    "transcription": "whisper-medium-sv",
    "live_transcription": "whisper-small-sv",
}


class ModelConfigManager:
    def __init__(self):
        self._presets: dict[str, dict] = {}
        self._settings: dict[str, str] = {}  # task -> preset_id
        self._load_presets()
        self._load_settings()

    def _load_presets(self):
        """Load all .json files from model_presets/ folder."""
        self._presets = {}
        if not PRESETS_DIR.exists():
            log.warning(f"Presets directory not found: {PRESETS_DIR}")
            return
        for f in sorted(PRESETS_DIR.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                preset_id = data.get("id", f.stem)
                self._presets[preset_id] = data
            except Exception as e:
                log.warning(f"Failed to load preset {f.name}: {e}")

    def _load_settings(self):
        """Load task->preset assignments from storage/settings.json."""
        path = get_storage_path() / "settings.json"
        if path.exists():
            try:
                self._settings = json.loads(path.read_text())
            except Exception as e:
                log.warning(f"Failed to load settings: {e}")
                self._settings = {}
        else:
            self._settings = {}

    def _save_settings(self):
        """Persist task->preset assignments."""
        path = get_storage_path() / "settings.json"
        path.write_text(json.dumps(self._settings, indent=2))

    def reload(self):
        """Reload presets and settings from disk."""
        self._load_presets()
        self._load_settings()

    def get_presets(self, type_filter: Optional[str] = None) -> list[dict]:
        """Return all presets, optionally filtered by type (llm/whisper)."""
        presets = list(self._presets.values())
        if type_filter:
            presets = [p for p in presets if p.get("type") == type_filter]
        return presets

    def get_assignments(self) -> dict[str, str]:
        """Return current task->preset_id mapping with defaults filled in."""
        result = {}
        for task, default_id in TASK_DEFAULTS.items():
            result[task] = self._settings.get(task, default_id)
        return result

    def update_assignments(self, assignments: dict[str, str]):
        """Update task->preset assignments and persist."""
        for task, preset_id in assignments.items():
            if task in TASK_DEFAULTS:
                self._settings[task] = preset_id
        self._save_settings()

    def get_preset_for_task(self, task: str) -> Optional[dict]:
        """Get the full preset dict for a given task category."""
        preset_id = self._settings.get(task, TASK_DEFAULTS.get(task))
        if not preset_id:
            return None
        return self._presets.get(preset_id)

    def get_model_for_task(self, task: str) -> Optional[dict]:
        """Alias for get_preset_for_task."""
        return self.get_preset_for_task(task)


# Singleton instance
_manager: Optional[ModelConfigManager] = None


def get_model_config() -> ModelConfigManager:
    global _manager
    if _manager is None:
        _manager = ModelConfigManager()
    return _manager

import re
import tempfile
from pathlib import Path

from .audio_service import AudioService
from .embedding_service import EmbeddingService
from .llm_service import LLMService

# Speaker colors palette
SPEAKER_COLORS = [
    "#6366f1",  # indigo
    "#ec4899",  # pink
    "#10b981",  # emerald
    "#f59e0b",  # amber
    "#3b82f6",  # blue
    "#ef4444",  # red
    "#8b5cf6",  # violet
    "#14b8a6",  # teal
    "#f97316",  # orange
    "#06b6d4",  # cyan
]

INTRO_PATTERNS = [
    r"jag heter\s+(\w+)",
    r"mitt namn [aä]r\s+(\w+)",
    r"jag [aä]r\s+(\w+)",
    r"hej.{0,20}jag heter",
    r"hej.{0,20}mitt namn",
]

INTRO_DURATION = 120.0  # First 2 minutes


class SpeakerIdService:
    def __init__(self):
        self.audio_service = AudioService()
        self.embedding_service = EmbeddingService()
        self.llm_service = LLMService()

    def has_intro(self, segments: list[dict]) -> bool:
        """Check if the transcript contains speaker introductions in the first 120s."""
        intro_text = " ".join(
            s["text"] for s in segments if s.get("start", 0) < INTRO_DURATION
        ).lower()

        for pattern in INTRO_PATTERNS:
            if re.search(pattern, intro_text):
                return True
        return False

    def identify_speakers_model2(
        self,
        aligned_segments: list[dict],
        audio_path: str,
        diarization_segments: list[dict],
    ) -> dict[str, dict]:
        """
        Model 2: Use LLM to identify speakers from intro.
        Returns {speaker_label: {name, confidence, identified_by}}.
        """
        # Get intro segments
        intro_segments = [s for s in aligned_segments if s.get("start", 0) < INTRO_DURATION]
        if not intro_segments:
            return {}

        # Build intro text with speaker labels
        intro_text = ""
        for seg in intro_segments:
            label = seg.get("speaker", "UNKNOWN")
            intro_text += f"[{label}]: {seg['text']}\n"

        # Ask LLM to identify speakers
        mappings = self.llm_service.identify_speakers_from_intro(intro_text)
        if not mappings:
            return {}

        result = {}
        for m in mappings:
            label = m.get("speaker_label", "")
            name = m.get("name", "")
            if label and name:
                result[label] = {
                    "name": name,
                    "confidence": 0.8,
                    "identified_by": "intro_llm",
                }

        return result

    def identify_speakers_model3(self, speaker_labels: list[str]) -> dict[str, dict]:
        """
        Model 3 (fallback): Label speakers as Deltagare 1, 2, etc.
        """
        result = {}
        for i, label in enumerate(sorted(set(speaker_labels))):
            result[label] = {
                "name": f"Deltagare {i + 1}",
                "confidence": None,
                "identified_by": None,
            }
        return result

    def get_color(self, index: int) -> str:
        return SPEAKER_COLORS[index % len(SPEAKER_COLORS)]

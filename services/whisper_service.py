import json
import subprocess
from pathlib import Path

from config import settings


class WhisperService:
    def __init__(self):
        self.cli_path = settings.whisper_cli_path
        self.model_path = settings.whisper_model_path

    def transcribe(self, audio_path: str) -> list[dict]:
        """
        Transcribe audio using whisper-cli.
        Returns list of {start, end, text} dicts.
        """
        output_json = audio_path + ".json"

        cmd = [
            self.cli_path,
            "-m", self.model_path,
            "-f", audio_path,
            "-l", "sv",
            "-oj",  # output JSON
            "-of", audio_path,  # output file prefix (creates audio.wav.json)
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800,  # 30 min max
        )

        if result.returncode != 0:
            raise RuntimeError(f"whisper-cli failed: {result.stderr}")

        with open(output_json, "r") as f:
            data = json.load(f)

        segments = []
        for item in data.get("transcription", []):
            text = item.get("text", "").strip()
            if not text:
                continue
            # Timestamps from whisper are in format "HH:MM:SS.mmm" -> convert
            start = self._parse_timestamp(item["timestamps"]["from"])
            end = self._parse_timestamp(item["timestamps"]["to"])
            segments.append({
                "start": start,
                "end": end,
                "text": text,
            })

        return segments

    def transcribe_chunk(self, audio_path: str, model_path: str | None = None, prompt: str | None = None) -> list[dict]:
        """
        Transcribe a short audio chunk using whisper-cli.
        Uses the small model by default for speed. Same output format as transcribe().
        prompt: previous transcription text for context continuity.
        """
        model = model_path or settings.whisper_small_model_path
        output_json = audio_path + ".json"

        cmd = [
            self.cli_path,
            "-m", model,
            "-f", audio_path,
            "-l", "sv",
            "-oj",
            "-of", audio_path,
            "--no-speech-thold", "0.5",  # Skip segments with high no-speech probability
        ]
        if prompt:
            # Pass last transcription as initial prompt for continuity
            cmd.extend(["--prompt", prompt[-200:]])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,  # 2 min max for chunks
        )

        if result.returncode != 0:
            raise RuntimeError(f"whisper-cli chunk failed: {result.stderr}")

        with open(output_json, "r") as f:
            data = json.load(f)

        segments = []
        for item in data.get("transcription", []):
            text = item.get("text", "").strip()
            if not text:
                continue
            start = self._parse_timestamp(item["timestamps"]["from"])
            end = self._parse_timestamp(item["timestamps"]["to"])
            segments.append({
                "start": start,
                "end": end,
                "text": text,
            })

        return segments

    def _parse_timestamp(self, ts: str) -> float:
        """Parse 'HH:MM:SS.mmm' or 'HH:MM:SS,mmm' to seconds."""
        ts = ts.replace(",", ".")
        parts = ts.split(":")
        if len(parts) == 3:
            h, m, s = parts
            return float(h) * 3600 + float(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return float(m) * 60 + float(s)
        return float(ts)

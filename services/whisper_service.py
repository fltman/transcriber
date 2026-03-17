import json
import subprocess

from config import settings


class WhisperService:
    def __init__(self):
        self.cli_path = settings.whisper_cli_path
        self.model_path = settings.whisper_model_path
        self.backend = settings.backend.strip().lower()

    def _use_mlx(self) -> bool:
        return self.backend == "mlx"

    def transcribe(self, audio_path: str, vocabulary: str | None = None) -> list[dict]:
        """
        Transcribe audio using whisper-cli.
        Returns list of {start, end, text} dicts.
        vocabulary: domain-specific terms to prime Whisper (passed as --prompt).
        """
        if self._use_mlx():
            return self._transcribe_mlx(audio_path, vocabulary=vocabulary)

        output_json = audio_path + ".json"

        cmd = [
            self.cli_path,
            "-m", self.model_path,
            "-f", audio_path,
            "-l", "sv",
            "-oj",  # output JSON
            "-of", audio_path,  # output file prefix (creates audio.wav.json)
        ]
        if vocabulary:
            cmd.extend(["--prompt", vocabulary[:500]])

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

    def transcribe_chunk(self, audio_path: str, model_path: str | None = None, prompt: str | None = None, vocabulary: str | None = None) -> list[dict]:
        """
        Transcribe a short audio chunk using whisper-cli.
        Uses the small model by default for speed. Same output format as transcribe().
        prompt: previous transcription text for context continuity.
        vocabulary: domain-specific terms prepended to prompt.
        """
        if self._use_mlx():
            return self._transcribe_chunk_mlx(audio_path, model_path=model_path, prompt=prompt, vocabulary=vocabulary)

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
        # Build prompt: vocabulary terms + previous transcription context
        full_prompt_parts = []
        if vocabulary:
            full_prompt_parts.append(vocabulary[:300])
        if prompt:
            full_prompt_parts.append(prompt[-200:])
        if full_prompt_parts:
            cmd.extend(["--prompt", " ".join(full_prompt_parts)])

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

    def _transcribe_mlx(self, audio_path: str, vocabulary: str | None = None) -> list[dict]:
        from mlx_audio.stt.generate import generate_transcription

        output_json = audio_path + ".json"
        model = self.model_path or "mlx-community/whisper-large-v3-turbo-asr-fp16"
        generate_transcription(
            model=model,
            audio=audio_path,
            output_path=audio_path,
            format="json",
            stream=False,
            prompt=vocabulary[:500] if vocabulary else None,
        )

        with open(output_json, "r") as f:
            data = json.load(f)
        return self._parse_mlx_segments(data)

    def _transcribe_chunk_mlx(
        self,
        audio_path: str,
        model_path: str | None = None,
        prompt: str | None = None,
        vocabulary: str | None = None,
    ) -> list[dict]:
        from mlx_audio.stt import generate_transcription

        output_json = audio_path + ".json"
        model = model_path or settings.whisper_small_model_path

        full_prompt_parts = []
        if vocabulary:
            full_prompt_parts.append(vocabulary[:300])
        if prompt:
            full_prompt_parts.append(prompt[-200:])
        full_prompt = " ".join(full_prompt_parts) if full_prompt_parts else None

        generate_transcription(
            model=model,
            audio=audio_path,
            output_path=audio_path,
            format="json",
            stream=False,
            prompt=full_prompt,
        )

        with open(output_json, "r") as f:
            data = json.load(f)
        return self._parse_mlx_segments(data)

    def _parse_mlx_segments(self, data: dict) -> list[dict]:
        segments = []
        for item in data.get("segments", []):
            text = item.get("text", "").strip()
            if not text:
                continue
            segments.append(
                {
                    "start": float(item.get("start", 0.0)),
                    "end": float(item.get("end", 0.0)),
                    "text": text,
                }
            )
        return segments

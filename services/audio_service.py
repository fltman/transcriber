import json
import subprocess
from pathlib import Path

from config import get_meeting_path


class AudioService:
    def extract_audio(self, input_path: str, meeting_id: str) -> str:
        """Extract audio from input file as 16kHz mono WAV."""
        output_dir = get_meeting_path(meeting_id)
        output_path = str(output_dir / "audio.wav")

        # If input is already our output, skip extraction
        if Path(input_path).resolve() == Path(output_path).resolve():
            return output_path

        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            output_path,
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def get_duration(self, filepath: str) -> float:
        """Get audio/video duration in seconds via ffprobe."""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            filepath,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        return float(info["format"]["duration"])

    def extract_segment(self, audio_path: str, start: float, end: float, output_path: str) -> str:
        """Extract a segment of audio."""
        cmd = [
            "ffmpeg", "-y",
            "-i", audio_path,
            "-ss", str(start),
            "-to", str(end),
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            output_path,
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

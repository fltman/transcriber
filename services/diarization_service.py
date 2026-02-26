import torchaudio
import torch
from config import settings

# torchaudio 2.10+ removed list_audio_backends; pyannote still calls it
if not hasattr(torchaudio, "list_audio_backends"):
    torchaudio.list_audio_backends = lambda: ["torchcodec"]

# torchaudio 2.10+ removed AudioMetaData; pyannote still references it
if not hasattr(torchaudio, "AudioMetaData"):
    from dataclasses import dataclass

    @dataclass
    class _AudioMetaData:
        sample_rate: int = 0
        num_frames: int = 0
        num_channels: int = 0
        bits_per_sample: int = 0
        encoding: str = ""

    torchaudio.AudioMetaData = _AudioMetaData


class DiarizationService:
    _pipeline = None

    @classmethod
    def get_pipeline(cls):
        if cls._pipeline is None:
            from pyannote.audio import Pipeline
            from preferences import get_secret

            kwargs = {}
            token = get_secret("hf_auth_token")
            if token:
                kwargs["token"] = token

            cls._pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                **kwargs,
            )
            if torch.backends.mps.is_available():
                cls._pipeline.to(torch.device("mps"))
        return cls._pipeline

    def diarize(
        self,
        audio_path: str,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
    ) -> list[dict]:
        """
        Run speaker diarization on audio file.
        Returns list of {start, end, speaker} dicts.
        """
        pipeline = self.get_pipeline()

        kwargs = {}
        if min_speakers is not None:
            kwargs["min_speakers"] = min_speakers
        if max_speakers is not None:
            kwargs["max_speakers"] = max_speakers

        result = pipeline(audio_path, **kwargs)

        # pyannote v4 returns DiarizeOutput with .serialize()
        if hasattr(result, "serialize"):
            data = result.serialize()
            return data.get("diarization", [])

        # pyannote v3 fallback
        segments = []
        for turn, _, speaker in result.itertracks(yield_label=True):
            segments.append({
                "start": round(turn.start, 3),
                "end": round(turn.end, 3),
                "speaker": speaker,
            })
        return segments

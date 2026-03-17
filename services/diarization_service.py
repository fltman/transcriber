import logging

import torchaudio
import torch
from config import settings
from preferences import get_secret
from translations import get_translation

log = logging.getLogger(__name__)

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
    _torch_pipeline = None
    _mlx_model = None

    @classmethod
    def get_backend(cls) -> str:
        backend = settings.backend.strip().lower()
        if backend not in {"torch", "mlx"}:
            raise ValueError(f"Unsupported backend: {settings.backend}")
        return backend

    @classmethod
    def get_torch_pipeline(cls):
        if cls._torch_pipeline is None:
            from pyannote.audio import Pipeline

            kwargs = {}
            token = get_secret("hf_auth_token")
            if token:
                kwargs["token"] = token

            cls._torch_pipeline = Pipeline.from_pretrained(
                settings.torch_diarization_model,
                **kwargs,
            )
            if torch.backends.mps.is_available():
                cls._torch_pipeline.to(torch.device("mps"))
        return cls._torch_pipeline

    @classmethod
    def get_mlx_model(cls):
        if cls._mlx_model is None:
            from mlx_audio.vad import load

            cls._mlx_model = load(settings.mlx_diarization_model)
        return cls._mlx_model

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
        backend = self.get_backend()
        if backend == "mlx":
            return self._diarize_mlx(audio_path, min_speakers=min_speakers, max_speakers=max_speakers)
        return self._diarize_torch(audio_path, min_speakers=min_speakers, max_speakers=max_speakers)

    def _diarize_torch(
        self,
        audio_path: str,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
    ) -> list[dict]:
        pipeline = self.get_torch_pipeline()

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

    def _diarize_mlx(
        self,
        audio_path: str,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
    ) -> list[dict]:
        if min_speakers is not None or max_speakers is not None:
            log.info(get_translation("diarization.mlx_ignores_speaker_constraints"))

        model = self.get_mlx_model()
        result = model.generate(audio_path, threshold=0.5)

        segments = []
        for segment in result.segments:
            segments.append({
                "start": round(segment.start, 3),
                "end": round(segment.end, 3),
                "speaker": str(segment.speaker),
            })
        return segments

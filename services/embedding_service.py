import numpy as np
import torch
import torchaudio


class EmbeddingService:
    _model = None

    @classmethod
    def get_model(cls):
        if cls._model is None:
            from speechbrain.inference.speaker import EncoderClassifier

            cls._model = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                run_opts={"device": "cpu"},
            )
        return cls._model

    def extract_embedding(self, audio_path: str) -> np.ndarray:
        """Extract speaker embedding from audio file."""
        model = self.get_model()
        signal, sr = torchaudio.load(audio_path)

        # Resample to 16kHz if needed
        if sr != 16000:
            resampler = torchaudio.transforms.Resample(sr, 16000)
            signal = resampler(signal)

        # Mono
        if signal.shape[0] > 1:
            signal = signal.mean(dim=0, keepdim=True)

        embedding = model.encode_batch(signal)
        return embedding.squeeze().detach().cpu().numpy()

    def cosine_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Compute cosine similarity between two embeddings."""
        dot = np.dot(emb1, emb2)
        norm = np.linalg.norm(emb1) * np.linalg.norm(emb2)
        if norm == 0:
            return 0.0
        return float(dot / norm)

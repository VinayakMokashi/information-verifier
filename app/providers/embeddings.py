"""Local embeddings for the semantic claim cache.

EmbeddingGemma-300m via sentence-transformers, on CPU — $0 per lookup,
offline after the one-time gated download (needs HF_TOKEN the first time),
multilingual across the Indic languages this project cares about.

The model loads lazily on first use (a few seconds, then cached in memory)
so API startup stays instant and everything else works when the model is
absent: any failure here just means the cache falls back to exact matching.
"""
import threading
from typing import Protocol

from app.config import settings


class Embedder(Protocol):
    def embed(self, text: str) -> list[float]:
        """Return a unit-normalized embedding of `text`."""
        ...


class GemmaEmbedder:
    def __init__(self) -> None:
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    import os

                    if settings.hf_token:
                        os.environ.setdefault("HF_TOKEN", settings.hf_token)
                    from sentence_transformers import SentenceTransformer

                    self._model = SentenceTransformer(
                        settings.embedding_model,
                        truncate_dim=settings.embedding_dim,
                    )
        return self._model

    def embed(self, text: str) -> list[float]:
        model = self._load()
        # EmbeddingGemma ships task-specific prompts; STS is the right one for
        # symmetric claim<->claim similarity (vs asymmetric query->document).
        prompt = "STS" if "STS" in (model.prompts or {}) else None
        vec = model.encode(text, prompt_name=prompt, normalize_embeddings=True)
        return vec.tolist()


_default: GemmaEmbedder | None = None
_default_lock = threading.Lock()


def get_embedder() -> Embedder:
    global _default
    if _default is None:
        with _default_lock:
            if _default is None:
                _default = GemmaEmbedder()
    return _default

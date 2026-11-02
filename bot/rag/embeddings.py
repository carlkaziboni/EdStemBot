"""
Embedding model wrapper using sentence-transformers.

Provides a thin, synchronous interface around SentenceTransformer.
All heavy ML work happens here so it's easy to swap the model.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import List

import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingModel:
    """
    Wraps a sentence-transformers model for text embedding.

    Args:
        model_name: HuggingFace model identifier (e.g. "all-MiniLM-L6-v2").
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        backend: str = "sentence-transformers",
    ) -> None:
        self._model_name = model_name
        self._backend = backend
        self._model = None  # lazy-loaded on first use

    def _load(self):
        if self._model is None:
            logger.info("Loading embedding model: %s (%s)", self._model_name, self._backend)
            if self._backend == "fastembed":
                from fastembed import TextEmbedding

                name = self._model_name
                if "/" not in name:
                    name = f"sentence-transformers/{name}"
                # Project-local cache so the model downloaded at build time ships with the app.
                self._model = TextEmbedding(
                    model_name=name,
                    cache_dir=os.environ.get("FASTEMBED_CACHE_PATH", ".fastembed_cache"),
                )
            else:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self._model_name)
            logger.info("Embedding model loaded")
        return self._model

    def encode(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a list of text strings.

        Returns:
            List of float vectors, one per input text.
        """
        if not texts:
            return []
        model = self._load()
        if self._backend == "fastembed":
            return [np.asarray(v).tolist() for v in model.embed(texts)]
        embeddings: np.ndarray = model.encode(
            texts,
            show_progress_bar=len(texts) > 20,
            convert_to_numpy=True,
        )
        return embeddings.tolist()

    def encode_single(self, text: str) -> List[float]:
        """Embed a single text string."""
        return self.encode([text])[0]


@lru_cache(maxsize=2)
def get_embedding_model(
    model_name: str = "all-MiniLM-L6-v2", backend: str | None = None
) -> EmbeddingModel:
    """Return a cached EmbeddingModel; the backend defaults to settings.embedding_backend."""
    if backend is None:
        from config.settings import settings

        backend = settings.embedding_backend
    return EmbeddingModel(model_name, backend)

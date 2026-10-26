"""
Embedding model wrapper using sentence-transformers.

Provides a thin, synchronous interface around SentenceTransformer.
All heavy ML work happens here so it's easy to swap the model.
"""

from __future__ import annotations

import logging
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

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._model_name = model_name
        self._model = None  # lazy-loaded on first use

    def _load(self):
        if self._model is None:
            logger.info("Loading embedding model: %s", self._model_name)
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
        embeddings: np.ndarray = model.encode(
            texts,
            show_progress_bar=len(texts) > 20,
            convert_to_numpy=True,
        )
        return embeddings.tolist()

    def encode_single(self, text: str) -> List[float]:
        """Embed a single text string."""
        return self.encode([text])[0]


@lru_cache(maxsize=1)
def get_embedding_model(model_name: str = "all-MiniLM-L6-v2") -> EmbeddingModel:
    """Return a cached, singleton EmbeddingModel instance."""
    return EmbeddingModel(model_name)

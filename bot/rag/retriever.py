"""
RAG retriever — query → relevant course material chunks.

Embeds a student's question and returns the most semantically
relevant chunks from the ChromaDB vector store.
"""

from __future__ import annotations

import logging
from typing import List

from bot.rag.embeddings import EmbeddingModel
from bot.rag.vectorstore import RetrievedChunk, VectorStore

logger = logging.getLogger(__name__)

# Similarity threshold: cosine distance above this is considered "not relevant"
# ChromaDB cosine distance is 1 - cosine_similarity, so 0 = identical, 1 = orthogonal
_MAX_DISTANCE = 0.6


class Retriever:
    """
    Retrieves course material chunks relevant to a student question.

    Args:
        vectorstore: Initialised VectorStore.
        embedder: Initialised EmbeddingModel.
        n_results: Number of chunks to retrieve per query.
    """

    def __init__(
        self,
        vectorstore: VectorStore,
        embedder: EmbeddingModel,
        n_results: int = 5,
        max_distance: float = _MAX_DISTANCE,
    ) -> None:
        self.vectorstore = vectorstore
        self.embedder = embedder
        self.n_results = n_results
        self.max_distance = max_distance

    def retrieve(self, query: str) -> List[RetrievedChunk]:
        """
        Retrieve the most relevant chunks for a query string.

        Filters out chunks with cosine distance > max_distance.
        Returns an empty list if the vector store is empty.

        Args:
            query: The student's question (plain text).

        Returns:
            List of RetrievedChunk, best match first.
        """
        if self.vectorstore.count() == 0:
            logger.warning("VectorStore is empty — no course materials ingested yet")
            return []

        query_embedding = self.embedder.encode_single(query)
        chunks = self.vectorstore.query(query_embedding, n_results=self.n_results)

        # Filter irrelevant results
        relevant = [c for c in chunks if c.distance <= self.max_distance]

        if not relevant:
            logger.debug("No relevant chunks found for query (best dist=%.3f)", 
                        chunks[0].distance if chunks else -1)
        else:
            logger.debug(
                "Retrieved %d chunks (distances: %s)",
                len(relevant),
                [f"{c.distance:.3f}" for c in relevant],
            )

        return relevant

    def format_context(self, chunks: List[RetrievedChunk]) -> str:
        """
        Format retrieved chunks into a context string for LLM prompts.

        Returns an empty string if no chunks provided.
        """
        if not chunks:
            return ""
        parts = []
        for i, chunk in enumerate(chunks, start=1):
            where = f"Section: {chunk.section}" if chunk.section else f"Page {chunk.page}"
            parts.append(f"[Source: {chunk.source}, {where}]\n{chunk.text}")
        return "\n\n---\n\n".join(parts)

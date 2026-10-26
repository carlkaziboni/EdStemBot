"""
ChromaDB vector store wrapper.

Provides a simple interface for adding, querying, and deleting document
chunks in a persistent ChromaDB collection.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """A single chunk returned by a similarity search."""
    text: str
    source: str
    page: int
    chunk_index: int
    distance: float  # lower = more similar (L2) or 1 - cosine


class VectorStore:
    """
    Wrapper around a persistent ChromaDB collection.

    Args:
        persist_dir: Directory to store the ChromaDB files.
        collection_name: Name of the collection within ChromaDB.
    """

    def __init__(
        self,
        persist_dir: str = "./chroma_db",
        collection_name: str = "course_materials",
    ) -> None:
        import chromadb

        self._persist_dir = persist_dir
        self._collection_name = collection_name
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},  # Use cosine similarity
        )
        logger.info(
            "VectorStore ready — collection '%s' has %d chunks",
            collection_name,
            self._collection.count(),
        )

    # ── Write ─────────────────────────────────────────────────────────────────

    def add(
        self,
        texts: List[str],
        embeddings: List[List[float]],
        metadatas: List[dict],
        ids: List[str],
    ) -> None:
        """Add document chunks to the collection."""
        self._collection.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )

    def exists(self, chunk_id: str) -> bool:
        """Check whether a chunk ID already exists in the collection."""
        result = self._collection.get(ids=[chunk_id], include=[])
        return len(result["ids"]) > 0

    def get_existing_ids(self, chunk_ids: List[str]) -> set[str]:
        """Return the subset of chunk IDs that already exist in the collection."""
        if not chunk_ids:
            return set()
        existing: set[str] = set()
        batch_size = 500
        for i in range(0, len(chunk_ids), batch_size):
            batch = chunk_ids[i : i + batch_size]
            res = self._collection.get(ids=batch, include=[])
            existing.update(res.get("ids", []))
        return existing

    def delete_source(self, source_filename: str) -> None:
        """Remove all chunks that came from a particular file."""
        self._collection.delete(where={"source": source_filename})
        logger.info("Deleted all chunks from source: %s", source_filename)

    # ── Read ──────────────────────────────────────────────────────────────────

    def query(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        source_filter: Optional[str] = None,
    ) -> List[RetrievedChunk]:
        """
        Retrieve the most relevant chunks for a query embedding.

        Args:
            query_embedding: Embedding of the query text.
            n_results: Number of results to return.
            source_filter: If set, restrict results to this source filename.

        Returns:
            List of RetrievedChunk sorted by relevance (best first).
        """
        where = {"source": source_filter} if source_filter else None
        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(n_results, self._collection.count() or 1),
            include=["documents", "metadatas", "distances"],
            where=where,
        )

        chunks: List[RetrievedChunk] = []
        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        for doc, meta, dist in zip(docs, metas, distances):
            chunks.append(RetrievedChunk(
                text=doc,
                source=meta.get("source", ""),
                page=meta.get("page", 0),
                chunk_index=meta.get("chunk_index", 0),
                distance=dist,
            ))

        return chunks

    def count(self) -> int:
        """Total number of chunks stored."""
        return self._collection.count()

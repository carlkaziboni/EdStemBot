"""
PDF ingestion pipeline for course materials.

Reads PDF files from a directory, extracts text page-by-page,
chunks it into overlapping segments, embeds them with sentence-transformers,
and stores the results in ChromaDB.

Usage:
    python scripts/ingest_materials.py
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Generator


logger = logging.getLogger(__name__)

# ── Chunking constants ────────────────────────────────────────────────────────
_CHUNK_SIZE = 500       # characters per chunk (approx. 100–130 tokens)
_CHUNK_OVERLAP = 100    # overlap between consecutive chunks


def _extract_pages(pdf_path: Path) -> list[tuple[int, str]]:
    """
    Extract text from every page of a PDF.

    Returns:
        List of (page_number, text) tuples. Empty pages are skipped.
    """
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = text.strip()
        if text:
            pages.append((i, text))
    logger.debug("Extracted %d non-empty pages from %s", len(pages), pdf_path.name)
    return pages


def _chunk_text(text: str, source: str, page: int) -> Generator[dict, None, None]:
    """
    Split a text block into overlapping chunks with metadata.

    Yields dicts with keys: text, source, page, chunk_index.
    """
    start = 0
    chunk_index = 0
    while start < len(text):
        end = min(start + _CHUNK_SIZE, len(text))
        chunk = text[start:end].strip()
        if chunk:
            yield {
                "text": chunk,
                "source": source,
                "page": page,
                "chunk_index": chunk_index,
            }
            chunk_index += 1
        start += _CHUNK_SIZE - _CHUNK_OVERLAP


def _stable_chunk_id(source: str, page: int, chunk_index: int) -> str:
    """Generate a deterministic ID for a chunk (used to avoid re-inserting)."""
    raw = f"{source}::p{page}::c{chunk_index}"
    return hashlib.md5(raw.encode()).hexdigest()


class MaterialIngester:
    """
    Orchestrates PDF ingestion into ChromaDB.

    Args:
        vectorstore: An initialised VectorStore instance.
        embedder: An initialised EmbeddingModel instance.
    """

    def __init__(self, vectorstore, embedder) -> None:  # type: ignore[type-arg]
        self.vectorstore = vectorstore
        self.embedder = embedder

    def ingest_directory(self, directory: str | Path) -> int:
        """
        Ingest all PDF files from a directory.

        Returns:
            Number of chunks added to the vector store.
        """
        directory = Path(directory)
        pdfs = list(directory.glob("*.pdf"))
        if not pdfs:
            logger.warning("No PDF files found in %s", directory)
            return 0

        logger.info("Found %d PDF(s) to ingest", len(pdfs))
        total_added = 0
        for pdf_path in pdfs:
            added = self.ingest_file(pdf_path)
            total_added += added
        logger.info("Ingestion complete — %d chunks stored", total_added)
        return total_added

    def ingest_staff_qa(self, qa_data: dict[str, Any]) -> bool:
        """
        Embed and store a staff-answered Q&A pair into ChromaDB.

        Args:
            qa_data: Dict with keys: thread_id, title, question, answer, author, role.

        Returns:
            True if newly stored, False if already indexed.
        """
        thread_id = qa_data["thread_id"]
        cid = hashlib.md5(f"edstem_qa::{thread_id}".encode()).hexdigest()

        if self.vectorstore.exists(cid):
            logger.debug("Staff Q&A for thread %d already indexed", thread_id)
            return False

        chunk_text = (
            f"[Course Q&A: {qa_data.get('title', '')}]\n"
            f"Question: {qa_data.get('question', '')}\n\n"
            f"Official Answer (by {qa_data.get('author', 'Staff')} - {qa_data.get('role', 'Staff')}):\n"
            f"{qa_data.get('answer', '')}"
        )

        meta = {
            "source": f"EdStem Q&A #{thread_id}",
            "page": 0,
            "chunk_index": 0,
        }

        embedding = self.embedder.encode_single(chunk_text)
        self.vectorstore.add(
            texts=[chunk_text],
            embeddings=[embedding],
            metadatas=[meta],
            ids=[cid],
        )
        logger.info("Indexed staff Q&A from thread %d by %s", thread_id, qa_data.get("author"))
        return True

    def ingest_file(self, pdf_path: Path) -> int:
        """
        Ingest a single PDF file.

        Skips chunks whose IDs already exist in the store (incremental updates).

        Returns:
            Number of new chunks added.
        """
        logger.info("Ingesting: %s", pdf_path.name)
        pages = _extract_pages(pdf_path)

        all_chunks: list[dict] = []
        for page_num, page_text in pages:
            for chunk in _chunk_text(page_text, pdf_path.name, page_num):
                all_chunks.append(chunk)

        if not all_chunks:
            logger.warning("No text extracted from %s", pdf_path.name)
            return 0

        # Filter out already-stored chunks using batch lookup
        all_ids = [
            _stable_chunk_id(c["source"], c["page"], c["chunk_index"])
            for c in all_chunks
        ]
        if hasattr(self.vectorstore, "get_existing_ids"):
            existing_ids = self.vectorstore.get_existing_ids(all_ids)
        else:
            existing_ids = {cid for cid in all_ids if self.vectorstore.exists(cid)}

        new_chunks = [
            c for c, cid in zip(all_chunks, all_ids) if cid not in existing_ids
        ]

        if not new_chunks:
            logger.info("All %d chunks from %s already indexed — skipping", len(all_chunks), pdf_path.name)
            return 0

        logger.info("Embedding and indexing %d new chunks from %s...", len(new_chunks), pdf_path.name)

        # Batch embed and store
        batch_size = 128
        total_added = 0
        for i in range(0, len(new_chunks), batch_size):
            batch = new_chunks[i : i + batch_size]
            b_texts = [c["text"] for c in batch]
            b_metas = [
                {
                    "source": c["source"],
                    "page": c["page"],
                    "chunk_index": c["chunk_index"],
                }
                for c in batch
            ]
            b_ids = [
                _stable_chunk_id(c["source"], c["page"], c["chunk_index"])
                for c in batch
            ]

            b_embeddings = self.embedder.encode(b_texts)
            self.vectorstore.add(texts=b_texts, embeddings=b_embeddings, metadatas=b_metas, ids=b_ids)
            total_added += len(b_texts)
            logger.info("Indexed %d/%d chunks from %s", total_added, len(new_chunks), pdf_path.name)

        return total_added

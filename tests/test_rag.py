"""
Unit tests for the RAG pipeline components: chunking, retriever, and context formatting.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from bot.rag.ingest import _chunk_text, _stable_chunk_id
from bot.rag.retriever import Retriever
from bot.rag.vectorstore import RetrievedChunk


def test_chunking_logic():
    text = "A" * 1200
    source = "lecture_01.pdf"
    page = 1

    chunks = list(_chunk_text(text, source, page))
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk["source"] == source
        assert chunk["page"] == page
        assert len(chunk["text"]) <= 500


def test_stable_chunk_id():
    id1 = _stable_chunk_id("lecture_01.pdf", 1, 0)
    id2 = _stable_chunk_id("lecture_01.pdf", 1, 0)
    id3 = _stable_chunk_id("lecture_01.pdf", 1, 1)

    assert id1 == id2
    assert id1 != id3


def test_retriever_context_formatting():
    mock_vectorstore = MagicMock()
    mock_embedder = MagicMock()

    retriever = Retriever(vectorstore=mock_vectorstore, embedder=mock_embedder)

    chunks = [
        RetrievedChunk(
            text="Virtual memory decouples physical address space.",
            source="lecture_04.pdf",
            page=12,
            chunk_index=0,
            distance=0.15,
        ),
        RetrievedChunk(
            text="TLB caches page table entries.",
            source="lecture_04.pdf",
            page=15,
            chunk_index=1,
            distance=0.22,
        ),
    ]

    formatted = retriever.format_context(chunks)
    assert "[Source: lecture_04.pdf, Page 12]" in formatted
    assert "Virtual memory decouples" in formatted
    assert "[Source: lecture_04.pdf, Page 15]" in formatted
    assert "TLB caches page table entries." in formatted


def test_retriever_filters_distant_chunks():
    mock_vectorstore = MagicMock()
    mock_vectorstore.count.return_value = 10
    mock_vectorstore.query.return_value = [
        RetrievedChunk(text="Relevant", source="a.pdf", page=1, chunk_index=0, distance=0.25),
        RetrievedChunk(text="Irrelevant", source="b.pdf", page=2, chunk_index=1, distance=0.85),
    ]
    mock_embedder = MagicMock()
    mock_embedder.encode_single.return_value = [0.1] * 384

    retriever = Retriever(vectorstore=mock_vectorstore, embedder=mock_embedder)
    results = retriever.retrieve("Virtual memory page replacement")

    assert len(results) == 1
    assert results[0].text == "Relevant"

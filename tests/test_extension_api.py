"""Tests for the Chrome-extension API: quiz parsing, auth, and endpoints."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from bot.rag.vectorstore import RetrievedChunk
from bot.study import StudyService, parse_quiz
from config.settings import settings
from dashboard.app import app

GOOD = {
    "questions": [
        {"q": "What is a TLB?", "options": ["a", "b", "c", "d"], "answer_index": 2, "explanation": "x"},
        {"q": "bad: 3 options", "options": ["a", "b", "c"], "answer_index": 0},
        {"q": "bad: index", "options": ["a", "b", "c", "d"], "answer_index": 9},
    ]
}


def test_parse_quiz_filters_invalid_and_tolerates_prose():
    qs = parse_quiz("Here you go:\n" + json.dumps(GOOD), n=3)
    assert len(qs) == 1
    assert qs[0]["answer_index"] == 2


def test_parse_quiz_rejects_garbage():
    with pytest.raises(ValueError):
        parse_quiz("no json here", n=3)
    with pytest.raises(ValueError):
        parse_quiz(json.dumps({"questions": []}), n=3)


def _service(llm_reply: str) -> StudyService:
    chunk = RetrievedChunk(text="TLB caches translations", source="notes.pdf", page=4, chunk_index=0, distance=0.2)
    retriever = MagicMock()
    retriever.retrieve.return_value = [chunk]
    retriever.format_context.return_value = "ctx"
    llm = MagicMock()
    llm.generate = AsyncMock(return_value=llm_reply)
    classifier = MagicMock()
    classifier.classify = AsyncMock(return_value=["Virtual Memory"])
    return StudyService(retriever, llm, classifier)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "extension_secret", "s3cret")
    app.state.study = _service(json.dumps(GOOD))
    return TestClient(app)


def test_requires_key(client):
    body = {"title": "What is a TLB?"}
    assert client.post("/ext/quiz", json=body).status_code == 401
    assert client.post("/ext/quiz", json=body, headers={"X-EdStemBot-Key": "wrong"}).status_code == 401


def test_fails_closed_without_configured_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "extension_secret", "")
    r = client.post("/ext/answer", json={"title": "t"}, headers={"X-EdStemBot-Key": ""})
    assert r.status_code == 503


def test_quiz_and_answer_ok(client):
    h = {"X-EdStemBot-Key": "s3cret"}
    q = client.post("/ext/quiz", json={"title": "tlb?", "body": "unique-quiz"}, headers=h)
    assert q.status_code == 200
    assert q.json()["topic"] == "Virtual Memory"
    a = client.post("/ext/answer", json={"title": "tlb?", "body": "unique-answer"}, headers=h)
    assert a.status_code == 200
    assert a.json()["sources"] == ["notes.pdf p.4"]
    assert a.json()["confidence"] == 0.8

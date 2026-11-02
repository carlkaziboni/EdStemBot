"""Tests for askEd Live: quiz bank, stats, rate limiting, routes and live-only mounting."""

from __future__ import annotations

import asyncio
import json
import random
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from bot.analytics.tracker import AnalyticsTracker
from bot.live.quiz_bank import QuizBank, QuizBankError
from bot.live.ratelimit import RateLimiter
from bot.live.stats import build_stats
from bot.live.store import LiveStore
from config.settings import settings
from dashboard.app import create_app

KEY = "present-secret"
SID_A, SID_B = "a" * 16, "b" * 16


def q(qid: str, topic: str, answer: int = 1) -> dict:
    return {
        "id": qid,
        "topic": topic,
        "q": f"Question {qid}?",
        "options": ["w", "x", "y", "z"],
        "answer_index": answer,
        "explanation": "because",
    }


BANK = [q("c1", "Cache"), q("c2", "Cache"), q("v1", "Virtual Memory"), q("v2", "Virtual Memory")]


# ── pure units ──────────────────────────────────────────────────────────────

def test_bank_rejects_malformed():
    bad = q("x", "Cache")
    bad["options"] = ["only", "three", "options"]
    with pytest.raises(QuizBankError):
        QuizBank([bad])
    with pytest.raises(QuizBankError):
        QuizBank([q("d", "Cache"), q("d", "Cache")])  # duplicate ids
    worse = q("y", "Cache")
    worse["answer_index"] = 7
    with pytest.raises(QuizBankError):
        QuizBank([worse])


def test_pick_set_interleaves_topics_and_hides_answers():
    picked = QuizBank(BANK).pick_set(4, random.Random(1))
    assert len(picked) == 4
    assert {p["topic"] for p in picked[:2]} == {"Cache", "Virtual Memory"}
    for p in picked:
        assert "answer_index" not in p and "explanation" not in p


def test_rate_limiter_window_and_daily_cap():
    rl = RateLimiter(per_window=2, window_s=60, daily_cap=3)
    assert rl.allow("s", now=0) is None
    assert rl.allow("s", now=1) is None
    assert rl.allow("s", now=2) == "rate"
    assert rl.allow("s", now=100) is None  # window slid past the first hits
    assert rl.allow("other", now=100) == "daily"  # 3 allowed today


def test_build_stats_ranks_and_applies_minimum():
    lookup = {x["id"]: x for x in BANK}
    attempts = []
    # Cache: 6 attempts, 5 wrong (most picked wrong option = index 2). Virtual Memory: 2 attempts, all wrong.
    for i in range(6):
        attempts.append({"session_id": f"s{i}", "question_id": "c1", "topic": "Cache",
                         "chosen_index": 1 if i == 0 else 2, "correct": i == 0})
    for i in range(2):
        attempts.append({"session_id": f"s{i}", "question_id": "v1", "topic": "Virtual Memory",
                         "chosen_index": 0, "correct": False})
    asked = [{"session_id": "s9", "topic_tags": json.dumps(["Cache", "Networking"])}]

    stats = build_stats(attempts, asked, lookup, min_attempts=5)

    assert stats["participants"] == 7  # s0-s5 plus s9
    assert stats["topics"][0]["topic"] == "Cache" and stats["topics"][0]["ranked"]
    assert stats["topics"][0]["pct_incorrect"] == 83
    # Virtual Memory is 100% wrong but has too few answers, so it must not outrank Cache.
    assert stats["topics"][1]["topic"] == "Virtual Memory" and not stats["topics"][1]["ranked"]
    hardest = stats["topics"][0]["hardest_question"]
    assert hardest["top_wrong"] == {"text": "y", "count": 5}
    assert {a["topic"] for a in stats["asked_topics"]} == {"Cache", "Networking"}


# ── routes ──────────────────────────────────────────────────────────────────

@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def live(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "presenter_key", KEY)
    monkeypatch.setattr(settings, "public_base_url", "https://asked.example.com")
    monkeypatch.setattr(settings, "live_min_attempts", 2)

    tracker = AnalyticsTracker(f"sqlite+aiosqlite:///{tmp_path}/live.db")
    await tracker.init_db()

    app = create_app(live_only=True)
    app.state.live_store = LiveStore(tracker.session_factory)
    app.state.quiz_bank = QuizBank(BANK)
    app.state.limiter = RateLimiter(per_window=2, window_s=60, daily_cap=100)
    app.state.ask_semaphore = asyncio.Semaphore(2)
    about = MagicMock()
    about.answer = AsyncMock(
        return_value={"answer": "askEd is read-only.", "topics": ["EdStem integration"],
                      "confidence": 0.8, "sources": ["askEd FAQ: What is askEd?"], "grounded": True}
    )
    app.state.about = about

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        client.app = app  # type: ignore[attr-defined]
        yield client
    await tracker.engine.dispose()


@pytest.mark.anyio
async def test_quiz_never_leaks_answers_and_check_is_correct(live):
    r = await live.get("/live/quiz", params={"n": 4})
    assert r.status_code == 200
    for item in r.json()["questions"]:
        assert set(item) == {"id", "topic", "q", "options"}

    right = await live.post("/live/quiz/answer", json={"session_id": SID_A, "question_id": "c1", "chosen_index": 1})
    wrong = await live.post("/live/quiz/answer", json={"session_id": SID_B, "question_id": "c1", "chosen_index": 0})
    assert right.json()["correct"] is True and right.json()["answer_index"] == 1
    assert wrong.json()["correct"] is False
    missing = await live.post("/live/quiz/answer", json={"session_id": SID_A, "question_id": "nope", "chosen_index": 0})
    assert missing.status_code == 404


@pytest.mark.anyio
async def test_repeat_answers_are_not_double_counted(live):
    body = {"session_id": SID_A, "question_id": "c1", "chosen_index": 0}
    for _ in range(3):
        assert (await live.post("/live/quiz/answer", json=body)).status_code == 200
    stats = (await live.get("/live/stats", headers={"X-Presenter-Key": KEY})).json()
    assert stats["attempts"] == 1


@pytest.mark.anyio
async def test_rejects_bad_session_ids_and_choices(live):
    bad_sid = await live.post("/live/quiz/answer", json={"session_id": "x", "question_id": "c1", "chosen_index": 0})
    bad_choice = await live.post("/live/quiz/answer", json={"session_id": SID_A, "question_id": "c1", "chosen_index": 9})
    assert bad_sid.status_code == 422 and bad_choice.status_code == 422


@pytest.mark.anyio
async def test_ask_logs_question_and_is_rate_limited(live):
    ok = await live.post("/live/ask", json={"session_id": SID_A, "text": "Does askEd post to EdStem?"})
    assert ok.status_code == 200 and ok.json()["topics"] == ["EdStem integration"]
    await live.post("/live/ask", json={"session_id": SID_A, "text": "again"})
    third = await live.post("/live/ask", json={"session_id": SID_A, "text": "and again"})
    assert third.status_code == 429
    stats = (await live.get("/live/stats", headers={"X-Presenter-Key": KEY})).json()
    assert stats["questions_asked"] == 2


@pytest.mark.anyio
async def test_ask_failure_returns_502_but_saves_question_for_followup(live):
    live.app.state.about.answer = AsyncMock(side_effect=RuntimeError("llm down"))
    r = await live.post("/live/ask", json={"session_id": SID_A, "text": "hello"})
    assert r.status_code == 502 and "saved" in r.json()["detail"]
    stats = (await live.get("/live/stats", headers={"X-Presenter-Key": KEY})).json()
    assert stats["questions_asked"] == 1 and stats["needs_followup"] == 1


@pytest.mark.anyio
async def test_presenter_routes_need_the_key(live):
    assert (await live.get("/present")).status_code == 401
    assert (await live.get("/present", params={"key": "wrong"})).status_code == 401
    assert (await live.get("/live/stats")).status_code == 401
    assert (await live.post("/live/reset")).status_code == 401
    page = await live.get("/present", params={"key": KEY})
    assert page.status_code == 200 and "https://asked.example.com/ask" in page.text


@pytest.mark.anyio
async def test_presenter_fails_closed_without_configured_key(live, monkeypatch):
    monkeypatch.setattr(settings, "presenter_key", "")
    assert (await live.get("/live/stats", headers={"X-Presenter-Key": ""})).status_code == 503


@pytest.mark.anyio
async def test_reset_clears_everything(live):
    await live.post("/live/quiz/answer", json={"session_id": SID_A, "question_id": "c1", "chosen_index": 0})
    await live.post("/live/ask", json={"session_id": SID_A, "text": "hello"})
    assert (await live.post("/live/reset", headers={"X-Presenter-Key": KEY})).status_code == 200
    stats = (await live.get("/live/stats", headers={"X-Presenter-Key": KEY})).json()
    assert stats["participants"] == 0 and stats["attempts"] == 0 and stats["questions_asked"] == 0


@pytest.mark.anyio
async def test_qr_is_svg_and_pages_render(live):
    qr = await live.get("/present/qr.svg")
    assert qr.status_code == 200 and qr.headers["content-type"].startswith("image/svg+xml")
    assert "<svg" in qr.text
    assert (await live.get("/ask")).status_code == 200
    assert (await live.get("/healthz")).json() == {"status": "ok"}


@pytest.mark.anyio
async def test_live_mode_does_not_mount_private_routes(live):
    for path in ("/", "/topics", "/unclassified", "/api/v1/kpis", "/docs", "/openapi.json"):
        assert (await live.get(path)).status_code == 404, path
    assert (await live.post("/ext/answer", json={"title": "t"})).status_code == 404

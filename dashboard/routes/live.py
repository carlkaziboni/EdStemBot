"""
askEd Live routes.

Public (audience phones): /ask, /live/ask, /live/quiz, /live/quiz/answer, /healthz.
Presenter (needs PRESENTER_KEY): /present, /live/stats, /live/reset.
"""

from __future__ import annotations

import asyncio
import hmac
import io
import logging
from pathlib import Path

import segno
from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from bot.live.about import FALLBACK_TOPIC
from config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

SESSION_PATTERN = r"^[A-Za-z0-9_-]{8,64}$"
ASK_TIMEOUT_S = 45


class AskIn(BaseModel):
    session_id: str = Field(pattern=SESSION_PATTERN)
    text: str = Field(min_length=1, max_length=500)


class AnswerIn(BaseModel):
    session_id: str = Field(pattern=SESSION_PATTERN)
    question_id: str = Field(max_length=64)
    chosen_index: int = Field(ge=0, le=3)


def _presenter_auth(key: str | None) -> None:
    secret = settings.presenter_key
    if not secret:
        raise HTTPException(503, "PRESENTER_KEY is not set on the server")
    if not key or not hmac.compare_digest(key, secret):
        raise HTTPException(401, "invalid presenter key")


def _state(request: Request, name: str):
    value = getattr(request.app.state, name, None)
    if value is None:
        raise HTTPException(503, f"{name} not ready")
    return value


def _join_url(request: Request) -> str:
    base = settings.public_base_url or str(request.base_url)
    return base.rstrip("/") + "/ask"


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


# ── Audience ────────────────────────────────────────────────────────────────

@router.get("/ask", response_class=HTMLResponse)
async def ask_page(request: Request):
    return templates.TemplateResponse(request, "ask.html", {})


@router.post("/live/ask")
async def live_ask(data: AskIn, request: Request):
    limiter = _state(request, "limiter")
    reason = limiter.allow(data.session_id)
    if reason == "rate":
        raise HTTPException(429, "Slow down a little and try again in a minute.")
    if reason == "daily":
        raise HTTPException(429, "askEd has reached its question limit for today.")

    about = _state(request, "about")
    store = _state(request, "live_store")
    text = data.text.strip()
    try:
        async with request.app.state.ask_semaphore:
            result = await asyncio.wait_for(about.answer(text), timeout=ASK_TIMEOUT_S)
    except Exception as exc:
        # Keep the question so the presenter can see it needs follow-up, even though
        # the model failed. Never log the question text itself.
        timed_out = isinstance(exc, asyncio.TimeoutError)
        if not timed_out:
            logger.exception("live answer failed")
        await store.log_question(data.session_id, text, "", [FALLBACK_TOPIC], None)
        if timed_out:
            raise HTTPException(504, "askEd took too long. Your question was saved. Please try again.")
        raise HTTPException(502, "askEd could not answer that right now. Your question was saved.")

    await store.log_question(
        data.session_id, text, result["answer"], result["topics"], result["confidence"]
    )
    return result


@router.get("/live/quiz")
async def live_quiz(request: Request, n: int = Query(default=10, ge=1, le=30)):
    bank = _state(request, "quiz_bank")
    if len(bank) == 0:
        raise HTTPException(503, "The quiz has not been set up yet.")
    return {"questions": bank.pick_set(n)}


@router.post("/live/quiz/answer")
async def live_quiz_answer(data: AnswerIn, request: Request):
    bank = _state(request, "quiz_bank")
    store = _state(request, "live_store")
    result = bank.check(data.question_id, data.chosen_index)
    if result is None:
        raise HTTPException(404, "unknown question")
    await store.log_attempt(
        data.session_id, data.question_id, result["topic"], data.chosen_index, result["correct"]
    )
    return result


# ── Presenter ───────────────────────────────────────────────────────────────

@router.get("/present", response_class=HTMLResponse)
async def present_page(request: Request, key: str | None = Query(default=None)):
    _presenter_auth(key)
    return templates.TemplateResponse(
        request, "present.html", {"join_url": _join_url(request)}
    )


@router.get("/present/qr.svg")
async def qr_svg(request: Request):
    """The QR only encodes the public join URL, so it needs no key."""
    buf = io.BytesIO()
    segno.make(_join_url(request), error="m").save(
        buf, kind="svg", scale=12, border=2, dark="#000000", light="#ffffff"
    )
    return Response(buf.getvalue(), media_type="image/svg+xml")


@router.get("/live/stats")
async def live_stats(
    request: Request, x_presenter_key: str | None = Header(default=None)
):
    _presenter_auth(x_presenter_key)
    store = _state(request, "live_store")
    bank = _state(request, "quiz_bank")
    return await store.get_stats(bank.lookup(), settings.live_min_attempts)


@router.post("/live/reset")
async def live_reset(
    request: Request, x_presenter_key: str | None = Header(default=None)
):
    _presenter_auth(x_presenter_key)
    await _state(request, "live_store").reset()
    return {"status": "cleared"}

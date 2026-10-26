"""
Local API for the EdStemBot Chrome extension.

Read-only helper endpoints: answer previews and MCQ quizzes. Protected by a
shared secret so other local web pages cannot call them.
"""

from __future__ import annotations

import hashlib
import hmac
import logging

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ext", tags=["extension"])

_cache: dict[str, dict] = {}
_CACHE_MAX = 200


class ThreadIn(BaseModel):
    title: str = Field(max_length=500)
    body: str = Field(default="", max_length=8000)
    n: int = Field(default=3, ge=1, le=5)
    refresh: bool = False


def _auth(key: str | None) -> None:
    secret = settings.extension_secret
    if not secret:
        raise HTTPException(503, "EXTENSION_SECRET is not set on the server")
    if not key or not hmac.compare_digest(key, secret):
        raise HTTPException(401, "invalid key")


def _service(request: Request):
    service = getattr(request.app.state, "study", None)
    if service is None:
        raise HTTPException(503, "study service not ready")
    return service


def _cache_key(kind: str, data: ThreadIn) -> str:
    raw = f"{kind}|{data.title}|{data.body}|{data.n}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _remember(key: str, value: dict) -> dict:
    if len(_cache) >= _CACHE_MAX:
        _cache.pop(next(iter(_cache)))
    _cache[key] = value
    return value


@router.post("/answer")
async def answer(
    data: ThreadIn, request: Request, x_edstembot_key: str | None = Header(default=None)
):
    _auth(x_edstembot_key)
    key = _cache_key("answer", data)
    if not data.refresh and key in _cache:
        return _cache[key]
    try:
        result = await _service(request).answer(data.title, data.body)
    except HTTPException:
        raise
    except Exception:
        logger.exception("answer generation failed")
        raise HTTPException(502, "answer generation failed")
    return _remember(key, result)


@router.post("/quiz")
async def quiz(
    data: ThreadIn, request: Request, x_edstembot_key: str | None = Header(default=None)
):
    _auth(x_edstembot_key)
    key = _cache_key("quiz", data)
    if not data.refresh and key in _cache:
        return _cache[key]
    try:
        result = await _service(request).quiz(data.title, data.body, data.n)
    except HTTPException:
        raise
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    except Exception:
        logger.exception("quiz generation failed")
        raise HTTPException(502, "quiz generation failed")
    return _remember(key, result)

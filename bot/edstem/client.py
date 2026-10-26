"""
EdStem REST API client — read-only operations.

Uses EdStem's unofficial internal REST API with bearer-token authentication.
All methods are async and use httpx.AsyncClient.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import httpx

from bot.edstem.models import Comment, Course, Thread, User

logger = logging.getLogger(__name__)

# Retry configuration
_MAX_RETRIES = 3
_RETRY_BACKOFF_BASE = 1.5  # seconds


class EdStemClient:
    """
    Async, read-only client for the EdStem REST API.

    Usage:
        async with EdStemClient(token="...", base_url="https://us.edstem.org") as client:
            threads = await client.list_threads(course_id=12345)
    """

    def __init__(self, token: str, base_url: str = "https://us.edstem.org") -> None:
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    # ── Context manager ──────────────────────────────────────────────────────

    async def __aenter__(self) -> "EdStemClient":
        self._client = httpx.AsyncClient(
            base_url=f"{self._base_url}/api",
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=30.0,
        )
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._client:
            await self._client.aclose()

    # ── Internal helpers ─────────────────────────────────────────────────────

    async def _get(self, path: str, **params: Any) -> dict[str, Any]:
        """Perform a GET request with retry + exponential backoff."""
        assert self._client, "Client not initialised — use as async context manager"
        for attempt in range(_MAX_RETRIES):
            try:
                response = await self._client.get(path, params=params or None)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    # Rate-limited — back off
                    wait = _RETRY_BACKOFF_BASE ** attempt
                    logger.warning("Rate limited by EdStem, retrying in %.1fs…", wait)
                    await asyncio.sleep(wait)
                elif exc.response.status_code in (401, 403):
                    logger.error("EdStem auth failure: %s", exc.response.text)
                    raise
                else:
                    logger.error("EdStem API error %s: %s", exc.response.status_code, exc.response.text)
                    raise
            except httpx.RequestError as exc:
                wait = _RETRY_BACKOFF_BASE ** attempt
                logger.warning("Network error (%s), retrying in %.1fs…", exc, wait)
                await asyncio.sleep(wait)
        raise RuntimeError(f"EdStem GET {path} failed after {_MAX_RETRIES} retries")

    # ── Public API ───────────────────────────────────────────────────────────

    async def get_course(self, course_id: int) -> Course:
        """Fetch course metadata."""
        data = await self._get(f"/courses/{course_id}")
        return Course(**data.get("course", data))

    async def list_threads(
        self,
        course_id: int,
        *,
        limit: int = 30,
        offset: int = 0,
        sort: str = "new",
    ) -> list[Thread]:
        """
        List threads in a course.

        Args:
            course_id: The EdStem course ID.
            limit: Max threads per page (EdStem default is 30).
            offset: Pagination offset.
            sort: Sort order — "new" | "top" | "unanswered".
        """
        data = await self._get(
            f"/courses/{course_id}/threads",
            limit=limit,
            offset=offset,
            sort=sort,
        )
        threads_raw = data.get("threads", [])
        threads = []
        for raw in threads_raw:
            try:
                threads.append(Thread(**raw))
            except Exception as exc:
                logger.debug("Skipping malformed thread: %s", exc)
        return threads

    async def get_thread(self, thread_id: int) -> Thread:
        """Fetch a single thread by ID."""
        data = await self._get(f"/threads/{thread_id}")
        return Thread(**data.get("thread", data))

    async def get_thread_staff_qa(self, thread_id: int) -> Optional[dict[str, Any]]:
        """
        Fetch a thread and extract any staff or accepted answer.

        Returns:
            Dict containing question & answer text and staff author metadata,
            or None if no staff answer exists.
        """
        import re

        data = await self._get(f"/threads/{thread_id}")
        thread_data = data.get("thread", data)
        users = {u.get("id"): u for u in data.get("users", []) if isinstance(u, dict)}

        answers = thread_data.get("answers", [])
        if not answers:
            return None

        accepted_id = thread_data.get("accepted_id")

        for a in answers:
            u_id = a.get("user_id")
            user = users.get(u_id, {})
            course_role = (user.get("course_role") or "").lower()
            system_role = (user.get("role") or "").lower()

            is_staff = course_role in ("admin", "staff", "ta", "tutor", "mentor", "instructor") or system_role == "admin"
            is_accepted = a.get("id") == accepted_id

            if is_staff or is_accepted:
                raw_q = thread_data.get("document") or thread_data.get("content") or ""
                q_text = re.sub(r"<[^>]+>", " ", raw_q).strip()

                raw_a = a.get("document") or a.get("content") or ""
                a_text = re.sub(r"<[^>]+>", " ", raw_a).strip()

                if a_text:
                    return {
                        "thread_id": thread_id,
                        "title": thread_data.get("title", ""),
                        "question": q_text,
                        "answer": a_text,
                        "author": user.get("name", "Staff Member"),
                        "role": user.get("course_role") or "staff",
                        "is_accepted": is_accepted,
                    }

        return None

    async def get_user(self, user_id: int) -> User:
        """Fetch a user by ID."""
        data = await self._get(f"/users/{user_id}")
        return User(**data.get("user", data))

    async def get_recent_questions(
        self,
        course_id: int,
        limit: int = 50,
    ) -> list[Thread]:
        """Convenience: fetch only question-type threads, sorted by newest."""
        threads = await self.list_threads(course_id, limit=limit, sort="new")
        return [t for t in threads if t.is_question]

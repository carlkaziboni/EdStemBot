"""Small in-memory limiters to bound LLM spend on the public endpoint."""

from __future__ import annotations

import time
from collections import deque
from datetime import date


class RateLimiter:
    """Sliding-window limit per key, plus a hard cap per calendar day."""

    def __init__(self, per_window: int, window_s: float, daily_cap: int) -> None:
        self.per_window = per_window
        self.window_s = window_s
        self.daily_cap = daily_cap
        self._hits: dict[str, deque[float]] = {}
        self._day = date.today()
        self._today = 0

    def allow(self, key: str, now: float | None = None) -> str | None:
        """Return None if allowed (and record it), else a reason string."""
        now = time.monotonic() if now is None else now
        if date.today() != self._day:
            self._day, self._today = date.today(), 0
        if self._today >= self.daily_cap:
            return "daily"
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] > self.window_s:
            hits.popleft()
        if len(hits) >= self.per_window:
            return "rate"
        hits.append(now)
        self._today += 1
        return None

"""
EdStem WebSocket listener.

Connects to EdStem's real-time WebSocket stream and emits events for
new threads (questions). Calls back into QuestionProcessor on each new
question-type thread.

EdStem uses a custom WebSocket protocol. Messages are JSON with a "type" field.
Key subscription message format (reverse-engineered):
    {"type": "subscribe", "data": {"course_id": <id>}}

Incoming events of interest:
    {"type": "thread.new", "data": {"thread": {...}}}
    {"type": "thread.update", "data": {"thread": {...}}}
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Callable, Awaitable, Optional

try:
    import websockets
    from websockets.exceptions import ConnectionClosedError, WebSocketException
except ImportError:
    websockets = None  # type: ignore
    ConnectionClosedError = Exception  # type: ignore
    WebSocketException = Exception  # type: ignore

from bot.edstem.models import Thread

logger = logging.getLogger(__name__)

# Reconnect config
_RECONNECT_DELAY_INITIAL = 2.0   # seconds
_RECONNECT_DELAY_MAX = 60.0      # seconds
_RECONNECT_DELAY_FACTOR = 2.0    # exponential backoff multiplier

ThreadCallback = Callable[[Thread], Awaitable[None]]


class EdStemWebSocketListener:
    """
    Persistent WebSocket listener for EdStem course events.

    Automatically reconnects on disconnection with exponential backoff.

    Args:
        token: EdStem API bearer token.
        course_id: Course to subscribe to.
        on_new_thread: Async callback invoked for each new question thread.
        base_url: Regional EdStem base URL.
    """

    def __init__(
        self,
        token: str,
        course_id: int,
        on_new_thread: ThreadCallback,
        base_url: str = "https://us.edstem.org",
    ) -> None:
        self._token = token
        self._course_id = course_id
        self._on_new_thread = on_new_thread
        # Convert https:// to wss://
        ws_base = base_url.replace("https://", "wss://").replace("http://", "ws://")
        self._ws_url = f"{ws_base}/api/stream"
        self._running = False

    # ── Public ───────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """
        Run the WebSocket listener loop indefinitely.
        Reconnects automatically on disconnection.
        """
        self._running = True
        delay = _RECONNECT_DELAY_INITIAL

        while self._running:
            try:
                await self._connect_and_listen()
                # If we get here cleanly, reset backoff
                delay = _RECONNECT_DELAY_INITIAL
            except (ConnectionClosedError, WebSocketException) as exc:
                logger.warning("WebSocket disconnected: %s", exc)
            except asyncio.CancelledError:
                logger.info("WebSocket listener cancelled")
                break
            except Exception as exc:
                logger.error("Unexpected WebSocket error: %s", exc, exc_info=True)

            if self._running:
                logger.info("Reconnecting in %.0fs…", delay)
                await asyncio.sleep(delay)
                delay = min(delay * _RECONNECT_DELAY_FACTOR, _RECONNECT_DELAY_MAX)

    def stop(self) -> None:
        """Signal the listener to stop after the current reconnect cycle."""
        self._running = False

    # ── Internal ─────────────────────────────────────────────────────────────

    async def _connect_and_listen(self) -> None:
        """Open a single WebSocket connection and process messages until closed."""
        if websockets is None:
            raise RuntimeError("websockets is required for WebSocket listener. Run: pip install websockets")

        headers = {"Authorization": f"Bearer {self._token}"}

        async with websockets.connect(
            self._ws_url,
            additional_headers=headers,
            ping_interval=30,
            ping_timeout=10,
        ) as ws:
            logger.info("WebSocket connected to %s", self._ws_url)

            # Subscribe to course events
            await ws.send(json.dumps({
                "type": "course.subscribe",
                "data": {"course_id": self._course_id},
            }))
            logger.info("Subscribed to course %d events", self._course_id)

            async for raw_message in ws:
                if not self._running:
                    break
                await self._handle_message(raw_message)

    async def _handle_message(self, raw: str | bytes) -> None:
        """Parse and dispatch a single WebSocket message."""
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            logger.debug("Non-JSON WebSocket message ignored: %s", raw)
            return

        event_type: str = msg.get("type", "")
        data: dict = msg.get("data", {})

        logger.debug("WS event: %s", event_type)

        if event_type in ("thread.new", "thread.create", "new_thread"):
            thread_data = data.get("thread", data)
            try:
                thread = Thread(**thread_data)
                if thread.is_question:
                    logger.info("New question: [%d] %s", thread.id, thread.title)
                    await self._on_new_thread(thread)
            except Exception as exc:
                logger.warning("Could not parse thread event: %s | data=%s", exc, data)

        elif event_type == "thread.update":
            # Optionally handle updates (e.g., edits) in a future phase
            pass

        elif event_type in ("heartbeat", "ping", "pong"):
            pass  # Ignore keep-alive messages

        else:
            logger.debug("Unhandled event type: %s", event_type)

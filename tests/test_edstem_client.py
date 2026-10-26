"""
Unit tests for the EdStem REST client with mocked HTTP transport.
"""

from __future__ import annotations

import httpx
import pytest

from bot.edstem.client import EdStemClient
from bot.edstem.models import Comment, Thread


@pytest.mark.anyio
async def test_edstem_client_list_threads():
    fake_threads_data = {
        "threads": [
            {
                "id": 1,
                "course_id": 999,
                "title": "Cache associativity",
                "type": "question",
                "document": "<p>Is direct-mapped cache 1-way associative?</p>",
                "user_id": 10,
            },
            {
                "id": 2,
                "course_id": 999,
                "title": "Welcome to CS201",
                "type": "announcement",
                "document": "<p>Class starts Monday</p>",
                "user_id": 1,
            },
        ]
    }

    def handler(request: httpx.Request):
        assert "Authorization" in request.headers
        assert request.headers["Authorization"] == "Bearer test_token"
        if request.url.path == "/api/courses/999/threads":
            return httpx.Response(200, json=fake_threads_data)
        return httpx.Response(404)

    client = EdStemClient(token="test_token", base_url="https://us.edstem.org")
    client._client = httpx.AsyncClient(
        base_url="https://us.edstem.org/api",
        headers={"Authorization": "Bearer test_token"},
        transport=httpx.MockTransport(handler),
    )

    threads = await client.list_threads(course_id=999)
    assert len(threads) == 2
    assert threads[0].id == 1
    assert threads[0].title == "Cache associativity"
    assert threads[0].plain_text == "Is direct-mapped cache 1-way associative?"

    questions = await client.get_recent_questions(course_id=999)
    assert len(questions) == 1
    assert questions[0].is_question is True
    assert questions[0].id == 1

    await client._client.aclose()


def test_thread_plain_text_strip_html():
    thread = Thread(
        id=5,
        course_id=999,
        title="Test",
        document="<div>Hello <b>world</b>! &nbsp; <code>code block</code></div>",
    )
    assert "Hello" in thread.plain_text
    assert "world" in thread.plain_text
    assert "<b>" not in thread.plain_text

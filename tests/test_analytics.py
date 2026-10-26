"""
Unit tests for the SQLite AnalyticsTracker and SQLAlchemy models.
"""

from __future__ import annotations

import os
import tempfile
import pytest

from bot.analytics.models import QuestionLog, TopicTrend
from bot.analytics.tracker import AnalyticsTracker
from bot.edstem.models import Thread


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db_url = f"sqlite+aiosqlite:///{path}"
    yield db_url
    if os.path.exists(path):
        os.remove(path)


@pytest.mark.anyio
async def test_analytics_tracker_lifecycle(temp_db):
    tracker = AnalyticsTracker(database_url=temp_db)
    await tracker.init_db()

    # 1. Log a question
    thread = Thread(
        id=42,
        course_id=101,
        title="What is a page fault?",
        content="<p>Can someone explain virtual memory and page faults?</p>",
        type="question",
        user_id=55,
    )

    log_entry = await tracker.log_question(
        thread=thread,
        topics=["Virtual Memory", "Operating Systems"],
        confidence_score=0.91,
        was_classifiable=True,
    )

    assert log_entry.id is not None
    assert log_entry.thread_id == 42
    assert "Virtual Memory" in log_entry.topics
    assert "Operating Systems" in log_entry.topics
    assert log_entry.confidence_score == 0.91

    # 2. Verify KPIs
    kpis = await tracker.get_kpis()
    assert kpis["total_questions"] == 1
    assert kpis["unique_students"] == 1
    assert kpis["unclassified_count"] == 0
    assert kpis["classifiable_rate"] == 100.0

    # 3. Verify Topic Counts
    counts = await tracker.get_topic_counts()
    assert len(counts) == 2
    topic_map = {item["topic"]: item["count"] for item in counts}
    assert topic_map["Virtual Memory"] == 1
    assert topic_map["Operating Systems"] == 1

    # 4. Verify Recent Questions
    recent = await tracker.get_recent_questions(limit=5)
    assert len(recent) == 1
    assert recent[0]["title"] == "What is a page fault?"

    # 5. Verify Unclassified
    unclassified_thread = Thread(
        id=43,
        course_id=101,
        title="Lost water bottle",
        content="Did anyone find a blue bottle in lecture hall?",
        type="question",
        user_id=56,
    )
    await tracker.log_question(
        thread=unclassified_thread,
        topics=["Other"],
        confidence_score=0.1,
        was_classifiable=False,
    )

    unclassified_list = await tracker.get_unclassified_questions()
    assert len(unclassified_list) == 1
    assert unclassified_list[0]["thread_id"] == 43

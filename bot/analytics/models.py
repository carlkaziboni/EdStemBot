"""
SQLAlchemy ORM models for the analytics database (SQLite via aiosqlite).
"""

from __future__ import annotations

import json
from datetime import datetime, date

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class QuestionLog(Base):
    """
    Logs every new question seen by the bot.

    topic_tags is stored as a JSON string (SQLite has no native array type).
    """
    __tablename__ = "question_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thread_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    course_id: Mapped[int] = mapped_column(Integer, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(512), default="")
    question_text: Mapped[str] = mapped_column(Text, default="")
    topic_tags: Mapped[str] = mapped_column(Text, default="[]")  # JSON list
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    was_classifiable: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True
    )

    # ── Helpers ──────────────────────────────────────────────────────────────

    @property
    def topics(self) -> list[str]:
        """Deserialise topic_tags JSON string → list."""
        try:
            return json.loads(self.topic_tags)
        except (json.JSONDecodeError, TypeError):
            return []

    @topics.setter
    def topics(self, value: list[str]) -> None:
        self.topic_tags = json.dumps(value)


class TopicTrend(Base):
    """
    Daily aggregated question counts per topic.

    Updated by the tracker each time a new question is logged.
    """
    __tablename__ = "topic_trends"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic: Mapped[str] = mapped_column(String(128), index=True)
    date_str: Mapped[str] = mapped_column(String(10), index=True)  # "YYYY-MM-DD"
    question_count: Mapped[int] = mapped_column(Integer, default=0)

    @staticmethod
    def today_str() -> str:
        return date.today().isoformat()

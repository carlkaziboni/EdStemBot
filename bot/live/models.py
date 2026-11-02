"""ORM tables for askEd Live. They share the analytics Base so init_db creates them."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from bot.analytics.models import Base


class LiveQuestion(Base):
    """A question an attendee asked askEd."""

    __tablename__ = "live_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    text: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text, default="")
    topic_tags: Mapped[str] = mapped_column(Text, default="[]")  # JSON list
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class QuizAttempt(Base):
    """One attendee's first answer to one quiz question."""

    __tablename__ = "quiz_attempts"
    __table_args__ = (UniqueConstraint("session_id", "question_id", name="uq_attempt"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    question_id: Mapped[str] = mapped_column(String(64), index=True)
    topic: Mapped[str] = mapped_column(String(128), index=True)
    chosen_index: Mapped[int] = mapped_column(Integer)
    correct: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

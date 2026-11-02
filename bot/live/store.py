"""Database access for askEd Live."""

from __future__ import annotations

import json
from typing import Any, List

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.live.models import LiveQuestion, QuizAttempt
from bot.live.stats import build_stats


class LiveStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def log_question(
        self,
        session_id: str,
        text: str,
        answer: str,
        topics: List[str],
        confidence: float | None,
    ) -> None:
        async with self.session_factory() as session:
            session.add(
                LiveQuestion(
                    session_id=session_id,
                    text=text,
                    answer=answer,
                    topic_tags=json.dumps(topics),
                    confidence_score=confidence,
                )
            )
            await session.commit()

    async def log_attempt(
        self, session_id: str, question_id: str, topic: str, chosen_index: int, correct: bool
    ) -> bool:
        """Record the first answer per (session, question). Returns False for repeats."""
        async with self.session_factory() as session:
            session.add(
                QuizAttempt(
                    session_id=session_id,
                    question_id=question_id,
                    topic=topic,
                    chosen_index=chosen_index,
                    correct=correct,
                )
            )
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                return False
        return True

    async def get_stats(
        self, bank_lookup: dict[str, dict[str, Any]], min_attempts: int
    ) -> dict[str, Any]:
        async with self.session_factory() as session:
            attempts = [
                {
                    "session_id": a.session_id,
                    "question_id": a.question_id,
                    "topic": a.topic,
                    "chosen_index": a.chosen_index,
                    "correct": a.correct,
                }
                for a in (await session.execute(select(QuizAttempt))).scalars()
            ]
            questions = [
                {
                    "session_id": q.session_id,
                    "topic_tags": q.topic_tags,
                    "confidence_score": q.confidence_score,
                }
                for q in (await session.execute(select(LiveQuestion))).scalars()
            ]
        return build_stats(attempts, questions, bank_lookup, min_attempts)

    async def reset(self) -> None:
        async with self.session_factory() as session:
            await session.execute(delete(QuizAttempt))
            await session.execute(delete(LiveQuestion))
            await session.commit()

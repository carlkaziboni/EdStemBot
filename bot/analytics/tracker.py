"""
Analytics tracker — logs question events and updates topic trends in SQLite.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any, List, Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.analytics.models import Base, QuestionLog, TopicTrend
from bot.edstem.models import Thread
from config.settings import settings

logger = logging.getLogger(__name__)


class AnalyticsTracker:
    """
    Manages database sessions and analytics tracking in SQLite.
    """

    def __init__(self, database_url: Optional[str] = None) -> None:
        url = database_url or settings.database_url
        self.engine = create_async_engine(url, echo=False)
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def init_db(self) -> None:
        """Create tables if they do not exist."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Analytics database tables verified/created.")

    async def log_question(
        self,
        thread: Thread,
        topics: List[str],
        confidence_score: Optional[float] = None,
        was_classifiable: bool = True,
    ) -> QuestionLog:
        """
        Record a question log entry and update daily topic trends.
        """
        today_str = TopicTrend.today_str()
        question_text = thread.plain_text or thread.title

        async with self.session_factory() as session:
            async with session.begin():
                # Check if this thread was already logged
                stmt = select(QuestionLog).where(QuestionLog.thread_id == thread.id)
                res = await session.execute(stmt)
                existing = res.scalars().first()

                if existing:
                    logger.debug("Thread %d already logged; updating topics.", thread.id)
                    existing.title = thread.title
                    existing.question_text = question_text
                    existing.topics = topics
                    existing.confidence_score = confidence_score
                    existing.was_classifiable = was_classifiable
                    log_entry = existing
                else:
                    log_entry = QuestionLog(
                        thread_id=thread.id,
                        course_id=thread.course_id,
                        user_id=thread.user_id,
                        title=thread.title,
                        question_text=question_text,
                        topic_tags=json.dumps(topics),
                        confidence_score=confidence_score,
                        was_classifiable=was_classifiable,
                    )
                    session.add(log_entry)

                # Update daily topic trends
                for topic in topics:
                    trend_stmt = select(TopicTrend).where(
                        TopicTrend.topic == topic,
                        TopicTrend.date_str == today_str,
                    )
                    trend_res = await session.execute(trend_stmt)
                    trend = trend_res.scalars().first()
                    if trend:
                        trend.question_count += 1
                    else:
                        trend = TopicTrend(
                            topic=topic,
                            date_str=today_str,
                            question_count=1,
                        )
                        session.add(trend)

            await session.commit()

        logger.info("Logged thread %d with topics: %s", thread.id, topics)
        return log_entry

    async def get_kpis(self) -> dict[str, Any]:
        """Fetch summary KPIs for the lecturer dashboard."""
        async with self.session_factory() as session:
            total_questions = await session.scalar(select(func.count(QuestionLog.id))) or 0
            unique_students = (
                await session.scalar(
                    select(func.count(func.distinct(QuestionLog.user_id))).where(
                        QuestionLog.user_id.is_not(None)
                    )
                )
                or 0
            )

            # Questions today
            today = date.today()
            today_start = datetime(today.year, today.month, today.day)
            questions_today = (
                await session.scalar(
                    select(func.count(QuestionLog.id)).where(
                        QuestionLog.created_at >= today_start
                    )
                )
                or 0
            )

            # Unclassifiable or low confidence count
            unclassified_count = (
                await session.scalar(
                    select(func.count(QuestionLog.id)).where(
                        (QuestionLog.was_classifiable.is_(False))
                        | (QuestionLog.topic_tags == '["Other"]')
                    )
                )
                or 0
            )

            # Distinct topics detected across all time
            distinct_topics = (
                await session.scalar(
                    select(func.count(func.distinct(TopicTrend.topic)))
                )
                or 0
            )

            classifiable_rate = (
                round(((total_questions - unclassified_count) / total_questions) * 100, 1)
                if total_questions > 0
                else 100.0
            )

            return {
                "total_questions": total_questions,
                "unique_students": unique_students,
                "questions_today": questions_today,
                "unclassified_count": unclassified_count,
                "distinct_topics": distinct_topics,
                "classifiable_rate": classifiable_rate,
            }

    async def get_topic_counts(self, limit: int = 15) -> list[dict[str, Any]]:
        """Fetch all-time question counts per topic, sorted highest first."""
        async with self.session_factory() as session:
            stmt = (
                select(
                    TopicTrend.topic,
                    func.sum(TopicTrend.question_count).label("total"),
                )
                .group_by(TopicTrend.topic)
                .order_by(desc("total"))
                .limit(limit)
            )
            res = await session.execute(stmt)
            return [{"topic": r.topic, "count": int(r.total)} for r in res.all()]

    async def get_topic_trends(self, days: int = 7) -> list[dict[str, Any]]:
        """
        Fetch topic counts for each of the last N days.
        Returns list of {date: str, topic: str, count: int}.
        """
        start_date = (date.today() - timedelta(days=days - 1)).isoformat()
        async with self.session_factory() as session:
            stmt = (
                select(
                    TopicTrend.date_str,
                    TopicTrend.topic,
                    TopicTrend.question_count,
                )
                .where(TopicTrend.date_str >= start_date)
                .order_by(TopicTrend.date_str.asc(), desc(TopicTrend.question_count))
            )
            res = await session.execute(stmt)
            return [
                {
                    "date": r.date_str,
                    "topic": r.topic,
                    "count": r.question_count,
                }
                for r in res.all()
            ]

    async def get_recent_questions(self, limit: int = 20) -> list[dict[str, Any]]:
        """Fetch recent questions for feed display."""
        async with self.session_factory() as session:
            stmt = (
                select(QuestionLog)
                .order_by(desc(QuestionLog.created_at))
                .limit(limit)
            )
            res = await session.execute(stmt)
            items = res.scalars().all()
            return [
                {
                    "id": item.id,
                    "thread_id": item.thread_id,
                    "course_id": item.course_id,
                    "title": item.title,
                    "snippet": (item.question_text[:140] + "...")
                    if len(item.question_text) > 140
                    else item.question_text,
                    "topics": item.topics,
                    "confidence_score": item.confidence_score,
                    "was_classifiable": item.was_classifiable,
                    "created_at": item.created_at.strftime("%Y-%m-%d %H:%M")
                    if item.created_at
                    else "",
                }
                for item in items
            ]

    async def get_unclassified_questions(self, limit: int = 20) -> list[dict[str, Any]]:
        """Fetch questions that were flagged unclassifiable or categorized as 'Other'."""
        async with self.session_factory() as session:
            stmt = (
                select(QuestionLog)
                .where(
                    (QuestionLog.was_classifiable.is_(False))
                    | (QuestionLog.topic_tags == '["Other"]')
                )
                .order_by(desc(QuestionLog.created_at))
                .limit(limit)
            )
            res = await session.execute(stmt)
            items = res.scalars().all()
            return [
                {
                    "id": item.id,
                    "thread_id": item.thread_id,
                    "title": item.title,
                    "question_text": item.question_text,
                    "topics": item.topics,
                    "confidence_score": item.confidence_score,
                    "created_at": item.created_at.strftime("%Y-%m-%d %H:%M")
                    if item.created_at
                    else "",
                }
                for item in items
            ]

    async def get_activity_heatmap(self) -> list[dict[str, Any]]:
        """
        Group questions by day-of-week (0=Mon, 6=Sun) and hour-of-day (0-23).
        """
        async with self.session_factory() as session:
            # Fetch all created_at timestamps to calculate day-of-week & hour in Python
            # (keeps SQLite queries portable and independent of strftime quirks)
            stmt = select(QuestionLog.created_at)
            res = await session.execute(stmt)
            timestamps = res.scalars().all()

            counts: dict[tuple[int, int], int] = {}
            for dt in timestamps:
                if dt:
                    key = (dt.weekday(), dt.hour)
                    counts[key] = counts.get(key, 0) + 1

            result = []
            for day in range(7):
                for hour in range(24):
                    result.append(
                        {
                            "day": day,
                            "hour": hour,
                            "count": counts.get((day, hour), 0),
                        }
                    )
            return result

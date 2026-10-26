"""
Seed script to populate SQLite with realistic sample Computer Systems questions.

Useful for testing the dashboard and seeing charts, heatmaps, and tables populated.

Usage:
    python scripts/seed_db.py
"""

from __future__ import annotations

import asyncio
import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.analytics.models import Base, QuestionLog, TopicTrend
from bot.analytics.tracker import AnalyticsTracker
from config.settings import settings

SAMPLE_QUESTIONS = [
    (
        "Page fault handling and TLB misses",
        "Can someone clarify what happens when a virtual address misses the TLB? Does hardware or OS walk the page table in x86?",
        ["Virtual Memory", "Operating Systems"],
        0.88,
        True,
    ),
    (
        "Cache write-through vs write-back policy",
        "In Assignment 2, should we assume a write-back cache with write-allocate on store misses?",
        ["Cache", "CPU Architecture"],
        0.92,
        True,
    ),
    (
        "Deadlock conditions with mutexes",
        "If thread A holds lock 1 and requests lock 2 while thread B does the reverse, why doesn't timeout solve deadlock?",
        ["Concurrency", "Operating Systems"],
        0.84,
        True,
    ),
    (
        "Assembly stack frame alignment",
        "Why does GCC align the stack to 16 bytes before calling a function in x86_64 ABI?",
        ["Assembly Language"],
        0.79,
        True,
    ),
    (
        "Inode structure in Ext4",
        "How many direct block pointers are in a standard inode, and how large a file can be represented without indirect blocks?",
        ["File Systems", "Operating Systems"],
        0.95,
        True,
    ),
    (
        "Process fork and copy-on-write semantics",
        "When fork() is called, do parent and child share the same physical pages until one writes to them?",
        ["Processes & Threads", "Memory Management"],
        0.91,
        True,
    ),
    (
        "Buffer overflow and stack canary",
        "In lab 4, how does the canary prevent return address overwrites if the attacker overflows a local array?",
        ["Security", "Memory Management"],
        0.86,
        True,
    ),
    (
        "DMA vs programmed I/O interrupt overhead",
        "Why is DMA more efficient for disk blocks compared to interrupt-driven character I/O?",
        ["I/O Systems", "CPU Architecture"],
        0.73,
        True,
    ),
    (
        "TCP sliding window vs go-back-N",
        "How does TCP selective acknowledgment (SACK) improve performance over pure Go-Back-N on high latency links?",
        ["Networking"],
        0.89,
        True,
    ),
    (
        "Office hours location today?",
        "Where are the TA office hours being held this afternoon? The syllabus link says room 302 but it seems locked.",
        ["Other"],
        0.18,
        False,
    ),
    (
        "Grading rubric for Assignment 1",
        "When will test case outputs for assignment 1 autograder be released?",
        ["Other"],
        0.22,
        False,
    ),
    (
        "Virtual address translation with multi-level page tables",
        "For a 4-level page table on 64-bit architecture, how many memory accesses are required without TLB?",
        ["Virtual Memory", "Memory Management"],
        0.94,
        True,
    ),
]


async def seed() -> None:
    tracker = AnalyticsTracker(settings.database_url)
    await tracker.init_db()

    async with tracker.session_factory() as session:
        async with session.begin():
            # Clear existing sample data for idempotent re-seeding
            print("Seeding database with sample Computer Systems questions...")
            from sqlalchemy import delete
            sample_ids = list(range(101, 101 + len(SAMPLE_QUESTIONS)))
            await session.execute(delete(QuestionLog).where(QuestionLog.thread_id.in_(sample_ids)))
            now = datetime.now()

            for i, (title, text, topics, conf, classifiable) in enumerate(SAMPLE_QUESTIONS, start=101):
                # Spread created dates across the past 7 days and various hours
                days_ago = random.randint(0, 6)
                hour = random.randint(8, 23)
                minute = random.randint(0, 59)
                created_time = now - timedelta(days=days_ago, hours=now.hour - hour, minutes=minute)

                q_log = QuestionLog(
                    thread_id=i,
                    course_id=settings.ed_course_id or 12345,
                    user_id=1000 + (i % 8),
                    title=title,
                    question_text=text,
                    topic_tags=json.dumps(topics),
                    confidence_score=conf,
                    was_classifiable=classifiable,
                    created_at=created_time,
                )
                session.add(q_log)

                # Update topic trend for that day
                date_str = created_time.date().isoformat()
                for topic in topics:
                    trend = TopicTrend(
                        topic=topic,
                        date_str=date_str,
                        question_count=1,
                    )
                    session.add(trend)

        await session.commit()

    print("Successfully seeded sample questions and topic trends!")


if __name__ == "__main__":
    asyncio.run(seed())

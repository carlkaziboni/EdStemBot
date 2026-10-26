"""
Question processor — orchestrates the read-only bot pipeline:
new question thread → RAG context retrieval → LLM topic classification → SQLite logging.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from bot.analytics.classifier import TopicClassifier
from bot.analytics.models import QuestionLog
from bot.analytics.tracker import AnalyticsTracker
from bot.edstem.models import Thread
from bot.rag.retriever import Retriever

logger = logging.getLogger(__name__)


class QuestionProcessor:
    """
    Orchestrates the read-only question processing workflow.

    Workflow:
    1. Extract plain-text question content.
    2. Retrieve semantically matching course material chunks.
    3. Classify into Computer Systems topic tags with LLM.
    4. Compute a confidence score from vector distance.
    5. Save everything to SQLite via AnalyticsTracker.
    """

    def __init__(
        self,
        retriever: Retriever,
        classifier: TopicClassifier,
        tracker: AnalyticsTracker,
    ) -> None:
        self.retriever = retriever
        self.classifier = classifier
        self.tracker = tracker

    async def process(self, thread: Thread) -> Optional[QuestionLog]:
        """
        Process an incoming EdStem thread.

        Args:
            thread: The Thread model received from WebSocket or REST API.

        Returns:
            The created/updated QuestionLog record, or None if skipped.
        """
        if not thread.is_question:
            logger.debug("Skipping non-question thread %d (%s)", thread.id, thread.type)
            return None

        query = f"{thread.title}\n{thread.plain_text}".strip()
        if not query:
            logger.warning("Thread %d has empty title and content; skipping.", thread.id)
            return None

        logger.info("Processing question thread %d: '%s'", thread.id, thread.title)

        # 1. Retrieve course material chunks (run in thread pool since embedder/chroma is sync)
        chunks = await asyncio.to_thread(self.retriever.retrieve, query)

        # 2. Compute confidence score (1 - cosine distance of best match, or 0.0)
        confidence_score: Optional[float] = None
        if chunks:
            best_chunk = chunks[0]
            confidence_score = round(max(0.0, min(1.0, 1.0 - best_chunk.distance)), 3)

        # 3. Classify topics using LLM + retrieved context hint
        topics = await self.classifier.classify(query, context=chunks)

        # Determine if classification was reliable
        was_classifiable = bool(topics and topics != ["Other"])

        # 4. Log to SQLite analytics database
        log_entry = await self.tracker.log_question(
            thread=thread,
            topics=topics,
            confidence_score=confidence_score,
            was_classifiable=was_classifiable,
        )

        logger.info(
            "Logged question %d: topics=%s, confidence=%s, classifiable=%s",
            thread.id,
            topics,
            confidence_score,
            was_classifiable,
        )

        return log_entry

"""
Topic classifier — uses the LLM + retrieved context to classify
a student question into Computer Systems topic tags.
"""

from __future__ import annotations

import logging
from typing import List

from bot.llm.provider import LLMProvider
from bot.llm.prompts import (
    COURSE_TOPICS,
    TOPIC_CLASSIFICATION_SYSTEM,
    TOPIC_CLASSIFICATION_USER,
)
from bot.rag.vectorstore import RetrievedChunk

logger = logging.getLogger(__name__)


class TopicClassifier:
    """
    Classifies student questions into Computer Systems topic tags.

    Uses the LLM with an optional RAG context hint to improve accuracy
    when the question alone is ambiguous.

    Args:
        llm: An initialised LLMProvider instance.
    """

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def classify(
        self,
        question: str,
        context: List[RetrievedChunk] | None = None,
    ) -> List[str]:
        """
        Classify a question into topic tags.

        Args:
            question: Plain-text student question.
            context: Optional retrieved course material chunks for context.

        Returns:
            List of topic tag strings (non-empty, from COURSE_TOPICS).
        """
        # Build an optional context hint for the LLM
        if context:
            sources = list({c.source for c in context[:3]})
            context_hint = f"(Relevant course material found in: {', '.join(sources)})"
        else:
            context_hint = ""

        user_prompt = TOPIC_CLASSIFICATION_USER.format(
            question=question,
            context_hint=context_hint,
        )

        try:
            topics = await self.llm.classify_topics(
                system_prompt=TOPIC_CLASSIFICATION_SYSTEM,
                user_prompt=user_prompt,
            )
        except Exception as exc:
            logger.error("Topic classification failed: %s", exc)
            return ["Other"]

        # Validate against known topics
        valid = [t for t in topics if t in COURSE_TOPICS]
        if not valid:
            logger.debug("LLM returned unknown topics %s — defaulting to Other", topics)
            return ["Other"]

        logger.debug("Classified '%s…' → %s", question[:60], valid)
        return valid

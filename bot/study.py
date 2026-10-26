"""
Student-facing study helpers used by the Chrome extension API:
answer previews and multiple-choice quizzes grounded in course material.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, List

from bot.analytics.classifier import TopicClassifier
from bot.llm.prompts import ANSWER_FORMAT, ANSWER_PROMPT, QUIZ_SYSTEM, QUIZ_USER
from bot.llm.provider import LLMProvider
from bot.rag.retriever import Retriever

logger = logging.getLogger(__name__)


def parse_quiz(raw: str, n: int) -> List[dict[str, Any]]:
    """
    Parse and validate an LLM quiz response.

    Returns only well-formed questions (4 string options, valid answer index).
    Raises ValueError if the response contains no valid question.
    """
    match = re.search(r"\{.*\}|\[.*\]", raw, re.DOTALL)
    if not match:
        raise ValueError("no JSON found in quiz response")
    data = json.loads(match.group())
    items = data.get("questions", []) if isinstance(data, dict) else data

    valid: List[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        options = item.get("options")
        idx = item.get("answer_index")
        question = item.get("q")
        if (
            isinstance(question, str)
            and isinstance(options, list)
            and len(options) == 4
            and all(isinstance(o, str) for o in options)
            and isinstance(idx, int)
            and 0 <= idx < 4
        ):
            valid.append(
                {
                    "q": question,
                    "options": options,
                    "answer_index": idx,
                    "explanation": str(item.get("explanation", "")),
                }
            )
    if not valid:
        raise ValueError("no valid questions in quiz response")
    return valid[:n]


class StudyService:
    """Generates answer previews and quizzes. Never talks to EdStem."""

    def __init__(
        self, retriever: Retriever, llm: LLMProvider, classifier: TopicClassifier
    ) -> None:
        self.retriever = retriever
        self.llm = llm
        self.classifier = classifier

    async def answer(self, title: str, body: str) -> dict[str, Any]:
        question = f"{title}\n\n{body}".strip()
        chunks = await asyncio.to_thread(self.retriever.retrieve, question)
        context = self.retriever.format_context(chunks)
        topics = await self.classifier.classify(question, chunks)
        confidence = round(1 - chunks[0].distance, 3) if chunks else 0.0

        if context:
            user_prompt = f"Course material:\n{context}\n\nStudent question:\n{question}"
        else:
            user_prompt = (
                "No relevant course material was found.\n\n"
                f"Student question:\n{question}"
            )
        text = await self.llm.generate(
            ANSWER_PROMPT + ANSWER_FORMAT, user_prompt, temperature=0.2, max_tokens=900
        )
        return {
            "answer": text.strip(),
            "topics": topics,
            "confidence": confidence,
            "sources": sorted({f"{c.source} p.{c.page}" for c in chunks}),
        }

    async def quiz(self, title: str, body: str, n: int = 3) -> dict[str, Any]:
        question = f"{title}\n\n{body}".strip()
        chunks = await asyncio.to_thread(self.retriever.retrieve, question)
        context = self.retriever.format_context(chunks)
        if not context:
            raise LookupError("no course material relevant to this thread")
        topics = await self.classifier.classify(question, chunks)

        user_prompt = QUIZ_USER.format(n=n, context=context, question=question)
        last_error: Exception | None = None
        for _ in range(2):  # one retry on malformed output
            raw = await self.llm.generate(
                QUIZ_SYSTEM, user_prompt, temperature=0.5, max_tokens=2000
            )
            try:
                return {"topic": topics[0], "questions": parse_quiz(raw, n)}
            except (ValueError, json.JSONDecodeError) as exc:
                last_error = exc
                logger.warning("Malformed quiz response: %s", exc)
        raise ValueError(f"could not generate quiz: {last_error}")

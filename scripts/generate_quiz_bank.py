"""
Generate a draft quiz bank for askEd Live from the ingested course notes.

Run this locally once, then REVIEW AND EDIT data/quiz_bank.json by hand before
the talk: LLM-written distractors are sometimes ambiguous or wrong, and the
reveal slide is only as trustworthy as the questions behind it.

Usage:
    python scripts/generate_quiz_bank.py [--per-topic 4] [--topics "Cache,Virtual Memory"]
                                         [--out data/quiz_bank.json]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.llm import get_llm_provider
from bot.llm.prompts import COURSE_TOPICS, QUIZ_SYSTEM, QUIZ_USER
from bot.rag import Retriever, VectorStore, get_embedding_model
from bot.study import parse_quiz
from config.settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("scripts.generate_quiz_bank")


def shuffle_options(question: dict, rng: random.Random) -> dict:
    """Randomise option order so the correct answer's position carries no signal."""
    options = question["options"]
    correct = options[question["answer_index"]]
    shuffled = options[:]
    rng.shuffle(shuffled)
    return {**question, "options": shuffled, "answer_index": shuffled.index(correct)}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


async def generate_for_topic(retriever: Retriever, llm, topic: str, n: int) -> list[dict]:
    chunks = retriever.retrieve(f"{topic} in computer systems")
    if not chunks:
        logger.warning("No notes matched '%s'; skipping", topic)
        return []
    context = retriever.format_context(chunks)
    prompt = QUIZ_USER.format(n=n, context=context, question=f"Topic: {topic}")
    for attempt in range(2):
        raw = await llm.generate(QUIZ_SYSTEM, prompt, temperature=0.5, max_tokens=2500)
        try:
            questions = parse_quiz(raw, n)
            break
        except ValueError as exc:
            logger.warning("%s: bad output (%s), attempt %d", topic, exc, attempt + 1)
    else:
        return []
    rng = random.Random(f"askEd-{topic}")  # deterministic per topic
    return [
        {"id": f"{slug(topic)}-{i + 1}", "topic": topic, **shuffle_options(q, rng)}
        for i, q in enumerate(questions)
    ]


async def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a draft askEd quiz bank.")
    parser.add_argument("--per-topic", type=int, default=4)
    parser.add_argument("--topics", default="", help="Comma-separated subset of topics")
    parser.add_argument("--out", default=settings.quiz_bank_path)
    args = parser.parse_args()

    topics = [t.strip() for t in args.topics.split(",") if t.strip()] or [
        t for t in COURSE_TOPICS if t != "Other"
    ]
    unknown = [t for t in topics if t not in COURSE_TOPICS]
    if unknown:
        sys.exit(f"Unknown topics: {unknown}. Valid: {COURSE_TOPICS}")

    vectorstore = VectorStore(
        persist_dir=settings.chroma_persist_dir, collection_name=settings.chroma_collection
    )
    retriever = Retriever(vectorstore, get_embedding_model(settings.embedding_model), n_results=8)
    llm = get_llm_provider(settings.llm_provider)

    questions: list[dict] = []
    for topic in topics:
        got = await generate_for_topic(retriever, llm, topic, args.per_topic)
        logger.info("%s: %d questions", topic, len(got))
        questions.extend(got)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"note": "Draft. Review every question before use.", "questions": questions}, indent=2),
        encoding="utf-8",
    )
    logger.info("Wrote %d questions to %s. Now review and edit them by hand.", len(questions), out)


if __name__ == "__main__":
    asyncio.run(main())

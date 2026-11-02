"""
Generate a draft quiz bank for askEd Live.

Two question sets:
  --set about   (default for the talk) questions about askEd itself, drawn from the approved
                askEd documents, one group per askEd topic (RAG, privacy, ...).
  --set course  Computer Systems questions drawn from the ingested course notes.

Run this locally once, then REVIEW AND EDIT data/quiz_bank.json by hand before
the talk: LLM-written distractors are sometimes ambiguous or wrong, and the
reveal slide is only as trustworthy as the questions behind it.

Usage:
    python scripts/generate_quiz_bank.py [--set about|course] [--per-topic 4]
                                         [--topics "Cache,Virtual Memory"] [--out data/quiz_bank.json]
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
from bot.live.about import TOPICS as ABOUT_TOPICS
from bot.llm.prompts import ABOUT_QUIZ_SYSTEM, COURSE_TOPICS, QUIZ_SYSTEM, QUIZ_USER
from bot.rag import Retriever, VectorStore, get_embedding_model
from bot.study import parse_quiz
from config.settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("scripts.generate_quiz_bank")


# What to retrieve for each askEd topic. The README is excluded as a quiz source: it is full of
# implementation detail that makes trivia, and the audience heard the talk, not the README.
ABOUT_QUERIES = {
    "How it works / RAG": "how askEd retrieves relevant material and generates grounded, cited answers",
    "Hallucinations & reliability": "how askEd handles hallucinations, confidence scores and not knowing an answer",
    "Privacy & security": "privacy and security: third-party model providers, read-only access, anonymous questions",
    "EdStem integration": "how askEd connects to EdStem, read-only access, what it never does on the forum",
    "Student experience": "what students get from the Chrome extension: answer preview and quiz",
    "Lecturer analytics": "the lecturer dashboard, topic trends, needs-review queue, what question counts mean",
    "Deployment & scalability": "how askEd is deployed, scalability limits, swappable language model providers",
    "Educational impact": "educational impact, expected benefits, risks, and what has not been evaluated",
}


def shuffle_options(question: dict, rng: random.Random) -> dict:
    """Randomise option order so the correct answer's position carries no signal."""
    options = question["options"]
    correct = options[question["answer_index"]]
    shuffled = options[:]
    rng.shuffle(shuffled)
    return {**question, "options": shuffled, "answer_index": shuffled.index(correct)}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


async def generate_for_topic(
    retriever: Retriever, llm, topic: str, n: int, question_set: str = "course"
) -> list[dict]:
    if question_set == "about":
        chunks = [c for c in retriever.retrieve(ABOUT_QUERIES[topic]) if c.source != "askEd README"][:6]
        system = ABOUT_QUIZ_SYSTEM
    else:
        chunks = retriever.retrieve(f"{topic} in computer systems")
        system = QUIZ_SYSTEM
    if not chunks:
        logger.warning("No material matched '%s'; skipping", topic)
        return []
    context = retriever.format_context(chunks)
    if question_set == "about":
        prompt = (
            f'Write {n} multiple-choice questions on the topic "{topic}" for an audience that has just '
            f"heard a talk about askEd.\n\nContext:\n{context}"
        )
    else:
        prompt = QUIZ_USER.format(n=n, context=context, question=f"Topic: {topic}")
    for attempt in range(2):
        raw = await llm.generate(system, prompt, temperature=0.5, max_tokens=2500)
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
    parser.add_argument("--set", dest="question_set", choices=["about", "course"], default="about")
    parser.add_argument("--per-topic", type=int, default=5)
    parser.add_argument("--topics", default="", help="Comma-separated subset of topics")
    parser.add_argument("--out", default=settings.quiz_bank_path)
    args = parser.parse_args()

    about = args.question_set == "about"
    valid = [t for t in (ABOUT_TOPICS if about else COURSE_TOPICS) if not t.startswith("Other")]
    topics = [t.strip() for t in args.topics.split(",") if t.strip()] or valid
    unknown = [t for t in topics if t not in valid]
    if unknown:
        sys.exit(f"Unknown topics: {unknown}. Valid: {valid}")

    vectorstore = VectorStore(
        persist_dir=settings.chroma_persist_dir,
        collection_name=settings.about_collection if about else settings.chroma_collection,
    )
    retriever = Retriever(
        vectorstore,
        get_embedding_model(settings.embedding_model),
        n_results=12 if about else 8,
        max_distance=0.8 if about else 0.6,
    )
    llm = get_llm_provider(settings.llm_provider)

    questions: list[dict] = []
    for topic in topics:
        got = await generate_for_topic(retriever, llm, topic, args.per_topic, args.question_set)
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

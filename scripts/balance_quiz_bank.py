"""
Repair a draft quiz bank so test-wise students cannot guess from the wording.

LLM-written questions tend to make the correct option the longest and most
detailed. This rewrites ONLY the wrong options of affected questions so they
match the correct option's length and specificity, checks the result in code,
then reshuffles option order. The correct answer text is never changed.

Usage:
    python scripts/balance_quiz_bank.py [--bank data/quiz_bank.json]
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
from config.settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("scripts.balance_quiz_bank")

SYSTEM = """You improve multiple-choice questions so they cannot be answered by test-taking tricks.
You are given a question, its correct answer, and three wrong answers.
Rewrite ONLY the three wrong answers:
- Each must be a plausible misconception that a student who half-understands the topic might believe, and must still be clearly wrong.
- Each must be about the same length and specificity as the correct answer (within roughly 10 percent, neither noticeably longer nor shorter), with similar structure and wording style.
- Do not copy the correct answer or make any wrong answer partially correct.
- Never mention "the notes", "the text" or "according to".
Return ONLY JSON: {"wrong": ["...", "...", "..."]}"""

REFERENCE = re.compile(r"\b(the notes|the text|the passage|the course material|according to)\b", re.I)


def even_positions(questions: list[dict]) -> None:
    """Spread the correct answer evenly over A-D by swapping it into a target slot."""
    targets = [i % 4 for i in range(len(questions))]
    random.Random("askEd-positions").shuffle(targets)
    for q, t in zip(questions, targets):
        a = q["answer_index"]
        q["options"][a], q["options"][t] = q["options"][t], q["options"][a]
        q["answer_index"] = t


def length_ratio(correct: str, wrong: list[str]) -> float:
    return len(correct) / (sum(len(w) for w in wrong) / len(wrong))


def needs_repair(q: dict) -> bool:
    correct = q["options"][q["answer_index"]]
    wrong = [o for i, o in enumerate(q["options"]) if i != q["answer_index"]]
    ratio = length_ratio(correct, wrong)
    return not 0.9 <= ratio <= 1.1 or bool(REFERENCE.search(q["q"] + " ".join(q["options"])))


def acceptable(correct: str, wrong: list[str]) -> bool:
    return (
        len(wrong) == 3
        and all(isinstance(w, str) and w.strip() for w in wrong)
        and correct not in wrong
        and len(set(wrong)) == 3
        and 0.9 <= length_ratio(correct, wrong) <= 1.1  # no length tell in either direction
        and not any(REFERENCE.search(w) for w in wrong)
    )


async def repair(llm, q: dict, sem: asyncio.Semaphore) -> dict:
    correct = q["options"][q["answer_index"]]
    wrong = [o for i, o in enumerate(q["options"]) if i != q["answer_index"]]
    prompt = json.dumps({"question": q["q"], "correct": correct, "wrong": wrong}, indent=1)
    for attempt in range(3):
        async with sem:
            raw = await llm.generate(SYSTEM, prompt, temperature=0.5, max_tokens=700)
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        try:
            new_wrong = json.loads(m.group())["wrong"] if m else None
        except (ValueError, KeyError, TypeError):
            new_wrong = None
        if new_wrong and acceptable(correct, new_wrong):
            options = [correct, *new_wrong]
            random.Random(f"balance-{q['id']}").shuffle(options)
            return {**q, "options": options, "answer_index": options.index(correct), "_repaired": True}
        logger.warning("%s: attempt %d rejected", q["id"], attempt + 1)
    return {**q, "_repaired": False}


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bank", default=settings.quiz_bank_path)
    args = parser.parse_args()

    path = Path(args.bank)
    data = json.loads(path.read_text(encoding="utf-8"))
    questions = data["questions"]
    todo = [q for q in questions if needs_repair(q)]
    logger.info("%d of %d questions need repair", len(todo), len(questions))

    llm = get_llm_provider(settings.llm_provider)
    sem = asyncio.Semaphore(5)
    fixed = {q["id"]: q for q in await asyncio.gather(*(repair(llm, q, sem) for q in todo))}

    out, failed = [], []
    for q in questions:
        r = fixed.get(q["id"], q)
        if r.get("_repaired") is False:
            failed.append(q["id"])
            continue  # drop questions we could not make fair rather than ship a giveaway
        r.pop("_repaired", None)
        out.append(r)
    even_positions(out)
    data["questions"] = out
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.info("Kept %d questions; dropped %d that could not be balanced: %s", len(out), len(failed), failed)


if __name__ == "__main__":
    asyncio.run(main())

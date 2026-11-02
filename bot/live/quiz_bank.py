"""Pre-generated, human-reviewed quiz bank served to the audience."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any


class QuizBankError(ValueError):
    pass


def validate_question(item: Any) -> dict[str, Any]:
    """Return a cleaned question dict or raise QuizBankError."""
    if not isinstance(item, dict):
        raise QuizBankError("question must be an object")
    qid, topic, q = item.get("id"), item.get("topic"), item.get("q")
    options, idx = item.get("options"), item.get("answer_index")
    if not (isinstance(qid, str) and qid and isinstance(topic, str) and topic and isinstance(q, str) and q):
        raise QuizBankError(f"question {qid!r} needs string id, topic and q")
    if not (isinstance(options, list) and len(options) == 4 and all(isinstance(o, str) for o in options)):
        raise QuizBankError(f"question {qid!r} needs exactly 4 string options")
    if not (isinstance(idx, int) and not isinstance(idx, bool) and 0 <= idx < 4):
        raise QuizBankError(f"question {qid!r} has an invalid answer_index")
    return {
        "id": qid,
        "topic": topic,
        "q": q,
        "options": options,
        "answer_index": idx,
        "explanation": str(item.get("explanation", "")),
    }


class QuizBank:
    def __init__(self, questions: list[dict[str, Any]]) -> None:
        cleaned = [validate_question(q) for q in questions]
        ids = [q["id"] for q in cleaned]
        if len(ids) != len(set(ids)):
            raise QuizBankError("duplicate question ids")
        self._by_id = {q["id"]: q for q in cleaned}

    @classmethod
    def load(cls, path: str | Path) -> "QuizBank":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        items = data["questions"] if isinstance(data, dict) else data
        return cls(items)

    def __len__(self) -> int:
        return len(self._by_id)

    def lookup(self) -> dict[str, dict[str, Any]]:
        return dict(self._by_id)

    def get(self, question_id: str) -> dict[str, Any] | None:
        return self._by_id.get(question_id)

    @staticmethod
    def public(q: dict[str, Any]) -> dict[str, Any]:
        """The question as sent to a phone: no answer, no explanation."""
        return {k: q[k] for k in ("id", "topic", "q", "options")}

    def pick_set(self, n: int, rng: random.Random | None = None) -> list[dict[str, Any]]:
        """Pick n questions, interleaving topics so every topic gets coverage."""
        rng = rng or random.Random()
        by_topic: dict[str, list[dict[str, Any]]] = {}
        for q in self._by_id.values():
            by_topic.setdefault(q["topic"], []).append(q)
        for qs in by_topic.values():
            rng.shuffle(qs)
        topics = list(by_topic)
        rng.shuffle(topics)
        picked: list[dict[str, Any]] = []
        while len(picked) < n and any(by_topic.values()):
            for t in topics:
                if by_topic[t] and len(picked) < n:
                    picked.append(by_topic[t].pop())
        return [self.public(q) for q in picked]

    def check(self, question_id: str, chosen: int) -> dict[str, Any] | None:
        q = self._by_id.get(question_id)
        if q is None:
            return None
        return {
            "correct": chosen == q["answer_index"],
            "answer_index": q["answer_index"],
            "explanation": q["explanation"],
            "topic": q["topic"],
        }

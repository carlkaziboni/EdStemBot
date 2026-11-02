"""Pure aggregation for the presenter reveal page (no database access)."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any, Iterable


def build_stats(
    attempts: Iterable[dict[str, Any]],
    questions: Iterable[dict[str, Any]],
    bank_lookup: dict[str, dict[str, Any]],
    min_attempts: int,
) -> dict[str, Any]:
    """
    attempts:  dicts with session_id, question_id, topic, chosen_index, correct
    questions: dicts with session_id, topic_tags (JSON string), confidence_score
               (None or <= 0 means askEd failed or could not answer: needs follow-up)
    bank_lookup: question_id -> bank question (for text and options)
    """
    attempts = list(attempts)
    questions = list(questions)

    sessions = {a["session_id"] for a in attempts} | {q["session_id"] for q in questions}

    per_topic: dict[str, dict[str, Any]] = {}
    per_question: dict[str, dict[str, Any]] = {}
    for a in attempts:
        t = per_topic.setdefault(a["topic"], {"attempts": 0, "incorrect": 0})
        t["attempts"] += 1
        pq = per_question.setdefault(
            a["question_id"],
            {"question_id": a["question_id"], "topic": a["topic"], "attempts": 0, "incorrect": 0, "wrong": Counter()},
        )
        pq["attempts"] += 1
        if not a["correct"]:
            t["incorrect"] += 1
            pq["incorrect"] += 1
            pq["wrong"][a["chosen_index"]] += 1

    topics = []
    for name, t in per_topic.items():
        worst = None
        candidates = [q for q in per_question.values() if q["topic"] == name and q["incorrect"] > 0]
        if candidates:
            w = max(candidates, key=lambda q: (q["incorrect"] / q["attempts"], q["attempts"]))
            meta = bank_lookup.get(w["question_id"], {})
            top_wrong = None
            if w["wrong"]:
                idx, count = w["wrong"].most_common(1)[0]
                options = meta.get("options", [])
                top_wrong = {
                    "text": options[idx] if idx < len(options) else "",
                    "count": count,
                }
            worst = {
                "q": meta.get("q", w["question_id"]),
                "pct_incorrect": round(100 * w["incorrect"] / w["attempts"]),
                "attempts": w["attempts"],
                "top_wrong": top_wrong,
            }
        topics.append(
            {
                "topic": name,
                "attempts": t["attempts"],
                "incorrect": t["incorrect"],
                "pct_incorrect": round(100 * t["incorrect"] / t["attempts"]),
                "ranked": t["attempts"] >= min_attempts,
                "hardest_question": worst,
            }
        )
    # Ranked topics first (worst first), then topics with too little data.
    topics.sort(key=lambda x: (not x["ranked"], -x["pct_incorrect"], -x["attempts"]))

    asked: Counter[str] = Counter()
    for q in questions:
        try:
            tags = json.loads(q["topic_tags"])
        except (TypeError, ValueError):
            tags = []
        for tag in tags:
            asked[tag] += 1

    needs_followup = sum(
        1 for q in questions if q.get("confidence_score") is None or q["confidence_score"] <= 0
    )

    return {
        "participants": len(sessions),
        "attempts": len(attempts),
        "questions_asked": len(questions),
        "needs_followup": needs_followup,
        "min_attempts": min_attempts,
        "topics": topics,
        "asked_topics": [{"topic": k, "count": v} for k, v in asked.most_common()],
    }

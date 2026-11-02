"""
Rehearse the reveal slide by simulating an audience against a running server.

Each fake attendee takes the quiz; every topic gets a hidden "difficulty" so the
reveal ranks topics in an interesting order. Needs the same data/quiz_bank.json
the server uses (to know which option is correct).

Usage:
    python scripts/simulate_audience.py --url http://localhost:8000 --key <PRESENTER_KEY> --people 60
    python scripts/simulate_audience.py --url ... --key ... --reset      # clear all data afterwards
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import uuid
from pathlib import Path

import httpx


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://localhost:8000")
    p.add_argument("--key", required=True, help="PRESENTER_KEY")
    p.add_argument("--people", type=int, default=60)
    p.add_argument("--bank", default="data/quiz_bank.json")
    p.add_argument("--asks", type=int, default=0, help="Also ask N real questions (costs LLM calls)")
    p.add_argument("--reset", action="store_true", help="Clear all data and exit")
    args = p.parse_args()

    base = args.url.rstrip("/")
    headers = {"X-Presenter-Key": args.key}
    client = httpx.Client(timeout=60)

    if args.reset:
        r = client.post(f"{base}/live/reset", headers=headers)
        print(r.status_code, r.text)
        return

    data = json.loads(Path(args.bank).read_text(encoding="utf-8"))
    bank = {q["id"]: q for q in (data["questions"] if isinstance(data, dict) else data)}
    rng = random.Random(7)
    p_correct = {t: rng.uniform(0.25, 0.9) for t in {q["topic"] for q in bank.values()}}

    for _ in range(args.people):
        sid = uuid.uuid4().hex[:24]
        quiz = client.get(f"{base}/live/quiz", params={"n": 10})
        if quiz.status_code != 200:
            sys.exit(f"quiz failed: {quiz.status_code} {quiz.text}")
        for q in quiz.json()["questions"]:
            full = bank[q["id"]]
            if rng.random() < p_correct[q["topic"]]:
                choice = full["answer_index"]
            else:
                choice = rng.choice([i for i in range(4) if i != full["answer_index"]])
            client.post(
                f"{base}/live/quiz/answer",
                json={"session_id": sid, "question_id": q["id"], "chosen_index": choice},
            ).raise_for_status()

    sample = [
        "What is a TLB?", "How does a mutex differ from a semaphore?",
        "Why do we need virtual memory?", "What does a cache line hold?", "What is a syscall?",
    ]
    for i in range(args.asks):
        client.post(
            f"{base}/live/ask",
            json={"session_id": uuid.uuid4().hex[:24], "text": sample[i % len(sample)]},
        )

    stats = client.get(f"{base}/live/stats", headers=headers).json()
    print(json.dumps({k: stats[k] for k in ("participants", "attempts", "questions_asked")}))
    for t in stats["topics"]:
        flag = "" if t["ranked"] else " (not ranked)"
        print(f"{t['pct_incorrect']:>3}% incorrect  {t['topic']}{flag}")


if __name__ == "__main__":
    main()

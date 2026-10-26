"""
CLI script to scan EdStem course discussions for staff-answered questions,
extract the verified staff answers, and index them into ChromaDB as high-value RAG knowledge.

Usage:
    python scripts/learn_staff_answers.py [--limit 50]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.edstem.client import EdStemClient
from bot.rag import MaterialIngester, VectorStore, get_embedding_model
from config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scripts.learn_staff_answers")


async def learn_from_staff_answers(limit: int = 50) -> int:
    token = settings.ed_api_token
    course_id = settings.ed_course_id
    base_url = settings.ed_base_url

    if not token or not course_id:
        logger.error("ED_API_TOKEN or ED_COURSE_ID not configured in .env")
        return 0

    # 1. Initialize RAG ingester
    vectorstore = VectorStore(
        persist_dir=settings.chroma_persist_dir,
        collection_name=settings.chroma_collection,
    )
    embedder = get_embedding_model(settings.embedding_model)
    ingester = MaterialIngester(vectorstore=vectorstore, embedder=embedder)

    learned_count = 0

    # 2. Connect to EdStem and list threads
    async with EdStemClient(token=token, base_url=base_url) as client:
        logger.info("Scanning course %d for answered questions (limit: %d)...", course_id, limit)
        threads = await client.list_threads(course_id, limit=limit, sort="new")
        
        answered_threads = [t for t in threads if t.is_question and (t.is_answered or t.is_staff_answered)]
        logger.info("Found %d answered questions. Extracting staff answers...", len(answered_threads))

        for t in answered_threads:
            try:
                qa = await client.get_thread_staff_qa(t.id)
                if qa:
                    added = ingester.ingest_staff_qa(qa)
                    if added:
                        learned_count += 1
                        print(f"✓ Learned Q&A #{qa['thread_id']}: '{qa['title']}'")
                        print(f"   Author: {qa['author']} ({qa['role']})")
                        print(f"   Answer: {qa['answer'][:90]}...\n")
                    else:
                        print(f"- Already indexed Q&A #{qa['thread_id']}: '{qa['title']}'")
            except Exception as exc:
                logger.warning("Could not extract QA for thread %d: %s", t.id, exc)

    logger.info("Finished learning from staff answers. Newly indexed: %d", learned_count)
    logger.info("Total chunks now in vector store: %d", vectorstore.count())
    return learned_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Learn from staff-answered EdStem questions and add to RAG vectorstore.")
    parser.add_argument("--limit", type=int, default=30, help="Max threads to inspect (default: 30)")
    args = parser.parse_args()

    asyncio.run(learn_from_staff_answers(limit=args.limit))


if __name__ == "__main__":
    main()

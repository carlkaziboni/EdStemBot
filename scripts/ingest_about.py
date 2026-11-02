"""
Index the approved askEd documents into their own ChromaDB collection.

Sources (and only these):
  - data/about/*.md        talk proposal and curated FAQ (edit these to change what askEd knows)
  - README.md              the project README

Re-running replaces each document's chunks, so edits never leave stale text.

Usage:
    python scripts/ingest_about.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bot.live.about import ingest_about
from bot.rag import VectorStore, get_embedding_model
from config.settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("scripts.ingest_about")

TITLES = {
    "teachathon_proposal.md": "TeachAthon proposal",
    "askEd_faq.md": "askEd FAQ",
}


def main() -> None:
    docs_dir = Path(settings.about_docs_dir)
    docs: list[tuple[str, Path]] = []
    for path in sorted(docs_dir.glob("*.md")):
        docs.append((TITLES.get(path.name, path.stem), path))
    readme = ROOT / "README.md"
    if readme.exists():
        docs.append(("askEd README", readme))
    if not docs:
        sys.exit(f"No documents found in {docs_dir} or README.md")

    store = VectorStore(
        persist_dir=settings.chroma_persist_dir, collection_name=settings.about_collection
    )
    added = ingest_about(store, get_embedding_model(settings.embedding_model), docs)
    logger.info("Indexed %d chunks; collection '%s' now holds %d.", added, settings.about_collection, store.count())


if __name__ == "__main__":
    main()

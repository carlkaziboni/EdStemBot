"""
CLI script to ingest course materials (PDFs) into ChromaDB.

Usage:
    python scripts/ingest_materials.py [--dir data/course_materials]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.rag.embeddings import get_embedding_model
from bot.rag.ingest import MaterialIngester
from bot.rag.vectorstore import VectorStore
from config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scripts.ingest_materials")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest Computer Systems course material PDFs into ChromaDB."
    )
    parser.add_argument(
        "--dir",
        default="./data/course_materials",
        help="Path to directory containing PDF files (default: data/course_materials)",
    )
    args = parser.parse_args()

    materials_dir = Path(args.dir)
    if not materials_dir.exists():
        materials_dir.mkdir(parents=True, exist_ok=True)
        logger.warning(
            "Created directory %s. Please place your lecture/assignment PDFs here.",
            materials_dir.resolve(),
        )
        return

    logger.info("Initializing vector store at %s...", settings.chroma_persist_dir)
    vectorstore = VectorStore(
        persist_dir=settings.chroma_persist_dir,
        collection_name=settings.chroma_collection,
    )
    embedder = get_embedding_model(settings.embedding_model)
    ingester = MaterialIngester(vectorstore=vectorstore, embedder=embedder)

    total_chunks = ingester.ingest_directory(materials_dir)
    logger.info(
        "Ingestion completed. Total chunks in vector store: %d",
        vectorstore.count(),
    )


if __name__ == "__main__":
    main()

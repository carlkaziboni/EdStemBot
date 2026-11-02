"""
Main entry point for EdStemBot.

Runs the real-time EdStem WebSocket listener and the FastAPI analytics dashboard concurrently.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn

from bot.analytics.classifier import TopicClassifier
from bot.analytics.tracker import AnalyticsTracker
from bot.edstem.client import EdStemClient
from bot.edstem.websocket import EdStemWebSocketListener
from bot.live.about import ABOUT_MAX_DISTANCE, AboutService
from bot.live.quiz_bank import QuizBank
from bot.live.ratelimit import RateLimiter
from bot.live.store import LiveStore
from bot.llm import get_llm_provider
from bot.processor import QuestionProcessor
from bot.rag import Retriever, VectorStore, get_embedding_model
from bot.study import StudyService
from config.settings import settings
from dashboard.app import app

logging.basicConfig(
    level=settings.log_level_int,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("bot.main")


async def sync_existing_questions(
    client: EdStemClient,
    course_id: int,
    processor: QuestionProcessor,
    limit: int = 30,
) -> None:
    """
    Backfill recent questions from EdStem so the dashboard has historical context on start.
    """
    logger.info("Backfilling up to %d recent questions from course %d...", limit, course_id)
    try:
        questions = await client.get_recent_questions(course_id, limit=limit)
        logger.info("Found %d questions on EdStem. Processing...", len(questions))
        for q in questions:
            await processor.process(q)
        logger.info("Finished backfilling recent questions.")
    except Exception as exc:
        logger.warning("Could not backfill questions from EdStem: %s", exc)


async def start_listener(processor: QuestionProcessor) -> None:
    """Run the WebSocket listener if credentials are configured."""
    if settings.app_mode == "live":
        logger.info("APP_MODE=live: EdStem listener disabled (audience mode only).")
        return

    token = settings.ed_api_token
    course_id = settings.ed_course_id

    if not token or not course_id:
        logger.warning(
            "ED_API_TOKEN or ED_COURSE_ID not configured in .env — "
            "WebSocket listener is paused. The dashboard is running in standalone mode."
        )
        return

    # Backfill recent questions using REST client
    try:
        async with EdStemClient(token=token, base_url=settings.ed_base_url) as client:
            await sync_existing_questions(client, course_id, processor, limit=25)
    except Exception as exc:
        logger.warning("Initial REST sync encountered an error: %s", exc)

    # Start live WebSocket listener
    listener = EdStemWebSocketListener(
        token=token,
        course_id=course_id,
        on_new_thread=processor.process,
        base_url=settings.ed_base_url,
    )
    logger.info("Starting EdStem WebSocket listener for course %d...", course_id)
    await listener.start()


async def start_dashboard() -> None:
    """Run the FastAPI web dashboard via uvicorn."""
    port = int(os.environ.get("PORT", settings.dashboard_port))  # Render sets PORT
    config = uvicorn.Config(
        app=app,
        host=settings.dashboard_host,
        port=port,
        log_level=settings.log_level.lower(),
    )
    server = uvicorn.Server(config)
    logger.info(
        "Starting lecturer dashboard at http://%s:%d",
        settings.dashboard_host if settings.dashboard_host != "0.0.0.0" else "localhost",
        port,
    )
    await server.serve()


async def main() -> None:
    """Initialize components and run bot + dashboard."""
    logger.info("Initializing EdStemBot...")

    # 1. Initialize SQLite Database
    tracker = AnalyticsTracker(settings.database_url)
    await tracker.init_db()

    # 2. Initialize RAG Components
    logger.info("Loading embedding model (%s)...", settings.embedding_model)
    embedder = get_embedding_model(settings.embedding_model)
    vectorstore = VectorStore(
        persist_dir=settings.chroma_persist_dir,
        collection_name=settings.chroma_collection,
    )
    retriever = Retriever(vectorstore=vectorstore, embedder=embedder)

    if settings.app_mode == "live":
        # Load the model now so the first attendee doesn't pay the cold-start cost.
        await asyncio.to_thread(embedder.encode_single, "warmup")

    # 3. Initialize LLM Provider & Classifier
    logger.info("Loading LLM provider (%s)...", settings.llm_provider)
    llm = get_llm_provider(settings.llm_provider)
    classifier = TopicClassifier(llm=llm)

    # 4. Orchestrator Processor
    processor = QuestionProcessor(
        retriever=retriever,
        classifier=classifier,
        tracker=tracker,
    )

    # Study helpers for the Chrome extension API
    app.state.study = StudyService(retriever=retriever, llm=llm, classifier=classifier)

    # askEd Live: audience Q&A about askEd itself, from an isolated approved-docs collection
    about_store = VectorStore(
        persist_dir=settings.chroma_persist_dir, collection_name=settings.about_collection
    )
    if about_store.count() == 0:
        logger.warning(
            "About-askEd collection is empty: run scripts/ingest_about.py. "
            "Audience questions will get a 'not in the materials' reply until then."
        )
    app.state.about = AboutService(
        Retriever(about_store, embedder, n_results=6, max_distance=ABOUT_MAX_DISTANCE), llm
    )

    # askEd Live: quiz bank and spend limits
    app.state.live_store = LiveStore(tracker.session_factory)
    try:
        app.state.quiz_bank = QuizBank.load(settings.quiz_bank_path)
        logger.info("Loaded %d quiz questions from %s", len(app.state.quiz_bank), settings.quiz_bank_path)
    except FileNotFoundError:
        logger.warning(
            "No quiz bank at %s. Run scripts/generate_quiz_bank.py to create one.",
            settings.quiz_bank_path,
        )
        app.state.quiz_bank = QuizBank([])
    app.state.limiter = RateLimiter(per_window=5, window_s=60, daily_cap=settings.live_daily_ask_cap)
    app.state.ask_semaphore = asyncio.Semaphore(8)  # cap concurrent LLM calls

    # 5. Run WebSocket Listener and Dashboard concurrently
    listener_task = asyncio.create_task(start_listener(processor))
    dashboard_task = asyncio.create_task(start_dashboard())

    try:
        await asyncio.gather(listener_task, dashboard_task)
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Shutting down EdStemBot...")
        listener_task.cancel()
        dashboard_task.cancel()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Terminated by user.")
        sys.exit(0)

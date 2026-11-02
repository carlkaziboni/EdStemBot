"""
FastAPI application for the EdStemBot Lecturer Analytics Dashboard.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from bot.analytics.tracker import AnalyticsTracker
from config.settings import settings
from dashboard.routes.api import router as api_router
from dashboard.routes.extension import router as extension_router
from dashboard.routes.live import router as live_router
from dashboard.routes.overview import router as overview_router
from dashboard.routes.topics import router as topics_router

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure database schema is initialised when the dashboard starts."""
    tracker = AnalyticsTracker()
    await tracker.init_db()
    logger.info("Dashboard initialized and connected to database.")
    yield


def create_app(live_only: bool) -> FastAPI:
    """
    Build the FastAPI app.

    live_only=True (public deployment) mounts just the audience and presenter
    routes. The private EdStem analytics and extension API are not mounted at
    all, and the interactive API docs are disabled.
    """
    application = FastAPI(
        title="askEd — Lecturer Analytics Dashboard",
        description="Real-time analytics on student questions and topic trends.",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None if live_only else "/docs",
        redoc_url=None if live_only else "/redoc",
        openapi_url=None if live_only else "/openapi.json",
    )
    application.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    application.include_router(live_router)

    if not live_only:
        application.add_middleware(
            CORSMiddleware,
            allow_origin_regex=r"chrome-extension://.*",
            allow_methods=["POST"],
            allow_headers=["Content-Type", "X-EdStemBot-Key"],
        )
        application.include_router(overview_router)
        application.include_router(topics_router)
        application.include_router(api_router)
        application.include_router(extension_router)
    return application


app = create_app(live_only=settings.app_mode == "live")

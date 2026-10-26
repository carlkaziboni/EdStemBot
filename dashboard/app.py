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
from dashboard.routes.api import router as api_router
from dashboard.routes.extension import router as extension_router
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


app = FastAPI(
    title="EdStemBot — Lecturer Analytics Dashboard",
    description="Real-time analytics on student questions and topic trends.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"chrome-extension://.*",
    allow_methods=["POST"],
    allow_headers=["Content-Type", "X-EdStemBot-Key"],
)

# Static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Routers
app.include_router(overview_router)
app.include_router(topics_router)
app.include_router(api_router)
app.include_router(extension_router)

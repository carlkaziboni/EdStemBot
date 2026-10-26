"""
Topics deep-dive HTML route for the lecturer dashboard.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from bot.analytics.tracker import AnalyticsTracker

router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def get_tracker() -> AnalyticsTracker:
    return AnalyticsTracker()


@router.get("/topics", response_class=HTMLResponse)
async def topics_page(
    request: Request,
    tracker: AnalyticsTracker = Depends(get_tracker),
):
    """Deep-dive topic analytics page."""
    topic_counts = await tracker.get_topic_counts(limit=25)
    recent_trends = await tracker.get_topic_trends(days=7)

    return templates.TemplateResponse(
        request=request,
        name="topics.html",
        context={
            "page_title": "Topic Analytics",
            "active_page": "topics",
            "topic_counts": topic_counts,
            "recent_trends": recent_trends,
        },
    )

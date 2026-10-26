"""
Overview and Unclassified HTML routes for the dashboard.
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


@router.get("/", response_class=HTMLResponse)
async def overview_page(
    request: Request,
    tracker: AnalyticsTracker = Depends(get_tracker),
):
    """Main dashboard overview page."""
    kpis = await tracker.get_kpis()
    recent_questions = await tracker.get_recent_questions(limit=10)
    top_topics = await tracker.get_topic_counts(limit=6)

    return templates.TemplateResponse(
        request=request,
        name="overview.html",
        context={
            "page_title": "Overview",
            "active_page": "overview",
            "kpis": kpis,
            "recent_questions": recent_questions,
            "top_topics": top_topics,
        },
    )


@router.get("/unclassified", response_class=HTMLResponse)
async def unclassified_page(
    request: Request,
    tracker: AnalyticsTracker = Depends(get_tracker),
):
    """Review questions with low confidence or unclassified topics."""
    questions = await tracker.get_unclassified_questions(limit=50)

    return templates.TemplateResponse(
        request=request,
        name="unclassified.html",
        context={
            "page_title": "Needs Review",
            "active_page": "unclassified",
            "questions": questions,
        },
    )

"""
JSON REST API endpoints for the dashboard visualizations and dynamic data.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from bot.analytics.tracker import AnalyticsTracker

router = APIRouter(prefix="/api/v1", tags=["analytics"])


def get_tracker() -> AnalyticsTracker:
    # Uses default settings.database_url
    return AnalyticsTracker()


@router.get("/kpis")
async def get_kpis(
    tracker: AnalyticsTracker = Depends(get_tracker),
) -> dict[str, Any]:
    """Summary KPI metrics for top stat cards."""
    return await tracker.get_kpis()


@router.get("/topics/distribution")
async def get_topic_distribution(
    limit: int = Query(default=15, ge=1, le=50),
    tracker: AnalyticsTracker = Depends(get_tracker),
) -> list[dict[str, Any]]:
    """Question frequency per topic."""
    return await tracker.get_topic_counts(limit=limit)


@router.get("/topics/trends")
async def get_topic_trends(
    days: int = Query(default=7, ge=1, le=30),
    tracker: AnalyticsTracker = Depends(get_tracker),
) -> list[dict[str, Any]]:
    """Daily question counts per topic over the past N days."""
    return await tracker.get_topic_trends(days=days)


@router.get("/activity/heatmap")
async def get_activity_heatmap(
    tracker: AnalyticsTracker = Depends(get_tracker),
) -> list[dict[str, Any]]:
    """Day of week (0-6) and hour (0-23) activity grid."""
    return await tracker.get_activity_heatmap()


@router.get("/questions/recent")
async def get_recent_questions(
    limit: int = Query(default=20, ge=1, le=100),
    tracker: AnalyticsTracker = Depends(get_tracker),
) -> list[dict[str, Any]]:
    """Recent student questions."""
    return await tracker.get_recent_questions(limit=limit)


@router.get("/questions/unclassified")
async def get_unclassified_questions(
    limit: int = Query(default=20, ge=1, le=100),
    tracker: AnalyticsTracker = Depends(get_tracker),
) -> list[dict[str, Any]]:
    """Questions that were unclassifiable or categorized as 'Other'."""
    return await tracker.get_unclassified_questions(limit=limit)

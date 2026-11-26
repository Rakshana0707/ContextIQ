"""
API Router for Long-Term Behavioral Trend Analysis (Phase 8.7).
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_id
from app.db.session import get_db
from app.models.behavioral_trend import (
    BehavioralMilestoneRecord,
    TemporalGranularity,
)
from app.schemas.behavioral_trend import (
    BehavioralMilestoneRead,
    BehavioralTrendsDashboardData,
    ChangePointRead,
    TrendCategorySummary,
)
from app.services.behavioral_trend_service import BehavioralTrendService

trends_router = APIRouter(prefix="/trends", tags=["behavioral-trends"])


@trends_router.get(
    "/dashboard",
    response_model=BehavioralTrendsDashboardData,
    summary="Get long-term behavioral trends dashboard",
)
def get_behavioral_trends_dashboard(
    lookback_days: int = Query(30, ge=7, le=365, description="Lookback window in days"),
    granularity: TemporalGranularity = Query(TemporalGranularity.DAILY, description="Aggregation granularity"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Retrieves multi-timescale daily metrics, rolling averages, category comparisons
    vs personal baseline, behavioral milestones, and long-term insight summaries.
    """
    return BehavioralTrendService.get_dashboard_data(
        db=db,
        user_id=user_id,
        granularity=granularity,
        lookback_days=lookback_days,
    )


@trends_router.get(
    "/categories",
    response_model=List[TrendCategorySummary],
    summary="Get trend summaries by category",
)
def get_trend_categories(
    lookback_days: int = Query(30, ge=7, le=365),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Returns trajectories and baseline comparisons across all 9 behavioral categories."""
    data = BehavioralTrendService.get_dashboard_data(
        db=db, user_id=user_id, lookback_days=lookback_days
    )
    return data.category_summaries


@trends_router.get(
    "/milestones",
    response_model=List[BehavioralMilestoneRead],
    summary="List achieved behavioral milestones",
)
def list_behavioral_milestones(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Lists statistically verified positive milestones in user habits and recovery."""
    data = BehavioralTrendService.get_dashboard_data(db=db, user_id=user_id)
    return data.milestones


@trends_router.post(
    "/milestones/{milestone_id}/acknowledge",
    response_model=BehavioralMilestoneRead,
    summary="Acknowledge behavioral milestone",
)
def acknowledge_milestone(
    milestone_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Marks a behavioral milestone as acknowledged by the user."""
    m = db.query(BehavioralMilestoneRecord).filter(
        BehavioralMilestoneRecord.id == milestone_id,
        BehavioralMilestoneRecord.user_id == user_id,
    ).first()
    if not m:
        from app.core.errors import NotFoundError
        raise NotFoundError(f"Milestone {milestone_id} not found.")

    m.is_acknowledged = True
    db.flush()
    return BehavioralMilestoneRead.model_validate(m)

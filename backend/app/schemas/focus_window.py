"""
Pydantic v2 schemas for Personalized Focus Window Discovery (Phase 4.3).
Defines temporal hourly metrics, discovered focus windows, category conditioning,
and grounded scheduling insights.
"""
from __future__ import annotations

import uuid
from datetime import datetime, time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class HourlyTemporalMetrics(BaseModel):
    """Aggregated empirical metrics for a 1-hour circadian time bucket."""
    hour: int = Field(ge=0, le=23, description="Hour of day (0-23) in user's local timezone")
    focus_minutes: float = Field(ge=0.0, description="Mean focused duration per session")
    task_completion_rate: float = Field(ge=0.0, le=1.0, description="Ratio of tasks completed vs created/scheduled")
    interruption_density_hourly: float = Field(ge=0.0, description="Average disruptions per active hour")
    avg_resumption_lag_seconds: float = Field(ge=0.0, description="Median cognitive recovery lag in seconds")
    context_switch_frequency: float = Field(ge=0.0, description="Application transitions per hour")
    quality_score: float = Field(ge=0.0, le=100.0, description="Composite Focus Quality Score Q(h)")
    observation_count: int = Field(ge=0, description="Number of observed records in this slot")
    is_prime_candidate: bool = Field(description="True if quality score exceeds threshold")


class FocusWindowItemRead(BaseModel):
    """Schema representing an individual discovered personal focus window."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    task_category: Optional[str] = Field(default=None, description="Conditioned category or None for general")
    day_of_week: Optional[int] = Field(default=None, description="0=Monday .. 6=Sunday, None=Daily recurrent")
    start_time: time
    end_time: time
    duration_minutes: int
    quality_score: float = Field(ge=0.0, le=100.0)
    focus_density: float = Field(ge=0.0, le=1.0)
    completion_rate: float = Field(ge=0.0, le=1.0)
    interruption_density_hourly: float = Field(ge=0.0)
    avg_resumption_lag_seconds: float = Field(ge=0.0)
    observation_count: int = Field(ge=0)
    confidence_score: float = Field(ge=0.0, le=1.0)
    pattern_status: str = Field(description="ESTABLISHED, EMERGING, or INSUFFICIENT_EVIDENCE")
    grounded_insights: List[str] = Field(default_factory=list)
    is_active: bool = True
    user_confirmed: bool = False
    discovered_at: datetime


class CategoryFocusWindowRead(BaseModel):
    """Schema representing focus windows conditioned on a specific task category."""
    category: str
    observation_count: int
    baseline_completion_rate: float = Field(ge=0.0, le=1.0)
    in_window_completion_rate: float = Field(ge=0.0, le=1.0)
    completion_lift_percentage: float = Field(description="Relative improvement in completion rate")
    focus_windows: List[FocusWindowItemRead]
    insights: List[str]


class FocusWindowMetricsResponse(BaseModel):
    """Circadian 24-hour metric distribution response for analytics dashboards."""
    user_id: uuid.UUID
    timezone: str
    observation_window_days: int
    hourly_metrics: List[HourlyTemporalMetrics]
    peak_focus_hours: List[int]
    fragmented_hours: List[int]
    insights: List[str]

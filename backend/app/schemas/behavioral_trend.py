"""
Pydantic schemas for Long-Term Behavioral Trend Analysis (Phase 8.7).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.behavioral_trend import (
    TemporalGranularity,
    TrendCategory,
    TrendDirection,
)


class DailyTrendPoint(BaseModel):
    date: str
    focus_minutes: float
    focus_consistency: float
    recovery_efficiency: float
    context_switches_per_hour: float
    tasks_completed: int
    deadline_adherence: float
    behavioral_friction: float
    data_coverage_pct: float
    rolling_7d_focus: Optional[float] = None
    rolling_30d_focus: Optional[float] = None
    ema_friction: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class TrendCategorySummary(BaseModel):
    category: TrendCategory
    current_period_mean: float
    previous_period_mean: float
    personal_baseline_mean: float
    period_change_pct: float
    baseline_change_pct: float
    trend_direction: TrendDirection
    slope: float
    confidence: float
    descriptive_summary: str

    model_config = ConfigDict(from_attributes=True)


class BehavioralMilestoneRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    milestone_type: str
    title: str
    description: str
    detected_at: datetime
    evaluation_period_start: datetime
    evaluation_period_end: datetime
    change_magnitude_pct: float
    statistical_confidence: float
    baseline_value: float
    observed_value: float
    supporting_evidence: Dict[str, Any] = Field(default_factory=dict)
    is_acknowledged: bool = False

    model_config = ConfigDict(from_attributes=True)


class ChangePointRead(BaseModel):
    id: uuid.UUID
    metric_name: str
    change_point_at: datetime
    change_type: str
    prior_mean: float
    subsequent_mean: float
    magnitude_delta: float
    p_value: float
    description: str

    model_config = ConfigDict(from_attributes=True)


class InterventionComparisonRead(BaseModel):
    intervention_id: Optional[uuid.UUID] = None
    title: str
    accepted_at: datetime
    pre_period_friction: float
    post_period_friction: float
    friction_delta: float
    pre_period_focus_mins: float
    post_period_focus_mins: float
    focus_delta: float
    observational_note: str

    model_config = ConfigDict(from_attributes=True)


class BehavioralInsightsSummary(BaseModel):
    what_improved: List[str] = Field(default_factory=list)
    what_became_less_consistent: List[str] = Field(default_factory=list)
    patterns_changed: List[str] = Field(default_factory=list)
    interventions_associated: List[str] = Field(default_factory=list)
    needs_attention: List[str] = Field(default_factory=list)


class BehavioralTrendsDashboardData(BaseModel):
    user_id: uuid.UUID
    granularity: TemporalGranularity
    date_range: Dict[str, str]
    overall_data_coverage_pct: float
    observed_days_count: int
    expected_days_count: int
    daily_series: List[DailyTrendPoint] = Field(default_factory=list)
    category_summaries: List[TrendCategorySummary] = Field(default_factory=list)
    milestones: List[BehavioralMilestoneRead] = Field(default_factory=list)
    change_points: List[ChangePointRead] = Field(default_factory=list)
    intervention_comparisons: List[InterventionComparisonRead] = Field(default_factory=list)
    long_term_insights: BehavioralInsightsSummary

    model_config = ConfigDict(from_attributes=True)

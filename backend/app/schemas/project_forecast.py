"""
Pydantic schemas for Intelligent Project Progress Forecasting (Phase 8.6).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.project_forecast import (
    DataSufficiencyStatus,
    DelayRiskTier,
    ForecastingModelType,
)


class MilestoneForecastItem(BaseModel):
    milestone_id: uuid.UUID
    title: str
    due_date: Optional[datetime] = None
    projected_completion_date: Optional[datetime] = None
    on_time_probability: float = Field(ge=0.0, le=1.0)
    is_completed: bool = False
    risk_tier: DelayRiskTier = DelayRiskTier.MODERATE
    model_config = ConfigDict(from_attributes=True)


class DelayContributor(BaseModel):
    factor: str
    impact_score: float = Field(ge=0.0, le=1.0)
    description: str
    remediation_suggestion: str
    model_config = ConfigDict(from_attributes=True)


class ProjectForecastRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    project_id: uuid.UUID
    forecast_at: datetime
    target_completion_date: Optional[datetime] = None
    estimated_completion_date: Optional[datetime] = None
    p10_completion_date: Optional[datetime] = None
    p90_completion_date: Optional[datetime] = None
    uncertainty_spread_days: float
    on_time_probability: float
    delay_risk_score: float
    delay_risk_tier: str
    expected_remaining_workload_hours: float
    remaining_tasks_count: int
    completed_tasks_count: int
    blocked_dependencies_count: int
    current_velocity_tasks_per_week: float
    required_velocity_tasks_per_week: float
    data_sufficiency: str
    model_name: str
    major_delay_contributors: List[Dict[str, Any]] = Field(default_factory=list)
    milestone_forecasts: List[Dict[str, Any]] = Field(default_factory=list)
    feature_snapshot: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectForecastGenerateRequest(BaseModel):
    project_id: uuid.UUID
    model_type: ForecastingModelType = ForecastingModelType.ENSEMBLE_FORECASTER
    simulate_monte_carlo: bool = True


class ForecastScenarioRequest(BaseModel):
    project_id: uuid.UUID
    prioritize_overdue_tasks: bool = False
    additional_focus_hours_per_week: float = Field(default=0.0, ge=0.0, le=40.0)
    resolve_blockers: bool = False
    deadline_extension_days: float = Field(default=0.0, ge=0.0, le=180.0)


class ForecastScenarioResult(BaseModel):
    project_id: uuid.UUID
    baseline_on_time_probability: float
    scenario_on_time_probability: float
    probability_lift: float
    baseline_estimated_completion: Optional[datetime] = None
    scenario_estimated_completion: Optional[datetime] = None
    days_saved: float
    baseline_risk_tier: str
    scenario_risk_tier: str
    scenario_summary: str
    recommended_interventions: List[str]


class ModelBenchmarkResult(BaseModel):
    benchmarked_at: datetime
    models_evaluated: List[str]
    mae_days_by_model: Dict[str, float]
    rmse_days_by_model: Dict[str, float]
    brier_score_by_model: Dict[str, float]
    interval_coverage_p10_p90: Dict[str, float]
    horizon_performance: Dict[str, Dict[str, float]]
    recommended_model: str
    benchmark_summary: str


class ProjectForecastDashboardData(BaseModel):
    project_id: uuid.UUID
    project_title: str
    target_completion_date: Optional[datetime] = None
    forecast: Optional[ProjectForecastRead] = None
    data_sufficiency: str
    recent_forecasts: List[ProjectForecastRead] = Field(default_factory=list)
    milestone_predictions: List[MilestoneForecastItem] = Field(default_factory=list)
    major_delay_contributors: List[DelayContributor] = Field(default_factory=list)

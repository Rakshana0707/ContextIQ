"""
SQLAlchemy ORM models for Intelligent Project Progress Forecasting (Phase 8.6).

Stores predictive progress intelligence, probabilistic completion intervals (P10/P50/P90),
milestone forecasts, delay contributors, and empirical data sufficiency ratings.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin, utcnow


class DelayRiskTier(str, Enum):
    """Categorical risk assessment for project timeline slippage."""
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DataSufficiencyStatus(str, Enum):
    """Integrity and depth indicator of historical evidence supporting the forecast."""
    DATA_SUFFICIENT = "DATA_SUFFICIENT"                   # High confidence, extensive task/session history
    LIMITED_HISTORY_FALLBACK = "LIMITED_HISTORY_FALLBACK" # Moderate confidence, uses Bayesian velocity prior
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"               # Low confidence, heuristic baseline with wide bounds


class ForecastingModelType(str, Enum):
    """Predictive model used to generate project forecast."""
    RULE_BASED_VELOCITY = "RULE_BASED_VELOCITY"           # Linear velocity extrapolation
    HISTORICAL_RATE = "HISTORICAL_RATE"                   # Empirical task completion distribution
    SURVIVAL_HAZARD = "SURVIVAL_HAZARD"                   # Weibull / Cox proportional hazard model
    ENSEMBLE_FORECASTER = "ENSEMBLE_FORECASTER"           # Calibrated multi-model ensemble with Monte Carlo bounds


class ProjectForecast(Base, UUIDPKMixin, TimestampMixin):
    """
    Probabilistic forecast of a project's completion trajectory,
    incorporating empirical velocity, blockers, friction, and uncertainty bounds.
    """
    __tablename__ = "project_forecasts"
    __table_args__ = (
        Index("ix_project_forecasts_user_proj", "user_id", "project_id"),
        Index("ix_project_forecasts_time", "project_id", "forecast_at"),
        {"extend_existing": True},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    forecast_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True
    )

    # Targets & Predictions
    target_completion_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    estimated_completion_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # Median / P50 estimate
    p10_completion_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # Optimistic 10th percentile
    p90_completion_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # Conservative 90th percentile
    uncertainty_spread_days: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )

    # Probability & Risk
    on_time_probability: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5
    )  # 0.0 to 1.0
    delay_risk_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5
    )  # 0.0 to 1.0
    delay_risk_tier: Mapped[str] = mapped_column(
        String(32), nullable=False, default=DelayRiskTier.MODERATE.value
    )

    # Workload & Bottlenecks
    expected_remaining_workload_hours: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    remaining_tasks_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    completed_tasks_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    blocked_dependencies_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    current_velocity_tasks_per_week: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    required_velocity_tasks_per_week: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )

    # Model & Evidence Metadata
    data_sufficiency: Mapped[str] = mapped_column(
        String(32), nullable=False, default=DataSufficiencyStatus.DATA_SUFFICIENT.value
    )
    model_name: Mapped[str] = mapped_column(
        String(64), nullable=False, default=ForecastingModelType.ENSEMBLE_FORECASTER.value
    )

    # Explainability & Milestones
    major_delay_contributors: Mapped[List[Dict[str, Any]]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list
    )
    milestone_forecasts: Mapped[List[Dict[str, Any]]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list
    )
    feature_snapshot: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )

    # Relationships
    user = relationship("User")
    project = relationship("Project")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ProjectForecast project={self.project_id} on_time_p={self.on_time_probability:.2f} "
            f"tier={self.delay_risk_tier} p50={self.estimated_completion_date}>"
        )

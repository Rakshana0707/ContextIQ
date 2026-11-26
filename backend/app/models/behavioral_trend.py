"""
SQLAlchemy ORM models for Long-Term Behavioral Trend Analysis (Phase 8.7).

Stores:
- Aggregated daily behavioral metrics.
- Detected behavioral milestones (statistically verified sustained improvements).
- Change-point detection records (structural shifts and behavioral drift).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin, utcnow


class TrendCategory(str, Enum):
    """Core categories of long-term productivity behavior."""
    FOCUS_CONSISTENCY = "FOCUS_CONSISTENCY"
    RECOVERY_EFFICIENCY = "RECOVERY_EFFICIENCY"
    CONTEXT_SWITCH_FREQUENCY = "CONTEXT_SWITCH_FREQUENCY"
    TASK_COMPLETION_CONSISTENCY = "TASK_COMPLETION_CONSISTENCY"
    DEADLINE_ADHERENCE = "DEADLINE_ADHERENCE"
    BEHAVIORAL_FRICTION = "BEHAVIORAL_FRICTION"
    INTERRUPTION_EXPOSURE = "INTERRUPTION_EXPOSURE"
    INTERVENTION_EFFECTIVENESS = "INTERVENTION_EFFECTIVENESS"
    GOAL_PROGRESS = "GOAL_PROGRESS"


class TrendDirection(str, Enum):
    """Directional trajectory of a behavioral metric over time."""
    IMPROVING = "IMPROVING"
    STABLE = "STABLE"
    DEGRADING = "DEGRADING"
    VOLATILE = "VOLATILE"


class TemporalGranularity(str, Enum):
    """Aggregation period granularity."""
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    CUSTOM = "CUSTOM"


class BehavioralDailyMetric(Base, UUIDPKMixin, TimestampMixin):
    """
    Daily aggregated behavioral metrics capturing focus, recovery, friction,
    and task execution with telemetry coverage tracking.
    """
    __tablename__ = "behavioral_daily_metrics"
    __table_args__ = (
        Index("ix_daily_metrics_user_date", "user_id", "metric_date"),
        UniqueConstraint("user_id", "metric_date", name="uq_user_daily_metric_date"),
        {"extend_existing": True},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Focus Dynamics
    total_focus_minutes: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    focus_sessions_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_session_duration_minutes: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    focus_consistency_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # 0.0 to 1.0

    # Interruption & Recovery
    interruption_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    interruptions_per_focus_hour: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_recovery_lag_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    recovery_efficiency_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # 0.0 to 1.0

    # Context Switching & Friction
    context_switch_frequency: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    behavioral_friction_index: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # 0.0 to 100.0

    # Task Execution & Deadlines
    tasks_completed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tasks_due_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tasks_completed_on_time: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deadline_adherence_rate: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)  # 0.0 to 1.0

    # Coverage & Confidence Integrity
    data_coverage_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)  # 0.0 to 1.0
    raw_telemetry_snapshot: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )

    # Relationships
    user = relationship("User")


class BehavioralMilestoneRecord(Base, UUIDPKMixin, TimestampMixin):
    """
    Statistically detected positive milestones in user behavioral patterns
    (e.g. sustained reduction in recovery lag, improved focus consistency).
    """
    __tablename__ = "behavioral_milestone_records"
    __table_args__ = (
        Index("ix_behavioral_milestones_user_time", "user_id", "detected_at"),
        {"extend_existing": True},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    milestone_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)

    evaluation_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evaluation_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    change_magnitude_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    statistical_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.95)
    baseline_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    observed_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    supporting_evidence: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user = relationship("User")


class BehavioralChangePoint(Base, UUIDPKMixin, TimestampMixin):
    """
    Identified structural change-point in behavior (CUSUM / Bayesian shift),
    marking when a sustained behavioral shift or drift occurred.
    """
    __tablename__ = "behavioral_change_points"
    __table_args__ = (
        Index("ix_change_points_user_metric", "user_id", "metric_name"),
        {"extend_existing": True},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    change_point_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    change_type: Mapped[str] = mapped_column(String(32), nullable=False)  # STEP_INCREASE, STEP_DECREASE, VARIANCE_SHIFT
    prior_mean: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    subsequent_mean: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    magnitude_delta: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    p_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.05)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    associated_intervention_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True
    )

    user = relationship("User")

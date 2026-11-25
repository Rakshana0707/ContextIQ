"""
Database models for ContextIQ Intervention Effectiveness and Causal Evaluation Engine (Phase 4.7).
Persists:
- InterventionOutcome: Multi-horizon empirical outcome observations, baseline-vs-observed deltas,
  execution evidence, confounder detection, and composite scores.
- InterventionExperiment: Randomized controlled holdout configurations, sample sizes,
  and estimated causal lift (ATE / p-values).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import UUIDPKMixin, utcnow


class InterventionOutcome(Base, UUIDPKMixin):
    """
    Measurable empirical outcome of an intervention event or control holdout.
    Connects explicit user feedback, empirical downstream execution telemetry,
    and causal comparison baselines.
    """

    __tablename__ = "intervention_outcomes"
    __table_args__ = (
        Index("ix_intervention_outcomes_user_created", "user_id", "created_at"),
        Index("ix_intervention_outcomes_type", "intervention_type"),
        Index("ix_intervention_outcomes_status", "treatment_status"),
        Index("ix_intervention_outcomes_experiment", "experiment_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    intervention_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_interventions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    decision_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bandit_decision_logs.id", ondelete="SET NULL"), nullable=True, index=True
    )

    intervention_type: Mapped[str] = mapped_column(String(64), nullable=False)
    intervention_category: Mapped[str] = mapped_column(String(32), nullable=False)  # FOCUS, RECOVERY, TASK, CONTEXTUAL, WORKLOAD

    # Causal & Treatment Attribution
    treatment_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="TREATED"
    )  # TREATED, CONTROL_HOLDOUT, OBSERVATIONAL
    experiment_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Exposure & Empirical Execution Tracking
    presented_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    user_action: Mapped[str] = mapped_column(
        String(32), nullable=False, default="NO_ACTION"
    )  # ACCEPTED, DISMISSED, DEFERRED, EXPIRED, NO_ACTION
    action_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    was_executed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    execution_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    execution_evidence: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )

    # Observation Horizons
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observation_window_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)

    # Pre-Intervention Baseline (t_0)
    baseline_bfi: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)
    baseline_resumption_lag_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=30.0)
    baseline_hourly_interruption_rate: Mapped[float] = mapped_column(Float, nullable=False, default=2.0)
    baseline_task_due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    baseline_task_postponed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Post-Intervention Observed (t_0 + Delta t)
    observed_bfi: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    observed_resumption_lag_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    observed_hourly_interruption_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target_task_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    task_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    adhered_to_deadline: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    postponed_after_intervention: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    focus_session_minutes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Deltas & Synthesized Outcomes
    bfi_delta: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # baseline_bfi - observed_bfi
    resumption_lag_delta_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # baseline - observed
    interruption_rate_delta: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # baseline - observed
    composite_effectiveness_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    user_reported_usefulness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confounders_detected: Mapped[List[Dict[str, Any]]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list
    )
    is_statistically_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<InterventionOutcome id={self.id} type={self.intervention_type} status={self.treatment_status} score={self.composite_effectiveness_score}>"


class InterventionExperiment(Base, UUIDPKMixin):
    """
    Randomized controlled holdout configuration and tracking for causal evaluation.
    Maintains allocation ratios, treatment vs. holdout sample counts, and estimated ATE.
    """

    __tablename__ = "intervention_experiments"
    __table_args__ = (
        Index("ix_experiments_user", "user_id"),
        Index("ix_experiments_type", "target_intervention_type"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    experiment_name: Mapped[str] = mapped_column(String(128), nullable=False)
    target_intervention_type: Mapped[str] = mapped_column(String(64), nullable=False)
    control_policy: Mapped[str] = mapped_column(
        String(32), nullable=False, default="NO_ACTION_HOLDOUT"
    )  # NO_ACTION_HOLDOUT, RANDOM_BASELINE
    allocation_ratio: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.8
    )  # 0.8 treated, 0.2 control
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    sample_size_treated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sample_size_control: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    estimated_ate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    p_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<InterventionExperiment id={self.id} name={self.experiment_name} target={self.target_intervention_type} active={self.is_active}>"

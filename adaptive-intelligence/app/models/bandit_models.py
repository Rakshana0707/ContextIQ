"""
Database models for ContextIQ Contextual Bandit Engine adapter (Phase 4.6).
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


class BanditArmState(Base, UUIDPKMixin):
    """
    Persisted state for a specific contextual bandit arm per user.
    Maintains A^-1 covariance matrix (d x d), b payoff vector (d), and pull statistics.
    """

    __tablename__ = "bandit_arm_states"
    __table_args__ = (
        sa.UniqueConstraint("user_id", "arm_id", name="uq_user_bandit_arm"),
        Index("ix_bandit_states_user", "user_id"),
        Index("ix_bandit_states_arm", "arm_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    arm_id: Mapped[str] = mapped_column(String(64), nullable=False)
    algorithm: Mapped[str] = mapped_column(String(32), nullable=False, default="LIN_UCB")  # LIN_UCB, THOMPSON_SAMPLING
    model_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")

    # Bandit Parameters (d = 12)
    a_inv_matrix: Mapped[List[List[float]]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    b_vector: Mapped[List[float]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    theta_vector: Mapped[List[float]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False
    )

    # Operational Statistics
    pull_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cumulative_reward: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    consecutive_negative_rewards: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quarantined_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    last_pulled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class BanditDecisionLog(Base, UUIDPKMixin):
    """
    Log of each contextual bandit decision epoch t.
    Captures exact context vector x_t, eligible action set, chosen arm, and selection propensity.
    """

    __tablename__ = "bandit_decision_logs"
    __table_args__ = (
        Index("ix_bandit_decisions_user_time", "user_id", "decision_timestamp"),
        Index("ix_bandit_decisions_status", "status"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    associated_intervention_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_interventions.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Context representation at decision time
    context_vector: Mapped[List[float]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    context_metadata: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )

    # Action choice
    eligible_arms: Mapped[List[str]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    selected_arm: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_no_action: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Policy attributes
    algorithm: Mapped[str] = mapped_column(String(32), nullable=False, default="LIN_UCB")
    policy_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")
    predicted_expected_reward: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    exploration_bonus: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    propensity_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING_FEEDBACK", index=True
    )

    decision_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )
    observation_window_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class BanditRewardLog(Base, UUIDPKMixin):
    """
    Measurable dual-loop reward attributed to a specific bandit decision.
    """

    __tablename__ = "bandit_reward_logs"
    __table_args__ = (
        Index("ix_bandit_rewards_user", "user_id"),
        Index("ix_bandit_rewards_decision", "decision_id", unique=True),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bandit_decision_logs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    arm_id: Mapped[str] = mapped_column(String(64), nullable=False)

    explicit_reward: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    behavioral_reward: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    composite_reward: Mapped[float] = mapped_column(Float, nullable=False)

    attribution_evidence: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )
    attributed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )

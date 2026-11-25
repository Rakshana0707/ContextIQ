"""
SQLAlchemy ORM models for Behavioral Digital Twin Simulation and Proposed Workflows (Phase 6.9).
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
from app.models.mixins import TimestampMixin, UUIDPKMixin, utcnow


class SavedScenario(Base, UUIDPKMixin, TimestampMixin):
    """
    Persisted user behavioral simulation scenario.
    Stores input hypotheses, simulated output metrics, counterfactual deltas,
    and the exact model/feature versions used for reproducibility.
    """

    __tablename__ = "saved_scenarios"
    __table_args__ = (
        Index("ix_saved_scenarios_user", "user_id"),
        Index("ix_saved_scenarios_created", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scenario_type: Mapped[str] = mapped_column(String(64), nullable=False, default="CUSTOM")

    # Inputs & Modifiers
    input_parameters: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )

    # Simulated Output Estimates & Deltas
    simulation_results: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )

    # Counterfactual Assumptions
    assumptions: Mapped[List[str]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list
    )

    # Version Tracking for Reproducibility
    model_version: Mapped[str] = mapped_column(String(64), nullable=False, default="2.3.0-digital-twin")
    feature_schema_version: Mapped[str] = mapped_column(String(64), nullable=False, default="v2.3")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user = relationship("User")


class ProposedWorkflow(Base, UUIDPKMixin, TimestampMixin):
    """
    Multi-step proposed behavioral workflow generated from simulation or optimization.
    Requires explicit user approval before execution. Tracks permission audits and reversibility.
    """

    __tablename__ = "proposed_workflows"
    __table_args__ = (
        Index("ix_proposed_workflows_user_status", "user_id", "status"),
        Index("ix_proposed_workflows_idempotency", "idempotency_key", unique=True),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    scenario_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("saved_scenarios.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PROPOSED", index=True
    )  # PROPOSED | PENDING_APPROVAL | APPROVED | EXECUTING | COMPLETED | CANCELLED | REVERTED

    # Idempotency token to prevent duplicate execution
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    # Actions list (previews of steps before execution)
    actions: Mapped[List[Dict[str, Any]]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list
    )

    # Permission check results
    permission_audit: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )

    # Execution logs & rollback state
    execution_audit: Mapped[List[Dict[str, Any]]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list
    )
    revert_payload: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )
    is_reversible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User")
    scenario = relationship("SavedScenario")

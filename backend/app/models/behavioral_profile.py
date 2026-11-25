"""
Database models for ContextIQ Personal Behavioral Digital Twin & Profiles (Phase 4.2).
Maintains evolving computational representations of individual working patterns,
versioned snapshot history, and compliance audit logs.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import UUIDPKMixin, utcnow


class UserBehavioralProfile(Base, UUIDPKMixin):
    """
    Active digital twin representation of a user's working patterns.
    Contains empirical measurements across focus, interruption, task completion,
    context-switching, and temporal dimensions, along with confidence ratings.
    """

    __tablename__ = "user_behavioral_profiles"
    __table_args__ = (
        Index("ix_behavioral_profiles_user", "user_id", unique=True),
        Index("ix_behavioral_profiles_updated", "updated_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    profile_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")
    is_cold_start: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    personalization_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    telemetry_days_observed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_sessions_observed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tasks_observed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_interruptions_observed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Dimension Payloads (Structured JSONB schemas containing values, sample counts, coverage, and confidence)
    # Dimension A: Focus Behavior (typical duration, variability, uninterrupted duration)
    focus_dimension: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )

    # Dimension B: Interruption Behavior (frequency, type distribution, sensitivity index, recovery distribution)
    interruption_dimension: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )

    # Dimension C: Task Completion (completion rate, postponement frequency, deadline adherence, category duration)
    task_completion_dimension: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )

    # Dimension D: Context Behavior (location patterns, transition frequency, switch overhead, category preferences)
    context_dimension: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )

    # Dimension E: Temporal Behavior (activity periods, day-of-week patterns, hourly completion density)
    temporal_dimension: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )

    # Behavioral Baselines Summary
    baselines: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )

    # Global Confidence Assessment
    global_confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    global_pattern_status: Mapped[str] = mapped_column(String(32), nullable=False, default="INSUFFICIENT_EVIDENCE")

    last_rebuilt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    user = relationship("User")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<UserBehavioralProfile user={self.user_id} status={self.global_pattern_status} v={self.profile_version}>"


class ProfileSnapshot(Base, UUIDPKMixin):
    """
    Immutable versioned snapshot of a user's behavioral digital twin.
    Guarantees historical auditability, reproducibility, and point-in-time evaluation.
    """

    __tablename__ = "profile_snapshots"
    __table_args__ = (
        Index("ix_profile_snapshots_user_time", "user_id", "snapshot_timestamp"),
        Index("ix_profile_snapshots_user_cutoff", "user_id", "source_data_cutoff"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    profile_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")
    snapshot_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    source_data_cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    feature_schema_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v4.2")
    observation_window_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    trigger_reason: Mapped[str] = mapped_column(String(64), nullable=False, default="INCREMENTAL_BATCH")

    # Complete Snapshot Payload
    snapshot_data: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship("User")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ProfileSnapshot id={self.id} user={self.user_id} cutoff={self.source_data_cutoff}>"


class ProfileAuditLog(Base, UUIDPKMixin):
    """
    Append-only compliance audit trail for sensitive profile operations
    (rebuild, reset, deletion, personalization toggles).
    """

    __tablename__ = "profile_audit_logs"
    __table_args__ = (
        Index("ix_profile_audit_logs_user_time", "user_id", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)  # REBUILD, RESET, PERSONALIZATION_TOGGLE, DELETE
    actor: Mapped[str] = mapped_column(String(64), nullable=False, default="USER")
    details: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship("User")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ProfileAuditLog user={self.user_id} action={self.action} time={self.created_at}>"

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import UUIDPKMixin, utcnow


class ContextSession(Base, UUIDPKMixin):
    """
    A continuous window of behavioral activity reconstructed from
    desktop telemetry, application transitions, idle intervals,
    detected and manual interruptions, and manual task activity.
    """

    __tablename__ = "context_sessions"
    __table_args__ = (
        Index("ix_context_sessions_user_start", "user_id", "started_at"),
        Index("ix_context_sessions_status", "status"),
        Index("ix_context_sessions_quality", "quality_tier"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True
    )
    context_tag: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    # Lifecycle & Timestamps
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="COMPLETED")

    # Aggregate counts (backward compatible)
    task_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    interruption_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Multi-Application Behavioral Context (Phase 3.6)
    primary_application: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    secondary_applications: Mapped[List[str]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list
    )
    application_breakdown: Mapped[Dict[str, float]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )
    transition_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    context_switch_frequency: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Granular Timing Metrics (seconds)
    focused_time_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    interruption_time_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    idle_time_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    resume_delay_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Task Association & Uncertainty
    task_association_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="UNKNOWN", index=True
    )  # EXPLICIT, MANUAL, SUGGESTED, UNKNOWN, USER_CORRECTED
    task_association_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    suggested_task_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )

    # Reconstruction Quality & Confidence Indicators
    reconstruction_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    quality_tier: Mapped[str] = mapped_column(String(16), nullable=False, default="HIGH")  # HIGH, MEDIUM, LOW
    quality_details: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )
    timeline: Mapped[List[Dict[str, Any]]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list
    )

    # Manual User Correction
    user_corrected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    user_correction_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_reconstructed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    task = relationship("Task", foreign_keys=[task_id])
    suggested_task = relationship("Task", foreign_keys=[suggested_task_id])
    user = relationship("User")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ContextSession id={self.id} user={self.user_id} "
            f"started_at={self.started_at} primary_app={self.primary_application}>"
        )

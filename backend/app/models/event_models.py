"""
SQLAlchemy ORM models for Standard Events, Dead-Letter Events,
and Proactive Intelligence Feed items (ContextIQ Phase 7.3).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin, utcnow


class StandardEventRecord(Base, TimestampMixin):
    """
    Durable, auditable storage for all standardized events ingested into ContextIQ.
    Enforces deduplication via unique index on user_id + idempotency_key.
    """
    __tablename__ = "standard_event_records"
    __table_args__ = (
        Index("ix_standard_events_user_time", "user_id", "event_timestamp"),
        Index("ix_standard_events_type_time", "event_type", "event_timestamp"),
        Index("ix_standard_events_user_idempotency", "user_id", "idempotency_key", unique=True),
    )

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ingestion_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="desktop_telemetry")

    payload: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    correlation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    rules_matched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    user = relationship("User")


class DeadLetterEventRecord(Base, UUIDPKMixin, TimestampMixin):
    """
    Dead-letter store for unparseable, unauthorized, corrupted, or repeatedly
    failing events with full diagnostic error reasons and retry tracking.
    """
    __tablename__ = "dead_letter_events"
    __table_args__ = (
        Index("ix_dead_letter_user_created", "user_id", "created_at"),
        Index("ix_dead_letter_status", "status"),
    )

    event_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    raw_payload: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    error_code: Mapped[str] = mapped_column(String(64), nullable=False)
    error_reason: Mapped[str] = mapped_column(Text, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")

    user = relationship("User")


class ProactiveFeedItem(Base, UUIDPKMixin, TimestampMixin):
    """
    Durable record for detected behavioral events and actionable intelligence insights.
    Exposes 'why it matters', contextual evidence, conformal confidence bounds,
    and user approval/action controls.
    """
    __tablename__ = "proactive_feed_items"
    __table_args__ = (
        Index("ix_proactive_feed_user_status", "user_id", "status"),
        Index("ix_proactive_feed_user_created", "user_id", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    detection_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    why_it_matters: Mapped[str] = mapped_column(Text, nullable=False)
    related_task_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    related_context: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    recommended_response: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )

    # Conformal uncertainty & confidence calibration
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.85)
    uncertainty_lower_bound: Mapped[float] = mapped_column(Float, nullable=False, default=0.75)
    uncertainty_upper_bound: Mapped[float] = mapped_column(Float, nullable=False, default=0.95)
    conformal_interval_text: Mapped[str] = mapped_column(String(128), nullable=False, default="90% coverage")

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE", index=True)
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    suggested_action: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )

    snoozed_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User")
    related_task = relationship("Task")

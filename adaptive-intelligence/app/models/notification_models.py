"""
Database models for ContextIQ Intelligent Notification and Cognitive Load Management (Phase 4.8).
Mirror adapter for adaptive-intelligence.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import UUIDPKMixin, utcnow


class UserNotification(Base, UUIDPKMixin):
    __tablename__ = "user_notifications"
    __table_args__ = (
        Index("ix_notifications_user_created", "user_id", "created_at"),
        Index("ix_notifications_user_status", "user_id", "is_read", "is_dismissed"),
        Index("ix_notifications_category", "category"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    intervention_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_interventions.id", ondelete="SET NULL"), nullable=True, index=True
    )

    category: Mapped[str] = mapped_column(String(64), nullable=False)
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default="MEDIUM")

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    delivery_channel: Mapped[str] = mapped_column(
        String(64), nullable=False, default="IN_APP_NOTIFICATION_CENTER"
    )
    delivery_strategy: Mapped[str] = mapped_column(
        String(64), nullable=False, default="IMMEDIATE"
    )

    is_delivered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    is_dismissed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dismissed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    is_deferred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deferred_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    metadata_payload: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class UserNotificationPreference(Base, UUIDPKMixin):
    __tablename__ = "user_notification_preferences"
    __table_args__ = (
        Index("ix_notification_preferences_user", "user_id", unique=True),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    enabled_categories: Mapped[Dict[str, bool]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=lambda: {
            "CRITICAL_DEADLINE_REMINDER": True,
            "HIGH_FORGETTING_RISK_ALERT": True,
            "RECOVERY_SUGGESTION": True,
            "FOCUS_SESSION_SUGGESTION": True,
            "CONTEXTUAL_REMINDER": True,
            "DAILY_BEHAVIORAL_SUMMARY": True,
        },
    )

    quiet_hours_start: Mapped[int] = mapped_column(Integer, nullable=False, default=22)
    quiet_hours_end: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    quiet_hours_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    max_notifications_per_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    max_notifications_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=12)

    summary_frequency: Mapped[str] = mapped_column(String(32), nullable=False, default="DAILY")

    is_paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    paused_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    desktop_agent_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sound_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class NotificationFatigueRecord(Base, UUIDPKMixin):
    __tablename__ = "notification_fatigue_records"
    __table_args__ = (
        Index("ix_notification_fatigue_user", "user_id", unique=True),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    total_presented_7d: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_accepted_7d: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_dismissed_7d: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_deferred_7d: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consecutive_dismissals: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    calculated_fatigue_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    last_interaction_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

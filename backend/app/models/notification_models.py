"""
Database models for ContextIQ Intelligent Notification and Cognitive Load Management (Phase 4.8).
Persists:
- UserNotification: Delivered, deferred, batched, or suppressed notification instances.
- UserNotificationPreference: User-configured category toggles, quiet periods, caps, and pause states.
- NotificationFatigueRecord: Algorithmic tracking of presentation frequency, dismissals, and cognitive load score.
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


class UserNotification(Base, UUIDPKMixin):
    """
    Individual notification created by ContextIQ with delivery status,
    priority, channel, and user interaction receipts.
    """

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
    # CRITICAL_DEADLINE_REMINDER, HIGH_FORGETTING_RISK_ALERT, RECOVERY_SUGGESTION,
    # FOCUS_SESSION_SUGGESTION, CONTEXTUAL_REMINDER, DAILY_BEHAVIORAL_SUMMARY

    priority: Mapped[str] = mapped_column(
        String(32), nullable=False, default="MEDIUM"
    )  # CRITICAL, HIGH, MEDIUM, LOW, BACKGROUND

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    delivery_channel: Mapped[str] = mapped_column(
        String(64), nullable=False, default="IN_APP_NOTIFICATION_CENTER"
    )  # WEB_IN_APP_TOAST, IN_APP_NOTIFICATION_CENTER, DESKTOP_AGENT_NOTIFICATION

    delivery_strategy: Mapped[str] = mapped_column(
        String(64), nullable=False, default="IMMEDIATE"
    )  # IMMEDIATE, DEFERRED, BATCHED_SUMMARY, SUPPRESSED_QUIET_PERIOD, EXPIRED, SUPPRESSED_DUPLICATE, NO_NOTIFICATION

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

    def __repr__(self) -> str:  # pragma: no cover
        return f"<UserNotification id={self.id} category={self.category} priority={self.priority} strategy={self.delivery_strategy}>"


class UserNotificationPreference(Base, UUIDPKMixin):
    """
    User-configured notification settings, quiet hours, rate limits,
    category toggles, and cognitive pause controls.
    """

    __tablename__ = "user_notification_preferences"
    __table_args__ = (
        Index("ix_notification_preferences_user", "user_id", unique=True),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # Category enable/disable toggles (map of category -> bool)
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

    quiet_hours_start: Mapped[int] = mapped_column(Integer, nullable=False, default=22)  # 22:00
    quiet_hours_end: Mapped[int] = mapped_column(Integer, nullable=False, default=8)    # 08:00
    quiet_hours_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    max_notifications_per_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    max_notifications_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=12)

    summary_frequency: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DAILY"
    )  # DAILY, TWICE_DAILY, OFF

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

    def __repr__(self) -> str:  # pragma: no cover
        return f"<UserNotificationPreference user={self.user_id} quiet={self.quiet_hours_enabled} paused={self.is_paused}>"


class NotificationFatigueRecord(Base, UUIDPKMixin):
    """
    Interaction pattern metrics and algorithmic fatigue tracking per user.
    Represents presentation frequency and dismissal behavior, NOT a clinical diagnosis.
    """

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

    # Algorithmic Fatigue Score in [0.0, 1.0]
    calculated_fatigue_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    last_interaction_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<NotificationFatigueRecord user={self.user_id} score={self.calculated_fatigue_score}>"

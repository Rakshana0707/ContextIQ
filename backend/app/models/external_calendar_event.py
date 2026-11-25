"""SQLAlchemy ORM model for synchronized external calendar events."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin, utcnow


class ExternalCalendarEvent(Base, UUIDPKMixin, TimestampMixin):
    """Normalized storage for synchronized events from Google Calendar and external providers."""

    __tablename__ = "external_calendar_events"
    __table_args__ = (
        sa.UniqueConstraint("integration_id", "external_event_id", name="uq_integration_external_event_id"),
        Index("ix_external_calendar_events_user_time", "user_id", "start_time", "end_time"),
        Index("ix_external_calendar_events_integration", "integration_id"),
        Index("ix_external_calendar_events_calendar", "calendar_id"),
        Index("ix_external_calendar_events_transparency", "user_id", "transparency"),
        Index("ix_external_calendar_events_recurring", "recurring_event_id"),
    )

    integration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calendar_integrations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    calendar_id: Mapped[str] = mapped_column(String(255), nullable=False, default="primary")
    external_event_id: Mapped[str] = mapped_column(String(255), nullable=False)

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    is_all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="CONFIRMED")  # CONFIRMED | TENTATIVE | CANCELLED
    transparency: Mapped[str] = mapped_column(String(32), nullable=False, default="OPAQUE")  # OPAQUE (busy) | TRANSPARENT (free)
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, default="default")  # default | public | private | confidential
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Recurrence metadata
    is_recurring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    recurring_event_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    recurrence_rule: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    original_start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Provenance & Ownership
    is_organizer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    organizer_email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)
    attendees_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    etag: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    html_link: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    external_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Two-Way Sync Attributes
    is_contextiq_managed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    linked_task_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    # Relationships
    integration = relationship("CalendarIntegration")
    user = relationship("User")
    linked_task = relationship("Task")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ExternalCalendarEvent {self.title!r} external_id={self.external_event_id} status={self.status}>"

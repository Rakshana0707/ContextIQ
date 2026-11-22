"""Persistent database model for raw behavioral telemetry events."""
import uuid
from datetime import datetime
from typing import Optional, Any

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import utcnow


class RawTelemetryEvent(Base):
    """
    Durable, queryable storage for ingested desktop behavioral telemetry events.
    Enforces idempotency via primary key on event_id.
    """

    __tablename__ = "raw_telemetry_events"
    __table_args__ = (
        Index("ix_raw_telemetry_user_time", "user_id", "event_timestamp"),
        Index("ix_raw_telemetry_user_device", "user_id", "device_id"),
        Index("ix_raw_telemetry_type_time", "event_type", "event_timestamp"),
    )

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ingestion_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="desktop_agent_windows")
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")

    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    correlation_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    application_identifier: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    previous_application_identifier: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    current_application_identifier: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    user = relationship("User")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RawTelemetryEvent id={self.event_id} type={self.event_type} user={self.user_id}>"

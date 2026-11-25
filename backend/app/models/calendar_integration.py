"""SQLAlchemy ORM models for unified calendar integrations and encrypted credentials."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin, utcnow


class CalendarIntegration(Base, UUIDPKMixin, TimestampMixin):
    """Represents a connected third-party calendar provider account for a user."""

    __tablename__ = "calendar_integrations"
    __table_args__ = (
        sa.UniqueConstraint("user_id", "provider", name="uq_user_calendar_provider"),
        Index("ix_calendar_integrations_user_id", "user_id"),
        Index("ix_calendar_integrations_provider", "provider"),
        Index("ix_calendar_integrations_status", "connection_status"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)  # 'google_calendar' | 'microsoft_outlook'
    provider_account_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    provider_email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)
    connection_status: Mapped[str] = mapped_column(String(32), nullable=False, default="CONNECTED")  # CONNECTED | EXPIRED | REVOKED | ERROR
    granted_scopes: Mapped[List[str]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    user = relationship("User")
    credentials: Mapped[Optional["CalendarCredential"]] = relationship(
        "CalendarCredential",
        back_populates="integration",
        uselist=False,
        cascade="all, delete-orphan",
    )
    sync_states: Mapped[List["CalendarSyncState"]] = relationship(
        "CalendarSyncState",
        back_populates="integration",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CalendarIntegration {self.provider} user={self.user_id} status={self.connection_status}>"


class CalendarCredential(Base, UUIDPKMixin, TimestampMixin):
    """Securely stores AES-256-GCM encrypted tokens. Never stores plaintext secrets."""

    __tablename__ = "calendar_credentials"
    __table_args__ = (
        Index("ix_calendar_credentials_integration_id", "integration_id", unique=True),
    )

    integration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calendar_integrations.id", ondelete="CASCADE"), nullable=False
    )
    # Binary storage for AES-256-GCM ciphertext + IV + Tag
    encrypted_access_token: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encrypted_refresh_token: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    expiration_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    credential_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    token_type: Mapped[str] = mapped_column(String(32), nullable=False, default="Bearer")

    # Relationship
    integration: Mapped["CalendarIntegration"] = relationship("CalendarIntegration", back_populates="credentials")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CalendarCredential integration={self.integration_id} v={self.credential_version}>"


class CalendarSyncState(Base, UUIDPKMixin, TimestampMixin):
    """Tracks incremental delta tokens and synchronization status per calendar."""

    __tablename__ = "calendar_sync_states"
    __table_args__ = (
        sa.UniqueConstraint("integration_id", "calendar_id", name="uq_integration_calendar_sync"),
        Index("ix_calendar_sync_states_integration", "integration_id"),
        Index("ix_calendar_sync_states_status", "sync_status"),
    )

    integration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calendar_integrations.id", ondelete="CASCADE"), nullable=False
    )
    calendar_id: Mapped[str] = mapped_column(String(255), nullable=False, default="primary")
    sync_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_sync_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_status: Mapped[str] = mapped_column(String(32), nullable=False, default="INITIALIZING")  # INITIALIZING | SYNCED | IN_PROGRESS | FAILED
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationship
    integration: Mapped["CalendarIntegration"] = relationship("CalendarIntegration", back_populates="sync_states")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CalendarSyncState integration={self.integration_id} cal={self.calendar_id} status={self.sync_status}>"

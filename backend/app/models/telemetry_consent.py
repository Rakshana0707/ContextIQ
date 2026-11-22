import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import ConsentStatus, TelemetryCategory
from app.models.mixins import UUIDPKMixin, utcnow


class TelemetryConsent(Base, UUIDPKMixin):
    """
    Auditable, versioned telemetry consent records.
    Every consent grant, modification, or revocation creates an immutable
    new record to maintain an auditable regulatory compliance trail.
    """

    __tablename__ = "telemetry_consents"
    __table_args__ = (
        Index("ix_telemetry_consents_user_status", "user_id", "consent_status"),
        Index("ix_telemetry_consents_user_granted", "user_id", "granted_timestamp"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    consent_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")
    enabled_categories: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    granted_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True
    )
    updated_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    revoked_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    device_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    consent_status: Mapped[ConsentStatus] = mapped_column(
        Enum(ConsentStatus, name="consent_status", native_enum=True),
        nullable=False,
        default=ConsentStatus.GRANTED,
        index=True,
    )
    ip_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship("User")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TelemetryConsent v={self.consent_version} status={self.consent_status} user={self.user_id}>"


class UserPrivacySettings(Base):
    """
    Configurable privacy parameters and retention limits per user.
    """

    __tablename__ = "user_privacy_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    is_paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    paused_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_event_retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    aggregated_metric_retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=365)
    allow_anonymized_research: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship("User")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<UserPrivacySettings user={self.user_id} paused={self.is_paused}>"


class UserAppExclusion(Base, UUIDPKMixin):
    """
    Application blacklist for privacy-preserving exclusion.
    When an excluded application is active, the agent must suppress
    its identity, duration, transitions, and contents.
    """

    __tablename__ = "user_app_exclusions"
    __table_args__ = (
        UniqueConstraint("user_id", "application_identifier", name="uq_user_app_exclusion"),
        Index("ix_user_app_exclusions_user_app", "user_id", "application_identifier"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    application_identifier: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship("User")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<UserAppExclusion app={self.application_identifier} user={self.user_id}>"

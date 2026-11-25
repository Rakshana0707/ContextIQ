"""SQLAlchemy ORM model for centralized device registry (ContextIQ Phase 5.7)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin, utcnow


class UserDevice(Base, UUIDPKMixin, TimestampMixin):
    """
    Centralized registry for authorized user hardware devices across
    Windows Desktop, Android, iOS, macOS, Linux, and Web clients.
    """

    __tablename__ = "user_devices"
    __table_args__ = (
        sa.UniqueConstraint("user_id", "device_id", name="uq_user_device_id"),
        Index("ix_user_devices_user_status", "user_id", "connection_status"),
        Index("ix_user_devices_device_id", "device_id"),
        Index("ix_user_devices_last_seen", "last_seen_timestamp"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[str] = mapped_column(String(128), nullable=False)

    device_type: Mapped[str] = mapped_column(String(32), nullable=False, default="DESKTOP")  # DESKTOP, MOBILE, TABLET, WEB
    platform: Mapped[str] = mapped_column(String(32), nullable=False, default="WINDOWS")      # WINDOWS, ANDROID, IOS, MACOS, LINUX, WEB
    device_name: Mapped[str] = mapped_column(String(255), nullable=False, default="Primary Device")
    application_version: Mapped[str] = mapped_column(String(64), nullable=False, default="1.0.0")

    registration_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    last_seen_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True
    )

    connection_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ONLINE"
    )  # ONLINE, OFFLINE, REVOKED
    synchronization_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="SYNCED"
    )  # SYNCED, PENDING, SYNCING, ERROR

    device_metadata: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<UserDevice device_id={self.device_id} type={self.device_type} "
            f"platform={self.platform} status={self.connection_status} user={self.user_id}>"
        )

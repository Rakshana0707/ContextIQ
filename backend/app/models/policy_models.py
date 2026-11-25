"""
SQLAlchemy ORM models for Permission, Consent, and Policy Enforcement (ContextIQ Phase 7.6).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin, utcnow


class UserPolicyConsent(Base, UUIDPKMixin, TimestampMixin):
    """
    Persistent, auditable user permission and consent grants/revocations across
    all 10 permission scopes.
    """
    __tablename__ = "user_policy_consents"
    __table_args__ = (
        Index("ix_policy_consents_user_scope", "user_id", "scope"),
        Index("ix_policy_consents_user_status", "user_id", "consent_status"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scope: Mapped[str] = mapped_column(String(64), nullable=False)
    consent_status: Mapped[str] = mapped_column(String(32), nullable=False, default="GRANTED")
    consent_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")
    granted_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    revoked_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="USER_EXPLICIT")
    device_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    integration_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    revocation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    policy_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB().with_variant(sa.JSON(), "sqlite"),
        nullable=True,
    )

    user = relationship("User")


class PolicyAuditTrail(Base, UUIDPKMixin):
    """
    Immutable audit trail recording every deterministic policy evaluation decision,
    scope verification, quiet-hours suppression, or denial.
    """
    __tablename__ = "policy_audit_trails"
    __table_args__ = (
        Index("ix_policy_audit_user_time", "user_id", "evaluated_at"),
        Index("ix_policy_audit_decision", "decision"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_identifier: Mapped[str] = mapped_column(String(128), nullable=False)
    scope_checked: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)  # ALLOWED, DENIED, BLOCKED_BY_POLICY
    risk_tier: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    context_snapshot: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB().with_variant(sa.JSON(), "sqlite"),
        nullable=True,
    )
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    user = relationship("User")

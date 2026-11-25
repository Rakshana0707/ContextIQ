"""
SQLAlchemy ORM models for Workflow Auditability, Rollback, and Emergency Stop (ContextIQ Phase 7.7).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin, utcnow


class WorkflowAuditEvent(Base, UUIDPKMixin):
    """
    Immutable, append-only workflow audit trail.
    Records every lifecycle event, action execution, policy check, and error
    without retaining credentials, OAuth tokens, or sensitive payloads.
    """
    __tablename__ = "workflow_audit_events"
    __table_args__ = (
        Index("ix_wf_audit_user_time", "user_id", "execution_timestamp"),
        Index("ix_wf_audit_plan_time", "plan_id", "execution_timestamp"),
        Index("ix_wf_audit_event_type", "event_type"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_execution_plans.id", ondelete="SET NULL"), nullable=True, index=True
    )
    workflow_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    action_identifier: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    step_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    execution_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    policy_decision: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    approval_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    result_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    error_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB().with_variant(sa.JSON(), "sqlite"),
        nullable=True,
    )
    correlation_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    sanitized_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB().with_variant(sa.JSON(), "sqlite"),
        nullable=True,
    )

    user = relationship("User")
    plan = relationship("WorkflowExecutionPlan")


class WorkflowApprovalRecord(Base, UUIDPKMixin):
    """
    Formal, immutable record of user or administrator approval/rejection of a workflow plan.
    """
    __tablename__ = "workflow_approval_records"
    __table_args__ = (
        Index("ix_wf_approval_plan", "plan_id"),
        Index("ix_wf_approval_user", "user_id"),
    )

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_execution_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    decision: Mapped[str] = mapped_column(String(32), nullable=False)  # APPROVED, REJECTED
    approver_type: Mapped[str] = mapped_column(String(32), nullable=False, default="USER_EXPLICIT")
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    plan_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    snapshot_checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    user = relationship("User")
    plan = relationship("WorkflowExecutionPlan")


class WorkflowRollbackRecord(Base, UUIDPKMixin):
    """
    Structured ledger tracking manual and automated compensations and reversions of workflow side effects.
    """
    __tablename__ = "workflow_rollback_records"
    __table_args__ = (
        Index("ix_wf_rollback_plan", "plan_id"),
        Index("ix_wf_rollback_user", "user_id"),
    )

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_execution_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    triggered_by: Mapped[str] = mapped_column(String(64), nullable=False, default="USER_MANUAL")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="IN_PROGRESS")
    total_steps_to_compensate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    compensated_steps_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_compensations: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSONB().with_variant(sa.JSON(), "sqlite"),
        nullable=True,
    )
    compensation_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB().with_variant(sa.JSON(), "sqlite"),
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user = relationship("User")
    plan = relationship("WorkflowExecutionPlan")


class EmergencyStopEvent(Base, UUIDPKMixin):
    """
    User-level or Administrator-level operational kill switch event that immediately
    fences execution, halts running workflows, and cancels pending scheduled actions.
    """
    __tablename__ = "emergency_stop_events"
    __table_args__ = (
        Index("ix_emergency_stop_user_active", "user_id", "is_active"),
        Index("ix_emergency_stop_scope_active", "scope", "is_active"),
    )

    scope: Mapped[str] = mapped_column(String(32), nullable=False, default="USER_LEVEL")  # USER_LEVEL, ADMIN_GLOBAL
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    triggered_by: Mapped[str] = mapped_column(String(64), nullable=False, default="USER")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    affected_plans_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    affected_rules_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    lifted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user = relationship("User")

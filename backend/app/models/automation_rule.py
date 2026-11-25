"""
SQLAlchemy ORM models for User-Defined Automation Rules, Triggers, Conditions,
Action Definitions, Executions, and Rule Versions (ContextIQ Phase 7.2).
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
from app.models.mixins import TimestampMixin, UUIDPKMixin, utcnow


class AutomationRule(Base, UUIDPKMixin, TimestampMixin):
    """
    User-defined automation rule that activates when behavioral, telemetry,
    or schedule conditions are satisfied.
    """

    __tablename__ = "automation_rules"
    __table_args__ = (
        Index("ix_automation_rules_user_enabled", "user_id", "is_enabled"),
        Index("ix_automation_rules_user_priority", "user_id", "priority"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    # Execution limits & safety controls
    cooldown_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    max_executions_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    risk_tier: Mapped[str] = mapped_column(String(32), nullable=False, default="Tier 2")

    # Time schedules & quiet hours
    active_schedule: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=lambda: {
            "days_of_week": [1, 2, 3, 4, 5],
            "start_time": "09:00",
            "end_time": "18:00",
            "timezone": "UTC",
        },
    )
    quiet_hours: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=lambda: {
            "enabled": True,
            "start_time": "22:00",
            "end_time": "07:00",
            "bypass_on_critical": False,
        },
    )

    # Expiration & state tracking
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_count_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_execution_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User")
    triggers = relationship(
        "AutomationTrigger",
        back_populates="rule",
        cascade="all, delete-orphan",
        order_by="AutomationTrigger.created_at",
    )
    conditions = relationship(
        "AutomationCondition",
        back_populates="rule",
        cascade="all, delete-orphan",
        order_by="AutomationCondition.condition_group, AutomationCondition.created_at",
    )
    actions = relationship(
        "AutomationActionDefinition",
        back_populates="rule",
        cascade="all, delete-orphan",
        order_by="AutomationActionDefinition.action_order",
    )
    executions = relationship(
        "AutomationExecution",
        back_populates="rule",
        cascade="all, delete-orphan",
        order_by="AutomationExecution.executed_at.desc()",
    )
    versions = relationship(
        "AutomationRuleVersion",
        back_populates="rule",
        cascade="all, delete-orphan",
        order_by="AutomationRuleVersion.version_number.desc()",
    )


class AutomationTrigger(Base, UUIDPKMixin, TimestampMixin):
    """
    Trigger specification linking an incoming event type to an automation rule.
    """

    __tablename__ = "automation_triggers"
    __table_args__ = (
        Index("ix_automation_triggers_rule_type", "rule_id", "trigger_type"),
        Index("ix_automation_triggers_type", "trigger_type"),
    )

    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("automation_rules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trigger_type: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )
    is_authorized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    authorization_source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    rule = relationship("AutomationRule", back_populates="triggers")


class AutomationCondition(Base, UUIDPKMixin, TimestampMixin):
    """
    Deterministic predicate evaluated against the current context or trigger payload.
    """

    __tablename__ = "automation_conditions"
    __table_args__ = (
        Index("ix_automation_conditions_rule_group", "rule_id", "condition_group"),
    )

    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("automation_rules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    condition_group: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    logical_operator: Mapped[str] = mapped_column(String(8), nullable=False, default="AND")  # AND | OR
    field_path: Mapped[str] = mapped_column(String(128), nullable=False)
    operator: Mapped[str] = mapped_column(String(32), nullable=False)  # EQUALS, GREATER_THAN, BETWEEN, etc.
    expected_value: Mapped[Any] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    min_evidence_observations: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    confidence_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    rule = relationship("AutomationRule", back_populates="conditions")


class AutomationActionDefinition(Base, UUIDPKMixin, TimestampMixin):
    """
    Executable action definition tied to an automation rule.
    """

    __tablename__ = "automation_action_definitions"
    __table_args__ = (
        Index("ix_automation_actions_rule_order", "rule_id", "action_order"),
    )

    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("automation_rules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    action_identifier: Mapped[str] = mapped_column(String(128), nullable=False)
    parameters_template: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )
    is_critical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_reversible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    action_preview_template: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )

    rule = relationship("AutomationRule", back_populates="actions")


class AutomationExecution(Base, UUIDPKMixin, TimestampMixin):
    """
    Record of rule evaluation and execution attempt, including match status and suppression.
    """

    __tablename__ = "automation_executions"
    __table_args__ = (
        Index("ix_automation_executions_user_time", "user_id", "executed_at"),
        Index("ix_automation_executions_rule_status", "rule_id", "status"),
        Index("ix_automation_executions_idempotency", "idempotency_key", unique=True),
    )

    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("automation_rules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trigger_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )  # EVALUATED_TRUE, EVALUATED_FALSE, SUPPRESSED_COOLDOWN, SUPPRESSED_QUIET_HOURS, EXECUTED, FAILED
    matched_conditions: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )
    suppression_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    workflow_instance_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    execution_duration_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    rule = relationship("AutomationRule", back_populates="executions")
    user = relationship("User")


class AutomationRuleVersion(Base, UUIDPKMixin, TimestampMixin):
    """
    Immutable versioned snapshot of an automation rule for historical audit and rollback.
    """

    __tablename__ = "automation_rule_versions"
    __table_args__ = (
        Index("ix_automation_rule_versions_rule_ver", "rule_id", "version_number", unique=True),
    )

    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("automation_rules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    rule_snapshot: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    change_summary: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    changed_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    rule = relationship("AutomationRule", back_populates="versions")

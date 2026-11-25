"""
SQLAlchemy ORM models for Multi-Step Workflow Planning, Dependencies,
Execution Plans, and Plan Versioning (ContextIQ Phase 7.4).
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


class WorkflowDefinition(Base, UUIDPKMixin, TimestampMixin):
    """
    Reusable workflow definition/template specifying a multi-step sequence
    of governed actions.
    """
    __tablename__ = "workflow_definitions"
    __table_args__ = (
        Index("ix_workflow_defs_user_active", "user_id", "is_active"),
        Index("ix_workflow_defs_category", "workflow_category"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    workflow_category: Mapped[str] = mapped_column(String(64), nullable=False, default="TASK_MANAGEMENT")
    trigger_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    steps: Mapped[List[WorkflowStep]] = relationship(
        "WorkflowStep",
        back_populates="workflow_definition",
        cascade="all, delete-orphan",
        order_by="WorkflowStep.order_index",
    )
    dependencies: Mapped[List[WorkflowDependency]] = relationship(
        "WorkflowDependency",
        back_populates="workflow_definition",
        cascade="all, delete-orphan",
    )
    execution_plans: Mapped[List[WorkflowExecutionPlan]] = relationship(
        "WorkflowExecutionPlan",
        back_populates="workflow_definition",
    )
    user = relationship("User")


class WorkflowStep(Base, UUIDPKMixin, TimestampMixin):
    """
    A single executable or conditional node within a WorkflowDefinition.
    References a registered action contract from ActionRegistry.
    """
    __tablename__ = "workflow_steps"
    __table_args__ = (
        Index("ix_workflow_steps_def_key", "workflow_definition_id", "step_key", unique=True),
        Index("ix_workflow_steps_action", "action_identifier"),
    )

    workflow_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    action_identifier: Mapped[str] = mapped_column(String(128), nullable=False)
    parameters: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_optional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    estimated_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    # Conditional branch expression
    condition_expression: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )

    # Rollback / compensation contract
    compensation_action_identifier: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    compensation_parameters: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )

    workflow_definition = relationship("WorkflowDefinition", back_populates="steps")


class WorkflowDependency(Base, UUIDPKMixin, TimestampMixin):
    """
    Directed edge in the workflow DAG linking step dependencies.
    """
    __tablename__ = "workflow_dependencies"
    __table_args__ = (
        Index("ix_workflow_dep_def", "workflow_definition_id"),
        Index("ix_workflow_dep_source_target", "workflow_definition_id", "source_step_key", "target_step_key", unique=True),
    )

    workflow_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_step_key: Mapped[str] = mapped_column(String(64), nullable=False)
    target_step_key: Mapped[str] = mapped_column(String(64), nullable=False)
    dependency_type: Mapped[str] = mapped_column(String(32), nullable=False, default="SUCCESS")
    condition_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )

    workflow_definition = relationship("WorkflowDefinition", back_populates="dependencies")


class WorkflowExecutionPlan(Base, UUIDPKMixin, TimestampMixin):
    """
    Concrete, instantiated workflow proposal with full lifecycle governance (13 states).
    Separates planning from execution and requires approval for consequential steps.
    """
    __tablename__ = "workflow_execution_plans"
    __table_args__ = (
        Index("ix_workflow_plans_user_status", "user_id", "status"),
        Index("ix_workflow_plans_idempotency", "user_id", "idempotency_key", unique=True),
        Index("ix_workflow_plans_created", "created_at"),
    )

    workflow_definition_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_definitions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="CREATED", index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)

    trigger_context: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    plan_steps: Mapped[List[Dict[str, Any]]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    plan_dependencies: Mapped[List[Dict[str, Any]]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    expected_benefits: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    potential_side_effects: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    utility_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.85)

    plan_comparison_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )
    reversibility_summary: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )

    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    workflow_definition = relationship("WorkflowDefinition", back_populates="execution_plans")
    versions: Mapped[List[WorkflowPlanVersion]] = relationship(
        "WorkflowPlanVersion",
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="WorkflowPlanVersion.version.desc()",
    )
    user = relationship("User")


class WorkflowPlanVersion(Base, UUIDPKMixin):
    """
    Immutable audit snapshot of each revision of a WorkflowExecutionPlan.
    """
    __tablename__ = "workflow_plan_versions"
    __table_args__ = (
        Index("ix_workflow_plan_versions_plan_v", "plan_id", "version", unique=True),
    )

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_execution_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    plan_snapshot: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
    )
    change_summary: Mapped[str] = mapped_column(String(255), nullable=False, default="Plan modified")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    plan = relationship("WorkflowExecutionPlan", back_populates="versions")

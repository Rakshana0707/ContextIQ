"""
Database models for ContextIQ Goal and Project Intelligence (Phase 8.4).
Extends task management into strategic multi-tier goals, projects, milestones, progress snapshots,
and behavioral alignment intelligence.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship

from app.db.session import Base
from app.models.knowledge_graph import Goal, Milestone, Project
from app.models.mixins import TimestampMixin, UUIDPKMixin, utcnow

ProjectMilestone = Milestone


class GoalHierarchyLevel(str, Enum):
    LONG_TERM = "LONG_TERM"
    INTERMEDIATE = "INTERMEDIATE"
    SHORT_TERM = "SHORT_TERM"


class ProjectHealthStatus(str, Enum):
    ON_TRACK = "ON_TRACK"
    AT_RISK = "AT_RISK"
    OFF_TRACK = "OFF_TRACK"
    STALLED = "STALLED"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"


class GoalRiskFactor(str, Enum):
    DEADLINE_PROXIMITY = "DEADLINE_PROXIMITY"
    STALLED_PROGRESS = "STALLED_PROGRESS"
    UNRESOLVED_BLOCKERS = "UNRESOLVED_BLOCKERS"
    REPEATED_POSTPONEMENTS = "REPEATED_POSTPONEMENTS"
    INSUFFICIENT_TIME = "INSUFFICIENT_TIME"
    DEPENDENCY_CONFLICT = "DEPENDENCY_CONFLICT"


class GoalTaskAssociation(Base, UUIDPKMixin, TimestampMixin):
    """
    Many-to-many bridge linking Tasks to Goals and Projects with importance weighting,
    effort weighting, and critical path designation.
    """
    __tablename__ = "goal_task_associations"
    __table_args__ = (
        Index("ix_goal_task_user_goal", "user_id", "goal_id"),
        Index("ix_goal_task_user_proj", "user_id", "project_id"),
        Index("ix_goal_task_task", "task_id"),
        {"extend_existing": True},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    goal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("goals.id", ondelete="CASCADE"), nullable=True, index=True
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    milestone_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("milestones.id", ondelete="SET NULL"), nullable=True, index=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )

    association_type: Mapped[str] = mapped_column(String(32), nullable=False, default="CONTRIBUTES_TO")
    importance_weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    effort_weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    is_critical_path: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)

    metadata_payload: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )

    user = orm_relationship("User")
    goal = orm_relationship("Goal")
    project = orm_relationship("Project")
    milestone = orm_relationship("Milestone")
    task = orm_relationship("Task")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<GoalTaskAssociation task={self.task_id} goal={self.goal_id} proj={self.project_id}>"


class ProjectGoalAssociation(Base, UUIDPKMixin, TimestampMixin):
    """
    Many-to-many relationship linking Projects to strategic Goals with contribution weight.
    """
    __tablename__ = "project_goal_associations"
    __table_args__ = (
        Index("ix_project_goal_user", "user_id", "project_id", "goal_id", unique=True),
        {"extend_existing": True},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    goal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("goals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contribution_weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    metadata_payload: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )

    user = orm_relationship("User")
    project = orm_relationship("Project")
    goal = orm_relationship("Goal")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ProjectGoalAssociation proj={self.project_id} -> goal={self.goal_id}>"


class GoalProgressSnapshot(Base, UUIDPKMixin, TimestampMixin):
    """
    Historical progress and risk evaluation for a strategic Goal.
    Evaluated from actual task efforts, milestones, and temporal closeness.
    """
    __tablename__ = "goal_progress_snapshots"
    __table_args__ = (
        Index("ix_goal_snapshots_user_time", "user_id", "goal_id", "snapshot_at"),
        {"extend_existing": True},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    goal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("goals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)

    progress_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    evidence_based_progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    completed_milestones_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_milestones_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_tasks_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tasks_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overdue_tasks_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blocked_tasks_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    health_status: Mapped[str] = mapped_column(String(32), nullable=False, default="ON_TRACK")
    risk_factors: Mapped[List[str]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    evidence_payload: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )

    user = orm_relationship("User")
    goal = orm_relationship("Goal")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<GoalProgressSnapshot goal={self.goal_id} progress={self.evidence_based_progress:.1f}% health={self.health_status}>"


class ProjectProgressSnapshot(Base, UUIDPKMixin, TimestampMixin):
    """
    Historical progress, health, and risk evaluation for a Project.
    """
    __tablename__ = "project_progress_snapshots"
    __table_args__ = (
        Index("ix_project_snapshots_user_time", "user_id", "project_id", "snapshot_at"),
        {"extend_existing": True},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)

    progress_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    evidence_based_progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    completed_milestones_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_milestones_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_tasks_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tasks_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overdue_tasks_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blocked_tasks_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_productive_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    health_status: Mapped[str] = mapped_column(String(32), nullable=False, default="ON_TRACK")
    risk_factors: Mapped[List[str]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    evidence_payload: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )

    user = orm_relationship("User")
    project = orm_relationship("Project")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ProjectProgressSnapshot proj={self.project_id} progress={self.evidence_based_progress:.1f}%>"


class GoalRecommendation(Base, UUIDPKMixin, TimestampMixin):
    """
    Intelligent recommendations for optimizing goal progress and resolving project blockers.
    Requires user review/approval before applying structural modifications.
    """
    __tablename__ = "goal_recommendations"
    __table_args__ = (
        Index("ix_goal_recs_user_approved", "user_id", "is_approved"),
        Index("ix_goal_recs_user_type", "user_id", "recommendation_type"),
        {"extend_existing": True},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    goal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("goals.id", ondelete="CASCADE"), nullable=True, index=True
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )

    recommendation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_action: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    priority_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_approved: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, default=None, index=True)
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user = orm_relationship("User")
    goal = orm_relationship("Goal")
    project = orm_relationship("Project")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<GoalRecommendation type={self.recommendation_type} title={self.title} approved={self.is_approved}>"

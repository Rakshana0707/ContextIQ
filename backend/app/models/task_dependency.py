"""
SQLAlchemy ORM models for Cross-Task Dependency Discovery and Intelligent Relationship Analysis (Phase 8.5).

Tracks both explicit and algorithmically inferred relationships between tasks:
- Shared projects & shared goals.
- Temporal patterns & sequence transitions.
- Resource & time-window conflicts.
- Potential execution blockers and bottlenecks.
- User confirmation workflow and epistemic separation.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin, utcnow


class TaskDependencyType(str, Enum):
    """Semantic taxonomy of dependencies and relationships between tasks."""
    EXPLICIT_DEPENDENCY = "EXPLICIT_DEPENDENCY"       # User-declared hard execution dependency
    INFERRED_DEPENDENCY = "INFERRED_DEPENDENCY"       # Algorithmically discovered general dependency
    SHARED_PROJECT = "SHARED_PROJECT"                 # Tasks linked via shared project context
    SHARED_GOAL = "SHARED_GOAL"                       # Tasks contributing to same strategic goal
    TEMPORAL_ASSOCIATION = "TEMPORAL_ASSOCIATION"     # Tasks executed closely in temporal succession
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"           # Competing for same focus slot / schedule window
    REPEATED_WORKFLOW = "REPEATED_WORKFLOW"           # Repeatedly executed sequence or recurring pattern
    POTENTIAL_BLOCKER = "POTENTIAL_BLOCKER"           # Upstream unfinished task that may block downstream task


class DependencyValidationStatus(str, Enum):
    """Epistemic state of an inferred or explicit task dependency."""
    PROPOSED = "PROPOSED"                             # Newly inferred, awaiting user review
    CONFIRMED = "CONFIRMED"                           # Confirmed by user as valid relationship
    REJECTED = "REJECTED"                             # Rejected by user as spurious / incorrect
    CONVERTED_EXPLICIT = "CONVERTED_EXPLICIT"         # Promoted to explicit hard execution constraint
    ARCHIVED = "ARCHIVED"                             # Deprecated or retired dependency


class DependencyDetectionMethod(str, Enum):
    """Analytical mechanism that discovered the task dependency."""
    RULE_BASED = "RULE_BASED"                         # Logical rule on project/goal/deadline metadata
    ASSOCIATION_MINING = "ASSOCIATION_MINING"         # Co-occurrence basket mining (support/confidence/lift)
    TEMPORAL_SEQUENCE = "TEMPORAL_SEQUENCE"           # Sequence analysis and Markovian transition ordering
    GRAPH_STRUCTURAL = "GRAPH_STRUCTURAL"             # Ancestor overlap in unified Knowledge Graph
    EXPLICIT_INPUT = "EXPLICIT_INPUT"                 # Manually defined by user


class TaskDependency(Base, UUIDPKMixin, TimestampMixin):
    """
    Directional relationship linking a source task to a target task.

    Semantic convention:
    - In BLOCKS / DEPENDENCY: `source_task` blocks or precedes `target_task`.
    - In SHARED_PROJECT / SHARED_GOAL / CONFLICT: symmetric or associative context.
    """
    __tablename__ = "task_dependencies"
    __table_args__ = (
        Index("ix_task_dep_user_source", "user_id", "source_task_id"),
        Index("ix_task_dep_user_target", "user_id", "target_task_id"),
        Index("ix_task_dep_user_type_status", "user_id", "dependency_type", "validation_status"),
        UniqueConstraint("user_id", "source_task_id", "target_task_id", "dependency_type", name="uq_task_dep_pair_type"),
        {"extend_existing": True},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )

    dependency_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default=TaskDependencyType.INFERRED_DEPENDENCY.value, index=True
    )
    is_inferred: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5
    )
    detection_method: Mapped[str] = mapped_column(
        String(64), nullable=False, default=DependencyDetectionMethod.RULE_BASED.value
    )
    validation_status: Mapped[str] = mapped_column(
        String(64), nullable=False, default=DependencyValidationStatus.PROPOSED.value, index=True
    )

    # Detailed empirical observations (frequencies, time intervals, event IDs, basket metrics)
    supporting_observations: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )

    first_observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    last_observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )

    # Relationships
    user = relationship("User")
    source_task = relationship("Task", foreign_keys=[source_task_id])
    target_task = relationship("Task", foreign_keys=[target_task_id])

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<TaskDependency {self.source_task_id} -[{self.dependency_type}]-> "
            f"{self.target_task_id} (conf={self.confidence:.2f}, status={self.validation_status})>"
        )

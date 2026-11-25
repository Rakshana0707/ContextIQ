"""
SQLAlchemy ORM models for the ContextIQ Unified Productivity Knowledge Graph (Phase 8.1).

Defines:
1. KnowledgeGraphNode: Universal node catalog and projection registry.
2. KnowledgeGraphEdge: Universal relationship adjacency model enforcing strict contracts,
   provenance tracking, confidence scoring, temporal validity, and epistemic boundaries.
3. Domain Entities expanding Phase 1-7 capabilities:
   - Project
   - Goal
   - Milestone
   - Habit
   - BehavioralPattern
   - Decision
   - Outcome
   - Resource
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship

from app.db.session import Base
from app.models.enums import GraphNodeType, GraphRelationshipType, KnowledgeEvidenceSource
from app.models.mixins import TimestampMixin, UUIDPKMixin, utcnow


class KnowledgeGraphNode(Base, UUIDPKMixin, TimestampMixin):
    """
    Universal registry index for nodes in the ContextIQ Knowledge Graph.
    Can reference an underlying entity from Phase 1-7 (e.g. Task, User, ContextSession)
    or one of the new Phase 8 domain entities (Project, Goal, Habit, etc.).
    """
    __tablename__ = "knowledge_graph_nodes"
    __table_args__ = (
        Index("ix_kg_nodes_user_type", "user_id", "node_type"),
        Index("ix_kg_nodes_entity", "entity_id", "entity_table"),
        sa.UniqueConstraint("user_id", "node_type", "entity_id", name="uq_kg_node_entity_identity"),
        {"extend_existing": True},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    node_type: Mapped[GraphNodeType] = mapped_column(
        Enum(GraphNodeType, name="graph_node_type", native_enum=False),
        nullable=False,
        index=True,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    entity_table: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    properties: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )

    # Relationships
    user = orm_relationship("User")
    outgoing_edges = orm_relationship(
        "KnowledgeGraphEdge",
        foreign_keys="KnowledgeGraphEdge.source_node_id",
        back_populates="source_node",
        cascade="all, delete-orphan",
    )
    incoming_edges = orm_relationship(
        "KnowledgeGraphEdge",
        foreign_keys="KnowledgeGraphEdge.target_node_id",
        back_populates="target_node",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<KnowledgeGraphNode id={self.id} type={self.node_type} name={self.name!r}>"


class KnowledgeGraphEdge(Base, UUIDPKMixin, TimestampMixin):
    """
    Universal relationship contract edge in the ContextIQ Knowledge Graph.

    Guarantees:
    1. Tenant isolation: Strictly owned by user_id.
    2. Epistemic boundary: is_inferred strictly separates verified facts from hypotheses.
    3. Provenance tracking: evidence_source and provenance_payload preserve origin trail.
    4. Temporal validity: valid_from and valid_until define lifespan.
    5. Calibrated confidence: confidence metric (0.0 to 1.0).
    """
    __tablename__ = "knowledge_graph_edges"
    __table_args__ = (
        Index("ix_kg_edges_user_source_rel", "user_id", "source_node_id", "relationship_type"),
        Index("ix_kg_edges_user_target_rel", "user_id", "target_node_id", "relationship_type"),
        Index("ix_kg_edges_source_target_type", "source_node_id", "target_node_id", "relationship_type", unique=True),
        Index("ix_kg_edges_inferred_conf", "user_id", "is_inferred", "confidence"),
        {"extend_existing": True},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_graph_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_graph_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    target_entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    relationship_type: Mapped[GraphRelationshipType] = mapped_column(
        Enum(GraphRelationshipType, name="graph_relationship_type", native_enum=False),
        nullable=False,
        index=True,
    )
    evidence_source: Mapped[KnowledgeEvidenceSource] = mapped_column(
        Enum(KnowledgeEvidenceSource, name="knowledge_evidence_source", native_enum=False),
        nullable=False,
        default=KnowledgeEvidenceSource.EXPLICIT_USER,
        index=True,
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    is_inferred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    # Temporal Validity Window
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    valid_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Immutable Provenance & Explanation Record
    provenance_payload: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )

    # Relationships
    user = orm_relationship("User")
    source_node = orm_relationship("KnowledgeGraphNode", foreign_keys=[source_node_id], back_populates="outgoing_edges")
    target_node = orm_relationship("KnowledgeGraphNode", foreign_keys=[target_node_id], back_populates="incoming_edges")
    evidences = orm_relationship(
        "KnowledgeEvidence",
        back_populates="edge",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<KnowledgeGraphEdge {self.relationship_type} "
            f"source={self.source_node_id} -> target={self.target_node_id} "
            f"conf={self.confidence:.2f} inferred={self.is_inferred}>"
        )


class KnowledgeEvidence(Base, UUIDPKMixin, TimestampMixin):
    """
    Evidence record grounding a KnowledgeRelationship in observed telemetry or inference data.
    """
    __tablename__ = "knowledge_evidence"
    __table_args__ = (
        Index("ix_kg_evidence_user_rel", "user_id", "relationship_id"),
        Index("ix_kg_evidence_type", "evidence_type"),
        {"extend_existing": True},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relationship_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_graph_edges.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False, default="EXPLICIT_USER")
    source_entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    source_entity_table: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    payload: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    # Relationships
    edge = orm_relationship("KnowledgeGraphEdge", back_populates="evidences")
    user = orm_relationship("User")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<KnowledgeEvidence id={self.id} type={self.evidence_type} rel={self.relationship_id}>"


class KnowledgeGraphVersion(Base, UUIDPKMixin, TimestampMixin):
    """
    Audit log and incremental version history of user's personal knowledge graph.
    """
    __tablename__ = "knowledge_graph_versions"
    __table_args__ = (
        Index("ix_kg_versions_user_ver", "user_id", "version_number", unique=True),
        Index("ix_kg_versions_created", "created_at"),
        {"extend_existing": True},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    change_type: Mapped[str] = mapped_column(String(64), nullable=False)
    affected_node_ids: Mapped[List[str]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list
    )
    affected_relationship_ids: Mapped[List[str]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list
    )
    change_summary: Mapped[str] = mapped_column(String(512), nullable=False)
    version_metadata: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )

    user = orm_relationship("User")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<KnowledgeGraphVersion user={self.user_id} v={self.version_number} type={self.change_type}>"


# Canonical Aliases
KnowledgeNode = KnowledgeGraphNode
KnowledgeRelationship = KnowledgeGraphEdge




# ===========================================================================
# Phase 8 Domain Entities (Expanding Phase 1-7 Core Models)
# ===========================================================================

class Project(Base, UUIDPKMixin, TimestampMixin):
    """
    High-level project container grouping related tasks, milestones, and resources.
    """
    __tablename__ = "projects"
    __table_args__ = (
        Index("ix_projects_user_status", "user_id", "status"),
        {"extend_existing": True},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default="MEDIUM")
    target_completion_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_payload: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )

    user = orm_relationship("User")
    milestones = orm_relationship("Milestone", back_populates="project", cascade="all, delete-orphan")


class Goal(Base, UUIDPKMixin, TimestampMixin):
    """
    Long-term strategic objective or aspiration of the user.
    """
    __tablename__ = "goals"
    __table_args__ = (
        Index("ix_goals_user_status", "user_id", "status"),
        Index("ix_goals_category", "category"),
        {"extend_existing": True},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="PRODUCTIVITY")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    target_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    progress_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    metadata_payload: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )

    user = orm_relationship("User")
    milestones = orm_relationship("Milestone", back_populates="goal", cascade="all, delete-orphan")


class Milestone(Base, UUIDPKMixin, TimestampMixin):
    """
    Checkpoint or key deliverable within a Project or Goal.
    """
    __tablename__ = "milestones"
    __table_args__ = (
        Index("ix_milestones_project", "project_id"),
        Index("ix_milestones_goal", "goal_id"),
        {"extend_existing": True},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    goal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("goals.id", ondelete="CASCADE"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_payload: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )

    user = orm_relationship("User")
    project = orm_relationship("Project", back_populates="milestones")
    goal = orm_relationship("Goal", back_populates="milestones")


class Habit(Base, UUIDPKMixin, TimestampMixin):
    """
    Recurring behavioral routine or intentional habit.
    """
    __tablename__ = "habits"
    __table_args__ = (
        Index("ix_habits_user_status", "user_id", "status"),
        {"extend_existing": True},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    cadence: Mapped[str] = mapped_column(String(32), nullable=False, default="DAILY")
    target_frequency_per_week: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    streak_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    preferred_time_window: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    metadata_payload: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )

    user = orm_relationship("User")


class BehavioralPattern(Base, UUIDPKMixin, TimestampMixin):
    """
    Empirically discovered behavioral regularity or friction pattern.
    """
    __tablename__ = "behavioral_patterns"
    __table_args__ = (
        Index("ix_patterns_user_cat", "user_id", "pattern_category"),
        {"extend_existing": True},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    pattern_category: Mapped[str] = mapped_column(String(64), nullable=False, default="FRICTION")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    frequency_per_week: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    friction_impact: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
    empirical_metrics: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    user = orm_relationship("User")


class Decision(Base, UUIDPKMixin, TimestampMixin):
    """
    Recorded choice made by the user or the autonomous system under governance.
    """
    __tablename__ = "decisions"
    __table_args__ = (
        Index("ix_decisions_user_type", "user_id", "decision_type"),
        Index("ix_decisions_time", "decided_at"),
        {"extend_existing": True},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    decision_type: Mapped[str] = mapped_column(String(64), nullable=False)
    chosen_option: Mapped[str] = mapped_column(String(255), nullable=False)
    alternative_options: Mapped[List[str]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    metadata_payload: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )

    user = orm_relationship("User")


class Outcome(Base, UUIDPKMixin, TimestampMixin):
    """
    Recorded empirical outcome resulting from tasks, decisions, or workflows.
    """
    __tablename__ = "outcomes"
    __table_args__ = (
        Index("ix_outcomes_user_type", "user_id", "outcome_type"),
        Index("ix_outcomes_time", "achieved_at"),
        {"extend_existing": True},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    outcome_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    metric_impact: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    achieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_payload: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )

    user = orm_relationship("User")


class Resource(Base, UUIDPKMixin, TimestampMixin):
    """
    External artifact, repository, document, or tool relevant to productivity.
    """
    __tablename__ = "resources"
    __table_args__ = (
        Index("ix_resources_user_type", "user_id", "resource_type"),
        {"extend_existing": True},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False, default="DOCUMENT")
    uri_or_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_payload: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )

    user = orm_relationship("User")

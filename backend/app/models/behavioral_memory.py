"""
Database models for ContextIQ Long-Term Behavioral Memory and Pattern Evolution (Phase 8.3).
Maintains structured, evolving behavioral memory over extended periods extending the core
Behavioral Profile digital twin rather than introducing a competing profile system.
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
    Enum as SQLEnum,
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
from app.models.mixins import TimestampMixin, UUIDPKMixin, utcnow


# ===========================================================================
# Behavioral Memory Enumerations
# ===========================================================================

class MemoryCategory(str, Enum):
    """
    Structured categories for long-term behavioral memory.
    """
    BEHAVIORAL_PREFERENCES = "BEHAVIORAL_PREFERENCES"
    PRODUCTIVITY_PATTERNS = "PRODUCTIVITY_PATTERNS"
    FOCUS_PATTERNS = "FOCUS_PATTERNS"
    RECOVERY_PATTERNS = "RECOVERY_PATTERNS"
    TASK_MANAGEMENT_PREFERENCES = "TASK_MANAGEMENT_PREFERENCES"
    CONTEXT_ASSOCIATIONS = "CONTEXT_ASSOCIATIONS"
    SUCCESSFUL_INTERVENTIONS = "SUCCESSFUL_INTERVENTIONS"
    UNSUCCESSFUL_INTERVENTIONS = "UNSUCCESSFUL_INTERVENTIONS"
    LONG_TERM_GOALS = "LONG_TERM_GOALS"
    EXPLICIT_USER_INSTRUCTIONS = "EXPLICIT_USER_INSTRUCTIONS"


class MemorySourceType(str, Enum):
    """
    Provenance origin distinguishing explicit user directives from observed data.
    """
    EXPLICIT_USER_INSTRUCTION = "EXPLICIT_USER_INSTRUCTION"
    FREQUENTLY_OBSERVED_BEHAVIOR = "FREQUENTLY_OBSERVED_BEHAVIOR"
    MODEL_INFERRED_PATTERN = "MODEL_INFERRED_PATTERN"


class MemoryValidityStatus(str, Enum):
    """
    Lifecycle status reflecting temporal evolution and validity.
    """
    ACTIVE = "ACTIVE"
    EMERGING = "EMERGING"
    STRENGTHENING = "STRENGTHENING"
    WEAKENING = "WEAKENING"
    CONTRADICTED = "CONTRADICTED"
    OUTDATED = "OUTDATED"
    ARCHIVED = "ARCHIVED"
    CORRECTED = "CORRECTED"


class PatternEvolutionType(str, Enum):
    """
    Types of pattern transitions over time.
    """
    EMERGING = "EMERGING"
    STRENGTHENING = "STRENGTHENING"
    WEAKENING = "WEAKENING"
    CONTRADICTORY = "CONTRADICTORY"
    OUTDATED = "OUTDATED"
    PREFERENCE_CHANGE = "PREFERENCE_CHANGE"


# ===========================================================================
# Database Models
# ===========================================================================

class BehavioralMemory(Base, UUIDPKMixin, TimestampMixin):
    """
    Long-term structured behavioral memory record.
    Grounds evolving behavioral patterns and explicit user instructions with provenance,
    observation counts, confidence adjustments, and historical evolution tracking.
    """
    __tablename__ = "behavioral_memories"
    __table_args__ = (
        Index("ix_behavioral_memories_user_cat", "user_id", "category"),
        Index("ix_behavioral_memories_user_status", "user_id", "validity_status"),
        Index("ix_behavioral_memories_source", "source_type"),
        Index("ix_behavioral_memories_last_obs", "user_id", "last_observed_at"),
        {"extend_existing": True},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[MemoryCategory] = mapped_column(
        SQLEnum(MemoryCategory, name="memory_category", native_enum=False),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[MemorySourceType] = mapped_column(
        SQLEnum(MemorySourceType, name="memory_source_type", native_enum=False),
        nullable=False,
        default=MemorySourceType.MODEL_INFERRED_PATTERN,
        index=True,
    )
    validity_status: Mapped[MemoryValidityStatus] = mapped_column(
        SQLEnum(MemoryValidityStatus, name="memory_validity_status", native_enum=False),
        nullable=False,
        default=MemoryValidityStatus.ACTIVE,
        index=True,
    )

    # Confidence & Evidence Metrics
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    reinforcement_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    contradiction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Observation Timestamps
    first_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_reinforced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_contradicted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Supporting Evidence & Provenance Details (e.g. metrics, event IDs, entity links)
    supporting_evidence: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )

    # Evolution Audit Log (chronological list of transitions, adjustments, and confidence shifts)
    evolution_history: Mapped[List[Dict[str, Any]]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )

    # Review & Expiration Policy
    expiration_policy: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=lambda: {
            "retention_days": 365,
            "review_after_days": 30,
            "auto_outdate_dormant_days": 60,
        },
    )

    # User Control & Corrections
    is_user_corrected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    user_correction_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)

    user = orm_relationship("User")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<BehavioralMemory id={self.id} cat={self.category} status={self.validity_status} conf={self.confidence:.2f}>"


class BehavioralTemporalSummary(Base, UUIDPKMixin, TimestampMixin):
    """
    Weekly or monthly aggregate summary capturing long-term pattern evolution,
    emerging behaviors, and behavioral trends.
    """
    __tablename__ = "behavioral_temporal_summaries"
    __table_args__ = (
        Index("ix_temporal_summaries_user_period", "user_id", "period_type", "period_start"),
        {"extend_existing": True},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period_type: Mapped[str] = mapped_column(String(16), nullable=False)  # "WEEKLY", "MONTHLY"
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    summary_metrics: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )

    emerging_pattern_ids: Mapped[List[str]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    strengthened_pattern_ids: Mapped[List[str]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    weakened_pattern_ids: Mapped[List[str]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    outdated_pattern_ids: Mapped[List[str]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )

    narrative_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user = orm_relationship("User")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<BehavioralTemporalSummary user={self.user_id} {self.period_type} {self.period_start}>"


class UserBehavioralMemoryPreference(Base, UUIDPKMixin, TimestampMixin):
    """
    User controls for behavioral memory retention, category toggles, and privacy preferences.
    """
    __tablename__ = "user_behavioral_memory_preferences"
    __table_args__ = (
        Index("ix_memory_prefs_user", "user_id", unique=True),
        {"extend_existing": True},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    disabled_categories: Mapped[List[str]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    retention_policy_days: Mapped[int] = mapped_column(Integer, nullable=False, default=365)
    auto_outdate_dormant_days: Mapped[int] = mapped_column(Integer, nullable=False, default=45)
    auto_synthesis_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    user = orm_relationship("User")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<UserBehavioralMemoryPreference user={self.user_id}>"

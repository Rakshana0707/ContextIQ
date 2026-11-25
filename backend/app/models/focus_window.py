"""
Database models for ContextIQ Personalized Focus Window Discovery (Phase 4.3).
Stores discovered recurrent personal productivity windows, category-specific cadences,
quality scores, and grounded scheduling insights.
"""
import uuid
from datetime import datetime, time
from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, Time
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import UUIDPKMixin, utcnow


class UserFocusWindow(Base, UUIDPKMixin):
    """
    Discovered recurrent personal focus interval.
    Captures measured periods of superior task completion, lower cognitive disruption,
    and sustained deep focus, optionally conditioned on specific task categories.
    """

    __tablename__ = "user_focus_windows"
    __table_args__ = (
        Index("ix_focus_windows_user_cat", "user_id", "task_category"),
        Index("ix_focus_windows_user_quality", "user_id", "quality_score"),
        Index("ix_focus_windows_user_active", "user_id", "is_active"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Category conditioning (e.g. "programming", "writing", "admin", or None for general)
    task_category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    # Temporal Specification (Local User Time)
    day_of_week: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 0=Monday .. 6=Sunday, None=Daily
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    # Multi-Objective Quality & Empirical Metrics
    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # 0.0 - 100.0
    focus_density: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # 0.0 - 1.0
    completion_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # 0.0 - 1.0
    interruption_density_hourly: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_resumption_lag_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Statistical Reliability
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # 0.0 - 1.0
    pattern_status: Mapped[str] = mapped_column(String(32), nullable=False, default="INSUFFICIENT_EVIDENCE")

    # Grounded Scheduling Insights (deterministic text rationales)
    grounded_insights: Mapped[List[str]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list
    )

    # Lifecycle & User Controls
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    user_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_validated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship("User")

    def __repr__(self) -> str:  # pragma: no cover
        cat_str = f"[{self.task_category}] " if self.task_category else ""
        q_val = f"{self.quality_score:.1f}" if getattr(self, "quality_score", None) is not None else "N/A"
        return f"<UserFocusWindow {cat_str}{self.start_time}-{self.end_time} Q={q_val}>"

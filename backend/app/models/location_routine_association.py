"""ORM model for mined and explicit location-routine task associations (Phase 5.8)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class LocationRoutineAssociation(Base, UUIDPKMixin, TimestampMixin):
    """
    Learned or declared relationship between a location and a task/category.
    Supports distinguishing explicit user configurations, statistically observed routines,
    and low-confidence suggestions.
    """

    __tablename__ = "location_routine_associations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True, index=True
    )
    task_category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False, default="ARRIVAL")  # ARRIVAL | DEPARTURE | PRESENCE
    association_source: Mapped[str] = mapped_column(String(32), nullable=False, default="EXPLICIT")  # EXPLICIT | STATISTICALLY_OBSERVED | LOW_CONFIDENCE
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    support: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship()
    location: Mapped["Location"] = relationship()
    task: Mapped[Optional["Task"]] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<LocationRoutineAssociation loc={self.location_id} task={self.task_id} source={self.association_source}>"

"""SQLAlchemy ORM model for proposed and approved intelligent task schedules."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class ScheduleProposal(Base, UUIDPKMixin, TimestampMixin):
    """Stores generated task schedule proposals, explainability traces, and approval lifecycles."""

    __tablename__ = "schedule_proposals"
    __table_args__ = (
        Index("ix_schedule_proposals_user_status", "user_id", "status"),
        Index("ix_schedule_proposals_horizon", "user_id", "horizon_start", "horizon_end"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DRAFT", index=True
    )  # DRAFT | APPROVED | REJECTED | COMMITTED

    horizon_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    horizon_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    scheduled_items: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    unscheduled_items: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    user = relationship("User")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ScheduleProposal {self.id} user={self.user_id} status={self.status} items={len(self.scheduled_items)}>"

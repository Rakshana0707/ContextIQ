"""
User Intervention ORM Model adapter (Phase 4.5).
"""
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import UUIDPKMixin, utcnow


class UserIntervention(Base, UUIDPKMixin):
    """
    Actionable behavioral recommendation generated for a user based on empirical
    working context, forgetting predictions, survival analysis, and focus windows.
    """

    __tablename__ = "user_interventions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    associated_task_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )

    intervention_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    intervention_category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_condition: Mapped[str] = mapped_column(String(255), nullable=False)

    supporting_evidence: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    expected_outcome: Mapped[str] = mapped_column(String(255), nullable=False)
    estimated_effort: Mapped[str] = mapped_column(String(16), nullable=False, default="LOW")

    relevance_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    lifecycle_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="GENERATED", index=True
    )

    creation_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )
    expiration_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    deferred_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    user_feedback_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

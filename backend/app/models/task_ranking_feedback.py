"""
Task Ranking Feedback ORM Model (Phase 4.4 Adaptive Prioritization).
Records explicit user interactions, overrides, and feedback on personalized task rankings.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import UUIDPKMixin, utcnow


class TaskRankingFeedback(Base, UUIDPKMixin):
    """
    Records explicit user actions on adaptive task recommendations (e.g., ACCEPTED,
    SNOOZED, PINNED, DISMISSED, REORDERED). Powers closed-loop evaluation and online calibration.
    """

    __tablename__ = "task_ranking_feedback"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True  # ACCEPTED, SNOOZED, PINNED, DISMISSED, REORDERED
    )
    rank_position: Mapped[int] = mapped_column(Integer, nullable=False)
    composite_score: Mapped[float] = mapped_column(Float, nullable=False)
    feedback_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TaskRankingFeedback task_id={self.task_id} action={self.action} rank={self.rank_position}>"

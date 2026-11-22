"""Database models for automated interruption detection and classification."""
import uuid
from datetime import datetime
from typing import Any, List, Optional

import sqlalchemy as sa
from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import (
    DetectedInterruptionType,
    InterruptionFeedbackClassification,
    InterruptionSeverity,
)
from app.models.mixins import UUIDPKMixin, utcnow


class DetectedInterruption(Base, UUIDPKMixin):
    """
    Automated interruption event reconstructed and classified from
    raw behavioral telemetry events.
    """

    __tablename__ = "detected_interruptions"
    __table_args__ = (
        Index("ix_detected_interruptions_user_time", "user_id", "start_timestamp"),
        Index("ix_detected_interruptions_type_time", "interruption_type", "start_timestamp"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_event_ids: Mapped[List[str]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list
    )
    interruption_type: Mapped[DetectedInterruptionType] = mapped_column(
        Enum(DetectedInterruptionType, name="detected_interruption_type", native_enum=False),
        nullable=False,
        index=True,
    )
    severity: Mapped[InterruptionSeverity] = mapped_column(
        Enum(InterruptionSeverity, name="interruption_severity", native_enum=False),
        nullable=False,
        default=InterruptionSeverity.LOW,
        index=True,
    )
    start_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    end_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    detection_method: Mapped[str] = mapped_column(
        String(64), nullable=False, default="RULE_BASED_HEURISTIC"
    )
    detection_version: Mapped[str] = mapped_column(
        String(32), nullable=False, default="1.0.0"
    )
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    primary_app: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    interrupting_app: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    resumption_lag_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    metadata_payload: Mapped[dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    user = relationship("User")
    feedback = relationship(
        "DetectedInterruptionFeedback",
        back_populates="interruption",
        cascade="all, delete-orphan",
        order_by="desc(DetectedInterruptionFeedback.created_at)",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<DetectedInterruption id={self.id} type={self.interruption_type} "
            f"user={self.user_id} start={self.start_timestamp}>"
        )


class DetectedInterruptionFeedback(Base, UUIDPKMixin):
    """
    Ground truth validation and manual feedback provided by the user
    for a detected interruption. Used for accuracy scoring and ML calibration.
    """

    __tablename__ = "detected_interruption_feedback"
    __table_args__ = (
        Index("ix_interruption_feedback_user", "user_id"),
        Index("ix_interruption_feedback_interruption", "interruption_id"),
    )

    interruption_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("detected_interruptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    feedback_classification: Mapped[InterruptionFeedbackClassification] = mapped_column(
        Enum(
            InterruptionFeedbackClassification,
            name="interruption_feedback_classification",
            native_enum=False,
        ),
        nullable=False,
        index=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    interruption = relationship("DetectedInterruption", back_populates="feedback")
    user = relationship("User")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<DetectedInterruptionFeedback id={self.id} "
            f"interruption_id={self.interruption_id} classification={self.feedback_classification}>"
        )

"""
SQLAlchemy ORM models for Natural-Language Productivity Analytics (Phase 8.9).

Stores user-saved analytics queries, execution history, and bookmarks.
Strictly scoped to user_id.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin, utcnow


class SavedAnalyticsQuery(Base, UUIDPKMixin, TimestampMixin):
    """
    User-saved natural-language analytics query with its compiled plan snapshot.
    Enables quick re-execution, dashboard bookmarking, and historical tracking.
    """
    __tablename__ = "saved_analytics_queries"
    __table_args__ = (
        Index("ix_saved_queries_user", "user_id"),
        Index("ix_saved_queries_user_fav", "user_id", "is_favorite"),
        Index("ix_saved_queries_created", "created_at"),
        {"extend_existing": True},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    query_text: Mapped[str] = mapped_column(String(1000), nullable=False)
    target_domain: Mapped[str] = mapped_column(String(64), nullable=False, default="GENERAL")
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    plan_snapshot: Mapped[Dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )

    user = relationship("User")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SavedAnalyticsQuery id={self.id} user={self.user_id} title={self.title!r}>"

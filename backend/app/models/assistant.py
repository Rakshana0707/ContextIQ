"""
SQLAlchemy ORM models for ContextIQ Knowledge-Grounded Conversational Assistant (Phase 8.8).

Maintains:
- Conversational sessions scoped strictly to individual users.
- Message history with evidence-grounded structured responses.
- Epistemic uncertainty, source attribution, and governed action proposals.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin, utcnow


class AssistantConversation(Base, UUIDPKMixin, TimestampMixin):
    """
    User-scoped conversational session with the ContextIQ assistant.
    Does not automatically turn casual conversation into permanent behavioral memory.
    """
    __tablename__ = "assistant_conversations"
    __table_args__ = (
        Index("ix_assistant_conv_user", "user_id"),
        Index("ix_assistant_conv_user_archived", "user_id", "is_archived"),
        Index("ix_assistant_conv_updated", "updated_at"),
        {"extend_existing": True},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="New Conversation")
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User")
    messages = relationship(
        "AssistantMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="AssistantMessage.created_at",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AssistantConversation id={self.id} user={self.user_id} title={self.title!r}>"


class AssistantMessage(Base, UUIDPKMixin):
    """
    Individual turn within a conversational session.
    Stores the role, textual prompt or response, and the structured evidence-grounded payload.
    """
    __tablename__ = "assistant_messages"
    __table_args__ = (
        Index("ix_assistant_msg_conv", "conversation_id"),
        Index("ix_assistant_msg_user", "user_id"),
        Index("ix_assistant_msg_created", "created_at"),
        {"extend_existing": True},
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assistant_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)  # "user", "assistant", "system"
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Structured grounded response payload for assistant turns
    structured_response: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=None,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    # Relationships
    conversation = relationship("AssistantConversation", back_populates="messages")
    user = relationship("User")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AssistantMessage id={self.id} role={self.role} conv={self.conversation_id}>"

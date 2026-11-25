"""ORM model for user location check-ins and edge geofence transitions (Phase 5.8)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class LocationCheckIn(Base, UUIDPKMixin, TimestampMixin):
    """
    Represents a discrete check-in or geofence boundary crossing.
    Adheres strictly to zero continuous GPS tracking: only stores the
    named place and transition type (MANUAL, GEOFENCE_ENTER, GEOFENCE_EXIT).
    """

    __tablename__ = "location_checkins"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    location_name: Mapped[str] = mapped_column(String(120), nullable=False)
    location_type: Mapped[str] = mapped_column(String(32), nullable=False, default="OTHER")
    check_in_type: Mapped[str] = mapped_column(String(32), nullable=False, default="MANUAL")  # MANUAL | GEOFENCE_ENTER | GEOFENCE_EXIT
    device_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict)

    user: Mapped["User"] = relationship()
    location: Mapped[Optional["Location"]] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<LocationCheckIn user={self.user_id} loc={self.location_name} type={self.check_in_type}>"

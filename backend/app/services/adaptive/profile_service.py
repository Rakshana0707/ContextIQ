"""
Backend service adapter for ContextIQ Personal Behavioral Digital Twin (Phase 4.2).
Connects FastAPI route dependencies to BehavioralProfileEngine.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.profiles.profile_engine import BehavioralProfileEngine
from app.schemas.profile_schemas import (
    DigitalTwinProfileRead,
    ProfileResetResponse,
    ProfileSnapshotRead,
)


class AdaptiveProfileService:
    """Service facade for behavioral profile operations."""

    @staticmethod
    def get_profile(db: Session, user_id: uuid.UUID) -> DigitalTwinProfileRead:
        return BehavioralProfileEngine.get_or_build_profile(db, user_id)

    @staticmethod
    def rebuild_profile(
        db: Session,
        user_id: uuid.UUID,
        as_of: Optional[datetime] = None,
        observation_window_days: int = 30,
    ) -> DigitalTwinProfileRead:
        return BehavioralProfileEngine.rebuild_profile(
            db=db,
            user_id=user_id,
            as_of=as_of,
            observation_window_days=observation_window_days,
            trigger_reason="API_REBUILD",
        )

    @staticmethod
    def reset_profile(db: Session, user_id: uuid.UUID) -> ProfileResetResponse:
        return BehavioralProfileEngine.reset_profile(db, user_id)

    @staticmethod
    def set_personalization(db: Session, user_id: uuid.UUID, enabled: bool) -> DigitalTwinProfileRead:
        return BehavioralProfileEngine.set_personalization(db, user_id, enabled)

    @staticmethod
    def get_history(db: Session, user_id: uuid.UUID, limit: int = 20) -> List[ProfileSnapshotRead]:
        return BehavioralProfileEngine.get_history(db, user_id, limit=limit)

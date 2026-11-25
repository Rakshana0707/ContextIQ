"""
Service facade for ContextIQ Focus Window Discovery & Temporal Behavior Analysis (Phase 4.3).
Connects database session and user timezone to FocusWindowDiscoveryEngine.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.context_session import ContextSession
from app.models.detected_interruption import DetectedInterruption
from app.models.task import Task
from app.models.user import User
from app.profiles.focus_window_engine import FocusWindowDiscoveryEngine
from app.profiles.focus_window_repository import FocusWindowRepository
from app.schemas.focus_window import (
    CategoryFocusWindowRead,
    FocusWindowItemRead,
    FocusWindowMetricsResponse,
)


class FocusWindowService:
    """Service layer managing personal focus window discovery and queries."""

    @classmethod
    def get_or_discover_windows(
        cls,
        db: Session,
        user_id: uuid.UUID,
        category: Optional[str] = None,
        min_confidence: float = 0.0,
        observation_window_days: int = 30,
        force_refresh: bool = False,
        as_of: Optional[datetime] = None,
    ) -> List[FocusWindowItemRead]:
        """Returns existing active focus windows or performs dynamic discovery."""
        if not force_refresh:
            existing = FocusWindowRepository.list_focus_windows(
                db=db, user_id=user_id, category=category, min_confidence=min_confidence
            )
            if existing:
                return existing

        # Fetch underlying data
        user = db.scalar(select(User).where(User.id == user_id))
        user_tz = user.timezone if user and user.timezone else "UTC"

        sessions = list(db.scalars(select(ContextSession).where(ContextSession.user_id == user_id)).all())
        tasks = list(db.scalars(select(Task).where(Task.user_id == user_id)).all())
        interruptions = list(db.scalars(select(DetectedInterruption).where(DetectedInterruption.user_id == user_id)).all())

        discovered = FocusWindowDiscoveryEngine.discover_focus_windows(
            user_id=user_id,
            sessions=sessions,
            tasks=tasks,
            interruptions=interruptions,
            user_timezone=user_tz,
            category_filter=category,
            as_of=as_of,
            observation_window_days=observation_window_days,
        )

        # Persist and return
        FocusWindowRepository.save_focus_windows(
            db=db, user_id=user_id, windows=discovered, category_filter=category
        )
        db.commit()

        if min_confidence > 0.0:
            discovered = [w for w in discovered if w.confidence_score >= min_confidence]
        return discovered

    @classmethod
    def get_category_focus_windows(
        cls,
        db: Session,
        user_id: uuid.UUID,
        category: str,
        observation_window_days: int = 30,
        as_of: Optional[datetime] = None,
    ) -> CategoryFocusWindowRead:
        """Returns focus windows conditioned on a specific task category with lift metrics."""
        user = db.scalar(select(User).where(User.id == user_id))
        user_tz = user.timezone if user and user.timezone else "UTC"

        sessions = list(db.scalars(select(ContextSession).where(ContextSession.user_id == user_id)).all())
        tasks = list(db.scalars(select(Task).where(Task.user_id == user_id)).all())
        interruptions = list(db.scalars(select(DetectedInterruption).where(DetectedInterruption.user_id == user_id)).all())

        res = FocusWindowDiscoveryEngine.discover_category_focus_windows(
            user_id=user_id,
            category=category,
            sessions=sessions,
            tasks=tasks,
            interruptions=interruptions,
            user_timezone=user_tz,
            as_of=as_of,
            observation_window_days=observation_window_days,
        )

        if res.focus_windows:
            FocusWindowRepository.save_focus_windows(
                db=db, user_id=user_id, windows=res.focus_windows, category_filter=category
            )
            db.commit()

        return res

    @classmethod
    def get_hourly_metrics(
        cls,
        db: Session,
        user_id: uuid.UUID,
        observation_window_days: int = 30,
        as_of: Optional[datetime] = None,
    ) -> FocusWindowMetricsResponse:
        """Returns circadian 24-hour metrics matrix for dashboard analysis."""
        user = db.scalar(select(User).where(User.id == user_id))
        user_tz = user.timezone if user and user.timezone else "UTC"

        sessions = list(db.scalars(select(ContextSession).where(ContextSession.user_id == user_id)).all())
        tasks = list(db.scalars(select(Task).where(Task.user_id == user_id)).all())
        interruptions = list(db.scalars(select(DetectedInterruption).where(DetectedInterruption.user_id == user_id)).all())

        return FocusWindowDiscoveryEngine.get_metrics_summary(
            user_id=user_id,
            sessions=sessions,
            tasks=tasks,
            interruptions=interruptions,
            user_timezone=user_tz,
            as_of=as_of,
            observation_window_days=observation_window_days,
        )

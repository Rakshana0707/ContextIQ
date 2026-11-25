"""
Repository for persisting discovered focus windows and updating the behavioral profile.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.models.focus_window import UserFocusWindow
from app.models.behavioral_profile import UserBehavioralProfile
from app.schemas.focus_window_schemas import FocusWindowItemRead


class FocusWindowRepository:
    """Manages persistence for user focus windows and profile temporal updates."""

    @classmethod
    def save_focus_windows(
        cls,
        db: Session,
        user_id: uuid.UUID,
        windows: List[FocusWindowItemRead],
        category_filter: Optional[str] = None,
    ) -> List[UserFocusWindow]:
        """Replaces active focus windows for the given user and category with newly discovered ones."""
        # 1. Delete previous unconfirmed active windows for this user and category
        del_stmt = delete(UserFocusWindow).where(
            UserFocusWindow.user_id == user_id,
            UserFocusWindow.task_category == category_filter,
            UserFocusWindow.user_confirmed == False,  # Preserve user-confirmed customizations
        )
        db.execute(del_stmt)

        # 2. Insert new records
        orm_records: List[UserFocusWindow] = []
        now = datetime.now(timezone.utc)
        for w in windows:
            orm = UserFocusWindow(
                id=w.id,
                user_id=user_id,
                task_category=w.task_category,
                day_of_week=w.day_of_week,
                start_time=w.start_time,
                end_time=w.end_time,
                duration_minutes=w.duration_minutes,
                quality_score=w.quality_score,
                focus_density=w.focus_density,
                completion_rate=w.completion_rate,
                interruption_density_hourly=w.interruption_density_hourly,
                avg_resumption_lag_seconds=w.avg_resumption_lag_seconds,
                observation_count=w.observation_count,
                confidence_score=w.confidence_score,
                pattern_status=w.pattern_status,
                grounded_insights=w.grounded_insights,
                is_active=w.is_active,
                user_confirmed=w.user_confirmed,
                discovered_at=now,
                last_validated_at=now,
            )
            db.add(orm)
            orm_records.append(orm)

        # 3. Synchronize with UserBehavioralProfile if general windows
        if category_filter is None and windows:
            profile_stmt = select(UserBehavioralProfile).where(UserBehavioralProfile.user_id == user_id)
            profile = db.scalar(profile_stmt)
            if profile:
                top_window = windows[0]
                temporal_dim = dict(profile.temporal_dimension)
                active_hrs = temporal_dim.get("active_daily_hours", {})
                if isinstance(active_hrs, dict) and "observed_value" in active_hrs:
                    active_hrs["observed_value"]["peak_hour"] = top_window.start_time.hour
                temporal_dim["active_daily_hours"] = active_hrs
                profile.temporal_dimension = temporal_dim
                db.add(profile)

        db.flush()
        return orm_records

    @classmethod
    def list_focus_windows(
        cls,
        db: Session,
        user_id: uuid.UUID,
        category: Optional[str] = None,
        min_confidence: float = 0.0,
    ) -> List[FocusWindowItemRead]:
        """Fetches active focus windows for user matching criteria."""
        stmt = (
            select(UserFocusWindow)
            .where(
                UserFocusWindow.user_id == user_id,
                UserFocusWindow.is_active == True,
                UserFocusWindow.confidence_score >= min_confidence,
            )
            .order_by(desc(UserFocusWindow.quality_score))
        )
        if category is not None:
            stmt = stmt.where(UserFocusWindow.task_category == category)

        records = db.scalars(stmt).all()
        return [FocusWindowItemRead.model_validate(r) for r in records]

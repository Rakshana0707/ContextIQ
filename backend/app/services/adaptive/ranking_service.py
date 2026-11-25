"""
Service layer for Adaptive Task Prioritization & Personalized Scheduling (Phase 4.4).
Orchestrates task queries, feature extraction, focus window integration, and feedback persistence.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import TaskStatus
from app.models.task import Task
from app.models.task_ranking_feedback import TaskRankingFeedback
from app.models.user import User
from app.prioritization.prioritization_engine import PrioritizationEngine
from app.prioritization.prioritization_features import PrioritizationFeatureExtractor
from app.schemas.task_ranking import (
    RankingPreset,
    RankingWeightConfig,
    TaskRankingFeedbackCreate,
    TaskRankingFeedbackRead,
    TaskRankingPreviewRequest,
    TaskRankingResponse,
)
from app.services.adaptive.focus_window_service import FocusWindowService
from app.services.adaptive.profile_service import AdaptiveProfileService


def _normalize_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class AdaptiveRankingService:
    """Service facade connecting database entities to PrioritizationEngine."""

    @classmethod
    def get_task_ranking(
        cls,
        db: Session,
        user_id: uuid.UUID,
        as_of: Optional[datetime] = None,
        current_context_tag: Optional[str] = None,
        current_location_id: Optional[uuid.UUID] = None,
        preset: Optional[RankingPreset | str] = None,
        weights: Optional[RankingWeightConfig] = None,
        include_blocked: bool = True,
        active_hour_override: Optional[int] = None,
        limit: int = 50,
    ) -> TaskRankingResponse:
        """Computes personalized task ranking for all pending tasks of the user."""
        ref_time = _normalize_utc(as_of) or _normalize_utc(datetime.now(timezone.utc))

        # 1. Fetch user & local timezone
        user = db.scalar(select(User).where(User.id == user_id))
        user_tz = user.timezone if user and user.timezone else "UTC"

        # Determine circadian hour
        from zoneinfo import ZoneInfo
        try:
            loc_time = ref_time.astimezone(ZoneInfo(user_tz))
            current_hour = active_hour_override if active_hour_override is not None else loc_time.hour
        except Exception:
            current_hour = active_hour_override if active_hour_override is not None else ref_time.hour

        # 2. Fetch pending tasks
        stmt = (
            select(Task)
            .where(
                Task.user_id == user_id,
                Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.PAUSED]),
            )
            .order_by(Task.created_at.asc())
        )
        tasks = list(db.scalars(stmt).all())
        pending_ids = {t.id for t in tasks if t.status != TaskStatus.COMPLETED}

        # 3. Fetch behavioral profile & active focus windows
        profile_data = None
        try:
            profile_read = AdaptiveProfileService.get_profile(db=db, user_id=user_id)
            profile_data = profile_read.model_dump()
        except Exception:
            pass

        focus_windows = FocusWindowService.get_or_discover_windows(
            db=db, user_id=user_id, as_of=ref_time
        )

        # 4. Extract features for all tasks
        tasks_features = [
            PrioritizationFeatureExtractor.extract_task_features(
                db=db,
                task=t,
                user_id=user_id,
                as_of=ref_time,
                profile_data=profile_data,
            )
            for t in tasks
        ]

        # 5. Execute ranking engine
        chosen_preset = preset or RankingPreset.BALANCED
        ranked_items = PrioritizationEngine.rank_tasks(
            tasks_features=tasks_features,
            focus_windows=focus_windows,
            current_hour=current_hour,
            current_context_tag=current_context_tag,
            weights=weights,
            preset=chosen_preset,
            include_blocked=include_blocked,
            pending_task_ids=pending_ids,
            profile_data=profile_data,
        )

        if limit and limit > 0:
            ranked_items = ranked_items[:limit]

        # 6. Generate summary insights
        insights = []
        if ranked_items:
            top_task = ranked_items[0]
            insights.append(
                f"Top recommendation: '{top_task.title}' (Composite Score {top_task.composite_score:.1f}/100) — {top_task.grounded_explanation}"
            )
        blocked_count = sum(1 for it in ranked_items if it.is_blocked)
        if blocked_count > 0:
            insights.append(f"{blocked_count} task(s) currently deprioritized due to pending parent dependencies.")

        return TaskRankingResponse(
            user_id=user_id,
            generated_at=datetime.now(timezone.utc),
            reference_time=ref_time,
            preset_applied=str(chosen_preset.value if hasattr(chosen_preset, "value") else chosen_preset),
            current_context={
                "current_hour": current_hour,
                "current_context_tag": current_context_tag,
                "timezone": user_tz,
                "active_focus_windows_count": len(focus_windows),
            },
            items=ranked_items,
            summary_insights=insights,
        )

    @classmethod
    def preview_task_ranking(
        cls,
        db: Session,
        user_id: uuid.UUID,
        request: TaskRankingPreviewRequest,
    ) -> TaskRankingResponse:
        """Simulates hypothetical ranking without changing persistence."""
        return cls.get_task_ranking(
            db=db,
            user_id=user_id,
            as_of=request.as_of,
            current_context_tag=request.current_context_tag,
            current_location_id=request.current_location_id,
            preset=request.preset,
            weights=request.custom_weights,
            include_blocked=request.include_blocked,
            active_hour_override=request.active_hour,
        )

    @classmethod
    def record_feedback(
        cls,
        db: Session,
        user_id: uuid.UUID,
        feedback_in: TaskRankingFeedbackCreate,
    ) -> TaskRankingFeedbackRead:
        """Records explicit user override or action on ranked tasks."""
        feedback_record = TaskRankingFeedback(
            id=uuid.uuid4(),
            user_id=user_id,
            task_id=feedback_in.task_id,
            action=feedback_in.action.upper(),
            rank_position=feedback_in.rank_position,
            composite_score=feedback_in.composite_score,
            feedback_note=feedback_in.feedback_note,
            created_at=datetime.now(timezone.utc),
        )
        db.add(feedback_record)
        db.commit()
        db.refresh(feedback_record)

        return TaskRankingFeedbackRead.model_validate(feedback_record)

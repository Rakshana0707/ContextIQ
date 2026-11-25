"""
Service layer for ContextIQ Personalized Intervention Recommendation Engine (Phase 4.5).
Orchestrates context gathering, rule evaluation via InterventionEngine,
lifecycle transitions (GENERATED -> PRESENTED -> ACCEPTED/DISMISSED/DEFERRED/EXPIRED),
and strict empirical evidence grounding.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.interventions.intervention_engine import InterventionEngine
from app.models.detected_interruption import DetectedInterruption
from app.models.enums import TaskStatus
from app.models.focus_window import UserFocusWindow
from app.models.task import Task
from app.models.task_association import TaskAssociation
from app.models.user import User
from app.models.user_intervention import UserIntervention
from app.schemas.intervention_schemas import (
    InterventionActionRequest,
    InterventionGenerateRequest,
    InterventionLifecycleStatus,
)
from app.services.adaptive.profile_service import AdaptiveProfileService


def _normalize_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class InterventionService:
    """Facade for managing personalized intervention generation and lifecycle transitions."""

    @classmethod
    def get_interventions(
        cls,
        db: Session,
        user_id: uuid.UUID,
        status_filter: Optional[str] = None,
        category: Optional[str] = None,
        include_deferred: bool = False,
        limit: int = 20,
    ) -> List[UserIntervention]:
        """
        Retrieves user interventions, automatically expiring stale recommendations
        and promoting GENERATED to PRESENTED upon reading.
        """
        now = datetime.now(timezone.utc)

        # 1. Update expired interventions
        stale_stmt = select(UserIntervention).where(
            UserIntervention.user_id == user_id,
            UserIntervention.expiration_timestamp <= now,
            UserIntervention.lifecycle_status.in_(
                [
                    InterventionLifecycleStatus.GENERATED.value,
                    InterventionLifecycleStatus.PRESENTED.value,
                    InterventionLifecycleStatus.DEFERRED.value,
                ]
            ),
        )
        stale_interventions = list(db.scalars(stale_stmt).all())
        for item in stale_interventions:
            item.lifecycle_status = InterventionLifecycleStatus.EXPIRED.value
        if stale_interventions:
            db.commit()

        # 2. Build fetch query
        query = select(UserIntervention).where(UserIntervention.user_id == user_id)

        if status_filter:
            query = query.where(UserIntervention.lifecycle_status == status_filter)
        else:
            # Default active feed: GENERATED, PRESENTED, or DEFERRED where deferral time has passed
            if include_deferred:
                query = query.where(
                    UserIntervention.lifecycle_status.in_(
                        [
                            InterventionLifecycleStatus.GENERATED.value,
                            InterventionLifecycleStatus.PRESENTED.value,
                            InterventionLifecycleStatus.DEFERRED.value,
                        ]
                    )
                )
            else:
                query = query.where(
                    or_(
                        UserIntervention.lifecycle_status.in_(
                            [
                                InterventionLifecycleStatus.GENERATED.value,
                                InterventionLifecycleStatus.PRESENTED.value,
                            ]
                        ),
                        (
                            (UserIntervention.lifecycle_status == InterventionLifecycleStatus.DEFERRED.value)
                            & (UserIntervention.deferred_until <= now)
                        ),
                    )
                )

        if category:
            query = query.where(UserIntervention.intervention_category == category.upper())

        query = query.order_by(
            UserIntervention.relevance_score.desc(),
            UserIntervention.creation_timestamp.desc(),
        ).limit(limit)

        results = list(db.scalars(query).all())

        # 3. Transition unread GENERATED to PRESENTED
        needs_commit = False
        for item in results:
            if item.lifecycle_status == InterventionLifecycleStatus.GENERATED.value:
                item.lifecycle_status = InterventionLifecycleStatus.PRESENTED.value
                needs_commit = True

        if needs_commit:
            db.commit()

        return results

    @classmethod
    def generate_interventions(
        cls,
        db: Session,
        user_id: uuid.UUID,
        request: Optional[InterventionGenerateRequest] = None,
    ) -> List[UserIntervention]:
        """
        Orchestrates context gathering and runs InterventionEngine to generate
        verifiable, deduplicated recommendations.
        """
        req = request or InterventionGenerateRequest()
        ref_time = _normalize_utc(req.as_of) or datetime.now(timezone.utc)

        # 1. Fetch user timezone
        user = db.get(User, user_id)
        current_hour = req.active_hour
        if current_hour is None:
            current_hour = ref_time.hour

        # 2. Query user tasks (pending/in-progress)
        task_stmt = select(Task).where(
            Task.user_id == user_id,
            Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
        )
        tasks = list(db.scalars(task_stmt).all())

        # 3. Query focus windows
        fw_stmt = select(UserFocusWindow).where(
            UserFocusWindow.user_id == user_id,
            UserFocusWindow.is_active == True,
        )
        focus_windows = list(db.scalars(fw_stmt).all())

        # 4. Query behavioral profile
        profile_dict = None
        try:
            profile_read = AdaptiveProfileService.get_profile(db=db, user_id=user_id)
            if profile_read:
                profile_dict = profile_read.model_dump()
        except Exception:
            profile_dict = None

        # 5. Query recent interruptions (last 48 hours)
        two_days_ago = ref_time - timedelta(days=2)
        int_stmt = select(DetectedInterruption).where(
            DetectedInterruption.user_id == user_id,
            DetectedInterruption.start_timestamp >= two_days_ago,
        )
        interruptions = list(db.scalars(int_stmt).all())

        # 6. Query task associations
        assoc_stmt = select(TaskAssociation).where(TaskAssociation.user_id == user_id)
        associations = list(db.scalars(assoc_stmt).all())

        # 7. Query historical feedback stats for personalization
        fb_stmt = select(UserIntervention.intervention_type, UserIntervention.lifecycle_status).where(
            UserIntervention.user_id == user_id,
            UserIntervention.lifecycle_status.in_(
                [
                    InterventionLifecycleStatus.ACCEPTED.value,
                    InterventionLifecycleStatus.DISMISSED.value,
                ]
            ),
        )
        fb_rows = db.execute(fb_stmt).all()
        fb_stats: Dict[str, Dict[str, int]] = {}
        for itype, lstatus in fb_rows:
            if itype not in fb_stats:
                fb_stats[itype] = {"ACCEPTED": 0, "DISMISSED": 0}
            if lstatus in fb_stats[itype]:
                fb_stats[itype][lstatus] += 1

        # 8. Query recently presented types (last 4 hours)
        four_hours_ago = ref_time - timedelta(hours=4)
        recent_presented_stmt = select(UserIntervention.intervention_type).where(
            UserIntervention.user_id == user_id,
            UserIntervention.creation_timestamp >= four_hours_ago,
        )
        recent_presented_types: Set[str] = set(db.scalars(recent_presented_stmt).all())

        # 9. Invoke InterventionEngine
        candidates = InterventionEngine.generate_interventions(
            user_id=user_id,
            tasks=tasks,
            focus_windows=focus_windows,
            profile_data=profile_dict,
            recent_interruptions=interruptions,
            task_associations=associations,
            current_hour=current_hour,
            current_context_tag=req.context_tag,
            historical_feedback_stats=fb_stats,
            recent_presented_types=recent_presented_types,
            as_of=ref_time,
            max_interventions=req.max_interventions,
        )

        if not candidates:
            return []

        # 10. Deduplication against active interventions in database
        active_stmt = select(UserIntervention).where(
            UserIntervention.user_id == user_id,
            UserIntervention.lifecycle_status.in_(
                [
                    InterventionLifecycleStatus.GENERATED.value,
                    InterventionLifecycleStatus.PRESENTED.value,
                ]
            ),
            UserIntervention.expiration_timestamp > ref_time,
        )
        existing_active = list(db.scalars(active_stmt).all())
        existing_signatures = {
            (item.intervention_type, str(item.associated_task_id) if item.associated_task_id else None)
            for item in existing_active
        }

        created_records: List[UserIntervention] = []
        for cand in candidates:
            sig = (cand.intervention_type, str(cand.associated_task_id) if cand.associated_task_id else None)
            if sig in existing_signatures:
                continue

            record = UserIntervention(
                id=cand.id,
                user_id=cand.user_id,
                associated_task_id=cand.associated_task_id,
                intervention_type=cand.intervention_type,
                intervention_category=cand.intervention_category,
                title=cand.title,
                message=cand.message,
                trigger_condition=cand.trigger_condition,
                supporting_evidence=cand.supporting_evidence,
                expected_outcome=cand.expected_outcome,
                estimated_effort=cand.estimated_effort,
                relevance_score=cand.relevance_score,
                confidence=cand.confidence,
                lifecycle_status=InterventionLifecycleStatus.GENERATED.value,
                creation_timestamp=cand.creation_timestamp,
                expiration_timestamp=cand.expiration_timestamp,
            )
            db.add(record)
            created_records.append(record)
            existing_signatures.add(sig)

        if created_records:
            db.commit()
            for r in created_records:
                db.refresh(r)

        return created_records

    @classmethod
    def accept_intervention(
        cls,
        db: Session,
        user_id: uuid.UUID,
        intervention_id: uuid.UUID,
        action: Optional[InterventionActionRequest] = None,
    ) -> UserIntervention:
        """Transitions intervention to ACCEPTED status."""
        item = db.get(UserIntervention, intervention_id)
        if not item or item.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Intervention {intervention_id} not found.",
            )

        item.lifecycle_status = InterventionLifecycleStatus.ACCEPTED.value
        item.completed_at = datetime.now(timezone.utc)
        if action and action.feedback_note:
            item.user_feedback_note = action.feedback_note

        db.commit()
        db.refresh(item)
        return item

    @classmethod
    def dismiss_intervention(
        cls,
        db: Session,
        user_id: uuid.UUID,
        intervention_id: uuid.UUID,
        action: Optional[InterventionActionRequest] = None,
    ) -> UserIntervention:
        """Transitions intervention to DISMISSED status."""
        item = db.get(UserIntervention, intervention_id)
        if not item or item.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Intervention {intervention_id} not found.",
            )

        item.lifecycle_status = InterventionLifecycleStatus.DISMISSED.value
        if action and action.feedback_note:
            item.user_feedback_note = action.feedback_note

        db.commit()
        db.refresh(item)
        return item

    @classmethod
    def defer_intervention(
        cls,
        db: Session,
        user_id: uuid.UUID,
        intervention_id: uuid.UUID,
        action: Optional[InterventionActionRequest] = None,
    ) -> UserIntervention:
        """Transitions intervention to DEFERRED status until specified future time."""
        item = db.get(UserIntervention, intervention_id)
        if not item or item.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Intervention {intervention_id} not found.",
            )

        defer_mins = (action.defer_minutes if action and action.defer_minutes else 30)
        item.lifecycle_status = InterventionLifecycleStatus.DEFERRED.value
        item.deferred_until = datetime.now(timezone.utc) + timedelta(minutes=defer_mins)
        if action and action.feedback_note:
            item.user_feedback_note = action.feedback_note

        db.commit()
        db.refresh(item)
        return item

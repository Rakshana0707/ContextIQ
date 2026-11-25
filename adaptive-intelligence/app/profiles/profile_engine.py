"""
Profile Engine orchestrator for ContextIQ Personal Behavioral Digital Twin (Phase 4.2).
Coordinates profile building, incremental updates, versioned snapshot management,
historical reproducibility verification, and privacy compliance.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.context_session import ContextSession
from app.models.detected_interruption import DetectedInterruption
from app.models.interruption import Interruption
from app.models.task import Task
from app.models.task_event import TaskEvent
from app.models.telemetry_consent import ConsentStatus, TelemetryConsent
from app.profiles.profile_builder import ProfileBuilder
from app.profiles.profile_repository import ProfileRepository
from app.profiles.profile_updater import ProfileUpdater
from app.schemas.profile_schemas import (
    DigitalTwinProfileRead,
    PatternStatus,
    ProfileResetResponse,
    ProfileSnapshotRead,
)

logger = logging.getLogger(__name__)


class BehavioralProfileEngine:
    """Core orchestrator for Personal Behavioral Digital Twin operations."""

    @classmethod
    def get_or_build_profile(
        cls,
        db: Session,
        user_id: uuid.UUID,
        observation_window_days: int = 30,
    ) -> DigitalTwinProfileRead:
        """
        Retrieves active digital twin profile from repository, or performs initial build
        from historical data if none exists.
        """
        existing = ProfileRepository.get_profile_read(db, user_id)
        if existing:
            return existing

        return cls.rebuild_profile(
            db=db,
            user_id=user_id,
            observation_window_days=observation_window_days,
            trigger_reason="INITIAL_BUILD",
        )

    @classmethod
    def rebuild_profile(
        cls,
        db: Session,
        user_id: uuid.UUID,
        as_of: Optional[datetime] = None,
        observation_window_days: int = 30,
        trigger_reason: str = "MANUAL_REBUILD",
    ) -> DigitalTwinProfileRead:
        """
        Authoritative full rebuild of personal behavioral digital twin from
        all underlying historical entities up to `as_of` cutoff.
        Persists profile and creates an immutable historical snapshot.
        """
        cutoff = as_of or datetime.now(timezone.utc)

        # 1. Fetch historical raw sessions prior to cutoff
        sessions = list(
            db.scalars(
                select(ContextSession)
                .where(ContextSession.user_id == user_id, ContextSession.started_at <= cutoff)
                .order_by(ContextSession.started_at)
            ).all()
        )

        # 2. Fetch detected interruptions prior to cutoff
        detected_interruptions = list(
            db.scalars(
                select(DetectedInterruption)
                .where(DetectedInterruption.user_id == user_id, DetectedInterruption.start_timestamp <= cutoff)
                .order_by(DetectedInterruption.start_timestamp)
            ).all()
        )

        # 3. Fetch manual interruptions prior to cutoff
        manual_interruptions = list(
            db.scalars(
                select(Interruption)
                .where(Interruption.user_id == user_id, Interruption.occurred_at <= cutoff)
                .order_by(Interruption.occurred_at)
            ).all()
        )

        # 4. Fetch tasks prior to cutoff
        tasks = list(
            db.scalars(
                select(Task)
                .where(Task.user_id == user_id, Task.created_at <= cutoff)
                .order_by(Task.created_at)
            ).all()
        )

        # 5. Fetch task events prior to cutoff
        task_events = list(
            db.scalars(
                select(TaskEvent)
                .where(TaskEvent.user_id == user_id, TaskEvent.occurred_at <= cutoff)
                .order_by(TaskEvent.occurred_at)
            ).all()
        )

        # 6. Check personalization toggle state from existing profile if present
        existing_profile = ProfileRepository.get_profile(db, user_id)
        personalization_enabled = existing_profile.personalization_enabled if existing_profile else True

        # 7. Build profile using deterministic builder
        profile_read = ProfileBuilder.build_profile(
            user_id=user_id,
            sessions=sessions,
            detected_interruptions=detected_interruptions,
            manual_interruptions=manual_interruptions,
            tasks=tasks,
            task_events=task_events,
            as_of=cutoff,
            observation_window_days=observation_window_days,
        )
        profile_read.personalization_enabled = personalization_enabled

        # 8. Persist active profile and create versioned snapshot
        ProfileRepository.save_profile(db, profile_read)
        ProfileRepository.create_snapshot(
            db=db,
            profile_data=profile_read,
            source_data_cutoff=cutoff,
            trigger_reason=trigger_reason,
            observation_window_days=observation_window_days,
        )
        ProfileRepository.log_audit(
            db=db,
            user_id=user_id,
            action="REBUILD",
            details={
                "as_of": cutoff.isoformat(),
                "trigger_reason": trigger_reason,
                "sessions_count": len(sessions),
                "tasks_count": len(tasks),
            },
        )
        db.commit()

        return profile_read

    @classmethod
    def reset_profile(
        cls,
        db: Session,
        user_id: uuid.UUID,
    ) -> ProfileResetResponse:
        """
        Resets personal behavioral digital twin to an uncalibrated prior template.
        Clears empirical measurements, resets confidence to INSUFFICIENT_EVIDENCE,
        creates an audit record, and snapshots the reset action.
        """
        now = datetime.now(timezone.utc)

        # Build clean blank profile (no historical records ingested)
        empty_profile = ProfileBuilder.build_profile(
            user_id=user_id,
            sessions=[],
            detected_interruptions=[],
            manual_interruptions=[],
            tasks=[],
            task_events=[],
            as_of=now,
            observation_window_days=30,
        )
        empty_profile.is_cold_start = True
        empty_profile.global_pattern_status = PatternStatus.INSUFFICIENT_EVIDENCE
        empty_profile.global_confidence_score = 0.0

        ProfileRepository.save_profile(db, empty_profile)
        ProfileRepository.create_snapshot(
            db=db,
            profile_data=empty_profile,
            source_data_cutoff=now,
            trigger_reason="USER_RESET",
            observation_window_days=30,
        )
        ProfileRepository.log_audit(
            db=db,
            user_id=user_id,
            action="RESET",
            details={"reset_at": now.isoformat()},
        )
        db.commit()

        return ProfileResetResponse(
            status="SUCCESS",
            message="Personal behavioral profile successfully reset to prior baseline.",
            user_id=user_id,
            reset_at=now,
        )

    @classmethod
    def set_personalization(
        cls,
        db: Session,
        user_id: uuid.UUID,
        enabled: bool,
    ) -> DigitalTwinProfileRead:
        """Enables or disables adaptive personalization for the user."""
        profile = cls.get_or_build_profile(db, user_id)
        profile.personalization_enabled = enabled
        ProfileRepository.save_profile(db, profile)
        ProfileRepository.log_audit(
            db=db,
            user_id=user_id,
            action="PERSONALIZATION_TOGGLE",
            details={"personalization_enabled": enabled},
        )
        db.commit()
        return profile

    @classmethod
    def get_history(
        cls,
        db: Session,
        user_id: uuid.UUID,
        limit: int = 20,
    ) -> List[ProfileSnapshotRead]:
        """Returns versioned historical snapshots."""
        return ProfileRepository.list_snapshots(db, user_id, limit=limit)

    @classmethod
    def check_telemetry_consent(cls, db: Session, user_id: uuid.UUID) -> bool:
        """Validates whether telemetry consent is actively granted."""
        stmt = (
            select(TelemetryConsent)
            .where(TelemetryConsent.user_id == user_id)
            .order_by(TelemetryConsent.granted_timestamp.desc())
        )
        consent = db.scalar(stmt)
        if not consent:
            return True  # Dev default if no consent record configured
        return consent.consent_status == ConsentStatus.GRANTED

    @classmethod
    def ingest_session(
        cls,
        db: Session,
        user_id: uuid.UUID,
        session_id: str,
        focused_time_seconds: float,
        transition_count: int = 0,
        started_at: Optional[datetime] = None,
    ) -> Optional[DigitalTwinProfileRead]:
        """Incremental ingestion of a newly finished session with privacy consent gating."""
        if not cls.check_telemetry_consent(db, user_id):
            logger.info("Telemetry consent not granted for user %s; skipping profile update", user_id)
            return None

        profile = cls.get_or_build_profile(db, user_id)
        if not profile.personalization_enabled:
            return profile

        updated = ProfileUpdater.update_with_session(
            profile=profile,
            session_id=session_id,
            focused_time_seconds=focused_time_seconds,
            transition_count=transition_count,
            started_at=started_at,
        )
        ProfileRepository.save_profile(db, updated)
        db.commit()
        return updated

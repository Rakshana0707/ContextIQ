"""
Repository abstraction for ContextIQ Personal Behavioral Profile persistence, snapshots,
and compliance audit logging.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.models.behavioral_profile import ProfileAuditLog, ProfileSnapshot, UserBehavioralProfile
from app.schemas.profile_schemas import (
    BaselinesSummary,
    ContextBehaviorDimension,
    DigitalTwinProfileRead,
    FocusBehaviorDimension,
    InterruptionBehaviorDimension,
    PatternStatus,
    ProfileSnapshotRead,
    TaskCompletionDimension,
    TemporalBehaviorDimension,
)


class ProfileRepository:
    """Manages database transactions for digital twin profiles, snapshots, and audit logs."""

    @staticmethod
    def get_profile(db: Session, user_id: uuid.UUID) -> Optional[UserBehavioralProfile]:
        """Fetches the active UserBehavioralProfile ORM model."""
        stmt = select(UserBehavioralProfile).where(UserBehavioralProfile.user_id == user_id)
        return db.scalar(stmt)

    @classmethod
    def get_profile_read(cls, db: Session, user_id: uuid.UUID) -> Optional[DigitalTwinProfileRead]:
        """Fetches and deserializes profile into DigitalTwinProfileRead."""
        orm = cls.get_profile(db, user_id)
        if not orm:
            return None

        return DigitalTwinProfileRead(
            user_id=orm.user_id,
            profile_version=orm.profile_version,
            is_cold_start=orm.is_cold_start,
            personalization_enabled=orm.personalization_enabled,
            global_confidence_score=orm.global_confidence_score,
            global_pattern_status=PatternStatus(orm.global_pattern_status),
            telemetry_days_observed=orm.telemetry_days_observed,
            total_sessions_observed=orm.total_sessions_observed,
            total_tasks_observed=orm.total_tasks_observed,
            total_interruptions_observed=orm.total_interruptions_observed,
            focus_behavior=FocusBehaviorDimension.model_validate(orm.focus_dimension),
            interruption_behavior=InterruptionBehaviorDimension.model_validate(orm.interruption_dimension),
            task_completion=TaskCompletionDimension.model_validate(orm.task_completion_dimension),
            context_behavior=ContextBehaviorDimension.model_validate(orm.context_dimension),
            temporal_behavior=TemporalBehaviorDimension.model_validate(orm.temporal_dimension),
            baselines=BaselinesSummary.model_validate(orm.baselines),
            last_rebuilt_at=orm.last_rebuilt_at,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    @classmethod
    def save_profile(
        cls,
        db: Session,
        profile_data: DigitalTwinProfileRead,
    ) -> UserBehavioralProfile:
        """Upserts active digital twin profile in database."""
        orm = cls.get_profile(db, profile_data.user_id)
        if not orm:
            orm = UserBehavioralProfile(
                user_id=profile_data.user_id,
                profile_version=profile_data.profile_version,
                is_cold_start=profile_data.is_cold_start,
                personalization_enabled=profile_data.personalization_enabled,
                telemetry_days_observed=profile_data.telemetry_days_observed,
                total_sessions_observed=profile_data.total_sessions_observed,
                total_tasks_observed=profile_data.total_tasks_observed,
                total_interruptions_observed=profile_data.total_interruptions_observed,
                focus_dimension=profile_data.focus_behavior.model_dump(mode="json"),
                interruption_dimension=profile_data.interruption_behavior.model_dump(mode="json"),
                task_completion_dimension=profile_data.task_completion.model_dump(mode="json"),
                context_dimension=profile_data.context_behavior.model_dump(mode="json"),
                temporal_dimension=profile_data.temporal_behavior.model_dump(mode="json"),
                baselines=profile_data.baselines.model_dump(mode="json"),
                global_confidence_score=profile_data.global_confidence_score,
                global_pattern_status=profile_data.global_pattern_status.value,
                last_rebuilt_at=profile_data.last_rebuilt_at,
            )
            db.add(orm)
        else:
            orm.profile_version = profile_data.profile_version
            orm.is_cold_start = profile_data.is_cold_start
            orm.personalization_enabled = profile_data.personalization_enabled
            orm.telemetry_days_observed = profile_data.telemetry_days_observed
            orm.total_sessions_observed = profile_data.total_sessions_observed
            orm.total_tasks_observed = profile_data.total_tasks_observed
            orm.total_interruptions_observed = profile_data.total_interruptions_observed
            orm.focus_dimension = profile_data.focus_behavior.model_dump(mode="json")
            orm.interruption_dimension = profile_data.interruption_behavior.model_dump(mode="json")
            orm.task_completion_dimension = profile_data.task_completion.model_dump(mode="json")
            orm.context_dimension = profile_data.context_behavior.model_dump(mode="json")
            orm.temporal_dimension = profile_data.temporal_behavior.model_dump(mode="json")
            orm.baselines = profile_data.baselines.model_dump(mode="json")
            orm.global_confidence_score = profile_data.global_confidence_score
            orm.global_pattern_status = profile_data.global_pattern_status.value
            orm.last_rebuilt_at = profile_data.last_rebuilt_at
            orm.updated_at = profile_data.updated_at

        db.flush()
        return orm

    @classmethod
    def create_snapshot(
        cls,
        db: Session,
        profile_data: DigitalTwinProfileRead,
        source_data_cutoff: datetime,
        trigger_reason: str = "INCREMENTAL_BATCH",
        observation_window_days: int = 30,
    ) -> ProfileSnapshot:
        """Creates an immutable historical snapshot."""
        snapshot = ProfileSnapshot(
            user_id=profile_data.user_id,
            profile_version=profile_data.profile_version,
            snapshot_timestamp=datetime.now(timezone.utc),
            source_data_cutoff=source_data_cutoff,
            feature_schema_version=profile_data.profile_version,
            observation_window_days=observation_window_days,
            trigger_reason=trigger_reason,
            snapshot_data=profile_data.model_dump(mode="json"),
        )
        db.add(snapshot)
        db.flush()
        return snapshot

    @classmethod
    def list_snapshots(
        cls,
        db: Session,
        user_id: uuid.UUID,
        limit: int = 20,
    ) -> List[ProfileSnapshotRead]:
        """Returns ordered list of historical snapshots for user."""
        stmt = (
            select(ProfileSnapshot)
            .where(ProfileSnapshot.user_id == user_id)
            .order_by(desc(ProfileSnapshot.snapshot_timestamp))
            .limit(limit)
        )
        snapshots = db.scalars(stmt).all()
        return [ProfileSnapshotRead.model_validate(s) for s in snapshots]

    @classmethod
    def log_audit(
        cls,
        db: Session,
        user_id: uuid.UUID,
        action: str,
        details: Optional[Dict[str, Any]] = None,
        actor: str = "USER",
    ) -> ProfileAuditLog:
        """Appends an immutable audit log entry."""
        audit = ProfileAuditLog(
            user_id=user_id,
            action=action,
            actor=actor,
            details=details or {},
            created_at=datetime.now(timezone.utc),
        )
        db.add(audit)
        db.flush()
        return audit

    @classmethod
    def delete_profile(cls, db: Session, user_id: uuid.UUID) -> None:
        """Hard deletes profile, snapshots, and audit records (right to be forgotten)."""
        db.execute(delete(ProfileSnapshot).where(ProfileSnapshot.user_id == user_id))
        db.execute(delete(UserBehavioralProfile).where(UserBehavioralProfile.user_id == user_id))
        db.execute(delete(ProfileAuditLog).where(ProfileAuditLog.user_id == user_id))
        db.flush()

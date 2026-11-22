"""
Temporal Feature Extractor for Phase 2 ML Pipeline Integration (Phase 3.7).

Extracts leakage-safe micro-delay, recovery, and friction features strictly
prior to a task's creation timestamp (as_of).
"""
from __future__ import annotations

import statistics
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.context_session import ContextSession
from app.models.detected_interruption import DetectedInterruption
from app.models.interruption import Interruption
from app.services.recovery_analytics import RecoveryAnalyticsService


class TemporalFeatureExtractor:
    """Extracts temporal recovery and behavioral friction features for ML training and inference."""

    FEATURE_SCHEMA_VERSION = "v2.3"

    @classmethod
    def extract_features_for_task(
        cls,
        db: Session,
        user_id: uuid.UUID,
        as_of: datetime,
    ) -> Dict[str, Any]:
        """
        Computes recovery and micro-delay features strictly BEFORE `as_of`.
        Enforces strict leakage prevention assertions.
        """
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)

        # 1. Fetch historical detected interruptions strictly before as_of
        det_interruptions = list(
            db.scalars(
                select(DetectedInterruption).where(
                    DetectedInterruption.user_id == user_id,
                    DetectedInterruption.start_timestamp < as_of,
                )
            ).all()
        )

        # 2. Fetch manual interruptions strictly before as_of
        man_interruptions = list(
            db.scalars(
                select(Interruption).where(
                    Interruption.user_id == user_id,
                    Interruption.occurred_at < as_of,
                )
            ).all()
        )

        # 3. Fetch context sessions strictly before as_of
        sessions = list(
            db.scalars(
                select(ContextSession).where(
                    ContextSession.user_id == user_id,
                    ContextSession.started_at < as_of,
                )
            ).all()
        )

        # Resumption lag values strictly prior to as_of
        lags: List[float] = [
            di.resumption_lag_seconds
            for di in det_interruptions
            if di.resumption_lag_seconds is not None and di.resumption_lag_seconds >= 0
        ] + [
            cs.resume_delay_seconds
            for cs in sessions
            if cs.resume_delay_seconds is not None and cs.resume_delay_seconds >= 0
        ]

        mean_lag = statistics.mean(lags) if lags else 0.0
        median_lag = statistics.median(lags) if lags else 0.0
        std_lag = statistics.stdev(lags) if len(lags) > 1 else 0.0

        def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
            if dt is None:
                return None
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)

        # Last 24 hours prior to as_of
        cutoff_24h = as_of - timedelta(hours=24)
        ints_24h = [
            di for di in det_interruptions if _to_utc(di.start_timestamp) >= cutoff_24h
        ] + [
            mi for mi in man_interruptions if _to_utc(mi.occurred_at) >= cutoff_24h
        ]
        recent_interruption_freq = float(len(ints_24h))

        sessions_24h = [cs for cs in sessions if _to_utc(cs.started_at) >= cutoff_24h]
        switches_24h = sum(cs.transition_count for cs in sessions_24h)

        # Consecutive cluster count prior to as_of
        sorted_times = sorted(
            [_to_utc(di.start_timestamp) for di in det_interruptions]
            + [_to_utc(mi.occurred_at) for mi in man_interruptions]
        )
        max_cluster = 0
        current_cluster = 1 if sorted_times else 0
        for i in range(1, len(sorted_times)):
            diff = (sorted_times[i] - sorted_times[i - 1]).total_seconds()
            if diff <= 300.0:
                current_cluster += 1
            else:
                max_cluster = max(max_cluster, current_cluster)
                current_cluster = 1
        max_cluster = max(max_cluster, current_cluster)

        # Behavioral friction score strictly as-of
        friction_response = RecoveryAnalyticsService.get_behavioral_friction_index(
            db=db, user_id=user_id, period_days=14, now=as_of
        )

        return {
            "avg_resumption_lag_seconds": round(mean_lag, 2),
            "median_resumption_lag_seconds": round(median_lag, 2),
            "resumption_lag_std_seconds": round(std_lag, 2),
            "recent_interruption_frequency": recent_interruption_freq,
            "consecutive_interruption_count": max_cluster,
            "context_switch_frequency_24h": float(switches_24h),
            "behavioral_friction_index": friction_response.overall_score,
            "feature_schema_version": cls.FEATURE_SCHEMA_VERSION,
        }

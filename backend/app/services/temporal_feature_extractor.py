"""
Temporal Feature Extractor for Phase 3.8 Predictive Intelligence Integration.

Extracts leakage-safe micro-delay, recovery, fragmentation, and behavioral friction
features strictly prior to a task's reference timestamp (as_of).
Handles cold-starts gracefully without assuming missing telemetry implies calm focus.
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
from app.models.raw_telemetry_event import RawTelemetryEvent
from app.models.task_event import TaskEvent
from app.services.recovery_analytics import RecoveryAnalyticsService

POPULATION_FEATURE_DEFAULTS: Dict[str, float] = {
    "behavioral_friction_index": 35.0,
    "telemetry_coverage_ratio": 0.0,
    "application_transition_frequency": 4.0,
    "session_fragmentation_score": 0.25,
    "time_since_last_activity_hours": 2.0,
    "interruption_density": 0.15,
    "recent_interruption_frequency": 1.5,
    "avg_resumption_lag_seconds": 45.0,
    "median_resumption_lag_seconds": 40.0,
    "consecutive_interruption_count": 1.0,
    "resumption_lag_std_seconds": 15.0,
    "context_switch_frequency_24h": 6.0,
    "return_to_app_delay_seconds": 30.0,
}


def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


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
        else:
            as_of = as_of.astimezone(timezone.utc)

        # 1. Fetch historical raw telemetry events strictly before as_of
        raw_events = list(
            db.scalars(
                select(RawTelemetryEvent).where(
                    RawTelemetryEvent.user_id == user_id,
                    RawTelemetryEvent.event_timestamp < as_of,
                )
            ).all()
        )

        # 2. Fetch historical detected interruptions strictly before as_of
        det_interruptions = list(
            db.scalars(
                select(DetectedInterruption).where(
                    DetectedInterruption.user_id == user_id,
                    DetectedInterruption.start_timestamp < as_of,
                )
            ).all()
        )

        # 3. Fetch manual interruptions strictly before as_of
        man_interruptions = list(
            db.scalars(
                select(Interruption).where(
                    Interruption.user_id == user_id,
                    Interruption.occurred_at < as_of,
                )
            ).all()
        )

        # 4. Fetch context sessions strictly before as_of
        sessions = list(
            db.scalars(
                select(ContextSession).where(
                    ContextSession.user_id == user_id,
                    ContextSession.started_at < as_of,
                )
            ).all()
        )

        # 5. Fetch task events strictly before as_of
        task_events = list(
            db.scalars(
                select(TaskEvent).where(
                    TaskEvent.user_id == user_id,
                    TaskEvent.occurred_at < as_of,
                )
            ).all()
        )

        observed_features: List[str] = []
        imputed_features: List[str] = []

        # 24-hour cutoff
        cutoff_24h = as_of - timedelta(hours=24)
        raw_events_24h = [ev for ev in raw_events if _to_utc(ev.event_timestamp) >= cutoff_24h]
        ints_24h = [
            di for di in det_interruptions if _to_utc(di.start_timestamp) >= cutoff_24h
        ] + [
            mi for mi in man_interruptions if _to_utc(mi.occurred_at) >= cutoff_24h
        ]
        sessions_24h = [cs for cs in sessions if _to_utc(cs.started_at) >= cutoff_24h]

        # Calculate telemetry coverage ratio
        # Active hours represented in telemetry in last 24h (assuming 8h active workday baseline)
        hours_with_telemetry = len(set(_to_utc(ev.event_timestamp).hour for ev in raw_events_24h))
        session_hours = sum(
            min(
                ((_to_utc(s.ended_at) - _to_utc(s.started_at)).total_seconds() if s.ended_at and s.started_at else (s.focused_time_seconds or 0.0) + (s.interruption_time_seconds or 0.0)),
                3600.0,
            ) / 3600.0
            for s in sessions_24h
        )
        effective_active_hours = max(float(hours_with_telemetry), float(session_hours))
        coverage_ratio = round(min(1.0, effective_active_hours / 8.0), 2) if (raw_events_24h or sessions_24h) else 0.0

        total_observations = len(raw_events) + len(det_interruptions) + len(sessions)

        if total_observations < 3 or coverage_ratio < 0.20:
            telemetry_coverage = "INSUFFICIENT_HISTORY"
            is_cold_start = True
        elif coverage_ratio >= 0.70:
            telemetry_coverage = "FULL"
            is_cold_start = False
        else:
            telemetry_coverage = "PARTIAL"
            is_cold_start = False

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

        if lags:
            mean_lag = statistics.mean(lags)
            median_lag = statistics.median(lags)
            std_lag = statistics.stdev(lags) if len(lags) > 1 else 0.0
            observed_features.extend(["avg_resumption_lag_seconds", "median_resumption_lag_seconds", "resumption_lag_std_seconds"])
        else:
            mean_lag = POPULATION_FEATURE_DEFAULTS["avg_resumption_lag_seconds"]
            median_lag = POPULATION_FEATURE_DEFAULTS["median_resumption_lag_seconds"]
            std_lag = POPULATION_FEATURE_DEFAULTS["resumption_lag_std_seconds"]
            imputed_features.extend(["avg_resumption_lag_seconds", "median_resumption_lag_seconds", "resumption_lag_std_seconds"])

        # Return to application delay
        app_delays: List[float] = []
        for di in det_interruptions:
            delay_val = getattr(di, "return_to_app_delay_seconds", None)
            if delay_val is None and hasattr(di, "metadata_payload") and isinstance(di.metadata_payload, dict):
                delay_val = di.metadata_payload.get("return_to_app_delay_seconds")
            if delay_val is None:
                delay_val = getattr(di, "resumption_lag_seconds", None)
            if delay_val is not None and delay_val >= 0:
                app_delays.append(float(delay_val))

        if app_delays:
            return_to_app_delay = statistics.median(app_delays)
            observed_features.append("return_to_app_delay_seconds")
        else:
            return_to_app_delay = POPULATION_FEATURE_DEFAULTS["return_to_app_delay_seconds"]
            imputed_features.append("return_to_app_delay_seconds")

        # Recent interruption frequency
        if ints_24h or total_observations >= 3:
            recent_interruption_freq = float(len(ints_24h))
            observed_features.append("recent_interruption_frequency")
        else:
            recent_interruption_freq = POPULATION_FEATURE_DEFAULTS["recent_interruption_frequency"]
            imputed_features.append("recent_interruption_frequency")

        # Switches / Transitions in last 24h
        raw_transitions = [
            ev for ev in raw_events_24h
            if ev.event_type in ("application_activated", "context_switch")
        ]
        session_transitions = sum(cs.transition_count for cs in sessions_24h)
        total_transitions_24h = max(len(raw_transitions), session_transitions)

        if raw_events_24h or sessions_24h:
            context_switches_24h = float(total_transitions_24h)
            active_h = max(1.0, effective_active_hours)
            app_trans_freq = round(total_transitions_24h / active_h, 2)
            observed_features.extend(["context_switch_frequency_24h", "application_transition_frequency"])
        else:
            context_switches_24h = POPULATION_FEATURE_DEFAULTS["context_switch_frequency_24h"]
            app_trans_freq = POPULATION_FEATURE_DEFAULTS["application_transition_frequency"]
            imputed_features.extend(["context_switch_frequency_24h", "application_transition_frequency"])

        # Consecutive cluster count prior to as_of
        sorted_times = sorted(
            [_to_utc(di.start_timestamp) for di in det_interruptions]
            + [_to_utc(mi.occurred_at) for mi in man_interruptions]
        )
        if sorted_times:
            max_cluster = 0
            current_cluster = 1
            for i in range(1, len(sorted_times)):
                diff = (sorted_times[i] - sorted_times[i - 1]).total_seconds()
                if diff <= 300.0:
                    current_cluster += 1
                else:
                    max_cluster = max(max_cluster, current_cluster)
                    current_cluster = 1
            max_cluster = max(max_cluster, current_cluster)
            observed_features.append("consecutive_interruption_count")
        else:
            max_cluster = int(POPULATION_FEATURE_DEFAULTS["consecutive_interruption_count"])
            imputed_features.append("consecutive_interruption_count")

        # Behavioral friction score strictly as-of
        if total_observations >= 3:
            friction_response = RecoveryAnalyticsService.get_behavioral_friction_index(
                db=db, user_id=user_id, period_days=14, now=as_of
            )
            bfi_score = friction_response.overall_score
            observed_features.append("behavioral_friction_index")
        else:
            bfi_score = POPULATION_FEATURE_DEFAULTS["behavioral_friction_index"]
            imputed_features.append("behavioral_friction_index")

        # Interruption density (ratio of interruption time to total duration in 24h)
        total_session_time_24h = sum(
            ((_to_utc(cs.ended_at) - _to_utc(cs.started_at)).total_seconds() if cs.ended_at and cs.started_at else (cs.focused_time_seconds or 0.0) + (cs.interruption_time_seconds or 0.0))
            for cs in sessions_24h
        )
        total_int_time_24h = sum(
            (di.duration_seconds or 0.0) for di in ints_24h if isinstance(di, DetectedInterruption)
        ) + sum(cs.interruption_time_seconds or 0.0 for cs in sessions_24h)

        if total_session_time_24h > 60.0:
            int_density = round(min(1.0, total_int_time_24h / max(1.0, total_session_time_24h)), 3)
            # Fragmentation: fraction of session time lost to interruptions + penalty for high switches
            frag = round(min(1.0, (total_int_time_24h + (total_transitions_24h * 15.0)) / max(1.0, total_session_time_24h)), 3)
            observed_features.extend(["interruption_density", "session_fragmentation_score"])
        else:
            int_density = POPULATION_FEATURE_DEFAULTS["interruption_density"]
            frag = POPULATION_FEATURE_DEFAULTS["session_fragmentation_score"]
            imputed_features.extend(["interruption_density", "session_fragmentation_score"])

        # Time since last observed activity
        recent_timestamps = (
            [_to_utc(ev.event_timestamp) for ev in raw_events]
            + [_to_utc(di.end_timestamp or di.start_timestamp) for di in det_interruptions]
            + [_to_utc(cs.ended_at or cs.started_at) for cs in sessions]
            + [_to_utc(te.occurred_at) for te in task_events]
        )
        valid_ts = [t for t in recent_timestamps if t is not None and t <= as_of]
        if valid_ts:
            latest_ts = max(valid_ts)
            gap_hours = max(0.0, round((as_of - latest_ts).total_seconds() / 3600.0, 2))
            observed_features.append("time_since_last_activity_hours")
        else:
            gap_hours = POPULATION_FEATURE_DEFAULTS["time_since_last_activity_hours"]
            imputed_features.append("time_since_last_activity_hours")

        if coverage_ratio > 0.0:
            observed_features.append("telemetry_coverage_ratio")
        else:
            imputed_features.append("telemetry_coverage_ratio")

        return {
            # Features
            "avg_resumption_lag_seconds": round(mean_lag, 2),
            "median_resumption_lag_seconds": round(median_lag, 2),
            "resumption_lag_std_seconds": round(std_lag, 2),
            "recent_interruption_frequency": round(recent_interruption_freq, 2),
            "consecutive_interruption_count": max_cluster,
            "context_switch_frequency_24h": round(context_switches_24h, 2),
            "behavioral_friction_index": round(bfi_score, 1),
            "return_to_app_delay_seconds": round(return_to_app_delay, 2),
            "telemetry_coverage_ratio": coverage_ratio,
            "application_transition_frequency": app_trans_freq,
            "session_fragmentation_score": frag,
            "time_since_last_activity_hours": gap_hours,
            "interruption_density": int_density,
            "feature_schema_version": cls.FEATURE_SCHEMA_VERSION,
            # Metadata
            "telemetry_coverage": telemetry_coverage,
            "is_cold_start": is_cold_start,
            "observed_features": sorted(list(set(observed_features))),
            "imputed_features": sorted(list(set(imputed_features))),
        }

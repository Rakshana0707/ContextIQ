"""
Recovery Prediction Dataset Builder (ContextIQ Phase 6.2).

Constructs leak-free, time-to-event datasets for cognitive recovery duration modeling.
Enforces the 6 distinct recovery states:
1. INTERRUPTION_DETECTED
2. APP_OR_TASK_REVISITED
3. ORIGINAL_CONTEXT_RESTORED
4. CONFIRMED_TASK_RESUMPTION
5. TASK_COMPLETED
6. RECOVERY_NOT_OBSERVED

Strictly adheres to point-in-time feature extraction (t < t_pred) and correct right-censoring mechanics.
"""
from __future__ import annotations

import logging
import math
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.context_session import ContextSession
from app.models.detected_interruption import DetectedInterruption
from app.models.enums import DetectedInterruptionType, InterruptionSeverity, TaskPriority, TaskStatus
from app.models.external_calendar_event import ExternalCalendarEvent
from app.models.task import Task
from app.models.task_event import TaskEvent
from app.schemas.recovery_prediction import (
    RecoveryDatasetRecord,
    RecoveryState,
)

logger = logging.getLogger(__name__)

# Observation cutoff limit in seconds (1 hour = 3600s)
DEFAULT_MAX_RECOVERY_HORIZON_SECONDS = 3600.0
MIN_DURATION_SECONDS = 1.0


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class RecoveryDatasetBuilder:
    """
    Extracts point-in-time features and ground-truth recovery labels
    from raw telemetry, detected interruptions, and task lifecycles.
    """

    def __init__(self, max_horizon_seconds: float = DEFAULT_MAX_RECOVERY_HORIZON_SECONDS):
        self.max_horizon_seconds = max_horizon_seconds

    @staticmethod
    def classify_recovery_outcome(
        interruption_end: datetime,
        resumed_timestamp: Optional[datetime] = None,
        app_returned_timestamp: Optional[datetime] = None,
        context_restored_timestamp: Optional[datetime] = None,
        completed_timestamp: Optional[datetime] = None,
        session_end_timestamp: Optional[datetime] = None,
        max_horizon_seconds: float = DEFAULT_MAX_RECOVERY_HORIZON_SECONDS,
    ) -> Tuple[float, int, RecoveryState, Optional[str]]:
        """
        Classifies the recovery outcome into one of 6 granular states and
        computes the bounded duration (seconds) with exact censoring indicator.

        Returns:
            (duration_seconds, event_observed, recovery_state, censoring_reason)
        """
        end_t = _ensure_utc(interruption_end)
        cutoff_t = end_t + timedelta(seconds=max_horizon_seconds)

        if session_end_timestamp:
            sess_end = _ensure_utc(session_end_timestamp)
            if sess_end < cutoff_t:
                cutoff_t = sess_end

        # 1. Confirmed task resumption
        if resumed_timestamp is not None:
            res_t = _ensure_utc(resumed_timestamp)
            if res_t <= cutoff_t and res_t >= end_t:
                dur = max(MIN_DURATION_SECONDS, (res_t - end_t).total_seconds())
                return dur, 1, RecoveryState.CONFIRMED_TASK_RESUMPTION, None

        # 2. Task Completed directly
        if completed_timestamp is not None:
            comp_t = _ensure_utc(completed_timestamp)
            if comp_t <= cutoff_t and comp_t >= end_t:
                dur = max(MIN_DURATION_SECONDS, (comp_t - end_t).total_seconds())
                return dur, 1, RecoveryState.TASK_COMPLETED, None

        # 3. Context restored but no confirmed task resumption before cutoff (Censored)
        if context_restored_timestamp is not None:
            ctx_t = _ensure_utc(context_restored_timestamp)
            if ctx_t <= cutoff_t and ctx_t >= end_t:
                dur = max(MIN_DURATION_SECONDS, (cutoff_t - end_t).total_seconds())
                return dur, 0, RecoveryState.ORIGINAL_CONTEXT_RESTORED, "context_restored_unconfirmed_resumption"

        # 4. App revisited but no confirmed task resumption before cutoff (Censored)
        if app_returned_timestamp is not None:
            app_t = _ensure_utc(app_returned_timestamp)
            if app_t <= cutoff_t and app_t >= end_t:
                dur = max(MIN_DURATION_SECONDS, (cutoff_t - end_t).total_seconds())
                return dur, 0, RecoveryState.APP_OR_TASK_REVISITED, "app_revisited_unconfirmed_resumption"

        # 5. Recovery Not Observed before cutoff (Administrative right-censoring)
        # Note: We do NOT set duration to infinity!
        dur = max(MIN_DURATION_SECONDS, (cutoff_t - end_t).total_seconds())
        reason = "session_ended_before_recovery" if session_end_timestamp and _ensure_utc(session_end_timestamp) <= cutoff_t else "horizon_cutoff_reached"
        return dur, 0, RecoveryState.RECOVERY_NOT_OBSERVED, reason

    def extract_features_at_timestamp(
        self,
        db: Session,
        user_id: uuid.UUID,
        as_of: datetime,
        interruption: Optional[DetectedInterruption] = None,
        task_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """
        Extracts all predictive features strictly prior to as_of (zero future leakage).
        """
        as_of_utc = _ensure_utc(as_of)

        # 1. Interruption features
        if interruption is not None:
            dur_sec = float(interruption.duration_seconds or 60.0)
            int_type = str(interruption.interruption_type.value if hasattr(interruption.interruption_type, "value") else interruption.interruption_type)
            int_sev = str(interruption.severity.value if hasattr(interruption.severity, "value") else interruption.severity)
        else:
            dur_sec = 120.0
            int_type = "APPLICATION_SWITCH"
            int_sev = "MEDIUM"

        # 2. Task features (as of timestamp)
        task = None
        if task_id:
            task = db.get(Task, task_id)
        elif interruption and interruption.metadata_payload and interruption.metadata_payload.get("task_id"):
            try:
                task = db.get(Task, uuid.UUID(str(interruption.metadata_payload["task_id"])))
            except Exception:
                task = None

        task_cat = getattr(task, "task_category", "DeepWork") or "DeepWork"
        task_prio = getattr(task, "priority", "MEDIUM") or "MEDIUM"
        if hasattr(task_prio, "value"):
            task_prio = task_prio.value
        task_complex = float(getattr(task, "complexity_score", 1.0) or 1.0)

        # 3. User historical recovery baseline (strictly prior to as_of)
        prior_interruptions = list(
            db.scalars(
                select(DetectedInterruption).where(
                    DetectedInterruption.user_id == user_id,
                    DetectedInterruption.start_timestamp < as_of_utc,
                    DetectedInterruption.resumption_lag_seconds.is_not(None),
                )
            ).all()
        )
        prior_lags = [float(di.resumption_lag_seconds) for di in prior_interruptions if di.resumption_lag_seconds and di.resumption_lag_seconds > 0]
        if prior_lags:
            prev_rec_mean = float(np.mean(prior_lags))
            prev_rec_median = float(np.median(prior_lags))
            prev_resumption_rate = len(prior_lags) / max(1, len(prior_interruptions))
        else:
            # Cold-start prior defaults (log-normal empirical population: ~4.5 minutes)
            prev_rec_mean = 270.0
            prev_rec_median = 240.0
            prev_resumption_rate = 0.75

        # 4. Context switching in trailing 1 hour
        one_hour_prior = as_of_utc - timedelta(hours=1)
        trailing_sessions = list(
            db.scalars(
                select(ContextSession).where(
                    ContextSession.user_id == user_id,
                    ContextSession.started_at >= one_hour_prior,
                    ContextSession.started_at < as_of_utc,
                )
            ).all()
        )
        recent_switches = sum(cs.context_switch_count or 0 for cs in trailing_sessions)

        # 5. Friction Index (BFI) proxy
        norm_switches = min(1.0, recent_switches / 6.0)
        norm_sev = 0.25 if int_sev == "LOW" else (0.5 if int_sev == "MEDIUM" else 0.85)
        bfi = round(100.0 * (0.35 * norm_sev + 0.35 * norm_switches + 0.30 * (min(dur_sec, 600) / 600.0)), 2)

        # 6. Calendar Context (if external events exist)
        cal_events = list(
            db.scalars(
                select(ExternalCalendarEvent).where(
                    ExternalCalendarEvent.user_id == user_id,
                    ExternalCalendarEvent.start_time >= as_of_utc,
                    ExternalCalendarEvent.start_time <= as_of_utc + timedelta(hours=2),
                )
            ).all()
        )
        has_cal_event = len(cal_events) > 0
        if has_cal_event:
            cal_slack = max(0.0, (cal_events[0].start_time - as_of_utc).total_seconds() / 60.0)
        else:
            cal_slack = 120.0

        return {
            "interruption_duration_seconds": dur_sec,
            "interruption_type": int_type,
            "interruption_severity": int_sev,
            "pre_interruption_task_category": str(task_cat),
            "task_priority": str(task_prio),
            "task_complexity": task_complex,
            "previous_recovery_duration_mean": round(prev_rec_mean, 2),
            "previous_recovery_duration_median": round(prev_rec_median, 2),
            "hour_of_day": as_of_utc.hour,
            "day_of_week": as_of_utc.weekday(),
            "recent_context_switches": recent_switches,
            "behavioral_friction_index": bfi,
            "previous_task_resumption_rate": round(prev_resumption_rate, 4),
            "has_calendar_event_next_hour": has_cal_event,
            "calendar_slack_minutes": round(cal_slack, 1),
            "device_type": "DESKTOP",
        }

    @classmethod
    def generate_benchmark_recovery_dataset(
        cls,
        n_samples: int = 600,
        n_users: int = 30,
        seed: int = 42,
    ) -> pd.DataFrame:
        """
        Synthesizes a realistic, leak-free benchmark dataset grounded in cognitive psychology
        recovery latency parameters (log-normal distribution with median ~3-6 minutes,
        approx 20-30% right-censoring rate, circadian fatigue, task priority, and calendar pressure).
        """
        rng = np.random.default_rng(seed)
        records: List[Dict[str, Any]] = []

        categories = ["DeepWork", "Coding", "Writing", "Research", "Admin", "Review"]
        priorities = ["LOW", "MEDIUM", "HIGH", "URGENT"]
        severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        types = ["APPLICATION_SWITCH", "EXTENDED_INACTIVITY", "RAPID_SWITCHING", "EXTERNAL_COMMUNICATION"]
        device_types = ["DESKTOP", "MOBILE", "CROSS_DEVICE"]

        # Base timestamp: 2026-10-01 08:00 UTC
        base_time = datetime(2026, 10, 1, 8, 0, tzinfo=timezone.utc)
        user_ids = [str(uuid.uuid4()) for _ in range(n_users)]

        # User baseline frailty terms
        user_frailties = {u: rng.normal(0.0, 0.35) for u in user_ids}

        for i in range(n_samples):
            u_id = user_ids[i % n_users]
            # Advance time chronologically
            pred_time = base_time + timedelta(hours=i * 1.5 + rng.uniform(0.1, 0.8))

            dur_int = float(rng.exponential(scale=180.0) + 15.0)  # 15s - 15m interruption
            dur_int = min(1800.0, dur_int)
            severity = rng.choice(severities, p=[0.35, 0.40, 0.20, 0.05])
            int_type = rng.choice(types, p=[0.45, 0.25, 0.15, 0.15])
            cat = rng.choice(categories)
            priority = rng.choice(priorities, p=[0.20, 0.45, 0.25, 0.10])
            complexity = round(float(rng.uniform(0.8, 2.5)), 2)

            hour = pred_time.hour
            weekday = pred_time.weekday()
            recent_switches = int(rng.poisson(lam=2.5 + (0.8 if hour >= 14 else 0.0)))
            bfi = round(float(np.clip(25.0 + dur_int / 30.0 + recent_switches * 5.0 + rng.normal(0, 5), 5, 95)), 1)
            prev_mean = round(float(np.clip(240.0 + user_frailties[u_id] * 80.0 + rng.normal(0, 20), 60, 900)), 1)
            prev_med = round(prev_mean * 0.88, 1)
            prev_rate = round(float(np.clip(0.80 - bfi / 250.0 + rng.normal(0, 0.05), 0.3, 0.98)), 3)
            has_cal = bool(rng.random() < 0.25)
            cal_slack = round(float(rng.uniform(10.0, 120.0)), 1) if has_cal else 120.0
            device = rng.choice(device_types, p=[0.75, 0.15, 0.10])

            # True generative log-normal recovery latency:
            # ln(T) = mu0 + beta_dur * ln(dur_int) + beta_sev + beta_bfi + frailty + noise
            mu = 5.2 + user_frailties[u_id]
            mu += 0.22 * math.log(max(15.0, dur_int) / 60.0)
            if severity == "HIGH":
                mu += 0.35
            elif severity == "CRITICAL":
                mu += 0.70
            elif severity == "LOW":
                mu -= 0.25

            if priority in ("HIGH", "URGENT"):
                mu -= 0.20  # Urgency speeds up recovery
            if cat in ("DeepWork", "Coding"):
                mu += 0.25  # High cognitive context takes longer to restore
            if hour >= 16:
                mu += 0.30  # Evening fatigue increases recovery time

            sigma = 0.65
            true_duration = float(np.exp(mu + rng.normal(0, sigma)))

            # Censoring process: user may abandon task, meeting starts, or session ends
            session_end_cutoff = float(rng.uniform(120.0, 1800.0))
            if has_cal and cal_slack * 60.0 < session_end_cutoff:
                session_end_cutoff = cal_slack * 60.0

            # Generate observed state
            if true_duration <= session_end_cutoff and true_duration <= DEFAULT_MAX_RECOVERY_HORIZON_SECONDS:
                dur_observed = round(true_duration, 2)
                event_obs = 1
                state = RecoveryState.CONFIRMED_TASK_RESUMPTION.value
                cens_reason = None
            else:
                dur_observed = round(min(session_end_cutoff, DEFAULT_MAX_RECOVERY_HORIZON_SECONDS), 2)
                event_obs = 0
                state = RecoveryState.APP_OR_TASK_REVISITED.value if rng.random() < 0.4 else RecoveryState.RECOVERY_NOT_OBSERVED.value
                cens_reason = "calendar_conflict_or_session_end"

            dur_observed = max(MIN_DURATION_SECONDS, dur_observed)

            record = {
                "interruption_id": str(uuid.uuid4()),
                "user_id": u_id,
                "prediction_timestamp": pred_time.isoformat(),
                "interruption_duration_seconds": dur_int,
                "interruption_type": int_type,
                "interruption_severity": severity,
                "pre_interruption_task_category": cat,
                "task_priority": priority,
                "task_complexity": complexity,
                "previous_recovery_duration_mean": prev_mean,
                "previous_recovery_duration_median": prev_med,
                "hour_of_day": hour,
                "day_of_week": weekday,
                "recent_context_switches": recent_switches,
                "behavioral_friction_index": bfi,
                "previous_task_resumption_rate": prev_rate,
                "has_calendar_event_next_hour": int(has_cal),
                "calendar_slack_minutes": cal_slack,
                "device_type": device,
                "duration_seconds": dur_observed,
                "duration_minutes": round(dur_observed / 60.0, 3),
                "event_observed": event_obs,
                "recovery_state": state,
                "censoring_reason": cens_reason,
            }
            records.append(record)

        df = pd.DataFrame(records)
        df.sort_values(by="prediction_timestamp", inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df

"""
Automated Cognitive Recovery and Micro-Delay Analytics Engine (ContextIQ Phase 3.7).

Calculates measurable behavioral recovery metrics, three-tier resumption delays,
calibrated Behavioral Friction Index (BFI), contextual interruption trends,
and personal historical baselines.
"""
from __future__ import annotations

import logging
import math
import statistics
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.context_session import ContextSession
from app.models.detected_interruption import DetectedInterruption
from app.models.enums import TaskStatus
from app.models.interruption import Interruption
from app.models.task import Task
from app.models.task_event import TaskEvent
from app.schemas.recovery_analytics import (
    BehavioralFrictionResponse,
    ContextSliceMetrics,
    InterruptionTrendsResponse,
    PersonalBaselineResponse,
    RecoveryMetricsResponse,
    ResumptionDelayTiers,
)

logger = logging.getLogger(__name__)

# Saturation constants for transparent BFI normalization
INTERRUPTION_SATURATION_PER_HOUR = 6.0
SWITCH_SATURATION_PER_SESSION = 3.0
RECOVERY_SATURATION_MINUTES = 30.0
VARIABILITY_SATURATION_MINUTES = 15.0

# BFI Component Weights (Sum = 1.0)
WEIGHT_FORGETTING = 0.30
WEIGHT_INTERRUPTION = 0.25
WEIGHT_CONTEXT_SWITCH = 0.20
WEIGHT_RECOVERY = 0.15
WEIGHT_VARIABILITY = 0.10


def _clamp(val: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, val))


def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class RecoveryAnalyticsService:
    """Service providing behavioral recovery analytics and micro-delay metrics."""

    @staticmethod
    def get_recovery_metrics(
        db: Session,
        user_id: uuid.UUID,
        period_days: int = 30,
        now: Optional[datetime] = None,
    ) -> RecoveryMetricsResponse:
        """Calculates three-tier resumption delays and recovery metrics over period."""
        now_dt = now or datetime.now(timezone.utc)
        since = now_dt - timedelta(days=period_days)

        # 1. Fetch detected and manual interruptions
        det_interruptions = list(
            db.scalars(
                select(DetectedInterruption).where(
                    DetectedInterruption.user_id == user_id,
                    DetectedInterruption.start_timestamp >= since,
                )
            ).all()
        )
        man_interruptions = list(
            db.scalars(
                select(Interruption).where(
                    Interruption.user_id == user_id,
                    Interruption.occurred_at >= since,
                )
            ).all()
        )

        # 2. Fetch context sessions
        sessions = list(
            db.scalars(
                select(ContextSession).where(
                    ContextSession.user_id == user_id,
                    ContextSession.started_at >= since,
                )
            ).all()
        )

        # Collect measured delays (seconds)
        app_return_delays: List[float] = []
        device_return_delays: List[float] = []
        confirmed_task_delays: List[float] = []
        all_resumption_lags: List[float] = []
        cost_by_category: Dict[str, List[float]] = {}
        cost_by_app: Dict[str, List[float]] = {}

        # Process Detected Interruptions
        for di in det_interruptions:
            lag = di.resumption_lag_seconds
            if lag is not None and lag >= 0:
                all_resumption_lags.append(lag)
                app_return_delays.append(lag)
                app = di.primary_app or di.interrupting_app or "general"
                cost_by_app.setdefault(app, []).append(lag)

        # Process Context Sessions (resume delay seconds & multi-app transitions)
        for cs in sessions:
            if cs.resume_delay_seconds is not None and cs.resume_delay_seconds >= 0:
                all_resumption_lags.append(cs.resume_delay_seconds)
                device_return_delays.append(cs.resume_delay_seconds)

            if cs.task_id and cs.resume_delay_seconds is not None:
                # Confirmed task resumption
                confirmed_task_delays.append(cs.resume_delay_seconds)

            # Categorical breakdown if task exists
            if cs.task and cs.resume_delay_seconds is not None:
                cat = getattr(cs.task, "task_category", "Work") or "Work"
                cost_by_category.setdefault(str(cat), []).append(cs.resume_delay_seconds)

        # Statistics
        mean_lag = statistics.mean(all_resumption_lags) if all_resumption_lags else None
        median_lag = statistics.median(all_resumption_lags) if all_resumption_lags else None
        std_lag = (
            statistics.stdev(all_resumption_lags)
            if len(all_resumption_lags) > 1
            else (0.0 if all_resumption_lags else None)
        )
        cov = (std_lag / mean_lag) if (std_lag is not None and mean_lag and mean_lag > 0) else None

        # Three-tier delays
        avg_device = statistics.mean(device_return_delays) if device_return_delays else None
        avg_app = statistics.mean(app_return_delays) if app_return_delays else None
        avg_confirmed = statistics.mean(confirmed_task_delays) if confirmed_task_delays else None

        # Session aggregations
        total_session_seconds = sum(
            max(0.0, (cs.ended_at - cs.started_at).total_seconds())
            for cs in sessions
            if cs.ended_at
        )
        total_interruption_seconds = sum(cs.interruption_time_seconds for cs in sessions)
        total_focused_seconds = sum(cs.focused_time_seconds for cs in sessions)
        total_context_switches = sum(cs.transition_count for cs in sessions)
        total_interruptions = len(det_interruptions) + len(man_interruptions)

        active_hours = (total_focused_seconds + total_interruption_seconds) / 3600.0
        int_frequency = (total_interruptions / active_hours) if active_hours > 0 else 0.0
        int_density = (
            (total_interruption_seconds / total_session_seconds)
            if total_session_seconds > 0
            else 0.0
        )
        ctx_frequency = (total_context_switches / active_hours) if active_hours > 0 else 0.0

        # Focus duration between interruptions
        avg_focus_min = (
            round((total_focused_seconds / max(1, total_interruptions)) / 60.0, 2)
            if total_focused_seconds > 0
            else None
        )

        # Consecutive interruption cluster count (< 5 minutes apart)
        sorted_int_times = sorted(
            [_to_utc(di.start_timestamp) for di in det_interruptions]
            + [_to_utc(mi.occurred_at) for mi in man_interruptions]
        )
        max_cluster = 0
        current_cluster = 1 if sorted_int_times else 0
        for i in range(1, len(sorted_int_times)):
            diff = (sorted_int_times[i] - sorted_int_times[i - 1]).total_seconds()
            if diff <= 300.0:  # <= 5 minutes
                current_cluster += 1
            else:
                max_cluster = max(max_cluster, current_cluster)
                current_cluster = 1
        max_cluster = max(max_cluster, current_cluster)

        # Average costs per category / app
        avg_cost_category = {
            k: round(statistics.mean(v), 2) for k, v in cost_by_category.items() if v
        }
        avg_cost_app = {
            k: round(statistics.mean(v), 2) for k, v in cost_by_app.items() if v
        }

        return RecoveryMetricsResponse(
            user_id=user_id,
            period_days=period_days,
            mean_resumption_lag_seconds=round(mean_lag, 2) if mean_lag is not None else None,
            median_resumption_lag_seconds=round(median_lag, 2) if median_lag is not None else None,
            recovery_time_variability=round(std_lag, 2) if std_lag is not None else None,
            coefficient_of_variation=round(cov, 4) if cov is not None else None,
            interruption_frequency=round(int_frequency, 2),
            interruption_density=round(int_density, 4),
            context_switching_frequency=round(ctx_frequency, 2),
            consecutive_interruption_count=max_cluster,
            average_focus_duration_minutes=avg_focus_min,
            delays_by_tier=ResumptionDelayTiers(
                return_to_device_delay_seconds=round(avg_device, 2) if avg_device is not None else None,
                return_to_app_delay_seconds=round(avg_app, 2) if avg_app is not None else None,
                confirmed_task_resumption_delay_seconds=round(avg_confirmed, 2) if avg_confirmed is not None else None,
                is_estimated=len(confirmed_task_delays) == 0,
                sample_count=len(all_resumption_lags),
            ),
            recovery_cost_by_category=avg_cost_category,
            recovery_cost_by_application=avg_cost_app,
        )

    @staticmethod
    def get_behavioral_friction_index(
        db: Session,
        user_id: uuid.UUID,
        period_days: int = 30,
        now: Optional[datetime] = None,
    ) -> BehavioralFrictionResponse:
        """
        Calculates calibrated Behavioral Friction Index (0–100) preventing double-counting
        and factoring recovery variability.
        """
        now_dt = now or datetime.now(timezone.utc)
        since = now_dt - timedelta(days=period_days)

        # 1. Tasks Forgetting Rate
        tasks = list(
            db.scalars(
                select(Task).where(
                    Task.user_id == user_id,
                    Task.created_at >= since,
                )
            ).all()
        )
        resolved = [t for t in tasks if t.status in (TaskStatus.COMPLETED, TaskStatus.FORGOTTEN)]
        forgotten = [t for t in resolved if t.status == TaskStatus.FORGOTTEN]
        forgetting_rate = (len(forgotten) / len(resolved)) if resolved else 0.0
        forgetting_score = _clamp(100.0 * forgetting_rate)

        # 2. Sessions & Interruption Rate
        sessions = list(
            db.scalars(
                select(ContextSession).where(
                    ContextSession.user_id == user_id,
                    ContextSession.started_at >= since,
                )
            ).all()
        )
        det_interruptions = list(
            db.scalars(
                select(DetectedInterruption).where(
                    DetectedInterruption.user_id == user_id,
                    DetectedInterruption.start_timestamp >= since,
                )
            ).all()
        )
        man_interruptions = list(
            db.scalars(
                select(Interruption).where(
                    Interruption.user_id == user_id,
                    Interruption.occurred_at >= since,
                )
            ).all()
        )

        total_int_count = len(det_interruptions) + len(man_interruptions)
        total_focused = sum(cs.focused_time_seconds for cs in sessions)
        total_int_secs = sum(cs.interruption_time_seconds for cs in sessions)
        active_hours = (total_focused + total_int_secs) / 3600.0

        int_per_hour = (total_int_count / active_hours) if active_hours > 0 else 0.0
        interruption_score = _clamp(100.0 * min(1.0, int_per_hour / INTERRUPTION_SATURATION_PER_HOUR))

        # 3. Context Switches per Session
        total_switches = sum(cs.transition_count for cs in sessions)
        switches_per_session = (total_switches / len(sessions)) if sessions else 0.0
        context_switch_score = _clamp(100.0 * min(1.0, switches_per_session / SWITCH_SATURATION_PER_SESSION))

        # 4. Recovery Duration & Variability
        resumption_delays: List[float] = [
            cs.resume_delay_seconds
            for cs in sessions
            if cs.resume_delay_seconds is not None and cs.resume_delay_seconds >= 0
        ] + [
            di.resumption_lag_seconds
            for di in det_interruptions
            if di.resumption_lag_seconds is not None and di.resumption_lag_seconds >= 0
        ]

        if resumption_delays:
            avg_delay_min = statistics.mean(resumption_delays) / 60.0
            recovery_score = _clamp(100.0 * min(1.0, avg_delay_min / RECOVERY_SATURATION_MINUTES))

            std_delay_min = (
                (statistics.stdev(resumption_delays) / 60.0)
                if len(resumption_delays) > 1
                else 0.0
            )
            variability_score = _clamp(100.0 * min(1.0, std_delay_min / VARIABILITY_SATURATION_MINUTES))
        else:
            recovery_score = 0.0
            variability_score = 0.0

        # Weighted Overall Score
        overall_score = (
            WEIGHT_FORGETTING * forgetting_score
            + WEIGHT_INTERRUPTION * interruption_score
            + WEIGHT_CONTEXT_SWITCH * context_switch_score
            + WEIGHT_RECOVERY * recovery_score
            + WEIGHT_VARIABILITY * variability_score
        )
        overall_score = round(_clamp(overall_score), 2)

        # Contributing factors
        components = [
            ("Task Forgetting", forgetting_score * WEIGHT_FORGETTING),
            ("Frequent Interruptions", interruption_score * WEIGHT_INTERRUPTION),
            ("Context Switching", context_switch_score * WEIGHT_CONTEXT_SWITCH),
            ("Prolonged Recovery Lag", recovery_score * WEIGHT_RECOVERY),
            ("Recovery Variability", variability_score * WEIGHT_VARIABILITY),
        ]
        components.sort(key=lambda x: x[1], reverse=True)
        top_factors = [c[0] for c in components if c[1] > 2.0][:3]

        explanation = (
            f"Behavioral Friction Index is {overall_score:.1f}/100 based on observed task and "
            f"desktop activity across {period_days} days. Primary driver: {components[0][0]}."
        )

        return BehavioralFrictionResponse(
            user_id=user_id,
            period_days=period_days,
            overall_score=overall_score,
            forgetting_score=round(forgetting_score, 2),
            interruption_score=round(interruption_score, 2),
            context_switch_score=round(context_switch_score, 2),
            recovery_score=round(recovery_score, 2),
            variability_score=round(variability_score, 2),
            telemetry_adjusted=True,
            explanation=explanation,
            contributing_factors=top_factors,
        )

    @staticmethod
    def get_interruption_trends(
        db: Session,
        user_id: uuid.UUID,
        period_days: int = 30,
        now: Optional[datetime] = None,
    ) -> InterruptionTrendsResponse:
        """Categorizes interruption events across time-of-day, day-of-week, app, and type."""
        now_dt = now or datetime.now(timezone.utc)
        since = now_dt - timedelta(days=period_days)

        det_interruptions = list(
            db.scalars(
                select(DetectedInterruption).where(
                    DetectedInterruption.user_id == user_id,
                    DetectedInterruption.start_timestamp >= since,
                )
            ).all()
        )

        # Slices
        time_of_day_buckets: Dict[str, List[float]] = {
            "Morning (06:00-12:00)": [],
            "Afternoon (12:00-17:00)": [],
            "Evening (17:00-22:00)": [],
            "Night (22:00-06:00)": [],
        }
        day_of_week_buckets: Dict[str, List[float]] = {
            "Monday": [], "Tuesday": [], "Wednesday": [],
            "Thursday": [], "Friday": [], "Saturday": [], "Sunday": [],
        }
        app_buckets: Dict[str, List[float]] = {}
        type_buckets: Dict[str, List[float]] = {}
        hourly_counts: Dict[int, int] = {h: 0 for h in range(24)}

        for di in det_interruptions:
            ts = di.start_timestamp
            lag = di.resumption_lag_seconds or 0.0

            # Time of day
            hour = ts.hour
            hourly_counts[hour] += 1
            if 6 <= hour < 12:
                time_of_day_buckets["Morning (06:00-12:00)"].append(lag)
            elif 12 <= hour < 17:
                time_of_day_buckets["Afternoon (12:00-17:00)"].append(lag)
            elif 17 <= hour < 22:
                time_of_day_buckets["Evening (17:00-22:00)"].append(lag)
            else:
                time_of_day_buckets["Night (22:00-06:00)"].append(lag)

            # Day of week
            dow_name = ts.strftime("%A")
            if dow_name in day_of_week_buckets:
                day_of_week_buckets[dow_name].append(lag)

            # App
            app = di.interrupting_app or "system"
            app_buckets.setdefault(app, []).append(lag)

            # Type
            t_name = di.interruption_type.value if hasattr(di.interruption_type, "value") else str(di.interruption_type)
            type_buckets.setdefault(t_name, []).append(lag)

        def _build_slice_dict(raw_dict: Dict[str, List[float]]) -> Dict[str, ContextSliceMetrics]:
            res: Dict[str, ContextSliceMetrics] = {}
            for k, lags in raw_dict.items():
                cnt = len(lags)
                insufficient = cnt < 3
                mean_l = round(statistics.mean(lags), 2) if (cnt > 0 and not insufficient) else None
                res[k] = ContextSliceMetrics(
                    observation_count=cnt,
                    mean_resumption_lag_seconds=mean_l,
                    interruption_count=cnt,
                    insufficient_data=insufficient,
                )
            return res

        total_ints = len(det_interruptions)
        density_map = {
            h: round(count / total_ints, 4) if total_ints > 0 else 0.0
            for h, count in hourly_counts.items()
        }

        return InterruptionTrendsResponse(
            user_id=user_id,
            period_days=period_days,
            by_time_of_day=_build_slice_dict(time_of_day_buckets),
            by_day_of_week=_build_slice_dict(day_of_week_buckets),
            by_application_context=_build_slice_dict(app_buckets),
            by_interruption_type=_build_slice_dict(type_buckets),
            hourly_interruption_density=density_map,
        )

    @staticmethod
    def get_personal_baseline(
        db: Session,
        user_id: uuid.UUID,
        baseline_period_days: int = 14,
        current_period_days: int = 3,
        now: Optional[datetime] = None,
    ) -> PersonalBaselineResponse:
        """
        Calculates self-relative personal baseline and evaluates current behavioral
        deviation without comparing against other users.
        """
        now_dt = now or datetime.now(timezone.utc)

        # Baseline metrics (e.g. 14 days)
        baseline_recovery = RecoveryAnalyticsService.get_recovery_metrics(
            db, user_id, period_days=baseline_period_days, now=now_dt
        )
        baseline_friction = RecoveryAnalyticsService.get_behavioral_friction_index(
            db, user_id, period_days=baseline_period_days, now=now_dt
        )

        # Current period metrics (e.g. 3 days)
        current_recovery = RecoveryAnalyticsService.get_recovery_metrics(
            db, user_id, period_days=current_period_days, now=now_dt
        )
        current_friction = RecoveryAnalyticsService.get_behavioral_friction_index(
            db, user_id, period_days=current_period_days, now=now_dt
        )

        b_sample_count = baseline_recovery.delays_by_tier.sample_count
        has_history = b_sample_count >= 3

        if not has_history:
            return PersonalBaselineResponse(
                user_id=user_id,
                baseline_period_days=baseline_period_days,
                trend_direction="INSUFFICIENT_DATA",
                has_sufficient_history=False,
            )

        # Ratios (Current / Baseline)
        lag_ratio = None
        if (
            current_recovery.mean_resumption_lag_seconds is not None
            and baseline_recovery.mean_resumption_lag_seconds
            and baseline_recovery.mean_resumption_lag_seconds > 0
        ):
            lag_ratio = round(
                current_recovery.mean_resumption_lag_seconds / baseline_recovery.mean_resumption_lag_seconds,
                4,
            )

        fric_ratio = None
        if baseline_friction.overall_score > 0:
            fric_ratio = round(current_friction.overall_score / baseline_friction.overall_score, 4)

        freq_ratio = None
        if baseline_recovery.interruption_frequency > 0:
            freq_ratio = round(
                current_recovery.interruption_frequency / baseline_recovery.interruption_frequency,
                4,
            )

        # Determine trend direction
        trend = "STABLE"
        target_ratio = fric_ratio or lag_ratio
        if target_ratio is not None:
            if target_ratio > 1.15:
                trend = "ELEVATED_FRICTION"
            elif target_ratio < 0.85:
                trend = "IMPROVING"

        return PersonalBaselineResponse(
            user_id=user_id,
            baseline_period_days=baseline_period_days,
            baseline_mean_resumption_lag=baseline_recovery.mean_resumption_lag_seconds,
            baseline_friction_score=baseline_friction.overall_score,
            baseline_interruption_frequency=baseline_recovery.interruption_frequency,
            current_mean_resumption_lag=current_recovery.mean_resumption_lag_seconds,
            current_friction_score=current_friction.overall_score,
            current_interruption_frequency=current_recovery.interruption_frequency,
            resumption_lag_ratio=lag_ratio,
            friction_ratio=fric_ratio,
            interruption_frequency_ratio=freq_ratio,
            trend_direction=trend,
            has_sufficient_history=True,
        )

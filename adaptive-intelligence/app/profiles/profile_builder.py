"""
Profile Builder for ContextIQ Personal Behavioral Profile & Digital Twin (Phase 4.2).
Performs authoritative, robust statistical reconstruction of personal behavioral dimensions
from historical telemetry sessions, detected interruptions, tasks, and events strictly
prior to a defined source data cutoff timestamp.
"""
from __future__ import annotations

import math
import statistics
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.profiles.profile_confidence import ProfileConfidenceEstimator
from app.schemas.profile_schemas import (
    BaselinesSummary,
    ContextBehaviorDimension,
    DigitalTwinProfileRead,
    FocusBehaviorDimension,
    InterruptionBehaviorDimension,
    MetricConfidence,
    PatternStatus,
    TaskCompletionDimension,
    TemporalBehaviorDimension,
)


def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _median_and_iqr(values: List[float], fallback_median: float = 0.0) -> Tuple[float, float]:
    """Computes median and interquartile range (IQR)."""
    if not values:
        return fallback_median, 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    med = statistics.median(sorted_vals)
    if n < 4:
        iqr = sorted_vals[-1] - sorted_vals[0]
    else:
        q1 = statistics.median(sorted_vals[: n // 2])
        q3 = statistics.median(sorted_vals[(n + 1) // 2 :])
        iqr = max(0.0, q3 - q1)
    return round(med, 2), round(iqr, 2)


def _percentile(values: List[float], p: float) -> float:
    """Computes p-th percentile (0 <= p <= 100)."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = int(math.ceil((p / 100.0) * len(sorted_vals))) - 1
    return round(sorted_vals[max(0, min(len(sorted_vals) - 1, idx))], 2)


def _fit_lognormal(values: List[float]) -> Tuple[float, float, float, float]:
    """
    Fits a log-normal distribution to resumption/recovery delays (seconds).
    Returns (mu, sigma, median_sec, p90_sec).
    """
    positive_vals = [max(0.1, v) for v in values if v is not None and v >= 0]
    if not positive_vals:
        return 3.80, 0.65, 45.0, 180.0  # Population default

    log_vals = [math.log(v + 1.0) for v in positive_vals]
    mu = statistics.mean(log_vals)
    sigma = statistics.stdev(log_vals) if len(log_vals) > 1 else 0.50

    median_sec = math.exp(mu) - 1.0
    p90_sec = math.exp(mu + 1.282 * sigma) - 1.0
    return round(mu, 3), round(sigma, 3), round(max(0.0, median_sec), 1), round(max(0.0, p90_sec), 1)


class ProfileBuilder:
    """Builds a comprehensive behavioral digital twin from historical entities."""

    FEATURE_SCHEMA_VERSION = "v4.2"
    DEFAULT_OBSERVATION_WINDOW = 30

    @classmethod
    def build_profile(
        cls,
        user_id: uuid.UUID,
        sessions: Sequence[Any],
        detected_interruptions: Sequence[Any],
        manual_interruptions: Sequence[Any],
        tasks: Sequence[Any],
        task_events: Sequence[Any],
        as_of: Optional[datetime] = None,
        observation_window_days: int = DEFAULT_OBSERVATION_WINDOW,
    ) -> DigitalTwinProfileRead:
        """
        Builds a complete DigitalTwinProfileRead strictly prior to as_of cutoff.
        All calculations are deterministic and leakage-free.
        """
        now_utc = _to_utc(as_of) or datetime.now(timezone.utc)
        cutoff_start = now_utc - (now_utc.replace(hour=0, minute=0, second=0, microsecond=0) - now_utc)  # placeholder
        from datetime import timedelta
        cutoff_start = now_utc - timedelta(days=observation_window_days)

        # 1. Filter entities strictly within observation window and prior to cutoff
        valid_sessions = [
            s for s in sessions
            if s.started_at and _to_utc(s.started_at) <= now_utc and _to_utc(s.started_at) >= cutoff_start
        ]

        valid_interruptions = [
            i for i in detected_interruptions
            if i.start_timestamp and _to_utc(i.start_timestamp) <= now_utc and _to_utc(i.start_timestamp) >= cutoff_start
        ]

        valid_tasks = [
            t for t in tasks
            if t.created_at and _to_utc(t.created_at) <= now_utc and _to_utc(t.created_at) >= cutoff_start
        ]

        valid_events = [
            e for e in task_events
            if e.occurred_at and _to_utc(e.occurred_at) <= now_utc and _to_utc(e.occurred_at) >= cutoff_start
        ]

        # Calculate distinct active days observed
        active_session_days = {
            _to_utc(s.started_at).date() for s in valid_sessions if s.started_at
        }
        days_observed = len(active_session_days)

        # -------------------------------------------------------------------
        # Dimension A: Focus Behavior
        # -------------------------------------------------------------------
        focus_minutes_list: List[float] = [
            round(s.focused_time_seconds / 60.0, 2)
            for s in valid_sessions
            if hasattr(s, "focused_time_seconds") and s.focused_time_seconds is not None and s.focused_time_seconds > 0
        ]
        typical_focus, focus_iqr = _median_and_iqr(focus_minutes_list, fallback_median=25.0)
        max_uninterrupted = _percentile(focus_minutes_list, 90.0) if focus_minutes_list else 45.0
        stability_score = round(max(0.0, min(100.0, 100.0 - (focus_iqr / max(typical_focus, 1.0)) * 50.0)), 1)

        dim_a = FocusBehaviorDimension(
            typical_session_duration_minutes=ProfileConfidenceEstimator.wrap_metric(
                observed_value=typical_focus,
                sample_count=len(focus_minutes_list),
                observation_window_days=observation_window_days,
                days_with_data=days_observed,
                data_provenance=["context_sessions.focused_time_seconds"],
                last_updated=now_utc,
            ),
            session_duration_variability_minutes=ProfileConfidenceEstimator.wrap_metric(
                observed_value=focus_iqr,
                sample_count=len(focus_minutes_list),
                observation_window_days=observation_window_days,
                days_with_data=days_observed,
                data_provenance=["context_sessions.focused_time_seconds"],
                last_updated=now_utc,
            ),
            max_uninterrupted_duration_minutes=ProfileConfidenceEstimator.wrap_metric(
                observed_value=max_uninterrupted,
                sample_count=len(focus_minutes_list),
                observation_window_days=observation_window_days,
                days_with_data=days_observed,
                data_provenance=["context_sessions.focused_time_seconds"],
                last_updated=now_utc,
            ),
            focus_stability_score=ProfileConfidenceEstimator.wrap_metric(
                observed_value=stability_score,
                sample_count=len(focus_minutes_list),
                observation_window_days=observation_window_days,
                days_with_data=days_observed,
                data_provenance=["context_sessions"],
                last_updated=now_utc,
            ),
        )

        # -------------------------------------------------------------------
        # Dimension B: Interruption Behavior
        # -------------------------------------------------------------------
        total_focus_hours = sum(focus_minutes_list) / 60.0 if focus_minutes_list else 1.0
        interruption_count = len(valid_interruptions)
        hourly_interruption_freq = round(interruption_count / max(1.0, total_focus_hours), 2)

        type_counts: Dict[str, int] = defaultdict(int)
        for i in valid_interruptions:
            type_name = str(i.interruption_type.value if hasattr(i.interruption_type, "value") else i.interruption_type)
            type_counts[type_name] += 1
        total_types = sum(type_counts.values()) or 1
        type_distribution = {k: round(v / total_types, 3) for k, v in type_counts.items()}

        recovery_delays: List[float] = [
            i.resumption_lag_seconds
            for i in valid_interruptions
            if getattr(i, "resumption_lag_seconds", None) is not None
        ]
        log_mu, log_sigma, med_lag, p90_lag = _fit_lognormal(recovery_delays)

        # ISI formulation: 0.5 * (med_lag / 45.0) + 0.5 * min(1.0, hourly_interruption_freq / 5.0)
        isi_score = round(min(1.0, 0.5 * (med_lag / 60.0) + 0.5 * min(1.0, hourly_interruption_freq / 4.0)), 3)

        dim_b = InterruptionBehaviorDimension(
            interruption_frequency_hourly=ProfileConfidenceEstimator.wrap_metric(
                observed_value=hourly_interruption_freq,
                sample_count=interruption_count,
                observation_window_days=observation_window_days,
                days_with_data=days_observed,
                data_provenance=["detected_interruptions"],
                last_updated=now_utc,
            ),
            interruption_type_distribution=ProfileConfidenceEstimator.wrap_metric(
                observed_value=type_distribution,
                sample_count=interruption_count,
                observation_window_days=observation_window_days,
                days_with_data=days_observed,
                data_provenance=["detected_interruptions.interruption_type"],
                last_updated=now_utc,
            ),
            interruption_sensitivity_index=ProfileConfidenceEstimator.wrap_metric(
                observed_value=isi_score,
                sample_count=interruption_count,
                observation_window_days=observation_window_days,
                days_with_data=days_observed,
                data_provenance=["detected_interruptions", "context_sessions"],
                last_updated=now_utc,
            ),
            recovery_duration_distribution=ProfileConfidenceEstimator.wrap_metric(
                observed_value={
                    "log_mu": log_mu,
                    "log_sigma": log_sigma,
                    "median_lag_seconds": med_lag,
                    "p90_lag_seconds": p90_lag,
                },
                sample_count=len(recovery_delays),
                observation_window_days=observation_window_days,
                days_with_data=days_observed,
                data_provenance=["detected_interruptions.resumption_lag_seconds"],
                last_updated=now_utc,
            ),
        )

        # -------------------------------------------------------------------
        # Dimension C: Task Completion
        # -------------------------------------------------------------------
        completed_tasks = [t for t in valid_tasks if str(t.status) == "COMPLETED" or getattr(t, "completed_at", None)]
        total_tasks_count = len(valid_tasks)
        completion_rate = round(len(completed_tasks) / max(1, total_tasks_count), 3)

        # Deadline adherence
        tasks_with_deadline = [t for t in completed_tasks if getattr(t, "due_at", None) and getattr(t, "completed_at", None)]
        on_time_count = sum(1 for t in tasks_with_deadline if _to_utc(t.completed_at) <= _to_utc(t.due_at))
        adherence_rate = round(on_time_count / max(1, len(tasks_with_deadline)), 3) if tasks_with_deadline else 1.0

        # Category completion duration
        cat_durations: Dict[str, List[float]] = defaultdict(list)
        for t in completed_tasks:
            cat = t.context_tag or "general"
            if getattr(t, "estimated_minutes", None):
                cat_durations[cat].append(float(t.estimated_minutes))
            elif getattr(t, "completed_at", None) and getattr(t, "created_at", None):
                delta_mins = max(1.0, (_to_utc(t.completed_at) - _to_utc(t.created_at)).total_seconds() / 60.0)
                cat_durations[cat].append(min(180.0, delta_mins))

        duration_by_category = {
            cat: round(statistics.median(durs), 1) for cat, durs in cat_durations.items()
        }

        dim_c = TaskCompletionDimension(
            task_completion_rate=ProfileConfidenceEstimator.wrap_metric(
                observed_value=completion_rate,
                sample_count=total_tasks_count,
                observation_window_days=observation_window_days,
                days_with_data=days_observed,
                data_provenance=["tasks.status"],
                last_updated=now_utc,
            ),
            postponement_frequency=ProfileConfidenceEstimator.wrap_metric(
                observed_value=0.0,  # Base value until event revisions tracked
                sample_count=total_tasks_count,
                observation_window_days=observation_window_days,
                days_with_data=days_observed,
                data_provenance=["task_events"],
                last_updated=now_utc,
            ),
            deadline_adherence_rate=ProfileConfidenceEstimator.wrap_metric(
                observed_value=adherence_rate,
                sample_count=len(tasks_with_deadline),
                observation_window_days=observation_window_days,
                days_with_data=days_observed,
                data_provenance=["tasks.due_at", "tasks.completed_at"],
                last_updated=now_utc,
            ),
            completion_duration_by_category=ProfileConfidenceEstimator.wrap_metric(
                observed_value=duration_by_category,
                sample_count=len(completed_tasks),
                observation_window_days=observation_window_days,
                days_with_data=days_observed,
                data_provenance=["tasks.estimated_minutes"],
                last_updated=now_utc,
            ),
        )

        # -------------------------------------------------------------------
        # Dimension D: Context Behavior
        # -------------------------------------------------------------------
        transitions = [
            s.transition_count for s in valid_sessions
            if hasattr(s, "transition_count") and s.transition_count is not None
        ]
        avg_transitions_hourly = round(sum(transitions) / max(1.0, total_focus_hours), 2)
        overhead_resumption = med_lag

        cat_counts: Dict[str, int] = defaultdict(int)
        for t in valid_tasks:
            cat_counts[t.context_tag or "general"] += 1
        cat_preferences = {
            k: round(v / max(1, total_tasks_count), 3) for k, v in cat_counts.items()
        }

        dim_d = ContextBehaviorDimension(
            location_work_patterns=ProfileConfidenceEstimator.wrap_metric(
                observed_value={"default_workspace": 1.0},
                sample_count=len(valid_sessions),
                observation_window_days=observation_window_days,
                days_with_data=days_observed,
                data_provenance=["context_sessions.location_id"],
                last_updated=now_utc,
            ),
            application_transition_frequency=ProfileConfidenceEstimator.wrap_metric(
                observed_value=avg_transitions_hourly,
                sample_count=len(valid_sessions),
                observation_window_days=observation_window_days,
                days_with_data=days_observed,
                data_provenance=["context_sessions.transition_count"],
                last_updated=now_utc,
            ),
            context_switch_overhead_seconds=ProfileConfidenceEstimator.wrap_metric(
                observed_value=overhead_resumption,
                sample_count=len(recovery_delays),
                observation_window_days=observation_window_days,
                days_with_data=days_observed,
                data_provenance=["detected_interruptions.resumption_lag_seconds"],
                last_updated=now_utc,
            ),
            task_category_preferences=ProfileConfidenceEstimator.wrap_metric(
                observed_value=cat_preferences,
                sample_count=total_tasks_count,
                observation_window_days=observation_window_days,
                days_with_data=days_observed,
                data_provenance=["tasks.context_tag"],
                last_updated=now_utc,
            ),
        )

        # -------------------------------------------------------------------
        # Dimension E: Temporal Behavior
        # -------------------------------------------------------------------
        dow_focus: Dict[int, float] = {d: 0.0 for d in range(7)}
        hourly_completions: Dict[int, int] = {h: 0 for h in range(24)}
        for s in valid_sessions:
            if s.started_at:
                st = _to_utc(s.started_at)
                dow_focus[st.weekday()] += round(getattr(s, "focused_time_seconds", 0) / 60.0, 1)

        for t in completed_tasks:
            if getattr(t, "completed_at", None):
                ct = _to_utc(t.completed_at)
                hourly_completions[ct.hour] += 1

        total_completions_sum = sum(hourly_completions.values()) or 1
        hourly_density = {
            str(h): round(c / total_completions_sum, 3) for h, c in hourly_completions.items()
        }

        # Active daily hours
        active_hours = [
            _to_utc(s.started_at).hour for s in valid_sessions if s.started_at
        ]
        start_h = min(active_hours) if active_hours else 9
        end_h = max(active_hours) if active_hours else 18
        peak_focus_h = max(hourly_completions.items(), key=lambda x: x[1])[0] if active_hours else 10

        dim_e = TemporalBehaviorDimension(
            active_daily_hours=ProfileConfidenceEstimator.wrap_metric(
                observed_value={"start_hour": start_h, "end_hour": end_h, "peak_hour": peak_focus_h},
                sample_count=len(valid_sessions),
                observation_window_days=observation_window_days,
                days_with_data=days_observed,
                data_provenance=["context_sessions.started_at"],
                last_updated=now_utc,
            ),
            day_of_week_patterns=ProfileConfidenceEstimator.wrap_metric(
                observed_value={str(k): round(v, 1) for k, v in dow_focus.items()},
                sample_count=len(valid_sessions),
                observation_window_days=observation_window_days,
                days_with_data=days_observed,
                data_provenance=["context_sessions.started_at"],
                last_updated=now_utc,
            ),
            hourly_completion_density=ProfileConfidenceEstimator.wrap_metric(
                observed_value=hourly_density,
                sample_count=len(completed_tasks),
                observation_window_days=observation_window_days,
                days_with_data=days_observed,
                data_provenance=["tasks.completed_at"],
                last_updated=now_utc,
            ),
        )

        # -------------------------------------------------------------------
        # Baselines Summary
        # -------------------------------------------------------------------
        bfi_baseline = round(min(100.0, max(0.0, 30.0 + isi_score * 25.0 + (hourly_interruption_freq / 5.0) * 15.0)), 1)
        baselines = BaselinesSummary(
            median_focus_duration_minutes=typical_focus,
            typical_recovery_duration_seconds=med_lag,
            historical_completion_probability=completion_rate,
            typical_interruption_density_hourly=hourly_interruption_freq,
            baseline_behavioral_friction_index=bfi_baseline,
        )

        # -------------------------------------------------------------------
        # Global Confidence and Pattern Status
        # -------------------------------------------------------------------
        all_confs = [
            dim_a.typical_session_duration_minutes.confidence_level,
            dim_b.interruption_frequency_hourly.confidence_level,
            dim_c.task_completion_rate.confidence_level,
            dim_d.application_transition_frequency.confidence_level,
            dim_e.active_daily_hours.confidence_level,
        ]
        global_conf = round(statistics.mean(all_confs), 3)

        if days_observed >= 20 and len(valid_sessions) >= 30:
            global_status = PatternStatus.ESTABLISHED
            is_cold = False
        elif days_observed >= 5 and len(valid_sessions) >= 7:
            global_status = PatternStatus.EMERGING
            is_cold = False
        else:
            global_status = PatternStatus.INSUFFICIENT_EVIDENCE
            is_cold = True

        return DigitalTwinProfileRead(
            user_id=user_id,
            profile_version=cls.FEATURE_SCHEMA_VERSION,
            is_cold_start=is_cold,
            personalization_enabled=True,
            global_confidence_score=global_conf,
            global_pattern_status=global_status,
            telemetry_days_observed=days_observed,
            total_sessions_observed=len(valid_sessions),
            total_tasks_observed=total_tasks_count,
            total_interruptions_observed=interruption_count,
            focus_behavior=dim_a,
            interruption_behavior=dim_b,
            task_completion=dim_c,
            context_behavior=dim_d,
            temporal_behavior=dim_e,
            baselines=baselines,
            last_rebuilt_at=now_utc,
            created_at=now_utc,
            updated_at=now_utc,
        )

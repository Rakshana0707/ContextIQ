"""
Incremental Profile Updater for ContextIQ Personal Behavioral Profile (Phase 4.2).
Provides high-efficiency O(1) online updates for newly arriving sessions, completed tasks,
confirmed interruptions, and explicit feedback without requiring full historical recomputation.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.profiles.profile_confidence import ProfileConfidenceEstimator
from app.schemas.profile_schemas import DigitalTwinProfileRead, MetricConfidence, PatternStatus


def _to_utc(dt: Optional[datetime]) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class ProfileUpdater:
    """Performs incremental updates to an existing DigitalTwinProfileRead."""

    @classmethod
    def update_with_session(
        cls,
        profile: DigitalTwinProfileRead,
        session_id: str,
        focused_time_seconds: float,
        transition_count: int = 0,
        started_at: Optional[datetime] = None,
    ) -> DigitalTwinProfileRead:
        """Incrementally incorporates a newly completed context session."""
        now = _to_utc(started_at)
        focus_mins = max(0.0, focused_time_seconds / 60.0)

        profile.total_sessions_observed += 1
        n_sessions = profile.total_sessions_observed

        old_focus_metric = profile.focus_behavior.typical_session_duration_minutes
        old_val = float(old_focus_metric.observed_value)
        alpha = min(0.20, 2.0 / (n_sessions + 1.0))
        new_val = round((1.0 - alpha) * old_val + alpha * focus_mins, 2)

        profile.focus_behavior.typical_session_duration_minutes = ProfileConfidenceEstimator.wrap_metric(
            observed_value=new_val,
            sample_count=n_sessions,
            observation_window_days=old_focus_metric.observation_window_days,
            days_with_data=min(old_focus_metric.observation_window_days, profile.telemetry_days_observed + 1),
            data_provenance=old_focus_metric.data_provenance,
            last_updated=now,
        )

        old_trans = profile.context_behavior.application_transition_frequency
        old_trans_val = float(old_trans.observed_value)
        new_trans_val = round((1.0 - alpha) * old_trans_val + alpha * transition_count, 2)
        profile.context_behavior.application_transition_frequency = ProfileConfidenceEstimator.wrap_metric(
            observed_value=new_trans_val,
            sample_count=n_sessions,
            observation_window_days=old_trans.observation_window_days,
            days_with_data=min(old_trans.observation_window_days, profile.telemetry_days_observed + 1),
            data_provenance=old_trans.data_provenance,
            last_updated=now,
        )

        dow_metric = profile.temporal_behavior.day_of_week_patterns
        dow_map = dict(dow_metric.observed_value) if isinstance(dow_metric.observed_value, dict) else {}
        weekday_key = str(now.weekday())
        dow_map[weekday_key] = round(dow_map.get(weekday_key, 0.0) + focus_mins, 1)
        profile.temporal_behavior.day_of_week_patterns.observed_value = dow_map

        profile.baselines.median_focus_duration_minutes = new_val
        profile.updated_at = now
        cls._refresh_global_status(profile)
        return profile

    @classmethod
    def update_with_task_completed(
        cls,
        profile: DigitalTwinProfileRead,
        task_id: str,
        category: Optional[str] = None,
        estimated_minutes: Optional[int] = None,
        completed_at: Optional[datetime] = None,
        due_at: Optional[datetime] = None,
    ) -> DigitalTwinProfileRead:
        """Incrementally incorporates a task completion event."""
        now = _to_utc(completed_at)
        profile.total_tasks_observed += 1
        n_tasks = profile.total_tasks_observed

        old_comp = profile.task_completion.task_completion_rate
        old_rate = float(old_comp.observed_value)
        new_rate = round((old_rate * (n_tasks - 1) + 1.0) / n_tasks, 3)

        profile.task_completion.task_completion_rate = ProfileConfidenceEstimator.wrap_metric(
            observed_value=new_rate,
            sample_count=n_tasks,
            observation_window_days=old_comp.observation_window_days,
            days_with_data=min(old_comp.observation_window_days, profile.telemetry_days_observed + 1),
            data_provenance=old_comp.data_provenance,
            last_updated=now,
        )

        if due_at:
            is_on_time = now <= _to_utc(due_at)
            old_adh = profile.task_completion.deadline_adherence_rate
            old_adh_val = float(old_adh.observed_value)
            new_adh_val = round((old_adh_val * old_adh.observation_count + (1.0 if is_on_time else 0.0)) / (old_adh.observation_count + 1), 3)
            profile.task_completion.deadline_adherence_rate = ProfileConfidenceEstimator.wrap_metric(
                observed_value=new_adh_val,
                sample_count=old_adh.observation_count + 1,
                observation_window_days=old_adh.observation_window_days,
                days_with_data=min(old_adh.observation_window_days, profile.telemetry_days_observed + 1),
                data_provenance=old_adh.data_provenance,
                last_updated=now,
            )

        if category and estimated_minutes:
            cat_metric = profile.task_completion.completion_duration_by_category
            cat_map = dict(cat_metric.observed_value) if isinstance(cat_metric.observed_value, dict) else {}
            old_cat_val = cat_map.get(category, float(estimated_minutes))
            cat_map[category] = round(0.8 * old_cat_val + 0.2 * float(estimated_minutes), 1)
            profile.task_completion.completion_duration_by_category.observed_value = cat_map

        density_metric = profile.temporal_behavior.hourly_completion_density
        density_map = dict(density_metric.observed_value) if isinstance(density_metric.observed_value, dict) else {}
        hour_key = str(now.hour)
        density_map[hour_key] = round(density_map.get(hour_key, 0.0) + 0.05, 3)
        profile.temporal_behavior.hourly_completion_density.observed_value = density_map

        profile.baselines.historical_completion_probability = new_rate
        profile.updated_at = now
        cls._refresh_global_status(profile)
        return profile

    @classmethod
    def update_with_interruption(
        cls,
        profile: DigitalTwinProfileRead,
        interruption_type: str,
        resumption_lag_seconds: Optional[float] = None,
        start_timestamp: Optional[datetime] = None,
    ) -> DigitalTwinProfileRead:
        """Incrementally incorporates a confirmed interruption event."""
        now = _to_utc(start_timestamp)
        profile.total_interruptions_observed += 1
        n_interruptions = profile.total_interruptions_observed

        dist_metric = profile.interruption_behavior.interruption_type_distribution
        dist_map = dict(dist_metric.observed_value) if isinstance(dist_metric.observed_value, dict) else {}
        dist_map[interruption_type] = dist_map.get(interruption_type, 0.0) + 1.0
        tot = sum(dist_map.values())
        norm_dist = {k: round(v / tot, 3) for k, v in dist_map.items()}
        profile.interruption_behavior.interruption_type_distribution = ProfileConfidenceEstimator.wrap_metric(
            observed_value=norm_dist,
            sample_count=n_interruptions,
            observation_window_days=dist_metric.observation_window_days,
            days_with_data=min(dist_metric.observation_window_days, profile.telemetry_days_observed + 1),
            data_provenance=dist_metric.data_provenance,
            last_updated=now,
        )

        if resumption_lag_seconds is not None and resumption_lag_seconds >= 0:
            rec_metric = profile.interruption_behavior.recovery_duration_distribution
            rec_data = dict(rec_metric.observed_value) if isinstance(rec_metric.observed_value, dict) else {}
            old_med = float(rec_data.get("median_lag_seconds", 45.0))
            new_med = round(0.85 * old_med + 0.15 * resumption_lag_seconds, 1)
            rec_data["median_lag_seconds"] = new_med
            profile.interruption_behavior.recovery_duration_distribution.observed_value = rec_data
            profile.baselines.typical_recovery_duration_seconds = new_med

        profile.updated_at = now
        cls._refresh_global_status(profile)
        return profile

    @classmethod
    def _refresh_global_status(cls, profile: DigitalTwinProfileRead) -> None:
        """Updates global confidence score and cold start status."""
        confs = [
            profile.focus_behavior.typical_session_duration_minutes.confidence_level,
            profile.interruption_behavior.interruption_frequency_hourly.confidence_level,
            profile.task_completion.task_completion_rate.confidence_level,
            profile.context_behavior.application_transition_frequency.confidence_level,
        ]
        profile.global_confidence_score = round(sum(confs) / len(confs), 3)
        if profile.total_sessions_observed >= 30:
            profile.global_pattern_status = PatternStatus.ESTABLISHED
            profile.is_cold_start = False
        elif profile.total_sessions_observed >= 7:
            profile.global_pattern_status = PatternStatus.EMERGING
            profile.is_cold_start = False
        else:
            profile.global_pattern_status = PatternStatus.INSUFFICIENT_EVIDENCE
            profile.is_cold_start = True

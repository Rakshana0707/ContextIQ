"""
Temporal Feature Aggregator for ContextIQ Focus Window Discovery (Phase 4.3).
Aggregates historical behavioral telemetry, tasks, and interruptions into circadian
time buckets with timezone-aware conversions and task-category conditioning.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.schemas.focus_window import HourlyTemporalMetrics


def _get_tz(tz_name: Optional[str]) -> ZoneInfo:
    """Returns valid ZoneInfo, defaulting to UTC if missing or invalid."""
    if not tz_name:
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def _normalize_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _to_user_local(dt: Optional[datetime], tz: ZoneInfo) -> Optional[datetime]:
    """Converts a UTC or naive datetime to user local time."""
    normalized = _normalize_utc(dt)
    if normalized is None:
        return None
    return normalized.astimezone(tz)


class TemporalFeatureAggregator:
    """Extracts 24-hour circadian metrics from historical entities."""

    @classmethod
    def aggregate_hourly_metrics(
        cls,
        sessions: Sequence[Any],
        tasks: Sequence[Any],
        interruptions: Sequence[Any],
        user_timezone: str = "UTC",
        category_filter: Optional[str] = None,
        as_of: Optional[datetime] = None,
        observation_window_days: int = 30,
    ) -> List[HourlyTemporalMetrics]:
        """
        Computes 24-hour temporal metrics strictly prior to as_of cutoff,
        conditioned on user timezone and optional task category filter.
        """
        tz = _get_tz(user_timezone)
        cutoff_utc = _normalize_utc(as_of)
        if cutoff_utc is None:
            now_utc = datetime.now(timezone.utc)
            session_times = [
                _normalize_utc(getattr(s, "started_at", None))
                for s in sessions
                if getattr(s, "started_at", None)
            ]
            latest_session = max(session_times) if session_times else None
            if latest_session and (now_utc - latest_session).days > observation_window_days:
                cutoff_utc = latest_session + timedelta(hours=1)
            else:
                cutoff_utc = now_utc
        window_start_utc = cutoff_utc - timedelta(days=observation_window_days)

        # 1. Filter sessions
        filtered_sessions = []
        for s in sessions:
            st = _normalize_utc(getattr(s, "started_at", None))
            if st and st <= cutoff_utc and st >= window_start_utc:
                if category_filter is None or getattr(s, "context_tag", None) == category_filter:
                    filtered_sessions.append(s)

        # 2. Filter tasks
        filtered_tasks = []
        for t in tasks:
            ct = _normalize_utc(getattr(t, "created_at", None))
            if ct and ct <= cutoff_utc and ct >= window_start_utc:
                if category_filter is None or getattr(t, "context_tag", None) == category_filter:
                    filtered_tasks.append(t)

        # 3. Filter interruptions
        filtered_interruptions = []
        for i in interruptions:
            it = _normalize_utc(getattr(i, "start_timestamp", None))
            if it and it <= cutoff_utc and it >= window_start_utc:
                filtered_interruptions.append(i)


        # Buckets for each hour 0..23
        session_focus_by_hour: Dict[int, List[float]] = defaultdict(list)
        session_transitions_by_hour: Dict[int, List[int]] = defaultdict(list)
        session_active_days_by_hour: Dict[int, set] = defaultdict(set)

        tasks_completed_by_hour: Dict[int, int] = defaultdict(int)
        tasks_uncompleted_created_by_hour: Dict[int, int] = defaultdict(int)

        interruptions_by_hour: Dict[int, int] = defaultdict(int)
        resumption_lags_by_hour: Dict[int, List[float]] = defaultdict(list)

        # Process Sessions
        for s in filtered_sessions:
            local_start = _to_user_local(s.started_at, tz)
            if not local_start:
                continue
            h = local_start.hour
            focus_mins = max(0.0, getattr(s, "focused_time_seconds", 0.0) / 60.0)
            transitions = getattr(s, "transition_count", 0) or 0

            session_focus_by_hour[h].append(focus_mins)
            session_transitions_by_hour[h].append(transitions)
            session_active_days_by_hour[h].add(local_start.date())

        # Process Tasks
        for t in filtered_tasks:
            created_local = _to_user_local(t.created_at, tz)
            comp_local = _to_user_local(t.completed_at, tz) if getattr(t, "completed_at", None) else None

            if comp_local:
                tasks_completed_by_hour[comp_local.hour] += 1

            if created_local:
                # If uncompleted or completed in a different hour/day, count as uncompleted in created hour
                if not comp_local or comp_local.hour != created_local.hour or comp_local.date() != created_local.date():
                    tasks_uncompleted_created_by_hour[created_local.hour] += 1

        # Process Interruptions
        for i in filtered_interruptions:
            int_local = _to_user_local(i.start_timestamp, tz)
            if not int_local:
                continue
            h = int_local.hour
            interruptions_by_hour[h] += 1
            lag = getattr(i, "resumption_lag_seconds", None)
            if lag is not None and lag >= 0:
                resumption_lags_by_hour[h].append(float(lag))

        # Distinct total active days
        total_active_days = len({
            _to_user_local(s.started_at, tz).date()
            for s in filtered_sessions if s.started_at
        }) or 1

        # Find max focus for scaling
        all_mean_focuses = [
            statistics.mean(session_focus_by_hour[h]) if session_focus_by_hour[h] else 0.0
            for h in range(24)
        ]
        max_focus = max(all_mean_focuses) or 1.0

        # Construct HourlyTemporalMetrics
        hourly_results: List[HourlyTemporalMetrics] = []
        for h in range(24):
            focus_list = session_focus_by_hour[h]
            mean_focus = round(statistics.mean(focus_list), 1) if focus_list else 0.0
            focus_hours = (sum(focus_list) / 60.0) if focus_list else 0.0

            n_completed = tasks_completed_by_hour[h]
            n_uncompleted = tasks_uncompleted_created_by_hour[h]
            total_relevant_tasks = n_completed + n_uncompleted
            completion_rate = round(n_completed / total_relevant_tasks, 3) if total_relevant_tasks > 0 else 0.0

            n_interruptions = interruptions_by_hour[h]
            int_density = round(n_interruptions / max(1.0, focus_hours), 2) if focus_hours > 0 else 0.0

            lags = resumption_lags_by_hour[h]
            med_lag = round(statistics.median(lags), 1) if lags else 45.0

            trans_list = session_transitions_by_hour[h]
            switch_freq = round(sum(trans_list) / max(1.0, focus_hours), 1) if focus_hours > 0 else 0.0

            consistency = len(session_active_days_by_hour[h]) / max(1, total_active_days)
            obs_count = len(focus_list) + n_completed + n_uncompleted + n_interruptions

            # Multi-objective Focus Quality Function Q(h)
            # Crucial: High activity with 0 completions & high disruptions gets a low score!
            f_norm = min(1.0, mean_focus / max_focus)
            int_penalty = min(1.0, int_density / 6.0)
            lag_penalty = min(1.0, med_lag / 120.0)

            # Quality Score formulation (0 to 100)
            raw_q = 100.0 * (
                0.25 * f_norm +
                0.30 * completion_rate +
                0.15 * (1.0 - int_penalty) +
                0.15 * (1.0 - lag_penalty) +
                0.15 * min(1.0, consistency)
            )
            q_score = round(max(0.0, min(100.0, raw_q)), 1)
            is_prime = (q_score >= 60.0 and (mean_focus >= 20.0 or completion_rate >= 0.50))

            hourly_results.append(
                HourlyTemporalMetrics(
                    hour=h,
                    focus_minutes=mean_focus,
                    task_completion_rate=completion_rate,
                    interruption_density_hourly=int_density,
                    avg_resumption_lag_seconds=med_lag,
                    context_switch_frequency=switch_freq,
                    quality_score=q_score,
                    observation_count=obs_count,
                    is_prime_candidate=is_prime,
                )
            )

        return hourly_results

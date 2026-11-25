"""
Focus Window Discovery Engine for ContextIQ (Phase 4.3).
Identifies recurrent personal productivity intervals, evaluates circular temporal smoothing,
delineates continuous focus blocks, conditions on task categories, and synthesizes grounded insights.
"""
from __future__ import annotations

import math
import statistics
import uuid
from datetime import datetime, time, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.profiles.temporal_feature_aggregator import TemporalFeatureAggregator
from app.schemas.focus_window import (
    CategoryFocusWindowRead,
    FocusWindowItemRead,
    FocusWindowMetricsResponse,
    HourlyTemporalMetrics,
)
from app.schemas.profile_schemas import PatternStatus


class FocusWindowDiscoveryEngine:
    """Core computational discovery engine for personal focus windows."""

    QUALITY_THRESHOLD = 58.0
    MIN_OBSERVATIONS_EMERGING = 5
    MIN_OBSERVATIONS_ESTABLISHED = 20

    @classmethod
    def discover_focus_windows(
        cls,
        user_id: uuid.UUID,
        sessions: Sequence[Any],
        tasks: Sequence[Any],
        interruptions: Sequence[Any],
        user_timezone: str = "UTC",
        category_filter: Optional[str] = None,
        as_of: Optional[datetime] = None,
        observation_window_days: int = 30,
    ) -> List[FocusWindowItemRead]:
        """
        Discovers continuous, high-quality focus intervals from behavioral telemetry.
        Never forces artificial clusters when data does not support them.
        """
        now = as_of or datetime.now(timezone.utc)

        # 1. Aggregate 24-hour circadian metrics
        hourly_metrics = TemporalFeatureAggregator.aggregate_hourly_metrics(
            sessions=sessions,
            tasks=tasks,
            interruptions=interruptions,
            user_timezone=user_timezone,
            category_filter=category_filter,
            as_of=as_of,
            observation_window_days=observation_window_days,
        )

        total_obs = sum(m.observation_count for m in hourly_metrics)

        # 2. Check for insufficient data
        if total_obs < cls.MIN_OBSERVATIONS_EMERGING:
            return []

        # 3. Apply circular 3-hour smoothing to Quality Scores:
        # Q_smooth(h) = 0.25*Q((h-1)%24) + 0.50*Q(h) + 0.25*Q((h+1)%24)
        smoothed_q: List[float] = []
        for h in range(24):
            prev_q = hourly_metrics[(h - 1) % 24].quality_score
            curr_q = hourly_metrics[h].quality_score
            next_q = hourly_metrics[(h + 1) % 24].quality_score
            sq = 0.25 * prev_q + 0.50 * curr_q + 0.25 * next_q
            smoothed_q.append(round(sq, 1))

        # 4. Check if data is completely uniform / diffuse (no distinct peak)
        q_mean = statistics.mean(smoothed_q)
        q_stdev = statistics.stdev(smoothed_q) if len(smoothed_q) > 1 else 0.0
        if q_stdev < 5.0 and q_mean < cls.QUALITY_THRESHOLD:
            # Data is flat with no distinct focus window
            return []

        # 5. Extract contiguous intervals where smoothed_q >= QUALITY_THRESHOLD or raw quality >= QUALITY_THRESHOLD
        prime_hour_flags = [
            (smoothed_q[h] >= cls.QUALITY_THRESHOLD) or (hourly_metrics[h].quality_score >= cls.QUALITY_THRESHOLD)
            for h in range(24)
        ]

        # Find continuous blocks of True
        blocks: List[List[int]] = []
        visited = set()
        for h in range(24):
            if prime_hour_flags[h] and h not in visited:
                block = [h]
                visited.add(h)
                # Walk forward
                next_h = (h + 1) % 24
                while prime_hour_flags[next_h] and next_h not in visited and next_h != h:
                    block.append(next_h)
                    visited.add(next_h)
                    next_h = (next_h + 1) % 24
                blocks.append(block)

        # Filter blocks by minimum duration (at least 1 hour, i.e. 60 min)
        discovered: List[FocusWindowItemRead] = []
        baseline_completion = statistics.mean([m.task_completion_rate for m in hourly_metrics]) or 0.10
        baseline_int_density = statistics.mean([m.interruption_density_hourly for m in hourly_metrics]) or 1.0

        for block in blocks:
            start_h = block[0]
            end_h = (block[-1] + 1) % 24
            duration_mins = len(block) * 60

            # Compute aggregated metrics inside this window
            window_metrics = [hourly_metrics[h] for h in block]
            w_obs = sum(m.observation_count for m in window_metrics)
            w_focus_density = round(statistics.mean([m.focus_minutes for m in window_metrics]) / 60.0, 3)
            w_completion = round(statistics.mean([m.task_completion_rate for m in window_metrics]), 3)
            w_int_density = round(statistics.mean([m.interruption_density_hourly for m in window_metrics]), 2)
            w_lag = round(statistics.median([m.avg_resumption_lag_seconds for m in window_metrics]), 1)
            w_quality = round(statistics.mean([max(smoothed_q[h], hourly_metrics[h].quality_score) for h in block]), 1)

            # Determine pattern status and confidence
            if w_obs >= cls.MIN_OBSERVATIONS_ESTABLISHED:
                status = PatternStatus.ESTABLISHED
                conf = min(1.0, 0.70 + 0.30 * min(1.0, w_obs / 40.0))
            else:
                status = PatternStatus.EMERGING
                conf = min(0.69, 0.35 + 0.34 * (w_obs / cls.MIN_OBSERVATIONS_ESTABLISHED))
            conf = round(conf, 2)

            # Synthesize grounded insights
            insights = cls._generate_grounded_insights(
                category=category_filter,
                start_h=start_h,
                end_h=end_h,
                w_completion=w_completion,
                base_completion=baseline_completion,
                w_int_density=w_int_density,
                base_int_density=baseline_int_density,
                w_focus_density=w_focus_density,
            )

            discovered.append(
                FocusWindowItemRead(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    task_category=category_filter,
                    day_of_week=None,  # Daily recurrent
                    start_time=time(hour=start_h, minute=0),
                    end_time=time(hour=end_h, minute=0),
                    duration_minutes=duration_mins,
                    quality_score=w_quality,
                    focus_density=min(1.0, w_focus_density),
                    completion_rate=w_completion,
                    interruption_density_hourly=w_int_density,
                    avg_resumption_lag_seconds=w_lag,
                    observation_count=w_obs,
                    confidence_score=conf,
                    pattern_status=status.value,
                    grounded_insights=insights,
                    is_active=True,
                    user_confirmed=False,
                    discovered_at=now,
                )
            )

        # Sort by quality score descending
        discovered.sort(key=lambda w: w.quality_score, reverse=True)
        return discovered

    @classmethod
    def discover_category_focus_windows(
        cls,
        user_id: uuid.UUID,
        category: str,
        sessions: Sequence[Any],
        tasks: Sequence[Any],
        interruptions: Sequence[Any],
        user_timezone: str = "UTC",
        as_of: Optional[datetime] = None,
        observation_window_days: int = 30,
    ) -> CategoryFocusWindowRead:
        """Discovers focus windows conditioned specifically on a task category."""
        # 1. Category-specific windows
        cat_windows = cls.discover_focus_windows(
            user_id=user_id,
            sessions=sessions,
            tasks=tasks,
            interruptions=interruptions,
            user_timezone=user_timezone,
            category_filter=category,
            as_of=as_of,
            observation_window_days=observation_window_days,
        )

        # Baseline completion across all categories
        all_metrics = TemporalFeatureAggregator.aggregate_hourly_metrics(
            sessions=sessions,
            tasks=tasks,
            interruptions=interruptions,
            user_timezone=user_timezone,
            category_filter=None,
            as_of=as_of,
            observation_window_days=observation_window_days,
        )
        base_completion = round(statistics.mean([m.task_completion_rate for m in all_metrics]) or 0.20, 3)

        if cat_windows:
            in_win_comp = cat_windows[0].completion_rate
            obs_count = sum(w.observation_count for w in cat_windows)
            lift = round(((in_win_comp - base_completion) / max(0.01, base_completion)) * 100.0, 1)
            insights = [
                f"Historical records show that '{category}' tasks achieve a {in_win_comp:.0%} completion rate "
                f"during detected focus windows, representing a {lift:+.1f}% lift over your daily baseline ({base_completion:.0%})."
            ]
        else:
            in_win_comp = base_completion
            obs_count = sum(1 for t in tasks if getattr(t, "context_tag", None) == category)
            lift = 0.0
            insights = [
                f"Insufficient historical data to isolate a category-specific focus cadence for '{category}'. "
                f"Recommendations will use your general focus schedule."
            ]

        return CategoryFocusWindowRead(
            category=category,
            observation_count=obs_count,
            baseline_completion_rate=base_completion,
            in_window_completion_rate=in_win_comp,
            completion_lift_percentage=lift,
            focus_windows=cat_windows,
            insights=insights,
        )

    @classmethod
    def get_metrics_summary(
        cls,
        user_id: uuid.UUID,
        sessions: Sequence[Any],
        tasks: Sequence[Any],
        interruptions: Sequence[Any],
        user_timezone: str = "UTC",
        as_of: Optional[datetime] = None,
        observation_window_days: int = 30,
    ) -> FocusWindowMetricsResponse:
        """Returns 24-hour circadian metrics and identifying peak vs fragmented hours."""
        hourly_metrics = TemporalFeatureAggregator.aggregate_hourly_metrics(
            sessions=sessions,
            tasks=tasks,
            interruptions=interruptions,
            user_timezone=user_timezone,
            category_filter=None,
            as_of=as_of,
            observation_window_days=observation_window_days,
        )

        peak_hours = [m.hour for m in hourly_metrics if m.is_prime_candidate]
        # Fragmented hours: high interruption density (> 3.0) or high context-switching (> 7.0) with low completion (< 0.25)
        fragmented_hours = [
            m.hour for m in hourly_metrics
            if (m.interruption_density_hourly >= 3.0 or m.context_switch_frequency >= 7.0)
            and m.task_completion_rate <= 0.30
        ]

        insights: List[str] = []
        if peak_hours:
            peak_str = ", ".join(f"{h:02d}:00" for h in peak_hours)
            insights.append(f"Observed peak cognitive throughput concentrated around {peak_str}.")
        if fragmented_hours:
            frag_str = ", ".join(f"{h:02d}:00" for h in fragmented_hours)
            insights.append(f"Elevated disruption and context switching detected around {frag_str}; well-suited for administrative batching.")

        return FocusWindowMetricsResponse(
            user_id=user_id,
            timezone=user_timezone,
            observation_window_days=observation_window_days,
            hourly_metrics=hourly_metrics,
            peak_focus_hours=peak_hours,
            fragmented_hours=fragmented_hours,
            insights=insights,
        )

    @staticmethod
    def _generate_grounded_insights(
        category: Optional[str],
        start_h: int,
        end_h: int,
        w_completion: float,
        base_completion: float,
        w_int_density: float,
        base_int_density: float,
        w_focus_density: float,
    ) -> List[str]:
        """Generates deterministic, grounded natural-language explanations."""
        insights = []
        target = f"'{category}' tasks" if category else "Tasks"
        int_diff_pct = round(((base_int_density - w_int_density) / max(0.01, base_int_density)) * 100.0, 0)

        insights.append(
            f"Historical records show that {target} have a {w_completion:.0%} completion rate "
            f"between {start_h:02d}:00 and {end_h:02d}:00 (vs. {base_completion:.0%} daily baseline)."
        )

        if int_diff_pct > 15:
            insights.append(
                f"Disruption density in this window is {int_diff_pct:.0f}% lower than your typical working hours ({w_int_density:.1f} vs {base_int_density:.1f} interruptions/hr)."
            )

        return insights

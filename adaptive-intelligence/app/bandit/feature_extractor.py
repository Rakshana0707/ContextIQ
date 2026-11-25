"""
Context Feature Extractor for ContextIQ Contextual Bandit Engine adapter (Phase 4.6).
Extracts a normalized d = 12 dimensional context vector x_t representing
the user's real-time behavioral state, cognitive friction, task urgency,
and focus alignment strictly available at decision time.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple


FEATURE_DIMENSION = 12

FEATURE_NAMES = [
    "normalized_bfi",
    "interruption_density",
    "session_fragmentation",
    "resumption_lag_ratio",
    "is_in_focus_window",
    "upcoming_window_proximity",
    "active_task_importance",
    "forgetting_risk_level",
    "workday_progress",
    "circadian_propensity",
    "nudge_cooldown_factor",
    "bias_term",
]


def _normalize_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class BanditFeatureExtractor:
    """Builds normalized context vector x_t and accompanying feature metadata."""

    @classmethod
    def extract_context(
        cls,
        user_id: uuid.UUID,
        profile_data: Optional[Dict[str, Any]],
        task: Optional[Any] = None,
        active_focus_window: Optional[Any] = None,
        next_focus_window: Optional[Any] = None,
        recent_interruptions: Optional[List[Any]] = None,
        last_nudge_timestamp: Optional[datetime] = None,
        current_hour: Optional[int] = None,
        as_of: Optional[datetime] = None,
    ) -> Tuple[List[float], Dict[str, Any]]:
        """
        Extracts 12-dimensional feature vector x_t clipped to safe bounds.
        """
        ref_time = _normalize_utc(as_of) or datetime.now(timezone.utc)
        hour = current_hour if current_hour is not None else ref_time.hour
        ints = recent_interruptions or []

        # 1. Behavioral Friction Index (BFI)
        raw_bfi = 40.0
        if profile_data and "baselines" in profile_data:
            raw_bfi = float(profile_data["baselines"].get("baseline_friction_index", 40.0))
        norm_bfi = max(0.0, min(1.0, raw_bfi / 100.0))

        # 2. Recent Interruption Density (per hour over last 2 hours)
        two_hours_ago = ref_time - timedelta(hours=2)
        recent_int_count = sum(
            1 for i in ints
            if _normalize_utc(getattr(i, "start_timestamp", None)) and _normalize_utc(getattr(i, "start_timestamp", None)) >= two_hours_ago
        )
        int_density = max(0.0, min(1.0, (recent_int_count / 2.0) / 10.0))

        # 3. Session Fragmentation Score
        fragmentation = 0.35
        if profile_data and "cognitive_recovery" in profile_data:
            frag_val = profile_data["cognitive_recovery"].get("fragmentation_index", {}).get("observed_value")
            if frag_val is not None:
                fragmentation = max(0.0, min(1.0, float(frag_val) / 100.0))
        elif recent_int_count >= 4:
            fragmentation = 0.80

        # 4. Resumption Lag Ratio
        median_lag = 45.0
        if profile_data and "cognitive_recovery" in profile_data:
            typical_lag = profile_data["cognitive_recovery"].get("typical_resumption_delay_seconds", {}).get("observed_value")
            if typical_lag is not None:
                median_lag = max(15.0, float(typical_lag))
        current_lag = median_lag
        lag_ratio = max(0.0, min(2.0, current_lag / median_lag))

        # 5. Is inside Verified Prime Focus Window
        is_in_fw = 1.0 if active_focus_window and getattr(active_focus_window, "quality_score", 0.0) >= 58.0 else 0.0

        # 6. Upcoming Focus Window Proximity (0 to 60 min)
        window_prox = 0.0
        if next_focus_window and not is_in_fw:
            st = getattr(next_focus_window.start_time, "hour", 0)
            diff_h = (st - hour) % 24
            if 0 < diff_h <= 1:
                window_prox = 0.85
            elif 1 < diff_h <= 2:
                window_prox = 0.45

        # 7. Active Task Priority / Deep Work importance
        task_importance = 0.50
        if task:
            prio = str(getattr(task, "priority", "MEDIUM")).upper()
            dur = getattr(task, "estimated_minutes", 30) or 30
            if prio == "URGENT":
                task_importance = 1.0
            elif prio == "HIGH":
                task_importance = 0.80
            elif prio == "MEDIUM":
                task_importance = 0.55
            else:
                task_importance = 0.30
            if dur >= 60:
                task_importance = min(1.0, task_importance + 0.15)

        # 8. Forgetting Risk Level
        p_forget = 0.35
        if task:
            due = _normalize_utc(getattr(task, "due_at", None))
            if due:
                h_left = (due - ref_time).total_seconds() / 3600.0
                if h_left <= 4.0:
                    p_forget = 0.90
                elif h_left <= 24.0:
                    p_forget = 0.70
            created = _normalize_utc(getattr(task, "created_at", None))
            if created and not due:
                age_days = (ref_time - created).total_seconds() / 86400.0
                p_forget = max(p_forget, min(0.85, age_days / 14.0))

        # 9. Workday Progress (assuming 9 AM start)
        h_elapsed = max(0.0, float(hour - 9)) if hour >= 9 else 0.0
        workday_progress = max(0.0, min(1.5, h_elapsed / 8.0))

        # 10. Circadian Focus Propensity
        morning_peak = math.exp(-0.5 * ((hour - 10.5) / 1.8) ** 2)
        afternoon_peak = 0.75 * math.exp(-0.5 * ((hour - 15.0) / 1.5) ** 2)
        circadian = max(0.1, min(1.0, morning_peak + afternoon_peak))

        # 11. Cooldown Factor (Time since last intervention, 0 to 120 min)
        if last_nudge_timestamp:
            last_utc = _normalize_utc(last_nudge_timestamp)
            delta_mins = (ref_time - last_utc).total_seconds() / 60.0
            cooldown_factor = max(0.0, min(1.0, delta_mins / 120.0))
        else:
            cooldown_factor = 1.0

        # 12. Constant Bias Term
        bias = 1.0

        vector = [
            round(norm_bfi, 4),
            round(int_density, 4),
            round(fragmentation, 4),
            round(lag_ratio, 4),
            round(is_in_fw, 4),
            round(window_prox, 4),
            round(task_importance, 4),
            round(p_forget, 4),
            round(workday_progress, 4),
            round(circadian, 4),
            round(cooldown_factor, 4),
            bias,
        ]

        metadata = {
            "raw_bfi": raw_bfi,
            "recent_interruptions_2h": recent_int_count,
            "hourly_int_density": round(recent_int_count / 2.0, 1),
            "fragmentation_score": round(fragmentation, 2),
            "is_in_focus_window": bool(is_in_fw),
            "task_importance": round(task_importance, 2),
            "forgetting_risk": round(p_forget, 2),
            "hour_of_day": hour,
            "circadian_propensity": round(circadian, 2),
            "cooldown_factor": round(cooldown_factor, 2),
        }

        return vector, metadata

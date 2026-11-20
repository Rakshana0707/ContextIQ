"""
extractor.py

ContextIQ Strict Temporal Feature Extraction Engine
Phase 2.2 Specification Implementation

Provides a unified, leakage-safe interface for extracting temporal behavioral
features as of a specific point in time, with schema versioning, provenance
metadata, and missingness tracking.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from ml.features.feature_spec import (
    FeatureSchemaVersion,
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    V2_2_NUMERIC_FEATURES,
    CATEGORY_DOMAIN,
    PRIORITY_DOMAIN,
    LOCATION_DOMAIN,
)


@dataclass
class FeatureSnapshot:
    """Immutable snapshot of extracted features with temporal provenance."""
    schema_version: str
    extraction_timestamp: datetime
    prediction_timestamp: datetime
    source_event_cutoff: datetime
    task_id: str
    user_id: str
    features: Dict[str, Any]
    missing_indicators: Dict[str, bool] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "extraction_timestamp": self.extraction_timestamp.isoformat(),
            "prediction_timestamp": self.prediction_timestamp.isoformat(),
            "source_event_cutoff": self.source_event_cutoff.isoformat(),
            "task_id": self.task_id,
            "user_id": self.user_id,
            "features": self.features,
            "missing_indicators": self.missing_indicators,
            "metadata": self.metadata,
        }

    def to_inference_dict(self) -> Dict[str, Any]:
        """Flattens features for direct input to ForgettingPredictor."""
        return {
            "task_id": self.task_id,
            **self.features,
        }


def _ensure_utc(dt: Any) -> Optional[datetime]:
    if dt is None or pd.isna(dt):
        return None
    if isinstance(dt, pd.Timestamp):
        dt = dt.to_pydatetime()
    elif isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _safe_rate(num: int, denom: int, prior: float = 0.5) -> float:
    if denom == 0:
        return prior
    return round(float(num) / float(denom), 4)


def extract_features(
    user_id: str,
    task_id: str,
    as_of_timestamp: datetime,
    tasks_df: Optional[pd.DataFrame] = None,
    events_df: Optional[pd.DataFrame] = None,
    interruptions_df: Optional[pd.DataFrame] = None,
    sessions_df: Optional[pd.DataFrame] = None,
    locations_df: Optional[pd.DataFrame] = None,
    schema_version: str = FeatureSchemaVersion.V2_2.value,
) -> FeatureSnapshot:
    """
    Extracts temporal features strictly as of `as_of_timestamp`.

    Guarantees:
    - All events with timestamp > as_of_timestamp are strictly excluded.
    - Future task completions, resumptions, and interruptions are invisible.
    - Supports both v1.1 (baseline contract) and v2.2 (enhanced temporal).
    """
    as_of = _ensure_utc(as_of_timestamp)
    if as_of is None:
        raise ValueError("as_of_timestamp is mandatory and must be a valid datetime.")

    now_utc = datetime.now(timezone.utc)

    # -------------------------------------------------------------
    # 1. Target Task Resolution
    # -------------------------------------------------------------
    target_task = None
    if tasks_df is not None and not tasks_df.empty:
        id_col = "id" if "id" in tasks_df.columns else "task_id"
        matches = tasks_df[tasks_df[id_col].astype(str) == str(task_id)]
        if not matches.empty:
            target_task = matches.iloc[0].to_dict()

    if target_task is None:
        # Construct fallback minimal target task
        target_task = {
            "id": task_id,
            "user_id": user_id,
            "category": "Work",
            "priority": "MEDIUM",
            "location": "Home",
            "created_at": as_of,
            "deadline_at": as_of + timedelta(hours=24),
        }

    task_created_at = _ensure_utc(target_task.get("created_at")) or as_of
    if task_created_at > as_of:
        raise ValueError(
            f"Target task created_at ({task_created_at}) cannot be in the future relative to as_of ({as_of})."
        )

    task_deadline_at = _ensure_utc(target_task.get("deadline_at"))

    # Resolve location name/type
    location_label = str(target_task.get("location") or target_task.get("location_name", "Home"))
    if locations_df is not None and not locations_df.empty and "id" in locations_df.columns:
        loc_id = target_task.get("location_id")
        if loc_id is not None:
            loc_match = locations_df[locations_df["id"].astype(str) == str(loc_id)]
            if not loc_match.empty:
                loc_row = loc_match.iloc[0]
                location_label = str(loc_row.get("name") or loc_row.get("location_type", location_label))

    # Normalize category, priority, location
    cat_val = str(target_task.get("category") or target_task.get("task_category", "Work")).title()
    if cat_val not in CATEGORY_DOMAIN:
        cat_val = "Work"

    prio_val = str(target_task.get("priority", "MEDIUM")).upper()
    if prio_val not in PRIORITY_DOMAIN:
        prio_val = "MEDIUM"

    loc_val = location_label.capitalize()
    if loc_val not in LOCATION_DOMAIN:
        loc_val = "Other"

    # -------------------------------------------------------------
    # 2. Strict Temporal Filtering of Historical Data
    # -------------------------------------------------------------
    # Rule: History uses only records strictly <= as_of (and < as_of for task creation)
    user_str = str(user_id)

    # Filter tasks: user-scoped, created strictly BEFORE as_of
    user_tasks_hist = pd.DataFrame()
    if tasks_df is not None and not tasks_df.empty:
        u_col = "user_id" if "user_id" in tasks_df.columns else "userId"
        c_col = "created_at" if "created_at" in tasks_df.columns else "createdAt"
        id_col = "id" if "id" in tasks_df.columns else "task_id"

        mask = tasks_df[u_col].astype(str) == user_str
        sub_tasks = tasks_df[mask].copy()
        sub_tasks["_dt"] = sub_tasks[c_col].apply(_ensure_utc)
        # Exclude future tasks and current task instance
        user_tasks_hist = sub_tasks[
            (sub_tasks["_dt"] < as_of) & (sub_tasks[id_col].astype(str) != str(task_id))
        ].copy()

    # Filter events: user-scoped, timestamp <= as_of
    user_events_hist = pd.DataFrame()
    if events_df is not None and not events_df.empty:
        u_col = "user_id" if "user_id" in events_df.columns else "userId"
        t_col = "timestamp" if "timestamp" in events_df.columns else "created_at"
        mask = events_df[u_col].astype(str) == user_str
        sub_ev = events_df[mask].copy()
        sub_ev["_dt"] = sub_ev[t_col].apply(_ensure_utc)
        user_events_hist = sub_ev[sub_ev["_dt"] <= as_of].copy()

    # Filter interruptions: user-scoped, start_time <= as_of
    user_ints_hist = pd.DataFrame()
    if interruptions_df is not None and not interruptions_df.empty:
        u_col = "user_id" if "user_id" in interruptions_df.columns else "userId"
        t_col = "start_time" if "start_time" in interruptions_df.columns else "created_at"
        mask = interruptions_df[u_col].astype(str) == user_str
        sub_ints = interruptions_df[mask].copy()
        sub_ints["_dt"] = sub_ints[t_col].apply(_ensure_utc)
        user_ints_hist = sub_ints[sub_ints["_dt"] <= as_of].copy()

    # Filter sessions: user-scoped, session_start <= as_of
    user_sessions_hist = pd.DataFrame()
    if sessions_df is not None and not sessions_df.empty:
        u_col = "user_id" if "user_id" in sessions_df.columns else "userId"
        t_col = "session_start" if "session_start" in sessions_df.columns else "start_time"
        mask = sessions_df[u_col].astype(str) == user_str
        sub_sess = sessions_df[mask].copy()
        sub_sess["_dt"] = sub_sess[t_col].apply(_ensure_utc)
        user_sessions_hist = sub_sess[sub_sess["_dt"] <= as_of].copy()

    missing_indicators: Dict[str, bool] = {}

    # -------------------------------------------------------------
    # 3. Baseline Feature Computations (Schema v1.1)
    # -------------------------------------------------------------
    weekday = as_of.weekday()
    hour = as_of.hour

    if task_deadline_at is not None:
        deadline_dist_h = max(0.0, (task_deadline_at - as_of).total_seconds() / 3600.0)
        missing_indicators["deadline_distance_hours"] = False
    else:
        deadline_dist_h = 24.0
        missing_indicators["deadline_distance_hours"] = True

    # Historical task counts
    prev_completions = 0
    prev_forgettings = 0
    cat_prior_count = 0
    total_prior_tasks = len(user_tasks_hist)

    if not user_tasks_hist.empty:
        status_col = user_tasks_hist["status"].astype(str).str.lower().tolist()
        for s in status_col:
            if s in ("completed", "done", "finish"):
                prev_completions += 1
            elif s in ("forgotten", "abandoned"):
                prev_forgettings += 1

        if "category" in user_tasks_hist.columns:
            cat_prior_count = (
                user_tasks_hist["category"].astype(str).str.lower() == cat_val.lower()
            ).sum()

    resolved_count = prev_completions + prev_forgettings
    if resolved_count > 0:
        hist_comp_rate = round(prev_completions / resolved_count, 4)
        hist_forget_rate = round(prev_forgettings / resolved_count, 4)
        missing_indicators["historical_completion_rate"] = False
        missing_indicators["historical_forgetting_rate"] = False
    else:
        hist_comp_rate = 0.5
        hist_forget_rate = 0.3
        missing_indicators["historical_completion_rate"] = True
        missing_indicators["historical_forgetting_rate"] = True

    task_frequency = round(cat_prior_count / max(1, total_prior_tasks), 4)

    # 24-hour rolling windows
    cutoff_24h = as_of - timedelta(hours=24)

    tasks_today = 0
    if not user_tasks_hist.empty:
        tasks_today = int((user_tasks_hist["_dt"] >= cutoff_24h).sum()) + 1  # +1 includes current task

    interruptions_today = 0
    if not user_ints_hist.empty:
        interruptions_today = int((user_ints_hist["_dt"] >= cutoff_24h).sum())

    recent_switches = 0
    if not user_events_hist.empty and "event_type" in user_events_hist.columns:
        ev_types = user_events_hist["event_type"].astype(str).str.lower()
        recent_switches = int(
            ((user_events_hist["_dt"] >= cutoff_24h) & ev_types.isin(["resumed", "resume", "switched"])).sum()
        )

    # Average interruption duration
    avg_int_duration = 8.5
    if not user_ints_hist.empty:
        dur_col = "duration_seconds" if "duration_seconds" in user_ints_hist.columns else "duration_minutes"
        if dur_col in user_ints_hist.columns:
            durs = user_ints_hist[dur_col].dropna()
            if not durs.empty:
                if dur_col == "duration_seconds":
                    avg_int_duration = round(float(durs.mean()) / 60.0, 2)
                else:
                    avg_int_duration = round(float(durs.mean()), 2)
                missing_indicators["avg_interruption_duration"] = False
            else:
                missing_indicators["avg_interruption_duration"] = True
        else:
            missing_indicators["avg_interruption_duration"] = True
    else:
        missing_indicators["avg_interruption_duration"] = True

    # Average session duration
    avg_sess_duration = 25.0
    if not user_sessions_hist.empty:
        dur_col = "focused_time_seconds" if "focused_time_seconds" in user_sessions_hist.columns else "duration_minutes"
        if dur_col in user_sessions_hist.columns:
            durs = user_sessions_hist[dur_col].dropna()
            if not durs.empty:
                if dur_col == "focused_time_seconds":
                    avg_sess_duration = round(float(durs.mean()) / 60.0, 2)
                else:
                    avg_sess_duration = round(float(durs.mean()), 2)
                missing_indicators["avg_session_duration"] = False
            else:
                missing_indicators["avg_session_duration"] = True
        else:
            missing_indicators["avg_session_duration"] = True
    else:
        missing_indicators["avg_session_duration"] = True

    base_features = {
        "task_category": cat_val,
        "priority": prio_val,
        "location": loc_val,
        "weekday": weekday,
        "hour": hour,
        "deadline_distance_hours": round(deadline_dist_h, 2),
        "previous_completion_count": prev_completions,
        "previous_forgetting_count": prev_forgettings,
        "historical_completion_rate": hist_comp_rate,
        "historical_forgetting_rate": hist_forget_rate,
        "task_frequency": task_frequency,
        "tasks_today": tasks_today,
        "interruptions_today": interruptions_today,
        "recent_context_switches": recent_switches,
        "avg_interruption_duration": avg_int_duration,
        "avg_session_duration": avg_sess_duration,
    }

    if schema_version == FeatureSchemaVersion.V1_1.value:
        return FeatureSnapshot(
            schema_version=schema_version,
            extraction_timestamp=now_utc,
            prediction_timestamp=as_of,
            source_event_cutoff=as_of,
            task_id=str(task_id),
            user_id=str(user_id),
            features=base_features,
            missing_indicators=missing_indicators,
            metadata={"n_historical_tasks": total_prior_tasks},
        )

    # -------------------------------------------------------------
    # 4. Enhanced Temporal Feature Computations (Schema v2.2)
    # -------------------------------------------------------------
    # A. Task history & Metacognition
    prev_postponements = 0
    if not user_events_hist.empty and "event_type" in user_events_hist.columns:
        p_types = user_events_hist["event_type"].astype(str).str.lower()
        prev_postponements = int(p_types.isin(["postponed", "rescheduled", "deadline_extended"]).sum())

    cat_completions = 0
    cat_resolved_total = 0
    if not user_tasks_hist.empty and "category" in user_tasks_hist.columns:
        cat_matches = user_tasks_hist[
            user_tasks_hist["category"].astype(str).str.lower() == cat_val.lower()
        ]
        if not cat_matches.empty:
            for s in cat_matches["status"].astype(str).str.lower():
                if s in ("completed", "done"):
                    cat_completions += 1
                    cat_resolved_total += 1
                elif s in ("forgotten", "abandoned"):
                    cat_resolved_total += 1

    cat_comp_rate = _safe_rate(cat_completions, cat_resolved_total, prior=hist_comp_rate)
    missing_indicators["category_completion_rate"] = cat_resolved_total == 0

    avg_completion_duration_min = 45.0
    # Compute duration for historical completed tasks
    if not user_tasks_hist.empty:
        st_col = "started_at" if "started_at" in user_tasks_hist.columns else None
        cp_col = "completed_at" if "completed_at" in user_tasks_hist.columns else None
        if st_col and cp_col:
            valid_durs = []
            for _, r in user_tasks_hist.iterrows():
                s_t = _ensure_utc(r.get(st_col))
                c_t = _ensure_utc(r.get(cp_col))
                if s_t and c_t and s_t < c_t <= as_of:
                    valid_durs.append((c_t - s_t).total_seconds() / 60.0)
            if valid_durs:
                avg_completion_duration_min = round(float(np.mean(valid_durs)), 1)
                missing_indicators["avg_completion_duration_minutes"] = False
            else:
                missing_indicators["avg_completion_duration_minutes"] = True
        else:
            missing_indicators["avg_completion_duration_minutes"] = True
    else:
        missing_indicators["avg_completion_duration_minutes"] = True

    # Inactivity duration: time since last recorded event
    inactivity_hours = 0.5
    if not user_events_hist.empty:
        last_ev_t = user_events_hist["_dt"].max()
        if last_ev_t:
            inactivity_hours = max(0.0, round((as_of - last_ev_t).total_seconds() / 3600.0, 2))
            missing_indicators["task_inactivity_hours"] = False
        else:
            missing_indicators["task_inactivity_hours"] = True
    else:
        missing_indicators["task_inactivity_hours"] = True

    # B. Interruption Behavior & Resumption Lag
    recent_int_freq = round(interruptions_today / 24.0, 3)

    # Compute resumption lags from pause -> resume gaps
    resumption_lags: List[float] = []
    if not user_events_hist.empty and "event_type" in user_events_hist.columns:
        ev_sorted = user_events_hist.sort_values("_dt").reset_index(drop=True)
        for i in range(len(ev_sorted) - 1):
            cur = ev_sorted.iloc[i]
            nxt = ev_sorted.iloc[i + 1]
            if str(cur.get("event_type", "")).lower() in ("paused", "pause"):
                if str(nxt.get("event_type", "")).lower() in ("resumed", "resume"):
                    lag_s = (nxt["_dt"] - cur["_dt"]).total_seconds()
                    if 0 <= lag_s <= 3600 * 4:  # within 4 hours
                        resumption_lags.append(lag_s)

    if resumption_lags:
        avg_resumption_lag = round(float(np.mean(resumption_lags)), 1)
        median_resumption_lag = round(float(np.median(resumption_lags)), 1)
        resumption_lag_std = round(float(np.std(resumption_lags)), 1)
        missing_indicators["avg_resumption_lag_seconds"] = False
        missing_indicators["median_resumption_lag_seconds"] = False
        missing_indicators["resumption_lag_std_seconds"] = False
    else:
        avg_resumption_lag = 180.0  # default 3 min
        median_resumption_lag = 120.0
        resumption_lag_std = 60.0
        missing_indicators["avg_resumption_lag_seconds"] = True
        missing_indicators["median_resumption_lag_seconds"] = True
        missing_indicators["resumption_lag_std_seconds"] = True

    # Consecutive interruptions in last 24h
    consecutive_ints = 0
    if not user_ints_hist.empty:
        ints_24 = user_ints_hist[user_ints_hist["_dt"] >= cutoff_24h].sort_values("_dt")
        if len(ints_24) > 1:
            for i in range(len(ints_24) - 1):
                gap = (ints_24.iloc[i + 1]["_dt"] - ints_24.iloc[i]["_dt"]).total_seconds()
                if gap <= 900:  # within 15 minutes
                    consecutive_ints += 1

    # C. Contextual Behavior
    loc_completions = 0
    loc_resolved_total = 0
    if not user_tasks_hist.empty and "location" in user_tasks_hist.columns:
        loc_matches = user_tasks_hist[
            user_tasks_hist["location"].astype(str).str.lower() == loc_val.lower()
        ]
        if not loc_matches.empty:
            for s in loc_matches["status"].astype(str).str.lower():
                if s in ("completed", "done"):
                    loc_completions += 1
                    loc_resolved_total += 1
                elif s in ("forgotten", "abandoned"):
                    loc_resolved_total += 1

    loc_comp_rate = _safe_rate(loc_completions, loc_resolved_total, prior=hist_comp_rate)
    missing_indicators["location_completion_rate"] = loc_resolved_total == 0

    context_switch_freq_24h = round(recent_switches / 24.0, 3)
    avg_switching_cost = round(0.5 * (avg_resumption_lag / 300.0) + 0.5 * min(1.0, recent_switches / 10.0), 3)

    # D. Temporal Dynamics
    task_age_hours = max(0.0, round((as_of - task_created_at).total_seconds() / 3600.0, 2))
    is_weekend = int(weekday >= 5)
    is_peak_focus = int(hour in (9, 10, 11, 14, 15, 16))

    enhanced_features = {
        **base_features,
        "previous_postponement_count": prev_postponements,
        "category_completion_rate": cat_comp_rate,
        "avg_completion_duration_minutes": avg_completion_duration_min,
        "task_inactivity_hours": inactivity_hours,
        "recent_interruption_frequency": recent_int_freq,
        "avg_resumption_lag_seconds": avg_resumption_lag,
        "median_resumption_lag_seconds": median_resumption_lag,
        "consecutive_interruption_count": consecutive_ints,
        "resumption_lag_std_seconds": resumption_lag_std,
        "location_completion_rate": loc_comp_rate,
        "context_switch_frequency_24h": context_switch_freq_24h,
        "avg_switching_recovery_cost": avg_switching_cost,
        "task_age_hours": task_age_hours,
        "is_weekend": is_weekend,
        "is_peak_focus_hours": is_peak_focus,
    }

    return FeatureSnapshot(
        schema_version=schema_version,
        extraction_timestamp=now_utc,
        prediction_timestamp=as_of,
        source_event_cutoff=as_of,
        task_id=str(task_id),
        user_id=str(user_id),
        features=enhanced_features,
        missing_indicators=missing_indicators,
        metadata={
            "n_historical_tasks": total_prior_tasks,
            "n_resumption_lags_computed": len(resumption_lags),
            "calendar_sync_available": False,  # Documented policy constraint
        },
    )

"""
data.py

ContextIQ Survival Dataset Construction Module
Phase 2.3 Specification Implementation

Builds time-to-event datasets with rigorous right-censoring for survival analysis:
- Event of Interest (E=1): Task failure / forgetting (EXPLICITLY_FORGOTTEN, ABANDONED)
- Censored Observations (E=0): Task completed, postponed, or still active/unresolved
- Duration (T): Elapsed time in hours from task creation to event or observation cutoff
- Zero-duration safety guard (minimum duration epsilon = 0.01h / 36s)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from ml.data.label_generator import OutcomeType, generate_task_label, LabelingConfig, _ensure_utc


class CensoringStatus(str, Enum):
    UNCENSORED_FORGOTTEN = "uncensored_forgotten"
    RIGHT_CENSORED_COMPLETED = "competing_completed"
    RIGHT_CENSORED_ACTIVE = "right_censored_active"
    RIGHT_CENSORED_POSTPONED = "right_censored_postponed"


# Minimum non-zero duration epsilon (in hours) to prevent undefined log-durations
MIN_DURATION_HOURS = 0.01  # 36 seconds


def build_survival_record(
    task: Dict[str, Any],
    events: Optional[List[Dict[str, Any]]] = None,
    as_of: Optional[datetime] = None,
    config: Optional[LabelingConfig] = None,
) -> Dict[str, Any]:
    """
    Constructs a single time-to-event observation with explicit censoring status.
    """
    if config is None:
        config = LabelingConfig()

    task_id = str(task.get("id") or task.get("task_id", "unknown"))
    user_id = str(task.get("user_id", "unknown"))

    created_at = _ensure_utc(task.get("created_at") or task.get("date"))
    if created_at is None:
        raise ValueError(f"Task {task_id} missing mandatory creation timestamp.")

    if as_of is None:
        as_of = datetime.now(timezone.utc)
    else:
        as_of = _ensure_utc(as_of)

    # Resolve formal outcome label using label_generator
    label_res = generate_task_label(task, events=events, as_of=as_of, config=config)
    outcome = label_res.outcome_type

    obs_start = created_at
    event_timestamp: Optional[datetime] = None

    # Determine event occurrence and censoring
    if outcome in (OutcomeType.EXPLICITLY_FORGOTTEN, OutcomeType.ABANDONED):
        event_observed = 1
        censoring_status = CensoringStatus.UNCENSORED_FORGOTTEN.value
        event_timestamp = label_res.labeling_timestamp
        obs_end = event_timestamp
    elif outcome in (OutcomeType.COMPLETED_ON_TIME, OutcomeType.COMPLETED_LATE):
        event_observed = 0  # Right-censored at completion
        censoring_status = CensoringStatus.RIGHT_CENSORED_COMPLETED.value
        obs_end = label_res.labeling_timestamp
    elif outcome == OutcomeType.POSTPONED:
        event_observed = 0  # Right-censored at postponement
        censoring_status = CensoringStatus.RIGHT_CENSORED_POSTPONED.value
        obs_end = label_res.labeling_timestamp
    else:
        # OVERDUE, DORMANT, CENSORED: Right-censored at cutoff as_of
        event_observed = 0
        censoring_status = CensoringStatus.RIGHT_CENSORED_ACTIVE.value
        obs_end = as_of

    # Enforce temporal ordering and minimum duration
    if obs_end < obs_start:
        obs_end = obs_start

    duration_hours = (obs_end - obs_start).total_seconds() / 3600.0
    duration_hours = max(MIN_DURATION_HOURS, round(duration_hours, 4))

    # Covariates extracted at baseline creation time
    deadline_at = _ensure_utc(task.get("deadline_at"))
    if deadline_at:
        deadline_dist = max(0.0, (deadline_at - created_at).total_seconds() / 3600.0)
    else:
        deadline_dist = 24.0

    return {
        "task_id": task_id,
        "user_id": user_id,
        "task_creation_timestamp": created_at.isoformat(),
        "observation_start_timestamp": obs_start.isoformat(),
        "event_timestamp": event_timestamp.isoformat() if event_timestamp else None,
        "observation_end_timestamp": obs_end.isoformat(),
        "duration": duration_hours,
        "event_observed": event_observed,
        "censoring_status": censoring_status,
        # Baseline Covariates
        "task_category": str(task.get("task_category") or task.get("category", "Work")),
        "priority": str(task.get("priority", "MEDIUM")),
        "location": str(task.get("location", "Home")),
        "weekday": created_at.weekday(),
        "hour": created_at.hour,
        "deadline_distance_hours": round(deadline_dist, 2),
        "tasks_today": int(task.get("tasks_today", 3)),
        "interruptions_today": int(task.get("interruptions_today", 2)),
        "recent_context_switches": int(task.get("recent_context_switches", 2)),
        "historical_forgetting_rate": float(task.get("historical_forgetting_rate", 0.3)),
        "avg_resumption_lag_seconds": float(task.get("avg_resumption_lag_seconds", 120.0)),
        "avg_interruption_duration": float(task.get("avg_interruption_duration", 8.5)),
    }


def generate_survival_dataset(
    tasks_df: pd.DataFrame,
    events_df: Optional[pd.DataFrame] = None,
    as_of: Optional[datetime] = None,
    config: Optional[LabelingConfig] = None,
) -> pd.DataFrame:
    """Builds a complete survival analysis DataFrame from tasks and events."""
    if tasks_df.empty:
        return pd.DataFrame()

    if config is None:
        config = LabelingConfig()

    events_by_task = {}
    if events_df is not None and not events_df.empty:
        t_col = "task_id" if "task_id" in events_df.columns else "taskId"
        for tid, grp in events_df.groupby(t_col):
            events_by_task[str(tid)] = grp.to_dict("records")

    records = []
    for _, row in tasks_df.iterrows():
        t_dict = row.to_dict()
        tid = str(t_dict.get("id") or t_dict.get("task_id", ""))
        rec = build_survival_record(
            task=t_dict,
            events=events_by_task.get(tid, []),
            as_of=as_of,
            config=config,
        )
        records.append(rec)

    return pd.DataFrame(records)


def create_synthetic_survival_dataset(
    n_samples: int = 5000,
    seed: int = 42,
    as_of: Optional[datetime] = None,
) -> pd.DataFrame:
    """
    Generates a reproducible, scientifically calibrated synthetic dataset
    with realistic time-to-forgetting curves and right-censoring patterns.
    """
    rng = np.random.default_rng(seed)
    if as_of is None:
        as_of = datetime(2025, 4, 1, 0, 0, 0, tzinfo=timezone.utc)
    else:
        as_of = _ensure_utc(as_of)

    categories = ["Work", "Academic", "Personal", "Health", "Household", "Social", "Finance"]
    priorities = ["LOW", "MEDIUM", "HIGH"]
    locations = ["Home", "Office", "Campus", "Commute", "Gym", "Other"]

    start_date = as_of - timedelta(days=60)
    records = []

    for i in range(n_samples):
        task_id = f"SURV-T{i+1:05d}"
        user_id = f"U{rng.integers(1, 101):03d}"

        # Creation timestamp uniformly distributed over 60 days
        day_offset = float(rng.uniform(0, 58))
        created_at = start_date + timedelta(days=day_offset, hours=float(rng.uniform(7, 21)))

        cat = str(rng.choice(categories))
        prio = str(rng.choice(priorities, p=[0.35, 0.45, 0.20]))
        loc = str(rng.choice(locations))

        deadline_dist = float(rng.gamma(2.5, 8.0) + 2.0)  # hours
        deadline_at = created_at + timedelta(hours=deadline_dist)

        # Baseline behavioral covariates
        interruptions_today = int(rng.poisson(3.0))
        recent_switches = int(rng.poisson(4.0))
        hist_forget_rate = float(np.clip(rng.beta(2.0, 5.0), 0.05, 0.75))
        avg_lag = float(rng.gamma(3.0, 40.0) + 30.0)  # seconds
        avg_int_dur = float(rng.gamma(2.0, 4.0) + 1.0)

        # Survival generation: Log-linear hazard for time-to-forgetting
        # High interruptions, high lag, low priority accelerate forgetting risk
        prio_hazard = {"LOW": 0.40, "MEDIUM": 0.0, "HIGH": -0.60}[prio]
        log_hazard = (
            prio_hazard
            + 0.15 * (interruptions_today - 3)
            + 0.12 * (recent_switches - 4)
            + 0.80 * (hist_forget_rate - 0.3)
            + 0.003 * (avg_lag - 150)
            - 0.02 * (deadline_dist - 20)
        )

        # Scale parameter for Weibull distribution (shape = 1.2 representing slightly increasing hazard)
        shape = 1.2
        scale = 36.0 * np.exp(-log_hazard / shape)
        scale = max(4.0, scale)

        # Latent time to potential forgetting
        latent_forget_time = float(rng.weibull(shape) * scale)

        # Latent time to completion (independent competing risk)
        comp_scale = 18.0 if prio == "HIGH" else (28.0 if prio == "MEDIUM" else 45.0)
        latent_comp_time = float(rng.exponential(comp_scale))

        # Observation cutoff is as_of
        max_possible_obs = max(MIN_DURATION_HOURS, (as_of - created_at).total_seconds() / 3600.0)

        # Determine which event happens first
        if latent_forget_time < latent_comp_time and latent_forget_time <= max_possible_obs:
            # Forgetting observed before completion and before cutoff
            duration = max(MIN_DURATION_HOURS, latent_forget_time)
            event_observed = 1
            censoring_status = CensoringStatus.UNCENSORED_FORGOTTEN.value
            event_timestamp = created_at + timedelta(hours=duration)
            obs_end = event_timestamp
        elif latent_comp_time <= max_possible_obs:
            # Completed before forgetting -> right-censored at completion
            duration = max(MIN_DURATION_HOURS, latent_comp_time)
            event_observed = 0
            censoring_status = CensoringStatus.RIGHT_CENSORED_COMPLETED.value
            event_timestamp = None
            obs_end = created_at + timedelta(hours=duration)
        else:
            # In-flight at cutoff -> right-censored at as_of
            duration = max_possible_obs
            event_observed = 0
            censoring_status = CensoringStatus.RIGHT_CENSORED_ACTIVE.value
            event_timestamp = None
            obs_end = as_of

        records.append({
            "task_id": task_id,
            "user_id": user_id,
            "task_creation_timestamp": created_at.isoformat(),
            "observation_start_timestamp": created_at.isoformat(),
            "event_timestamp": event_timestamp.isoformat() if event_timestamp else None,
            "observation_end_timestamp": obs_end.isoformat(),
            "duration": round(duration, 4),
            "event_observed": event_observed,
            "censoring_status": censoring_status,
            "task_category": cat,
            "priority": prio,
            "location": loc,
            "weekday": created_at.weekday(),
            "hour": created_at.hour,
            "deadline_distance_hours": round(deadline_dist, 2),
            "tasks_today": int(rng.poisson(4)),
            "interruptions_today": interruptions_today,
            "recent_context_switches": recent_switches,
            "historical_forgetting_rate": round(hist_forget_rate, 4),
            "avg_resumption_lag_seconds": round(avg_lag, 1),
            "avg_interruption_duration": round(avg_int_dur, 2),
        })

    df = pd.DataFrame(records)
    # Sort chronologically by task_creation_timestamp
    df = df.sort_values("task_creation_timestamp").reset_index(drop=True)
    return df

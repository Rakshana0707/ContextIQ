"""
label_generator.py

ContextIQ Formal Target Labeling Module
Phase 2.1 Specification Implementation

Produces scientifically grounded, multi-state behavioral labels from task
attributes and event lifecycles while guaranteeing temporal validity,
right-censorship handling, and backward compatibility with `will_forget`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import pandas as pd


class OutcomeType(str, Enum):
    COMPLETED_ON_TIME = "COMPLETED_ON_TIME"
    COMPLETED_LATE = "COMPLETED_LATE"
    EXPLICITLY_FORGOTTEN = "EXPLICITLY_FORGOTTEN"
    ABANDONED = "ABANDONED"
    OVERDUE = "OVERDUE"
    DORMANT = "DORMANT"
    POSTPONED = "POSTPONED"
    CENSORED = "CENSORED"


@dataclass(frozen=True)
class LabelingConfig:
    grace_period_hours: float = 4.0
    grace_period_ratio: float = 0.10
    max_grace_period_hours: float = 24.0
    abandon_inactivity_hours: float = 48.0
    dormant_inactivity_days: float = 14.0


@dataclass
class TaskLabelResult:
    task_id: str
    outcome_type: OutcomeType
    will_forget: Optional[int]
    is_valid_training_sample: bool
    labeling_timestamp: datetime
    observation_window_hours: float
    censoring_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "outcome_type": self.outcome_type.value,
            "will_forget": self.will_forget,
            "is_valid_training_sample": self.is_valid_training_sample,
            "labeling_timestamp": self.labeling_timestamp.isoformat(),
            "observation_window_hours": round(self.observation_window_hours, 2),
            "censoring_reason": self.censoring_reason,
            **self.metadata,
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


def compute_grace_period_hours(
    created_at: datetime, deadline_at: Optional[datetime], config: LabelingConfig
) -> float:
    if deadline_at is None:
        return config.grace_period_hours
    task_span_hours = max(0.0, (deadline_at - created_at).total_seconds() / 3600.0)
    ratio_grace = task_span_hours * config.grace_period_ratio
    grace = max(config.grace_period_hours, ratio_grace)
    return min(grace, config.max_grace_period_hours)


def generate_task_label(
    task: Dict[str, Any],
    events: Optional[List[Dict[str, Any]]] = None,
    as_of: Optional[datetime] = None,
    config: Optional[LabelingConfig] = None,
) -> TaskLabelResult:
    """
    Computes the formal behavioral outcome for a single task observation.

    Strict Temporal Rule:
    Any event with timestamp > as_of is excluded (future blindness).
    """
    if config is None:
        config = LabelingConfig()

    task_id = str(task.get("id") or task.get("task_id", "unknown"))
    created_at = _ensure_utc(task.get("created_at"))
    if created_at is None:
        raise ValueError(f"Task {task_id} missing mandatory created_at timestamp.")

    if as_of is None:
        as_of = datetime.now(timezone.utc)
    else:
        as_of = _ensure_utc(as_of)

    if as_of < created_at:
        raise ValueError(
            f"Observation cutoff as_of ({as_of}) cannot be earlier than task created_at ({created_at})."
        )

    deadline_at = _ensure_utc(task.get("deadline_at"))

    # Extract & sort lifecycle events occurring strictly <= as_of
    valid_events = []
    if events:
        for ev in events:
            ev_time = _ensure_utc(ev.get("timestamp") or ev.get("created_at"))
            if ev_time is not None and created_at <= ev_time <= as_of:
                valid_events.append({
                    "event_type": str(ev.get("event_type", "")).lower(),
                    "timestamp": ev_time,
                    "metadata": ev.get("metadata", {}),
                })
        valid_events.sort(key=lambda x: x["timestamp"])

    # Fallback to denormalized task columns if events not provided
    comp_time = _ensure_utc(task.get("completed_at"))
    start_time = _ensure_utc(task.get("started_at"))
    forgotten_time = _ensure_utc(task.get("forgotten_at"))
    cancelled_time = _ensure_utc(task.get("cancelled_at"))

    # Find earliest completion event if present
    for ev in valid_events:
        etype = ev["event_type"]
        etime = ev["timestamp"]
        if etype in ("completed", "finish", "done") and (comp_time is None or etime < comp_time):
            comp_time = etime
        elif etype in ("started", "resume", "resumed") and (start_time is None or etime < start_time):
            start_time = etime
        elif etype in ("forgotten",) and (forgotten_time is None or etime < forgotten_time):
            forgotten_time = etime
        elif etype in ("cancelled",) and (cancelled_time is None or etime < cancelled_time):
            cancelled_time = etime

    # Check for intentional postponement events
    has_postponement = any(
        ev["event_type"] in ("postponed", "rescheduled", "deadline_extended")
        for ev in valid_events
    ) or bool(task.get("is_postponed") or task.get("postponed_count", 0) > 0)

    # Check latest interaction timestamp
    last_event_time = created_at
    if valid_events:
        last_event_time = valid_events[-1]["timestamp"]
    elif start_time:
        last_event_time = max(last_event_time, start_time)

    # Determine grace period
    grace_hours = compute_grace_period_hours(created_at, deadline_at, config)
    grace_delta = timedelta(hours=grace_hours)

    obs_window_hours = (as_of - created_at).total_seconds() / 3600.0

    # -------------------------------------------------------------
    # RULE 1: Task Completed
    # -------------------------------------------------------------
    if comp_time is not None and comp_time <= as_of:
        if deadline_at is None or comp_time <= (deadline_at + grace_delta):
            return TaskLabelResult(
                task_id=task_id,
                outcome_type=OutcomeType.COMPLETED_ON_TIME,
                will_forget=0,
                is_valid_training_sample=True,
                labeling_timestamp=comp_time,
                observation_window_hours=(comp_time - created_at).total_seconds() / 3600.0,
                metadata={"completion_delay_hours": 0.0},
            )
        else:
            delay_h = (comp_time - deadline_at).total_seconds() / 3600.0
            return TaskLabelResult(
                task_id=task_id,
                outcome_type=OutcomeType.COMPLETED_LATE,
                will_forget=0,  # Successfully remembered, delayed in execution
                is_valid_training_sample=True,
                labeling_timestamp=comp_time,
                observation_window_hours=(comp_time - created_at).total_seconds() / 3600.0,
                metadata={"completion_delay_hours": round(delay_h, 2)},
            )

    # -------------------------------------------------------------
    # RULE 2: Task Intentionally Postponed
    # -------------------------------------------------------------
    if has_postponement:
        return TaskLabelResult(
            task_id=task_id,
            outcome_type=OutcomeType.POSTPONED,
            will_forget=0,  # Conscious deferral, not forgetting
            is_valid_training_sample=True,
            labeling_timestamp=last_event_time,
            observation_window_hours=obs_window_hours,
            metadata={"postponed": True},
        )

    # -------------------------------------------------------------
    # RULE 3: Explicit Forgetting Event
    # -------------------------------------------------------------
    if forgotten_time is not None and forgotten_time <= as_of:
        return TaskLabelResult(
            task_id=task_id,
            outcome_type=OutcomeType.EXPLICITLY_FORGOTTEN,
            will_forget=1,
            is_valid_training_sample=True,
            labeling_timestamp=forgotten_time,
            observation_window_hours=(forgotten_time - created_at).total_seconds() / 3600.0,
            metadata={"explicit_event": True},
        )

    # -------------------------------------------------------------
    # RULE 4: Scheduled Tasks with Deadline
    # -------------------------------------------------------------
    if deadline_at is not None:
        deadline_with_grace = deadline_at + grace_delta

        if as_of >= deadline_with_grace:
            # Deadline + grace period has fully passed without completion
            if start_time is not None:
                # Work was initiated but never finished
                return TaskLabelResult(
                    task_id=task_id,
                    outcome_type=OutcomeType.ABANDONED,
                    will_forget=1,
                    is_valid_training_sample=True,
                    labeling_timestamp=deadline_with_grace,
                    observation_window_hours=(deadline_with_grace - created_at).total_seconds() / 3600.0,
                    metadata={"started_but_uncompleted": True},
                )
            else:
                # Never even started
                return TaskLabelResult(
                    task_id=task_id,
                    outcome_type=OutcomeType.EXPLICITLY_FORGOTTEN,
                    will_forget=1,
                    is_valid_training_sample=True,
                    labeling_timestamp=deadline_with_grace,
                    observation_window_hours=(deadline_with_grace - created_at).total_seconds() / 3600.0,
                    metadata={"unstarted_past_deadline": True},
                )
        elif as_of > deadline_at:
            # Deadline passed, but within grace period
            return TaskLabelResult(
                task_id=task_id,
                outcome_type=OutcomeType.OVERDUE,
                will_forget=None,
                is_valid_training_sample=False,
                labeling_timestamp=as_of,
                observation_window_hours=obs_window_hours,
                censoring_reason="Task is in grace period resolution window.",
            )
        else:
            # Deadline is in the future relative to as_of
            return TaskLabelResult(
                task_id=task_id,
                outcome_type=OutcomeType.CENSORED,
                will_forget=None,
                is_valid_training_sample=False,
                labeling_timestamp=as_of,
                observation_window_hours=obs_window_hours,
                censoring_reason="Deadline has not yet arrived as of observation cutoff.",
            )

    # -------------------------------------------------------------
    # RULE 5: Unscheduled Tasks (No Deadline)
    # -------------------------------------------------------------
    inactivity_hours = (as_of - last_event_time).total_seconds() / 3600.0
    age_days = (as_of - created_at).total_seconds() / 86400.0

    if start_time is not None and inactivity_hours >= config.abandon_inactivity_hours:
        # Started, but idle for >= abandon window
        abandon_time = last_event_time + timedelta(hours=config.abandon_inactivity_hours)
        return TaskLabelResult(
            task_id=task_id,
            outcome_type=OutcomeType.ABANDONED,
            will_forget=1,
            is_valid_training_sample=True,
            labeling_timestamp=abandon_time,
            observation_window_hours=(abandon_time - created_at).total_seconds() / 3600.0,
            metadata={"abandon_inactivity_hours": round(inactivity_hours, 1)},
        )

    if age_days >= config.dormant_inactivity_days:
        return TaskLabelResult(
            task_id=task_id,
            outcome_type=OutcomeType.DORMANT,
            will_forget=None,
            is_valid_training_sample=False,
            labeling_timestamp=as_of,
            observation_window_hours=obs_window_hours,
            censoring_reason=f"Unscheduled task dormant for {age_days:.1f} days without activity.",
        )

    # Active unscheduled task within observation threshold
    return TaskLabelResult(
        task_id=task_id,
        outcome_type=OutcomeType.CENSORED,
        will_forget=None,
        is_valid_training_sample=False,
        labeling_timestamp=as_of,
        observation_window_hours=obs_window_hours,
        censoring_reason="Unscheduled task is active within observation window.",
    )


def generate_labels_for_dataframe(
    tasks_df: pd.DataFrame,
    events_df: Optional[pd.DataFrame] = None,
    as_of: Optional[datetime] = None,
    config: Optional[LabelingConfig] = None,
) -> pd.DataFrame:
    """Batch processes a DataFrame of tasks into formal outcome labels."""
    if tasks_df.empty:
        return pd.DataFrame()

    if config is None:
        config = LabelingConfig()

    events_by_task = {}
    if events_df is not None and not events_df.empty:
        task_col = "task_id" if "task_id" in events_df.columns else "taskId"
        for t_id, group in events_df.groupby(task_col):
            events_by_task[str(t_id)] = group.to_dict("records")

    results = []
    for _, row in tasks_df.iterrows():
        t_dict = row.to_dict()
        t_id = str(t_dict.get("id") or t_dict.get("task_id", ""))
        t_events = events_by_task.get(t_id, [])
        label_res = generate_task_label(t_dict, events=t_events, as_of=as_of, config=config)
        results.append(label_res.to_dict())

    return pd.DataFrame(results)

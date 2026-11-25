"""
Outcome Tracker for ContextIQ Intervention Effectiveness Engine (Phase 4.7).
Mirror for adaptive-intelligence.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.effectiveness_schemas import OutcomeWindowMinutes, TreatmentStatus


def _normalize_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class OutcomeTracker:
    """
    Tracks and synthesizes downstream behavioral outcomes following intervention delivery.
    """

    CRITICAL_DEADLINE_THRESHOLD_HOURS: float = 2.0

    @classmethod
    def determine_observation_window_minutes(cls, intervention_category: str) -> int:
        category = (intervention_category or "").upper()
        if category == "RECOVERY":
            return OutcomeWindowMinutes.IMMEDIATE_RECOVERY.value
        elif category in ("FOCUS", "CONTEXTUAL"):
            return OutcomeWindowMinutes.MEDIUM_SESSION.value
        elif category in ("TASK", "WORKLOAD"):
            return OutcomeWindowMinutes.DAILY_WORKLOAD.value
        return OutcomeWindowMinutes.IMMEDIATE_RECOVERY.value

    @classmethod
    def can_assign_to_control_holdout(
        cls,
        task_due_at: Optional[datetime],
        as_of: Optional[datetime] = None,
        is_critical_urgency: bool = False,
    ) -> bool:
        if is_critical_urgency:
            return False

        if task_due_at is not None:
            now = _normalize_utc(as_of) or datetime.now(timezone.utc)
            due = _normalize_utc(task_due_at)
            time_remaining = (due - now).total_seconds() / 3600.0
            if time_remaining <= cls.CRITICAL_DEADLINE_THRESHOLD_HOURS:
                return False

        return True

    @classmethod
    def verify_execution(
        cls,
        intervention_type: str,
        user_action: str,
        telemetry_events: Optional[List[Dict[str, Any]]] = None,
        task_events: Optional[List[Dict[str, Any]]] = None,
        target_task_id: Optional[uuid.UUID] = None,
        action_timestamp: Optional[datetime] = None,
        window_end: Optional[datetime] = None,
    ) -> Tuple[bool, Optional[datetime], Dict[str, Any]]:
        action = (user_action or "").upper()
        if action not in ("ACCEPTED", "SNOOZED"):
            return False, None, {"reason": f"Action was {action}, not accepted."}

        telemetry = telemetry_events or []
        t_events = task_events or []
        start_ts = _normalize_utc(action_timestamp) or datetime.now(timezone.utc)
        end_ts = _normalize_utc(window_end) or (start_ts + timedelta(minutes=30))

        if "RECOVERY" in intervention_type or "RESUME" in intervention_type:
            for te in t_events:
                event_type = te.get("event_type", "").upper()
                te_task_id = te.get("task_id")
                te_time = _normalize_utc(te.get("created_at") or te.get("timestamp"))

                if te_time and start_ts <= te_time <= (start_ts + timedelta(minutes=20)):
                    if event_type in ("STARTED", "RESUMED"):
                        if target_task_id is None or str(te_task_id) == str(target_task_id):
                            return True, te_time, {
                                "criterion": "TASK_RESUMPTION_LOGGED",
                                "event_type": event_type,
                                "task_id": str(te_task_id),
                                "lag_minutes": round((te_time - start_ts).total_seconds() / 60.0, 2),
                            }
            if telemetry:
                first_active = next(
                    (
                        e for e in telemetry
                        if _normalize_utc(e.get("timestamp")) and _normalize_utc(e.get("timestamp")) >= start_ts
                    ),
                    None,
                )
                if first_active:
                    ts = _normalize_utc(first_active.get("timestamp"))
                    return True, ts, {
                        "criterion": "WORK_ACTIVITY_DETECTED",
                        "app_name": first_active.get("app_name", "editor"),
                    }

        if "FOCUS" in intervention_type or "PROTECTED" in intervention_type:
            focus_time = 0.0
            app_switches = 0
            last_app = None
            exec_time = None

            for e in telemetry:
                e_time = _normalize_utc(e.get("timestamp"))
                if e_time and start_ts <= e_time <= end_ts:
                    if exec_time is None:
                        exec_time = e_time
                    app = e.get("app_name")
                    if last_app and app != last_app:
                        app_switches += 1
                    last_app = app
                    focus_time += float(e.get("duration_seconds", 30)) / 60.0

            if focus_time >= 20.0 or (focus_time >= 10.0 and app_switches <= 4):
                return True, exec_time or start_ts, {
                    "criterion": "FOCUS_SESSION_SUSTAINED",
                    "focus_minutes": round(focus_time, 1),
                    "window_switches": app_switches,
                }

        if "BREAK" in intervention_type or "POSTPONE" in intervention_type or "SUBTASK" in intervention_type:
            for te in t_events:
                te_time = _normalize_utc(te.get("created_at") or te.get("timestamp"))
                if te_time and start_ts <= te_time <= end_ts:
                    e_type = te.get("event_type", "").upper()
                    if e_type in ("SUBTASK_CREATED", "SPLIT", "POSTPONED", "RESCHEDULED", "COMPLETED"):
                        return True, te_time, {
                            "criterion": "TASK_STRUCTURE_MODIFIED",
                            "action_taken": e_type,
                        }

        if telemetry or t_events:
            return True, start_ts, {"criterion": "ACTIVITY_VERIFIED", "event_count": len(telemetry) + len(t_events)}

        return False, None, {"criterion": "NO_DOWNSTREAM_TELEMETRY_RECORDED"}

    @classmethod
    def compute_cognitive_deltas(
        cls,
        baseline_bfi: float,
        observed_bfi: Optional[float],
        baseline_lag_seconds: float,
        observed_lag_seconds: Optional[float],
        baseline_interruption_rate: float,
        observed_interruption_rate: Optional[float],
    ) -> Dict[str, Optional[float]]:
        bfi_delta = None
        if observed_bfi is not None:
            bfi_delta = round(float(baseline_bfi - observed_bfi), 2)

        lag_delta = None
        if observed_lag_seconds is not None:
            lag_delta = round(float(baseline_lag_seconds - observed_lag_seconds), 2)

        int_delta = None
        if observed_interruption_rate is not None:
            int_delta = round(float(baseline_interruption_rate - observed_interruption_rate), 2)

        return {
            "bfi_delta": bfi_delta,
            "resumption_lag_delta_seconds": lag_delta,
            "interruption_rate_delta": int_delta,
        }

    @classmethod
    def synthesize_composite_score(
        cls,
        user_action: str,
        was_executed: bool,
        bfi_delta: Optional[float],
        resumption_lag_delta: Optional[float],
        target_task_completed: bool,
        user_reported_usefulness: Optional[float] = None,
        postponed_after_intervention: bool = False,
    ) -> float:
        action = (user_action or "").upper()

        if action == "ACCEPTED":
            r_exp = 1.0 if was_executed else 0.5
        elif action == "SNOOZED":
            r_exp = 0.2
        elif action == "DISMISSED":
            r_exp = -0.5
        elif action == "EXPIRED":
            r_exp = -0.2
        elif action in ("EXPLICIT_NEGATIVE", "REJECTED"):
            r_exp = -1.0
        else:
            r_exp = 0.0

        norm_bfi = 0.0
        if bfi_delta is not None:
            norm_bfi = max(-1.0, min(1.0, bfi_delta / 50.0))

        norm_lag = 0.0
        if resumption_lag_delta is not None:
            norm_lag = max(-1.0, min(1.0, resumption_lag_delta / 60.0))

        comp_score = 1.0 if target_task_completed else (-0.2 if postponed_after_intervention else 0.0)

        r_beh = 0.35 * norm_lag + 0.35 * norm_bfi + 0.30 * comp_score
        r_beh = max(-1.0, min(1.0, r_beh))

        composite = 0.40 * r_exp + 0.60 * r_beh

        if user_reported_usefulness is not None:
            usefulness_norm = (user_reported_usefulness - 3.0) / 2.0
            composite = 0.80 * composite + 0.20 * usefulness_norm

        return round(max(-1.0, min(1.0, composite)), 3)

    @classmethod
    def detect_confounders(
        cls,
        window_start: datetime,
        window_end: datetime,
        concurrent_outcomes: List[Dict[str, Any]],
        current_intervention_id: Optional[uuid.UUID] = None,
    ) -> List[Dict[str, Any]]:
        confounders: List[Dict[str, Any]] = []
        w_start = _normalize_utc(window_start)
        w_end = _normalize_utc(window_end)

        for other in concurrent_outcomes:
            other_id = other.get("intervention_id") or other.get("id")
            if current_intervention_id and str(other_id) == str(current_intervention_id):
                continue

            pres_at = _normalize_utc(other.get("presented_at"))
            if pres_at and w_start <= pres_at <= w_end:
                confounders.append({
                    "type": "CONCURRENT_INTERVENTION",
                    "intervention_type": other.get("intervention_type"),
                    "presented_at": pres_at.isoformat(),
                    "impact": "Shared observation window, treatment effect may be confounded.",
                })

        return confounders

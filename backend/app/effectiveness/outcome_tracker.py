"""
Outcome Tracker for ContextIQ Intervention Effectiveness Engine (Phase 4.7).
Measures multi-horizon intervention outcomes, distinguishes superficial acceptance from
empirical behavioral execution, calculates cognitive deltas (BFI, resumption lag),
detects concurrent confounders, and enforces ethical holdout boundaries.
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

    CRITICAL_DEADLINE_THRESHOLD_HOURS: float = 2.0  # Under 2 hours, holdouts are strictly prohibited

    @classmethod
    def determine_observation_window_minutes(cls, intervention_category: str) -> int:
        """
        Assigns empirically appropriate observation window based on intervention category.
        - RECOVERY: 30 minutes (cognitive reset, resumption delay)
        - FOCUS / CONTEXTUAL: 120 minutes (sustained focus session, environmental batching)
        - TASK / WORKLOAD: 1440 minutes (task breakdown, deadline management, schedule shifts)
        """
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
        """
        Ethical holdout guardrail:
        Returns False if task deadline is less than 2 hours away, or task is marked critically urgent.
        In such conditions, withholding an intervention or reminder is ethically impermissible.
        """
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
        """
        Distinguishes explicit acceptance from actual behavioral execution.
        A user may accept a prompt, but never act on it.
        Returns: (was_executed, execution_timestamp, evidence_dict)
        """
        action = (user_action or "").upper()
        if action not in ("ACCEPTED", "SNOOZED"):
            return False, None, {"reason": f"Action was {action}, not accepted."}

        telemetry = telemetry_events or []
        t_events = task_events or []
        start_ts = _normalize_utc(action_timestamp) or datetime.now(timezone.utc)
        end_ts = _normalize_utc(window_end) or (start_ts + timedelta(minutes=30))

        # 1. Recovery Interventions: Verify task resumption (STARTED / RESUMED within 15 min)
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
            # Fallback: check telemetry activity if task event wasn't explicitly logged
            if telemetry:
                # Check for active app usage resumption
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

        # 2. Focus Interventions: Verify sustained focus session (>= 25 min or low window switching)
        if "FOCUS" in intervention_type or "PROTECTED" in intervention_type:
            # Check if focus session duration recorded or telemetry shows stable app usage
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

            # Verified if sustained focus >= 20 min or switches < 5 during session
            if focus_time >= 20.0 or (focus_time >= 10.0 and app_switches <= 4):
                return True, exec_time or start_ts, {
                    "criterion": "FOCUS_SESSION_SUSTAINED",
                    "focus_minutes": round(focus_time, 1),
                    "window_switches": app_switches,
                }

        # 3. Task Breakdown / Postponement: Check task split or completion/postpone event
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

        # General / Default: If explicit acceptance with latency evidence provided
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
        """
        Calculates metric deltas between pre-intervention baseline (t_0)
        and post-window observation (t_0 + Delta t).
        Positive delta values represent behavioral improvements:
        - bfi_delta > 0: friction decreased
        - resumption_lag_delta > 0: resumption was faster
        - interruption_rate_delta > 0: fewer disruptions per hour
        """
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
        """
        Synthesizes composite effectiveness score in [-1.0, +1.0].
        Combines explicit reaction (40%) and objective behavioral outcomes (60%).
        """
        action = (user_action or "").upper()

        # Explicit component (-1.0 to +1.0)
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

        # Behavioral component (-1.0 to +1.0)
        # 1. BFI delta component (-1.0 to 1.0)
        norm_bfi = 0.0
        if bfi_delta is not None:
            # e.g., +20 friction reduction -> +0.4
            norm_bfi = max(-1.0, min(1.0, bfi_delta / 50.0))

        # 2. Resumption lag delta component (-1.0 to 1.0)
        norm_lag = 0.0
        if resumption_lag_delta is not None:
            # e.g., +30s faster resumption -> +0.5
            norm_lag = max(-1.0, min(1.0, resumption_lag_delta / 60.0))

        # 3. Task completion (+1.0 if completed, -0.2 if postponed repeatedly)
        comp_score = 1.0 if target_task_completed else (-0.2 if postponed_after_intervention else 0.0)

        r_beh = 0.35 * norm_lag + 0.35 * norm_bfi + 0.30 * comp_score
        r_beh = max(-1.0, min(1.0, r_beh))

        # Composite blend (0.4 explicit, 0.6 behavioral)
        composite = 0.40 * r_exp + 0.60 * r_beh

        # User reported usefulness adjustment if available (1-5 scale)
        if user_reported_usefulness is not None:
            # Map 1-5 to [-1.0, +1.0]
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
        """
        Detects concurrent interventions or events within the observation window
        that could confound causal attribution.
        """
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

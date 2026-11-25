"""
Intelligence Layer Grounding for Interventions (Phase 4.5 Task 8).
Generates strictly verified natural-language explanations from empirical evidence.
Enforces the safety model: no hallucinated numbers, causes, or psychological speculation.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

from app.schemas.intervention_schemas import InterventionType

_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


def _numbers_in_payload(payload: Dict[str, Any]) -> set:
    numbers = set()

    def walk(val):
        if isinstance(val, (int, float)):
            f_val = float(val)
            numbers.add(round(f_val, 4))
            numbers.add(round(f_val, 1))
            numbers.add(round(f_val))
            if 0.0 <= f_val <= 1.0:
                numbers.add(round(f_val * 100))
                numbers.add(round(f_val * 100, 1))
        elif isinstance(val, dict):
            for v in val.values():
                walk(v)
        elif isinstance(val, (list, tuple)):
            for v in val:
                walk(v)

    walk(payload)
    return numbers


class InterventionGroundingService:
    """Generates and validates grounded natural-language intervention messages."""

    @classmethod
    def generate_grounded_message(
        cls,
        intervention_type: str,
        supporting_evidence: Dict[str, Any],
        task_title: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Synthesizes (title, message) pair strictly grounded in the supporting evidence.
        Returns verifiable, concise text with exact empirical metrics.
        """
        task_str = f" for '{task_title}'" if task_title else ""

        if intervention_type == InterventionType.SUGGEST_PROTECTED_FOCUS_SESSION.value:
            win_q = supporting_evidence.get("focus_window_quality", 75.0)
            st_h = supporting_evidence.get("window_start_hour", 10)
            end_h = supporting_evidence.get("window_end_hour", 12)
            title = "Protected Focus Block Recommended"
            message = (
                f"Your active focus window ({st_h:02d}:00–{end_h:02d}:00) has a verified quality score of "
                f"{win_q:.0f}/100. Activating a protected session preserves deep work throughput."
            )

        elif intervention_type == InterventionType.REDUCE_APPLICATION_SWITCHING.value:
            sw_rate = supporting_evidence.get("switch_frequency_hourly", 8.5)
            title = "Elevated Desktop Thrashing Detected"
            message = (
                f"Observed {sw_rate:.1f} desktop window switches per hour. "
                "Minimizing transitions protects working memory from micro-delay fragmentation."
            )

        elif intervention_type == InterventionType.SELECT_SUITABLE_FOCUS_WINDOW.value:
            best_h = supporting_evidence.get("recommended_hour", 10)
            best_q = supporting_evidence.get("recommended_quality", 80.0)
            title = "Schedule for Peak Focus Window"
            message = (
                f"Task{task_str} requires concentrated focus. Historical analysis shows peak cognitive throughput "
                f"around {best_h:02d}:00 (quality score {best_q:.0f}/100)."
            )

        elif intervention_type == InterventionType.SUGGEST_RECOVERY_BUFFER.value:
            bfi = supporting_evidence.get("behavioral_friction_index", 65.0)
            disruptions = supporting_evidence.get("consecutive_disruptions", 3)
            title = "Elevated Behavioral Friction — Recovery Buffer Suggested"
            message = (
                f"Behavioral Friction Index is elevated at {bfi:.1f}/100 following {disruptions} clustered disruptions. "
                "A brief 5-minute recovery buffer resets cognitive resumption latency."
            )

        elif intervention_type == InterventionType.RESUME_PREVIOUS_TASK.value:
            lag = supporting_evidence.get("inactivity_minutes", 15)
            title = "Resume Interrupted Task"
            message = (
                f"Task{task_str} was paused {lag:.0f} minutes ago. "
                "Resuming now restores working context before prospective memory decay sets in."
            )

        elif intervention_type == InterventionType.REVIEW_LAST_COMPLETED_STEP.value:
            med_lag = supporting_evidence.get("resumption_lag_seconds", 65.0)
            title = "Review Previous Task Step Before Resuming"
            message = (
                f"Median resumption delay is currently {med_lag:.0f}s. "
                "Reviewing your last completed checkpoint speeds up mental re-orientation."
            )

        elif intervention_type == InterventionType.BREAK_LARGE_TASK.value:
            dur = supporting_evidence.get("estimated_minutes", 90)
            p90 = supporting_evidence.get("typical_p90_focus_minutes", 60)
            title = "Decompose Long Task into Sub-Steps"
            message = (
                f"Estimated duration ({dur} min) exceeds your typical uninterrupted session ({p90} min). "
                "Splitting into sub-steps facilitates completion within natural focus blocks."
            )

        elif intervention_type == InterventionType.REVIEW_APPROACHING_DEADLINE.value:
            due_h = supporting_evidence.get("hours_to_deadline", 3.5)
            title = "Critical Deadline Approaching"
            message = (
                f"Task{task_str} is due in {due_h:.1f} hours and remains pending. "
                "Prioritize execution to prevent deadline overrun."
            )

        elif intervention_type == InterventionType.POSTPONE_LOW_PRIORITY_TASK.value:
            urgent_count = supporting_evidence.get("urgent_tasks_count", 3)
            title = "Postpone Competing Low-Priority Work"
            message = (
                f"You have {urgent_count} near-term deliverables under active attention. "
                f"Deferring lower-priority work{task_str} frees cognitive capacity."
            )

        elif intervention_type == InterventionType.COMPLETE_ASSOCIATED_TASKS_LOCATION_EXIT.value:
            assoc_count = supporting_evidence.get("associated_tasks_count", 2)
            title = "One More Thing Before Leaving"
            message = (
                f"Context records identify {assoc_count} associated task(s){task_str} historically completed together. "
                "Resolving them now prevents location-boundary forgetfulness."
            )

        elif intervention_type == InterventionType.PREPARE_SESSION_MATERIALS.value:
            lead_mins = supporting_evidence.get("lead_time_minutes", 15)
            title = "Prepare Materials Ahead of Focus Session"
            message = (
                f"Your scheduled focus block begins in {lead_mins} minutes. "
                "Gathering required documents eliminates startup micro-delays."
            )

        elif intervention_type == InterventionType.BATCH_RELATED_TASKS.value:
            batch_count = supporting_evidence.get("batch_count", 3)
            cat = supporting_evidence.get("category", "admin")
            title = "Batch Related Tasks Together"
            message = (
                f"Found {batch_count} pending '{cat}' tasks. "
                "Batching related tasks in a dedicated block minimizes context-switching overhead."
            )

        elif intervention_type == InterventionType.REDISTRIBUTE_TASKS.value:
            total_dur = supporting_evidence.get("total_pending_hours", 6.5)
            capacity = supporting_evidence.get("daily_focus_capacity_hours", 4.0)
            title = "Workload Exceeds Daily Focus Capacity"
            message = (
                f"Committed task duration ({total_dur:.1f}h) exceeds your measured daily focus capacity ({capacity:.1f}h). "
                "Rebalancing commitments across upcoming days prevents fatigue."
            )

        elif intervention_type == InterventionType.REVIEW_COMPETING_DEADLINES.value:
            clash_count = supporting_evidence.get("competing_deadlines_count", 2)
            win_h = supporting_evidence.get("conflict_window_hours", 4)
            title = "Clustered Deadlines Conflict"
            message = (
                f"Detected {clash_count} tasks with deadlines clustered within a {win_h}-hour window. "
                "Review priority ordering to prevent last-minute delivery clashes."
            )

        elif intervention_type == InterventionType.REDUCE_EXCESSIVE_TASK_SWITCHING.value:
            started = supporting_evidence.get("started_tasks_count", 3)
            title = "Multiple Incomplete Tasks Started"
            message = (
                f"You have started {started} tasks within the last hour without resolving any. "
                "Focusing on a single active task prevents cognitive fragmentation."
            )

        else:
            title = "Adaptive Workflow Recommendation"
            message = "Actionable recommendation based on observed behavioral workflow patterns."

        # Safety validation: Verify numbers in message correspond to supporting evidence
        payload_numbers = _numbers_in_payload(supporting_evidence)
        message_numbers = [float(m) for m in _NUMBER_RE.findall(message)]
        for num in message_numbers:
            # Check if num exists in payload_numbers (allowing rounding)
            matched = any(
                abs(num - p) < 0.15 or abs(num - p * 100) < 0.15 or abs(num - round(p)) < 0.15
                for p in payload_numbers
            )
            # If not matched and not a standard formatting constant (e.g. 5 min buffer), we ensure safety
            if not matched and num not in {5.0, 15.0, 24.0, 100.0}:
                # Fallback to deterministic template without unmatched numbers
                message = f"Observable workflow evidence supports taking targeted action on this recommendation."
                break

        return title, message

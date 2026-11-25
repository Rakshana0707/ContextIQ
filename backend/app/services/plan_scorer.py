"""
Multi-Attribute Plan Scorer and Comparison Engine (ContextIQ Phase 7.4).
Scores candidate workflow plans across:
- Expected task benefit
- Schedule feasibility
- Recovery impact
- Notification burden
- User preference alignment
- Prediction uncertainty penalty
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from app.schemas.workflow_schemas import PlanComparisonCandidate, WorkflowStepSchema


class PlanScorer:
    """
    Computes normalized multi-attribute utility scores U in [0.0, 1.0]
    to compare alternative workflow configurations and surface trade-offs.
    """

    WEIGHT_BENEFIT = 0.35
    WEIGHT_FEASIBILITY = 0.25
    WEIGHT_RECOVERY = 0.20
    WEIGHT_PREFERENCE = 0.10
    WEIGHT_UNCERTAINTY = 0.10

    @classmethod
    def score_plan(
        cls,
        steps: List[WorkflowStepSchema],
        context: Dict[str, Any],
        strategy: str = "BALANCED",
    ) -> Dict[str, Any]:
        """
        Computes composite utility and dimension sub-scores for a candidate plan.
        """
        task_priority = str(context.get("task_priority", "HIGH")).upper()
        lapse_prob = float(context.get("lapse_probability", 0.75))
        has_calendar_conflict = bool(context.get("has_calendar_conflict", True))
        has_recovery_step = any("recovery:" in s.action_identifier for s in steps)
        has_focus_step = any("focus:" in s.action_identifier or "calendar:" in s.action_identifier for s in steps)
        has_reminder_step = any("reminder:" in s.action_identifier for s in steps)
        step_count = len(steps)

        # 1. Expected Task Benefit [0.0, 1.0]
        # Higher benefit if protecting high priority task from forgetting
        base_benefit = 0.70
        if task_priority in ("HIGH", "CRITICAL"):
            base_benefit += 0.15
        if has_focus_step:
            base_benefit += 0.10
        benefit_score = min(1.0, base_benefit)

        # 2. Schedule Feasibility [0.0, 1.0]
        # Penalize overly complex plans or unaddressed calendar collisions
        feasibility = 0.90
        if has_calendar_conflict and not any("calendar:reschedule" in s.action_identifier for s in steps):
            feasibility -= 0.25
        if step_count > 6:
            feasibility -= (step_count - 6) * 0.05
        feasibility_score = max(0.40, min(1.0, feasibility))

        # 3. Recovery Impact [0.0, 1.0]
        # Higher score if cognitive buffer / decompression step is present
        recovery_score = 0.85 if has_recovery_step else 0.45

        # 4. Notification Burden [0.0, 1.0]
        # Lower burden score (closer to 1.0) means less intrusive UI interruption
        notification_steps = sum(1 for s in steps if "reminder:" in s.action_identifier or "intervention:" in s.action_identifier)
        burden_penalty = min(0.40, notification_steps * 0.10)
        burden_score = round(1.0 - burden_penalty, 3)

        # 5. User Preference Alignment [0.0, 1.0]
        pref_score = 0.88

        # 6. Prediction Uncertainty Penalty [0.0, 0.30]
        # Uncertainty is derived from conformal spread or lack of context
        confidence = float(context.get("confidence_score", 0.85))
        uncertainty_penalty = round(max(0.0, (1.0 - confidence) * 0.5), 3)

        # Composite Utility
        raw_utility = (
            cls.WEIGHT_BENEFIT * benefit_score
            + cls.WEIGHT_FEASIBILITY * feasibility_score
            + cls.WEIGHT_RECOVERY * recovery_score
            + cls.WEIGHT_PREFERENCE * pref_score
            - cls.WEIGHT_UNCERTAINTY * uncertainty_penalty
        )
        utility_score = round(max(0.0, min(1.0, raw_utility)), 3)

        return {
            "utility_score": utility_score,
            "task_benefit_score": round(benefit_score, 3),
            "schedule_feasibility_score": round(feasibility_score, 3),
            "recovery_impact_score": round(recovery_score, 3),
            "notification_burden_score": burden_score,
            "user_preference_alignment": pref_score,
            "prediction_uncertainty_penalty": uncertainty_penalty,
            "strategy": strategy,
        }

    @classmethod
    def generate_plan_alternatives(
        cls,
        primary_steps: List[WorkflowStepSchema],
        context: Dict[str, Any],
    ) -> List[PlanComparisonCandidate]:
        """
        Synthesizes 3 distinct strategy candidates for comparison:
        1. BALANCED_BUFFERED (Recommended): Full focus, calendar adjustment, and recovery buffer.
        2. AGGRESSIVE_FOCUS: Immediate calendar block with distraction clamping; zero extra buffer.
        3. MINIMAL_INTRUSION: Light context warming reminder and deferral without external calendar changes.
        """
        # Plan 1: Balanced (Primary)
        score1 = cls.score_plan(primary_steps, context, strategy="BALANCED_BUFFERED")
        cand1 = PlanComparisonCandidate(
            plan_name="Balanced Cognitive Optimization (Recommended)",
            strategy="BALANCED_BUFFERED",
            utility_score=score1["utility_score"],
            task_benefit_score=score1["task_benefit_score"],
            schedule_feasibility_score=score1["schedule_feasibility_score"],
            recovery_impact_score=score1["recovery_impact_score"],
            notification_burden_score=score1["notification_burden_score"],
            prediction_uncertainty_penalty=score1["prediction_uncertainty_penalty"],
            trade_off_summary="Harmonizes deep focus blocks with mandatory post-task recovery buffers.",
            steps_count=len(primary_steps),
        )

        # Plan 2: Aggressive Focus
        cand2 = PlanComparisonCandidate(
            plan_name="Aggressive Deep Focus",
            strategy="AGGRESSIVE_FOCUS",
            utility_score=0.81,
            task_benefit_score=0.95,
            schedule_feasibility_score=0.72,
            recovery_impact_score=0.50,
            notification_burden_score=0.85,
            prediction_uncertainty_penalty=0.08,
            trade_off_summary="Maximizes immediate focus time but sacrifices cognitive decompression intervals.",
            steps_count=max(3, len(primary_steps) - 1),
        )

        # Plan 3: Minimal Intrusion
        cand3 = PlanComparisonCandidate(
            plan_name="Minimal Intrusion Nudge",
            strategy="MINIMAL_INTRUSION",
            utility_score=0.74,
            task_benefit_score=0.68,
            schedule_feasibility_score=0.96,
            recovery_impact_score=0.60,
            notification_burden_score=0.95,
            prediction_uncertainty_penalty=0.12,
            trade_off_summary="Leaves external calendar untouched; relies solely on internal task reminders.",
            steps_count=2,
        )

        return [cand1, cand2, cand3]

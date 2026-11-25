"""
Multi-Objective Intervention Optimization Engine (ContextIQ Phase 6.7).

Implements:
1. Hard Constraint Filtering (Quiet Hours, Quotas, Calendar, Working Hours, Consent, Opt-outs).
2. 8-Dimensional Normalized Objective Vector Generation.
3. Multi-Attribute Scalarized Utility with Context-Dependent Weight Adaptation.
4. Non-Dominated Pareto-Front Identification and Dominance Ranking.
5. First-Class No-Action Option and Rigorous Fallback Criteria.
6. Transparent Trade-Off Explanations & Uncertainty Assessment.
"""
from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime, time, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from app.schemas.counterfactual import CandidateIntervention
from app.schemas.multi_objective_optimization import (
    EvaluatedCandidate,
    HardConstraintType,
    MultiObjectiveOptimizationRequest,
    MultiObjectiveOptimizationResponse,
    ObjectiveVector,
    ObjectiveWeights,
    OptimizationConstraintStatus,
)

logger = logging.getLogger(__name__)

# Baseline Candidate Profiles (Unconditional Estimates)
CANDIDATE_BASE_PROFILES: Dict[CandidateIntervention, Dict[str, Any]] = {
    CandidateIntervention.NO_INTERVENTION: {
        "title": "No Intervention (Passive Holdout)",
        "completion": 0.52,
        "resumption": 0.45,
        "recovery": 0.40,
        "friction": 0.48,
        "notification_economy": 1.00,  # Zero notification burden
        "interruption_comfort": 1.00,  # Zero cognitive disruption
        "user_pref": 0.70,
        "schedule_feas": 1.00,
        "is_notification": False,
        "is_calendar": False,
        "uncertainty": 0.08,
    },
    CandidateIntervention.IMMEDIATE_REMINDER: {
        "title": "Immediate Contextual Reminder",
        "completion": 0.72,
        "resumption": 0.82,
        "recovery": 0.50,
        "friction": 0.52,
        "notification_economy": 0.35,  # Moderate disruption penalty
        "interruption_comfort": 0.45,
        "user_pref": 0.65,
        "schedule_feas": 0.95,
        "is_notification": True,
        "is_calendar": False,
        "uncertainty": 0.12,
    },
    CandidateIntervention.DELAYED_REMINDER: {
        "title": "Delayed Follow-Up Reminder (15m)",
        "completion": 0.68,
        "resumption": 0.65,
        "recovery": 0.55,
        "friction": 0.58,
        "notification_economy": 0.50,
        "interruption_comfort": 0.60,
        "user_pref": 0.60,
        "schedule_feas": 0.90,
        "is_notification": True,
        "is_calendar": False,
        "uncertainty": 0.14,
    },
    CandidateIntervention.SHORT_RECOVERY_BUFFER: {
        "title": "Micro Recovery Buffer (10m)",
        "completion": 0.64,
        "resumption": 0.76,
        "recovery": 0.88,  # Exceptional recovery enhancement
        "friction": 0.82,  # Substantial friction reduction
        "notification_economy": 0.80,  # Minimal notification burden
        "interruption_comfort": 0.85,
        "user_pref": 0.80,
        "schedule_feas": 0.85,
        "is_notification": False,
        "is_calendar": True,
        "uncertainty": 0.10,
    },
    CandidateIntervention.FOCUS_SESSION_RECOMMENDATION: {
        "title": "Protected Focus Block (45m)",
        "completion": 0.86,  # Maximum completion likelihood
        "resumption": 0.70,
        "recovery": 0.75,
        "friction": 0.78,
        "notification_economy": 0.75,
        "interruption_comfort": 0.75,
        "user_pref": 0.75,
        "schedule_feas": 0.65,  # Requires open schedule block
        "is_notification": False,
        "is_calendar": True,
        "uncertainty": 0.15,
    },
    CandidateIntervention.CALENDAR_RESCHEDULING: {
        "title": "Adaptive Calendar Rescheduling",
        "completion": 0.78,
        "resumption": 0.58,
        "recovery": 0.65,
        "friction": 0.70,
        "notification_economy": 0.85,
        "interruption_comfort": 0.70,
        "user_pref": 0.55,  # Some users resist schedule changes
        "schedule_feas": 0.55,  # Heavily dependent on calendar slack
        "is_notification": False,
        "is_calendar": True,
        "uncertainty": 0.18,
    },
    CandidateIntervention.BREAK_LARGE_TASK: {
        "title": "Decompose into Subtasks",
        "completion": 0.75,
        "resumption": 0.72,
        "recovery": 0.60,
        "friction": 0.75,
        "notification_economy": 0.90,
        "interruption_comfort": 0.80,
        "user_pref": 0.70,
        "schedule_feas": 0.90,
        "is_notification": False,
        "is_calendar": False,
        "uncertainty": 0.12,
    },
}


class MultiObjectiveOptimizer:
    """
    Core optimizer executing multi-attribute utility scalarization, hard constraint gating,
    contextual weight modulation, Pareto dominance ranking, and explainability generation.
    """

    @classmethod
    def optimize(
        cls,
        request: MultiObjectiveOptimizationRequest,
    ) -> MultiObjectiveOptimizationResponse:
        """
        Executes end-to-end multi-objective intervention optimization.
        Guarantees:
        1. Non-bypassable hard constraint enforcement.
        2. Pareto frontier computation.
        3. No-Action preference if utility lift is negligible or uncertainty excessive.
        4. Full transparency on improved and worsened trade-offs.
        """
        eval_time = request.current_time or datetime.now(timezone.utc)
        user_id = request.user_id or uuid.uuid4()
        features = dict(request.context_features or {})
        constraints_cfg = dict(request.user_constraints or {})
        base_weights = request.custom_weights or ObjectiveWeights()

        # 1. Adapt Weights for Real-Time Context
        effective_weights, adaptations = cls.adapt_weights_for_context(
            base_weights=base_weights, context_features=features, eval_time=eval_time
        )

        # 2. Evaluate Hard Constraints for all candidates
        constraint_audit, candidate_violations = cls.evaluate_hard_constraints(
            eval_time=eval_time,
            features=features,
            constraints_cfg=constraints_cfg,
        )

        # 3. Compute Objective Vectors for all candidates
        evaluated_candidates: List[EvaluatedCandidate] = []
        for cand, profile in CANDIDATE_BASE_PROFILES.items():
            violations = candidate_violations.get(cand, [])
            is_feasible = len(violations) == 0

            obj_vector = cls.compute_objective_vector(
                candidate=cand,
                profile=profile,
                context_features=features,
                constraints_cfg=constraints_cfg,
            )

            # Scalarized utility: U(a) = sum(w_i * o_i)
            weighted_u = cls.scalarize_utility(obj_vector, effective_weights)

            evaluated_candidates.append(
                EvaluatedCandidate(
                    candidate=cand,
                    title=profile["title"],
                    is_feasible=is_feasible,
                    constraint_violations=violations,
                    objectives=obj_vector,
                    weighted_utility=round(weighted_u, 4),
                    net_utility_lift=0.0,  # Computed relative to No-Intervention below
                    is_pareto_optimal=False,
                    pareto_rank=1,
                    dominates=[],
                    dominated_by=[],
                    confidence_score=round(1.0 - profile["uncertainty"], 2),
                    uncertainty_width=round(profile["uncertainty"] * 2.0, 2),
                )
            )

        # 4. Compute Net Utility Lift Relative to No-Intervention
        no_action_candidate = next(
            c for c in evaluated_candidates if c.candidate == CandidateIntervention.NO_INTERVENTION
        )
        u_no_action = no_action_candidate.weighted_utility

        for c in evaluated_candidates:
            c.net_utility_lift = round(c.weighted_utility - u_no_action, 4)
            # Identify improved vs worsened trade-offs relative to No-Intervention
            c.improved_objectives, c.worsened_objectives = cls.analyze_trade_offs(
                candidate_vector=c.objectives,
                baseline_vector=no_action_candidate.objectives,
            )

        # 5. Compute Pareto-Frontier across Feasible Candidates
        feasible_candidates = [c for c in evaluated_candidates if c.is_feasible]
        cls.compute_pareto_frontier(feasible_candidates)

        pareto_frontier = [c for c in feasible_candidates if c.is_pareto_optimal]

        # 6. Champion Selection with Strict No-Action Safeguards
        selected_intervention, is_no_action, rationale = cls.select_champion_with_safeguards(
            evaluated_candidates=evaluated_candidates,
            feasible_candidates=feasible_candidates,
            no_action_candidate=no_action_candidate,
            min_utility_lift=request.min_utility_lift_threshold,
            uncertainty_threshold=request.strict_uncertainty_threshold,
            features=features,
        )

        # 7. Collect explanations for selected champion
        chosen_candidate_obj = next(
            c for c in evaluated_candidates if c.candidate == selected_intervention
        )

        return MultiObjectiveOptimizationResponse(
            optimization_id=f"opt_{uuid.uuid4().hex[:10]}",
            user_id=user_id,
            evaluated_at=eval_time,
            selected_intervention=selected_intervention,
            is_no_action=is_no_action,
            selection_rationale=rationale,
            effective_weights=effective_weights,
            context_adaptations=adaptations,
            pareto_frontier=pareto_frontier,
            all_evaluated_candidates=evaluated_candidates,
            applied_constraints=constraint_audit,
            improved_objectives=chosen_candidate_obj.improved_objectives,
            worsened_objectives=chosen_candidate_obj.worsened_objectives,
            requires_authorization=True,
            disclaimer="Optimization balances productivity against cognitive burden and quiet hours. No-Action is preferred when benefit is negligible or uncertainty exceeds tolerance.",
        )

    # -----------------------------------------------------------------------
    # Hard Constraints Evaluation
    # -----------------------------------------------------------------------

    @classmethod
    def evaluate_hard_constraints(
        cls,
        eval_time: datetime,
        features: Dict[str, Any],
        constraints_cfg: Dict[str, Any],
    ) -> Tuple[List[OptimizationConstraintStatus], Dict[CandidateIntervention, List[str]]]:
        """
        Evaluates 7 non-bypassable constraints against candidate requirements.
        Returns audit list of checked constraints and map of violations per candidate.
        """
        violations_map: Dict[CandidateIntervention, List[str]] = {
            c: [] for c in CANDIDATE_BASE_PROFILES.keys()
        }
        audit: List[OptimizationConstraintStatus] = []

        # 1. Quiet Hours (e.g. 22:00 to 08:00 default or configured)
        qh_enabled = bool(constraints_cfg.get("quiet_hours_enabled", True))
        qh_start = int(constraints_cfg.get("quiet_hours_start", 22))
        qh_end = int(constraints_cfg.get("quiet_hours_end", 8))
        current_hour = eval_time.hour

        in_quiet_hours = False
        if qh_enabled:
            if qh_start > qh_end:  # Over midnight (e.g. 22 -> 8)
                in_quiet_hours = current_hour >= qh_start or current_hour < qh_end
            else:
                in_quiet_hours = qh_start <= current_hour < qh_end

        if in_quiet_hours:
            audit.append(
                OptimizationConstraintStatus(
                    constraint_type=HardConstraintType.QUIET_HOURS,
                    passed=False,
                    reason=f"Current time ({eval_time.strftime('%H:%M')}) falls inside active quiet hours ({qh_start:02d}:00-{qh_end:02d}:00).",
                )
            )
            # Notification alerts are prohibited during quiet hours
            for cand, prof in CANDIDATE_BASE_PROFILES.items():
                if prof.get("is_notification", False):
                    violations_map[cand].append("Violates quiet hours: Audible or visual notifications prohibited.")
        else:
            audit.append(
                OptimizationConstraintStatus(
                    constraint_type=HardConstraintType.QUIET_HOURS,
                    passed=True,
                    reason=f"Current time ({eval_time.strftime('%H:%M')}) is outside quiet hours window.",
                )
            )

        # 2. Maximum Notification Frequency (Hourly & Daily Limits)
        daily_count = int(constraints_cfg.get("notifications_sent_today", features.get("notifications_sent_today", 0)))
        hourly_count = int(constraints_cfg.get("notifications_sent_this_hour", features.get("notifications_sent_this_hour", 0)))
        max_daily = int(constraints_cfg.get("max_notifications_per_day", 8))
        max_hourly = int(constraints_cfg.get("max_notifications_per_hour", 2))

        freq_violation = False
        freq_reason = ""
        if daily_count >= max_daily:
            freq_violation = True
            freq_reason = f"Daily notification limit reached ({daily_count}/{max_daily})."
        elif hourly_count >= max_hourly:
            freq_violation = True
            freq_reason = f"Hourly notification limit reached ({hourly_count}/{max_hourly})."

        if freq_violation:
            audit.append(
                OptimizationConstraintStatus(
                    constraint_type=HardConstraintType.MAX_NOTIFICATION_FREQUENCY,
                    passed=False,
                    reason=freq_reason,
                )
            )
            for cand, prof in CANDIDATE_BASE_PROFILES.items():
                if prof.get("is_notification", False):
                    violations_map[cand].append(f"Notification quota exceeded: {freq_reason}")
        else:
            audit.append(
                OptimizationConstraintStatus(
                    constraint_type=HardConstraintType.MAX_NOTIFICATION_FREQUENCY,
                    passed=True,
                    reason=f"Notification frequency within quota ({hourly_count}/{max_hourly} hourly, {daily_count}/{max_daily} daily).",
                )
            )

        # 3. Calendar Availability & Meeting Conflicts
        calendar_load = float(features.get("calendar_load", 3.0))  # 0 to 8 hours
        is_calendar_full = bool(constraints_cfg.get("calendar_fully_booked", calendar_load >= 7.5))

        if is_calendar_full:
            audit.append(
                OptimizationConstraintStatus(
                    constraint_type=HardConstraintType.CALENDAR_AVAILABILITY,
                    passed=False,
                    reason="Calendar has zero available slots; schedule is completely booked.",
                )
            )
            for cand in [CandidateIntervention.CALENDAR_RESCHEDULING, CandidateIntervention.FOCUS_SESSION_RECOMMENDATION]:
                violations_map[cand].append("Calendar unavailable: No open slot exists for rescheduling or focus session.")
        else:
            audit.append(
                OptimizationConstraintStatus(
                    constraint_type=HardConstraintType.CALENDAR_AVAILABILITY,
                    passed=True,
                    reason=f"Calendar availability confirmed ({calendar_load:.1f}h booked, free slots available).",
                )
            )

        # 4. User-Defined Working Hours
        work_start = int(constraints_cfg.get("working_hours_start", 9))
        work_end = int(constraints_cfg.get("working_hours_end", 18))
        outside_work_hours = current_hour < work_start or current_hour >= work_end

        if outside_work_hours:
            audit.append(
                OptimizationConstraintStatus(
                    constraint_type=HardConstraintType.WORKING_HOURS,
                    passed=False,
                    reason=f"Current time ({eval_time.strftime('%H:%M')}) is outside working hours ({work_start:02d}:00-{work_end:02d}:00).",
                )
            )
            # Rescheduling or focus sessions cannot be booked outside work hours
            for cand in [CandidateIntervention.CALENDAR_RESCHEDULING, CandidateIntervention.FOCUS_SESSION_RECOMMENDATION]:
                violations_map[cand].append("Outside working hours: Cannot schedule professional work sessions.")
        else:
            audit.append(
                OptimizationConstraintStatus(
                    constraint_type=HardConstraintType.WORKING_HOURS,
                    passed=True,
                    reason=f"Current time is within working hours ({work_start:02d}:00-{work_end:02d}:00).",
                )
            )

        # 5. Explicit Task Constraints (Immutability / Deadlines)
        task_immutable = bool(constraints_cfg.get("task_is_immutable", False))
        due_minutes = float(features.get("due_in_minutes", 120.0))

        if task_immutable or due_minutes <= 15.0:
            audit.append(
                OptimizationConstraintStatus(
                    constraint_type=HardConstraintType.EXPLICIT_TASK_CONSTRAINTS,
                    passed=False,
                    reason="Task has hard deadline (<15m) or explicit immutability constraint.",
                )
            )
            violations_map[CandidateIntervention.CALENDAR_RESCHEDULING].append(
                "Task immutability constraint: Rescheduling prohibited for imminent deadline or locked task."
            )
            violations_map[CandidateIntervention.BREAK_LARGE_TASK].append(
                "Task immutability constraint: Decomposition prohibited on imminent deadline."
            )
        else:
            audit.append(
                OptimizationConstraintStatus(
                    constraint_type=HardConstraintType.EXPLICIT_TASK_CONSTRAINTS,
                    passed=True,
                    reason="No hard task deadline or immutability constraints violated.",
                )
            )

        # 6. Consent & Channel Permissions
        notifications_permitted = bool(constraints_cfg.get("notifications_permitted", True))
        if not notifications_permitted:
            audit.append(
                OptimizationConstraintStatus(
                    constraint_type=HardConstraintType.CONSENT_AND_PERMISSIONS,
                    passed=False,
                    reason="User has revoked notification delivery permissions for this channel.",
                )
            )
            for cand, prof in CANDIDATE_BASE_PROFILES.items():
                if prof.get("is_notification", False):
                    violations_map[cand].append("Consent missing: Notification permissions not granted.")
        else:
            audit.append(
                OptimizationConstraintStatus(
                    constraint_type=HardConstraintType.CONSENT_AND_PERMISSIONS,
                    passed=True,
                    reason="Notification and telemetry consent verified.",
                )
            )

        # 7. User Opt-Out Settings
        opt_outs: Set[str] = set(constraints_cfg.get("opted_out_interventions", []))
        if opt_outs:
            audit.append(
                OptimizationConstraintStatus(
                    constraint_type=HardConstraintType.USER_OPT_OUT,
                    passed=False,
                    reason=f"User has opted out of {len(opt_outs)} intervention types.",
                )
            )
            for cand in CANDIDATE_BASE_PROFILES.keys():
                if cand.value in opt_outs or cand in opt_outs:
                    violations_map[cand].append(f"User opt-out: Explicitly disabled by user settings.")
        else:
            audit.append(
                OptimizationConstraintStatus(
                    constraint_type=HardConstraintType.USER_OPT_OUT,
                    passed=True,
                    reason="No intervention opt-outs configured.",
                )
            )

        # Invariant: NO_INTERVENTION can NEVER be violated by constraints
        violations_map[CandidateIntervention.NO_INTERVENTION] = []

        return audit, violations_map

    # -----------------------------------------------------------------------
    # Objective Computation
    # -----------------------------------------------------------------------

    @classmethod
    def compute_objective_vector(
        cls,
        candidate: CandidateIntervention,
        profile: Dict[str, Any],
        context_features: Dict[str, Any],
        constraints_cfg: Dict[str, Any],
    ) -> ObjectiveVector:
        """
        Computes normalized 8-objective vector for candidate adjusted by context.
        Higher is strictly better for every dimension in [0.0, 1.0].
        """
        bfi = float(context_features.get("baseline_bfi", 50.0))
        recent_ints = float(context_features.get("recent_interruptions", 2.0))
        task_pri = float(context_features.get("task_priority", 2.0))

        # Start with base estimates
        comp = profile["completion"]
        resump = profile["resumption"]
        rec = profile["recovery"]
        fric = profile["friction"]
        notif_econ = profile["notification_economy"]
        comfort = profile["interruption_comfort"]
        pref = profile["user_pref"]
        sched = profile["schedule_feas"]

        # Modulations based on real-time context
        # High cognitive fatigue lowers completion efficiency, elevates recovery impact
        if bfi > 65.0:
            comp = max(0.20, comp - 0.10)
            if candidate == CandidateIntervention.SHORT_RECOVERY_BUFFER:
                rec = min(0.98, rec + 0.08)
                fric = min(0.95, fric + 0.08)
            elif profile.get("is_notification", False):
                # Notifications worsen cognitive comfort during fatigue
                comfort = max(0.15, comfort - 0.18)
                fric = max(0.20, fric - 0.12)

        # High task priority boosts completion focus
        if task_pri >= 3.5:
            comp = min(0.98, comp + 0.10)
            resump = min(0.98, resump + 0.08)

        # Frequent recent interruptions penalize notification economy
        if recent_ints >= 3.0 and profile.get("is_notification", False):
            notif_econ = max(0.10, notif_econ - 0.15)
            comfort = max(0.10, comfort - 0.15)

        # Check explicit user preference overrides
        user_affinities = constraints_cfg.get("intervention_affinities", {})
        if candidate.value in user_affinities:
            pref = float(np.clip(user_affinities[candidate.value], 0.0, 1.0))

        return ObjectiveVector(
            task_completion=round(float(np.clip(comp, 0.0, 1.0)), 4),
            task_resumption=round(float(np.clip(resump, 0.0, 1.0)), 4),
            recovery_duration=round(float(np.clip(rec, 0.0, 1.0)), 4),
            behavioral_friction=round(float(np.clip(fric, 0.0, 1.0)), 4),
            notification_economy=round(float(np.clip(notif_econ, 0.0, 1.0)), 4),
            interruption_comfort=round(float(np.clip(comfort, 0.0, 1.0)), 4),
            user_preferences=round(float(np.clip(pref, 0.0, 1.0)), 4),
            schedule_feasibility=round(float(np.clip(sched, 0.0, 1.0)), 4),
        )

    # -----------------------------------------------------------------------
    # Context Weight Adaptation
    # -----------------------------------------------------------------------

    @classmethod
    def adapt_weights_for_context(
        cls,
        base_weights: ObjectiveWeights,
        context_features: Dict[str, Any],
        eval_time: datetime,
    ) -> Tuple[ObjectiveWeights, List[str]]:
        """
        Dynamically adjusts objective weights to reflect user cognitive state and time horizon.
        """
        w = base_weights.normalized()
        adaptations: List[str] = []

        comp = w.task_completion
        resump = w.task_resumption
        rec = w.recovery_duration
        fric = w.behavioral_friction
        notif = w.notification_economy
        comf = w.interruption_comfort
        pref = w.user_preferences
        sched = w.schedule_feasibility

        bfi = float(context_features.get("baseline_bfi", 50.0))
        due_minutes = float(context_features.get("due_in_minutes", 180.0))
        recent_ints = float(context_features.get("recent_interruptions", 2.0))

        # Condition 1: Elevated Cognitive Fatigue / High Friction
        if bfi > 65.0:
            rec += 0.10
            fric += 0.10
            comp = max(0.05, comp - 0.12)
            adaptations.append(
                f"Elevated Cognitive Fatigue (BFI {bfi:.0f} > 65): Prioritized Recovery (+10%) & Friction Reduction (+10%), reduced Task Completion pressure."
            )

        # Condition 2: Imminent Task Deadline (< 2 hours)
        if due_minutes < 120.0:
            comp += 0.15
            resump += 0.08
            comf = max(0.05, comf - 0.10)
            adaptations.append(
                f"Imminent Deadline ({due_minutes:.0f}m remaining): Prioritized Task Completion (+15%) and Resumption (+8%)."
            )

        # Condition 3: Notification Clustering / Disruption
        if recent_ints >= 3.0:
            notif += 0.12
            comf += 0.08
            adaptations.append(
                f"Frequent Recent Disruptions ({recent_ints:.0f} interruptions): Elevated Notification Economy (+12%) to guard attention."
            )

        # Re-normalize
        adapted = ObjectiveWeights(
            task_completion=comp,
            task_resumption=resump,
            recovery_duration=rec,
            behavioral_friction=fric,
            notification_economy=notif,
            interruption_comfort=comf,
            user_preferences=pref,
            schedule_feasibility=sched,
        ).normalized()

        return adapted, adaptations

    # -----------------------------------------------------------------------
    # Utility Scalarization
    # -----------------------------------------------------------------------

    @classmethod
    def scalarize_utility(
        cls,
        vector: ObjectiveVector,
        weights: ObjectiveWeights,
    ) -> float:
        """
        Scalarizes 8-dimensional normalized objective vector into single multi-attribute utility:
        U(a) = sum(w_i * o_i) in [0.0, 1.0].
        """
        w = weights.normalized()
        u = (
            w.task_completion * vector.task_completion
            + w.task_resumption * vector.task_resumption
            + w.recovery_duration * vector.recovery_duration
            + w.behavioral_friction * vector.behavioral_friction
            + w.notification_economy * vector.notification_economy
            + w.interruption_comfort * vector.interruption_comfort
            + w.user_preferences * vector.user_preferences
            + w.schedule_feasibility * vector.schedule_feasibility
        )
        return float(np.clip(u, 0.0, 1.0))

    # -----------------------------------------------------------------------
    # Pareto Dominance Analysis
    # -----------------------------------------------------------------------

    @classmethod
    def compute_pareto_frontier(
        cls,
        candidates: List[EvaluatedCandidate],
    ) -> None:
        """
        Performs multi-dimensional Pareto dominance comparisons on feasible candidates:
        Candidate A dominates B (A > B) if for all 8 objectives o_i(A) >= o_i(B)
        and for at least one objective o_j(A) > o_j(B) + 1e-4.
        Updates is_pareto_optimal, pareto_rank, dominates, and dominated_by in-place.
        """
        if not candidates:
            return

        for a in candidates:
            a.dominates = []
            a.dominated_by = []

        for i, a in enumerate(candidates):
            v_a = a.objectives.to_dict()
            for j, b in enumerate(candidates):
                if i == j:
                    continue
                v_b = b.objectives.to_dict()

                all_ge = all(v_a[k] >= v_b[k] - 1e-4 for k in v_a.keys())
                strict_gt = any(v_a[k] > v_b[k] + 1e-3 for k in v_a.keys())

                if all_ge and strict_gt:
                    a.dominates.append(b.candidate)
                    b.dominated_by.append(a.candidate)

        # Candidates with dominated_by == 0 form the Pareto frontier (rank 1)
        for c in candidates:
            if len(c.dominated_by) == 0:
                c.is_pareto_optimal = True
                c.pareto_rank = 1
            else:
                c.is_pareto_optimal = False
                c.pareto_rank = 1 + len(c.dominated_by)

    # -----------------------------------------------------------------------
    # Trade-Off Analysis
    # -----------------------------------------------------------------------

    @classmethod
    def analyze_trade_offs(
        cls,
        candidate_vector: ObjectiveVector,
        baseline_vector: ObjectiveVector,
    ) -> Tuple[List[str], List[str]]:
        """
        Compares candidate objectives against No-Intervention baseline.
        Returns explicit list of improved and worsened objectives.
        """
        cand_dict = candidate_vector.to_dict()
        base_dict = baseline_vector.to_dict()

        improved: List[str] = []
        worsened: List[str] = []

        objective_names = {
            "task_completion": "Task Completion Likelihood",
            "task_resumption": "Task Resumption Speed",
            "recovery_duration": "Cognitive Recovery Enhancement",
            "behavioral_friction": "Cognitive Friction Reduction",
            "notification_economy": "Notification Economy (Disruption Penalty)",
            "interruption_comfort": "Interruption Comfort",
            "user_preferences": "Preference Alignment",
            "schedule_feasibility": "Schedule Feasibility",
        }

        for k, name in objective_names.items():
            delta = cand_dict[k] - base_dict[k]
            if delta > 0.03:
                improved.append(f"{name} (+{delta * 100:.1f}%)")
            elif delta < -0.03:
                worsened.append(f"{name} ({delta * 100:.1f}%)")

        return improved, worsened

    # -----------------------------------------------------------------------
    # Champion Selection & No-Action Safeguards
    # -----------------------------------------------------------------------

    @classmethod
    def select_champion_with_safeguards(
        cls,
        evaluated_candidates: List[EvaluatedCandidate],
        feasible_candidates: List[EvaluatedCandidate],
        no_action_candidate: EvaluatedCandidate,
        min_utility_lift: float,
        uncertainty_threshold: float,
        features: Dict[str, Any],
    ) -> Tuple[CandidateIntervention, bool, str]:
        """
        Selects the optimal intervention candidate while strictly enforcing No-Action safeguards:
        1. If all active candidates are infeasible -> No-Action.
        2. If top candidate lift over No-Action is < min_utility_lift -> No-Action.
        3. If top candidate uncertainty width > uncertainty_threshold -> No-Action.
        4. If notification burden during high fatigue is excessive -> No-Action.
        """
        active_feasible = [
            c for c in feasible_candidates if c.candidate != CandidateIntervention.NO_INTERVENTION
        ]

        # Case 1: Infeasible schedule or all active filtered by constraints
        if not active_feasible:
            return (
                CandidateIntervention.NO_INTERVENTION,
                True,
                "No active intervention candidate satisfied all hard constraints (quiet hours, quotas, or calendar availability). Selected No-Action as safe passive holdout.",
            )

        # Sort active candidates by weighted utility
        active_feasible.sort(key=lambda x: x.weighted_utility, reverse=True)
        top_active = active_feasible[0]

        # Case 2: Excessive Uncertainty Fallback
        if top_active.uncertainty_width > uncertainty_threshold:
            return (
                CandidateIntervention.NO_INTERVENTION,
                True,
                f"Candidate '{top_active.title}' exhibits prediction uncertainty interval width ({top_active.uncertainty_width:.2f}) exceeding threshold ({uncertainty_threshold:.2f}). Defaulted to No-Action to prevent erratic disruption.",
            )

        # Case 3: Negligible Net Utility Lift over No-Action
        if top_active.net_utility_lift < min_utility_lift:
            return (
                CandidateIntervention.NO_INTERVENTION,
                True,
                f"Top candidate '{top_active.title}' provides marginal net utility lift (+{top_active.net_utility_lift:.3f}) below required threshold (+{min_utility_lift:.3f}). Passive holdout (No-Action) preserved to prevent notification fatigue.",
            )

        # Case 4: High Fatigue Notification Defense
        bfi = float(features.get("baseline_bfi", 50.0))
        if bfi > 75.0 and top_active.candidate in (
            CandidateIntervention.IMMEDIATE_REMINDER,
            CandidateIntervention.DELAYED_REMINDER,
        ):
            # Prefer recovery buffer or no-action
            rec_candidates = [
                c for c in active_feasible if c.candidate == CandidateIntervention.SHORT_RECOVERY_BUFFER
            ]
            if rec_candidates and rec_candidates[0].net_utility_lift >= min_utility_lift:
                chosen = rec_candidates[0]
                return (
                    chosen.candidate,
                    False,
                    f"Selected '{chosen.title}' over reminder due to critical cognitive fatigue (BFI {bfi:.0f} > 75). Prioritized recovery restoration over active prompt.",
                )
            else:
                return (
                    CandidateIntervention.NO_INTERVENTION,
                    True,
                    f"Selected No-Action: Critical cognitive fatigue (BFI {bfi:.0f} > 75) makes active notification prompts counterproductive.",
                )

        # Case 5: Valid Optimal Candidate
        pareto_status = "Non-dominated Pareto-optimal" if top_active.is_pareto_optimal else f"Rank {top_active.pareto_rank} in candidate space"
        rationale = (
            f"Selected '{top_active.title}' ({pareto_status}) with weighted utility {top_active.weighted_utility:.3f} "
            f"(+{top_active.net_utility_lift:.3f} lift over No-Action). "
            f"Optimizes {', '.join(top_active.improved_objectives[:2]) or 'primary performance'} "
            f"while safely respecting quiet hours and notification quotas."
        )

        return top_active.candidate, False, rationale

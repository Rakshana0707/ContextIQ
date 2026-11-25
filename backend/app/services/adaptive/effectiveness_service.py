"""
Service layer for ContextIQ Intervention Effectiveness and Causal Evaluation Engine (Phase 4.7).
Orchestrates:
- Empirical outcome ingestion and multi-horizon tracking.
- Execution verification (distinguishing acceptance from behavioral action).
- Randomized experiment tracking and ethical holdout boundary enforcement.
- Causal ATE estimation (Doubly Robust / IPW) with FDR control and power guards.
- Statistical reporting with clear observational vs. causal demarcation.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.effectiveness.causal_evaluator import CausalEvaluator
from app.effectiveness.outcome_tracker import OutcomeTracker, _normalize_utc
from app.models.effectiveness_models import InterventionExperiment, InterventionOutcome
from app.models.user_intervention import UserIntervention
from app.schemas.effectiveness_schemas import (
    InterventionEffectivenessOverview,
    InterventionExperimentRead,
    InterventionOutcomeRead,
    InterventionTypeComparison,
    OutcomeWindowMinutes,
    TreatmentStatus,
)


class EffectivenessService:
    """Service orchestrating intervention outcome evaluation and causal analytics."""

    @classmethod
    def record_outcome(
        cls,
        db: Session,
        user_id: uuid.UUID,
        intervention_type: str,
        intervention_category: str,
        treatment_status: str = TreatmentStatus.TREATED.value,
        intervention_id: Optional[uuid.UUID] = None,
        decision_id: Optional[uuid.UUID] = None,
        experiment_id: Optional[str] = None,
        presented_at: Optional[datetime] = None,
        user_action: str = "NO_ACTION",
        action_timestamp: Optional[datetime] = None,
        telemetry_events: Optional[List[Dict[str, Any]]] = None,
        task_events: Optional[List[Dict[str, Any]]] = None,
        target_task_id: Optional[uuid.UUID] = None,
        baseline_bfi: float = 50.0,
        baseline_resumption_lag_seconds: float = 30.0,
        baseline_hourly_interruption_rate: float = 2.0,
        baseline_task_due_at: Optional[datetime] = None,
        baseline_task_postponed_count: int = 0,
        observed_bfi: Optional[float] = None,
        observed_resumption_lag_seconds: Optional[float] = None,
        observed_hourly_interruption_rate: Optional[float] = None,
        target_task_completed: bool = False,
        task_completed_at: Optional[datetime] = None,
        adhered_to_deadline: Optional[bool] = None,
        postponed_after_intervention: bool = False,
        focus_session_minutes: Optional[float] = None,
        user_reported_usefulness: Optional[float] = None,
        is_critical_urgency: bool = False,
    ) -> InterventionOutcome:
        """
        Records an intervention outcome or holdout observation, verifying behavioral execution,
        enforcing ethical constraints, computing metric deltas, and synthesizing composite scores.
        """
        now = _normalize_utc(presented_at) or datetime.now(timezone.utc)

        # 1. Ethical holdout guardrail check:
        # Never place in control/holdout if deadline < 2h or critically urgent
        effective_status = treatment_status
        if treatment_status == TreatmentStatus.CONTROL_HOLDOUT.value:
            can_holdout = OutcomeTracker.can_assign_to_control_holdout(
                task_due_at=baseline_task_due_at,
                as_of=now,
                is_critical_urgency=is_critical_urgency,
            )
            if not can_holdout:
                effective_status = TreatmentStatus.TREATED.value

        # 2. Observation window
        window_minutes = OutcomeTracker.determine_observation_window_minutes(intervention_category)
        window_start = now
        window_end = window_start + timedelta(minutes=window_minutes)

        # 3. Execution verification
        act_ts = _normalize_utc(action_timestamp) or now
        was_executed, exec_ts, exec_evidence = OutcomeTracker.verify_execution(
            intervention_type=intervention_type,
            user_action=user_action,
            telemetry_events=telemetry_events,
            task_events=task_events,
            target_task_id=target_task_id,
            action_timestamp=act_ts,
            window_end=window_end,
        )

        # 4. Deltas
        deltas = OutcomeTracker.compute_cognitive_deltas(
            baseline_bfi=baseline_bfi,
            observed_bfi=observed_bfi,
            baseline_lag_seconds=baseline_resumption_lag_seconds,
            observed_lag_seconds=observed_resumption_lag_seconds,
            baseline_interruption_rate=baseline_hourly_interruption_rate,
            observed_interruption_rate=observed_hourly_interruption_rate,
        )

        # 5. Composite effectiveness score
        comp_score = OutcomeTracker.synthesize_composite_score(
            user_action=user_action,
            was_executed=was_executed,
            bfi_delta=deltas["bfi_delta"],
            resumption_lag_delta=deltas["resumption_lag_delta_seconds"],
            target_task_completed=target_task_completed,
            user_reported_usefulness=user_reported_usefulness,
            postponed_after_intervention=postponed_after_intervention,
        )

        # 6. Confounders detection
        # Query recent outcomes in window
        recent_stmt = (
            select(InterventionOutcome)
            .where(
                InterventionOutcome.user_id == user_id,
                InterventionOutcome.created_at >= window_start - timedelta(minutes=60),
            )
            .limit(20)
        )
        recent_rows = db.scalars(recent_stmt).all()
        recent_dicts = [
            {
                "id": str(r.id),
                "intervention_id": str(r.intervention_id) if r.intervention_id else None,
                "intervention_type": r.intervention_type,
                "presented_at": r.presented_at,
            }
            for r in recent_rows
        ]
        confounders = OutcomeTracker.detect_confounders(
            window_start=window_start,
            window_end=window_end,
            concurrent_outcomes=recent_dicts,
            current_intervention_id=intervention_id,
        )

        outcome = InterventionOutcome(
            user_id=user_id,
            intervention_id=intervention_id,
            decision_id=decision_id,
            intervention_type=intervention_type,
            intervention_category=intervention_category,
            treatment_status=effective_status,
            experiment_id=experiment_id,
            presented_at=now,
            user_action=user_action,
            action_timestamp=act_ts,
            was_executed=was_executed,
            execution_timestamp=exec_ts,
            execution_evidence=exec_evidence,
            window_start=window_start,
            window_end=window_end,
            observation_window_minutes=window_minutes,
            baseline_bfi=baseline_bfi,
            baseline_resumption_lag_seconds=baseline_resumption_lag_seconds,
            baseline_hourly_interruption_rate=baseline_hourly_interruption_rate,
            baseline_task_due_at=baseline_task_due_at,
            baseline_task_postponed_count=baseline_task_postponed_count,
            observed_bfi=observed_bfi,
            observed_resumption_lag_seconds=observed_resumption_lag_seconds,
            observed_hourly_interruption_rate=observed_hourly_interruption_rate,
            target_task_completed=target_task_completed,
            task_completed_at=task_completed_at,
            adhered_to_deadline=adhered_to_deadline,
            postponed_after_intervention=postponed_after_intervention,
            focus_session_minutes=focus_session_minutes,
            bfi_delta=deltas["bfi_delta"],
            resumption_lag_delta_seconds=deltas["resumption_lag_delta_seconds"],
            interruption_rate_delta=deltas["interruption_rate_delta"],
            composite_effectiveness_score=comp_score,
            user_reported_usefulness=user_reported_usefulness,
            confounders_detected=confounders,
            is_statistically_valid=len(confounders) < 3,
        )

        db.add(outcome)

        # Update experiment sample counts if linked
        if experiment_id:
            try:
                exp_uuid = uuid.UUID(experiment_id)
                exp = db.get(InterventionExperiment, exp_uuid)
            except (ValueError, TypeError):
                exp = db.scalar(
                    select(InterventionExperiment).where(
                        InterventionExperiment.user_id == user_id,
                        InterventionExperiment.experiment_name == experiment_id,
                    )
                )

            if exp and exp.user_id == user_id:
                if effective_status == TreatmentStatus.CONTROL_HOLDOUT.value:
                    exp.sample_size_control += 1
                else:
                    exp.sample_size_treated += 1

        db.commit()
        db.refresh(outcome)
        return outcome

    @classmethod
    def get_overview(cls, db: Session, user_id: uuid.UUID) -> InterventionEffectivenessOverview:
        """
        Calculates aggregate effectiveness metrics, explicit acceptance vs. empirical execution rates,
        cognitive improvements, and overall estimated ATE across all interventions for the user.
        """
        stmt = (
            select(InterventionOutcome)
            .where(InterventionOutcome.user_id == user_id)
            .order_by(InterventionOutcome.presented_at.asc())
        )
        outcomes = list(db.scalars(stmt).all())

        total = len(outcomes)
        if total == 0:
            return InterventionEffectivenessOverview(
                total_interventions=0,
                treated_count=0,
                control_count=0,
                accepted_count=0,
                acceptance_rate=0.0,
                executed_count=0,
                execution_rate=0.0,
                execution_to_acceptance_gap=0.0,
                mean_bfi_reduction=0.0,
                mean_resumption_lag_reduction_seconds=0.0,
                task_completion_lift=0.0,
                overall_causal_ate=None,
                top_effective_interventions=[],
                fatigued_interventions=[],
            )

        treated = [o for o in outcomes if o.treatment_status != TreatmentStatus.CONTROL_HOLDOUT.value]
        control = [o for o in outcomes if o.treatment_status == TreatmentStatus.CONTROL_HOLDOUT.value]

        accepted = [o for o in treated if o.user_action.upper() in ("ACCEPTED", "SNOOZED")]
        executed = [o for o in treated if o.was_executed]

        acceptance_rate = round(len(accepted) / max(1, len(treated)), 3)
        execution_rate = round(len(executed) / max(1, len(treated)), 3)
        exec_gap = round(acceptance_rate - execution_rate, 3)

        # Behavioral improvements (among treated)
        bfi_deltas = [o.bfi_delta for o in treated if o.bfi_delta is not None]
        mean_bfi_red = round(sum(bfi_deltas) / len(bfi_deltas), 2) if bfi_deltas else 0.0

        lag_deltas = [o.resumption_lag_delta_seconds for o in treated if o.resumption_lag_delta_seconds is not None]
        mean_lag_red = round(sum(lag_deltas) / len(lag_deltas), 2) if lag_deltas else 0.0

        # Task completion lift
        comp_t = [o for o in treated if o.target_task_completed]
        rate_t = len(comp_t) / max(1, len(treated))

        if control:
            comp_c = [o for o in control if o.target_task_completed]
            rate_c = len(comp_c) / len(control)
            comp_lift = round(rate_t - rate_c, 3)
        else:
            comp_lift = round(rate_t, 3)

        # Causal evaluation samples
        samples = [
            {
                "treatment": 0 if o.treatment_status == TreatmentStatus.CONTROL_HOLDOUT.value else 1,
                "outcome": o.composite_effectiveness_score,
                "propensity": 0.8 if o.treatment_status != TreatmentStatus.CONTROL_HOLDOUT.value else 0.2,
            }
            for o in outcomes
        ]
        dr_res = CausalEvaluator.estimate_doubly_robust_ate(samples)
        overall_ate = dr_res["ate"] if control else None

        # Breakdown by type for top effective and fatigued
        type_scores: Dict[str, List[float]] = {}
        type_acceptance_history: Dict[str, List[Tuple[float, int]]] = {}

        for idx, o in enumerate(outcomes):
            itype = o.intervention_type
            type_scores.setdefault(itype, []).append(o.composite_effectiveness_score)
            is_acc = 1 if o.user_action.upper() in ("ACCEPTED", "SNOOZED") else 0
            type_acceptance_history.setdefault(itype, []).append((float(idx), is_acc))

        top_effective: List[str] = []
        for itype, scores in type_scores.items():
            avg_score = sum(scores) / len(scores)
            if avg_score >= 0.2:
                top_effective.append(itype)
        top_effective.sort(key=lambda t: sum(type_scores[t]) / len(type_scores[t]), reverse=True)

        fatigued: List[str] = []
        for itype, history in type_acceptance_history.items():
            is_fatigued, _ = CausalEvaluator.detect_habituation_fatigue(history)
            if is_fatigued:
                fatigued.append(itype)

        return InterventionEffectivenessOverview(
            total_interventions=total,
            treated_count=len(treated),
            control_count=len(control),
            accepted_count=len(accepted),
            acceptance_rate=acceptance_rate,
            executed_count=len(executed),
            execution_rate=execution_rate,
            execution_to_acceptance_gap=exec_gap,
            mean_bfi_reduction=mean_bfi_red,
            mean_resumption_lag_reduction_seconds=mean_lag_red,
            task_completion_lift=comp_lift,
            overall_causal_ate=overall_ate,
            top_effective_interventions=top_effective[:5],
            fatigued_interventions=fatigued,
        )

    @classmethod
    def get_interventions_comparison(
        cls, db: Session, user_id: uuid.UUID
    ) -> List[InterventionTypeComparison]:
        """
        Returns comparative effectiveness breakdown across distinct intervention types,
        including sample sizes, unadjusted observational differences, Doubly Robust ATEs,
        95% Confidence Intervals, p-values, FDR corrections, and habituation fatigue indicators.
        """
        stmt = (
            select(InterventionOutcome)
            .where(InterventionOutcome.user_id == user_id)
            .order_by(InterventionOutcome.presented_at.asc())
        )
        outcomes = list(db.scalars(stmt).all())

        # Group by intervention_type
        by_type: Dict[str, List[InterventionOutcome]] = {}
        for o in outcomes:
            by_type.setdefault(o.intervention_type, []).append(o)

        raw_comparisons: List[Dict[str, Any]] = []

        for itype, type_outcomes in by_type.items():
            category = type_outcomes[0].intervention_category

            treated = [o for o in type_outcomes if o.treatment_status != TreatmentStatus.CONTROL_HOLDOUT.value]
            control = [o for o in type_outcomes if o.treatment_status == TreatmentStatus.CONTROL_HOLDOUT.value]

            n_t = len(treated)
            n_c = len(control)

            accepted = [o for o in treated if o.user_action.upper() in ("ACCEPTED", "SNOOZED")]
            executed = [o for o in treated if o.was_executed]

            acc_rate = round(len(accepted) / max(1, n_t), 3)
            exec_rate = round(len(executed) / max(1, n_t), 3)
            gap = round(acc_rate - exec_rate, 3)

            # Observational difference
            y_t = [o.composite_effectiveness_score for o in treated]
            y_c = [o.composite_effectiveness_score for o in control]
            obs_diff, _, _ = CausalEvaluator.compute_observational_difference(y_t, y_c)

            # Causal evaluation via Doubly Robust estimator
            samples = [
                {
                    "treatment": 0 if o.treatment_status == TreatmentStatus.CONTROL_HOLDOUT.value else 1,
                    "outcome": o.composite_effectiveness_score,
                    "propensity": 0.8 if o.treatment_status != TreatmentStatus.CONTROL_HOLDOUT.value else 0.2,
                }
                for o in type_outcomes
            ]
            dr_res = CausalEvaluator.estimate_doubly_robust_ate(samples)

            # Habituation fatigue detection
            history = [
                (float(idx), 1 if o.user_action.upper() in ("ACCEPTED", "SNOOZED") else 0)
                for idx, o in enumerate(type_outcomes)
            ]
            is_fatigued, slope = CausalEvaluator.detect_habituation_fatigue(history)

            raw_comparisons.append({
                "intervention_type": itype,
                "intervention_category": category,
                "sample_size_treated": n_t,
                "sample_size_control": n_c,
                "acceptance_rate": acc_rate,
                "execution_rate": exec_rate,
                "execution_to_acceptance_gap": gap,
                "unadjusted_observational_difference": obs_diff,
                "estimated_ate": dr_res["ate"] if n_c > 0 else obs_diff,
                "confidence_interval_95": dr_res["confidence_interval_95"],
                "p_value": dr_res["p_value"],
                "estimation_method": "DOUBLY_ROBUST_IPW" if n_c > 0 else "UNADJUSTED_OBSERVATIONAL",
                "is_statistically_valid": dr_res["is_statistically_valid"],
                "validation_note": dr_res["validation_note"],
                "is_fatigued": is_fatigued,
                "fatigue_slope": slope,
            })

        # Apply Benjamini-Hochberg FDR correction across evaluated types
        corrected = CausalEvaluator.apply_benjamini_hochberg_correction(raw_comparisons)

        return [InterventionTypeComparison(**c) for c in corrected]

    @classmethod
    def get_experiments(cls, db: Session, user_id: uuid.UUID) -> List[InterventionExperimentRead]:
        """Returns randomized controlled holdout experiments configured for the user."""
        stmt = (
            select(InterventionExperiment)
            .where(InterventionExperiment.user_id == user_id)
            .order_by(InterventionExperiment.created_at.desc())
        )
        experiments = list(db.scalars(stmt).all())
        return [InterventionExperimentRead.model_validate(e) for e in experiments]

    @classmethod
    def get_outcome_by_id(
        cls, db: Session, user_id: uuid.UUID, outcome_or_intervention_id: uuid.UUID
    ) -> InterventionOutcomeRead:
        """
        Retrieves a single intervention outcome by outcome UUID or associated intervention UUID.
        Strictly enforces tenant isolation (user_id matching).
        """
        stmt = select(InterventionOutcome).where(
            InterventionOutcome.user_id == user_id,
            (InterventionOutcome.id == outcome_or_intervention_id)
            | (InterventionOutcome.intervention_id == outcome_or_intervention_id),
        )
        outcome = db.scalar(stmt)
        if not outcome:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Intervention outcome {outcome_or_intervention_id} not found for this user.",
            )
        return InterventionOutcomeRead.model_validate(outcome)

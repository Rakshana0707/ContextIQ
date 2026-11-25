"""
Counterfactual Intervention Dataset Builder & Multi-Lifecycle Integrator (ContextIQ Phase 6.4).

Connects:
1. Recommendation generation records (RECOMMENDED)
2. UI delivery timestamps (DELIVERED)
3. Explicit user acceptance (ACCEPTED)
4. Explicit user dismissal / ignoring (DISMISSED)
5. Telemetry-verified behavioral execution (EXECUTED)
6. Subsequent downstream task events & outcomes.

Enforces strict demarcation:
- Recommendation != Delivery != Acceptance != Execution.
- Only pre-treatment features ($t < t_{\text{delivery}}$) are used for confounding adjustment.
"""
from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.effectiveness_models import InterventionOutcome
from app.models.task import Task
from app.models.user_intervention import UserIntervention
from app.schemas.counterfactual import (
    CandidateIntervention,
    InterventionLifecycleStage,
)

logger = logging.getLogger(__name__)


# Standardized mapping between internal intervention strings and CandidateIntervention enum
INTERVENTION_TO_CANDIDATE_MAP: Dict[str, CandidateIntervention] = {
    "SUGGEST_PROTECTED_FOCUS_SESSION": CandidateIntervention.FOCUS_SESSION_RECOMMENDATION,
    "SUGGEST_RECOVERY_BUFFER": CandidateIntervention.SHORT_RECOVERY_BUFFER,
    "SELECT_SUITABLE_FOCUS_WINDOW": CandidateIntervention.CALENDAR_RESCHEDULING,
    "BREAK_LARGE_TASK": CandidateIntervention.BREAK_LARGE_TASK,
    "REMIND_UPCOMING_DEADLINE": CandidateIntervention.IMMEDIATE_REMINDER,
    "SCHEDULE_PROPOSAL": CandidateIntervention.CALENDAR_RESCHEDULING,
    "DELAYED_NUDGE": CandidateIntervention.DELAYED_REMINDER,
    "NONE": CandidateIntervention.NO_INTERVENTION,
    "CONTROL_HOLDOUT": CandidateIntervention.NO_INTERVENTION,
}


class CounterfactualDatasetBuilder:
    """
    Assembles leak-free, lifecycle-aware counterfactual datasets for intervention comparison.
    """

    @classmethod
    def extract_intervention_records_from_db(
        cls,
        db: Session,
        user_id: Optional[uuid.UUID] = None,
        limit: int = 500,
    ) -> pd.DataFrame:
        """
        Extracts linked records connecting recommendations, outcomes, and task events.
        """
        query = select(InterventionOutcome).order_by(InterventionOutcome.presented_at.desc()).limit(limit)
        if user_id is not None:
            query = query.where(InterventionOutcome.user_id == user_id)

        outcomes = list(db.scalars(query).all())
        if not outcomes:
            return pd.DataFrame()

        rows: List[Dict[str, Any]] = []
        for o in outcomes:
            c_type = INTERVENTION_TO_CANDIDATE_MAP.get(o.intervention_type, CandidateIntervention.NO_INTERVENTION)
            evidence = o.execution_evidence or {}

            # Determine lifecycle stage
            if o.was_executed:
                stage = InterventionLifecycleStage.EXECUTED
            elif o.user_action == "ACCEPTED":
                stage = InterventionLifecycleStage.ACCEPTED
            elif o.user_action in ("DISMISSED", "EXPIRED"):
                stage = InterventionLifecycleStage.DISMISSED
            else:
                stage = InterventionLifecycleStage.DELIVERED

            rows.append({
                "outcome_id": str(o.id),
                "user_id": str(o.user_id),
                "candidate": c_type.value,
                "lifecycle_stage": stage.value,
                "was_executed": int(o.was_executed),
                "user_action": o.user_action,
                "treatment_status": o.treatment_status,
                "presented_at": o.presented_at,
                # Outome measurements
                "task_resumption": float(evidence.get("task_resumed", 0.0)),
                "task_completion": float(evidence.get("task_completed", 0.0)),
                "recovery_duration_seconds": float(evidence.get("recovery_duration_seconds", 180.0)),
                "behavioral_friction": float(evidence.get("subsequent_bfi", 45.0)),
                "notification_burden": 1.0 if o.user_action == "DISMISSED" else 0.1,
                # Pre-treatment covariates
                "baseline_bfi": float(evidence.get("baseline_bfi", 45.0)),
                "task_priority": float(evidence.get("task_priority_score", 2.0)),
                "forgetting_risk": float(evidence.get("forgetting_risk", 0.3)),
                "recent_interruptions": float(evidence.get("recent_interruptions", 2.0)),
            })

        return pd.DataFrame(rows)

    @classmethod
    def generate_benchmark_counterfactual_dataset(
        cls,
        n_samples: int = 400,
        seed: int = 42,
    ) -> pd.DataFrame:
        """
        Generates realistic multi-treatment counterfactual benchmark data with known potential outcomes,
        explicit confounding, selection mechanisms, and varying data coverage across candidates.
        """
        rng = np.random.RandomState(seed)

        # 1. Pre-treatment confounders X
        baseline_bfi = rng.normal(48.0, 16.0, size=n_samples)
        baseline_bfi = np.clip(baseline_bfi, 10.0, 95.0)

        forgetting_risk = rng.beta(2, 4, size=n_samples)
        task_priority = rng.choice([1.0, 2.0, 3.0, 4.0], size=n_samples, p=[0.25, 0.40, 0.25, 0.10])
        calendar_load = rng.gamma(shape=2.0, scale=1.5, size=n_samples)
        recent_interruptions = rng.poisson(lam=2.5, size=n_samples)

        # 2. Multi-treatment allocation with selection bias
        # Higher friction -> recovery buffer; Higher forgetting -> reminders; High load -> rescheduling
        candidates_list = [c.value for c in CandidateIntervention]
        # Candidates:
        # 0: no_intervention (baseline)
        # 1: immediate_reminder
        # 2: delayed_reminder
        # 3: calendar_rescheduling
        # 4: short_recovery_buffer
        # 5: focus_session_recommendation
        # 6: break_large_task

        allocated_candidates: List[str] = []
        for i in range(n_samples):
            bfi_i = baseline_bfi[i]
            fr_i = forgetting_risk[i]
            prio_i = task_priority[i]
            cal_i = calendar_load[i]

            # Unnormalized logits
            logits = np.array([
                1.5,                                       # no_intervention (baseline control holdout)
                1.2 * fr_i + 0.3 * prio_i,                 # immediate_reminder
                0.8 * fr_i - 0.2 * prio_i,                 # delayed_reminder
                0.6 * (cal_i - 2.5),                       # calendar_rescheduling
                0.04 * (bfi_i - 45.0),                     # short_recovery_buffer
                0.03 * (bfi_i - 40.0) + 0.3 * prio_i,      # focus_session_recommendation
                0.1,                                       # break_large_task (sparse in this dataset)
            ])
            # Softmax probabilities
            exp_l = np.exp(logits - np.max(logits))
            probs = exp_l / np.sum(exp_l)
            choice_idx = rng.choice(len(candidates_list), p=probs)
            allocated_candidates.append(candidates_list[choice_idx])

        # 3. Simulate true potential outcomes Y(a) under each strategy
        # Ground truth lifts relative to no_intervention:
        # - short_recovery_buffer: +0.22 resumption, -12.0 friction, +60s recovery duration saved
        # - immediate_reminder: +0.18 completion, -0.05 resumption (immediate alert cost), +0.25 burden
        # - delayed_reminder: +0.14 completion, +0.02 resumption, +0.10 burden
        # - calendar_rescheduling: +0.25 completion, -8.0 friction, +0.05 burden
        # - focus_session_recommendation: +0.20 completion, +0.15 resumption, -15.0 friction
        # - break_large_task: +0.10 completion, -5.0 friction

        rows: List[Dict[str, Any]] = []
        for i in range(n_samples):
            c_name = allocated_candidates[i]
            bfi_i = baseline_bfi[i]
            fr_i = forgetting_risk[i]
            prio_i = task_priority[i]
            cal_i = calendar_load[i]

            # Base outcomes under No Intervention
            base_resumption = max(0.10, min(0.90, 0.55 - 0.003 * (bfi_i - 45.0) + 0.04 * (prio_i - 2.0)))
            base_completion = max(0.15, min(0.85, 0.60 - 0.25 * fr_i - 0.03 * cal_i + 0.05 * prio_i))
            base_recovery_sec = max(30.0, min(600.0, 240.0 + 2.5 * (bfi_i - 45.0)))
            base_friction = max(10.0, min(95.0, bfi_i + rng.normal(0, 3.0)))
            base_burden = 0.0  # No notification delivered

            # Treatment shifts
            if c_name == CandidateIntervention.SHORT_RECOVERY_BUFFER.value:
                y_resume = base_resumption + 0.22
                y_comp = base_completion + 0.05
                y_rec_sec = max(30.0, base_recovery_sec - 75.0)
                y_frict = max(10.0, base_friction - 12.0)
                y_burden = 0.12
                p_exec = 0.78
            elif c_name == CandidateIntervention.IMMEDIATE_REMINDER.value:
                y_resume = base_resumption - 0.04  # Distraction penalty
                y_comp = base_completion + 0.19
                y_rec_sec = base_recovery_sec + 20.0
                y_frict = base_friction + 4.0
                y_burden = 0.35
                p_exec = 0.85
            elif c_name == CandidateIntervention.DELAYED_REMINDER.value:
                y_resume = base_resumption + 0.03
                y_comp = base_completion + 0.15
                y_rec_sec = base_recovery_sec - 10.0
                y_frict = base_friction - 2.0
                y_burden = 0.15
                p_exec = 0.80
            elif c_name == CandidateIntervention.CALENDAR_RESCHEDULING.value:
                y_resume = base_resumption + 0.08
                y_comp = base_completion + 0.26
                y_rec_sec = max(30.0, base_recovery_sec - 40.0)
                y_frict = max(10.0, base_friction - 8.0)
                y_burden = 0.08
                p_exec = 0.72
            elif c_name == CandidateIntervention.FOCUS_SESSION_RECOMMENDATION.value:
                y_resume = base_resumption + 0.16
                y_comp = base_completion + 0.22
                y_rec_sec = max(30.0, base_recovery_sec - 60.0)
                y_frict = max(10.0, base_friction - 15.0)
                y_burden = 0.10
                p_exec = 0.75
            elif c_name == CandidateIntervention.BREAK_LARGE_TASK.value:
                y_resume = base_resumption + 0.05
                y_comp = base_completion + 0.12
                y_rec_sec = base_recovery_sec - 20.0
                y_frict = max(10.0, base_friction - 6.0)
                y_burden = 0.08
                p_exec = 0.65
            else:
                # No intervention
                y_resume = base_resumption
                y_comp = base_completion
                y_rec_sec = base_recovery_sec
                y_frict = base_friction
                y_burden = base_burden
                p_exec = 0.0

            # Empirical execution status
            was_executed = 1 if (c_name != CandidateIntervention.NO_INTERVENTION.value and rng.uniform(0, 1) < p_exec) else 0

            # Observed outcomes with stochastic noise
            obs_resume = int(rng.uniform(0, 1) < np.clip(y_resume, 0.02, 0.98))
            obs_comp = int(rng.uniform(0, 1) < np.clip(y_comp, 0.05, 0.95))
            obs_rec_sec = round(float(np.clip(y_rec_sec + rng.normal(0, 15.0), 20.0, 900.0)), 1)
            obs_frict = round(float(np.clip(y_frict + rng.normal(0, 4.0), 5.0, 98.0)), 1)
            obs_burden = round(float(np.clip(y_burden + rng.normal(0, 0.03), 0.0, 1.0)), 2)

            rows.append({
                "candidate": c_name,
                "was_executed": was_executed,
                "task_resumption": obs_resume,
                "task_completion": obs_comp,
                "recovery_duration_seconds": obs_rec_sec,
                "behavioral_friction": obs_frict,
                "notification_burden": obs_burden,
                # Covariates
                "baseline_bfi": bfi_i,
                "forgetting_risk": fr_i,
                "task_priority": prio_i,
                "calendar_load": cal_i,
                "recent_interruptions": recent_interruptions[i],
            })

        return pd.DataFrame(rows)

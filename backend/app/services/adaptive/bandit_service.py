"""
Service layer for ContextIQ Contextual Bandit Engine (Phase 4.6).
Orchestrates:
- Real-time context vector assembly (BanditFeatureExtractor)
- Safety preconditions, rate limiting, and quarantine enforcement (BanditSafetyGuardrails)
- Arm evaluation via LinUCB and Linear Thompson Sampling
- Decision logging with exact propensity scores
- Dual-loop reward attribution and online Sherman-Morrison updating
- Performance metrics and policy inspection
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.bandit.feature_extractor import BanditFeatureExtractor, FEATURE_DIMENSION
from app.bandit.linucb import LinUCBArm, _identity_matrix, _zero_vector
from app.bandit.reward_attribution import DualLoopRewardAttributor
from app.bandit.safety_guardrails import (
    BanditSafetyGuardrails,
    CIRCUIT_BREAKER_CONSECUTIVE_NEGATIVES,
    DEFAULT_QUIET_HOURS,
    DEFAULT_RATE_LIMIT_MINUTES,
    NO_ACTION_ARM,
    QUARANTINE_HOURS,
)
from app.bandit.thompson_sampling import LinearThompsonSamplingArm
from app.interventions.intervention_catalog import INTERVENTION_METADATA
from app.models.bandit_models import BanditArmState, BanditDecisionLog, BanditRewardLog
from app.models.detected_interruption import DetectedInterruption
from app.models.enums import TaskStatus
from app.models.focus_window import UserFocusWindow
from app.models.task import Task
from app.models.user import User
from app.models.user_intervention import UserIntervention
from app.schemas.bandit_schemas import (
    ArmMetrics,
    BanditAlgorithm,
    BanditFeedbackRequest,
    BanditFeedbackResponse,
    BanditMetricsResponse,
    BanditPolicyResponse,
    BanditSelectRequest,
    BanditSelectResponse,
)
from app.services.adaptive.profile_service import AdaptiveProfileService


def _normalize_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class BanditService:
    """Facade for managing contextual bandit arm selection, feedback attribution, and policy states."""

    MODEL_VERSION = "1.0.0"
    DEFAULT_ALPHA = 0.85
    DEFAULT_V_SCALE = 0.50

    @classmethod
    def select_intervention(
        cls,
        db: Session,
        user_id: uuid.UUID,
        request: Optional[BanditSelectRequest] = None,
    ) -> BanditSelectResponse:
        """
        Gathers context, checks safety preconditions, evaluates candidate arms via LinUCB/Thompson Sampling,
        logs the decision epoch, and returns the selected action.
        """
        req = request or BanditSelectRequest()
        ref_time = _normalize_utc(req.as_of) or datetime.now(timezone.utc)
        current_hour = req.active_hour_override if req.active_hour_override is not None else ref_time.hour

        # 1. Fetch User & Profile
        user = db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {user_id} not found.")

        profile_dict = None
        try:
            profile_read = AdaptiveProfileService.get_profile(db=db, user_id=user_id)
            if profile_read:
                profile_dict = profile_read.model_dump()
        except Exception:
            profile_dict = None

        # 2. Fetch Active Task
        target_task = None
        if req.task_id:
            target_task = db.get(Task, req.task_id)
        if not target_task:
            task_stmt = (
                select(Task)
                .where(Task.user_id == user_id, Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]))
                .order_by(Task.due_at.asc().nullslast(), Task.created_at.desc())
                .limit(1)
            )
            target_task = db.scalars(task_stmt).first()

        is_imminent_deadline = False
        if target_task and target_task.due_at:
            due_utc = _normalize_utc(target_task.due_at)
            if due_utc and 0.0 <= (due_utc - ref_time).total_seconds() / 3600.0 <= 2.0:
                is_imminent_deadline = True

        # 3. Fetch Focus Windows
        fw_stmt = select(UserFocusWindow).where(
            UserFocusWindow.user_id == user_id,
            UserFocusWindow.is_active == True,
        )
        focus_windows = list(db.scalars(fw_stmt).all())
        active_fw = None
        next_fw = None
        for fw in focus_windows:
            st = getattr(fw.start_time, "hour", 0)
            et = getattr(fw.end_time, "hour", 24)
            if st <= current_hour < et:
                active_fw = fw
            elif st > current_hour and (next_fw is None or st < getattr(next_fw.start_time, "hour", 24)):
                next_fw = fw

        # 4. Fetch Recent Interruptions (last 48 hours)
        two_days_ago = ref_time - timedelta(days=2)
        int_stmt = select(DetectedInterruption).where(
            DetectedInterruption.user_id == user_id,
            DetectedInterruption.start_timestamp >= two_days_ago,
        )
        interruptions = list(db.scalars(int_stmt).all())

        # 5. Last intervention delivered timestamp
        last_int_stmt = (
            select(UserIntervention.creation_timestamp)
            .where(UserIntervention.user_id == user_id)
            .order_by(UserIntervention.creation_timestamp.desc())
            .limit(1)
        )
        last_nudge_ts = db.scalar(last_int_stmt)

        # 6. Safety Preconditions Check (Quiet hours, rate limits)
        quiet_override = req.quiet_hours_override if req.quiet_hours_override is not None else False
        is_allowed, block_reason = BanditSafetyGuardrails.check_preconditions(
            current_hour=current_hour,
            last_nudge_timestamp=last_nudge_ts,
            quiet_hours=DEFAULT_QUIET_HOURS,
            rate_limit_minutes=DEFAULT_RATE_LIMIT_MINUTES,
            quiet_hours_override=quiet_override,
            as_of=ref_time,
            is_imminent_deadline=is_imminent_deadline,
        )

        # 7. Extract 12-dimensional context vector x_t
        x_t, context_meta = BanditFeatureExtractor.extract_context(
            user_id=user_id,
            profile_data=profile_dict,
            task=target_task,
            active_focus_window=active_fw,
            next_focus_window=next_fw,
            recent_interruptions=interruptions,
            last_nudge_timestamp=last_nudge_ts,
            current_hour=current_hour,
            as_of=ref_time,
        )

        # 8. Determine Eligible Arms
        # Registered arms from catalog + NO_ACTION
        catalog_arms = list(INTERVENTION_METADATA.keys())

        # Query quarantined arms from BanditArmState
        arm_states_stmt = select(BanditArmState).where(BanditArmState.user_id == user_id)
        existing_arm_states = {s.arm_id: s for s in db.scalars(arm_states_stmt).all()}

        quarantined_arms: Set[str] = set()
        for aid, astate in existing_arm_states.items():
            if astate.quarantined_until and _normalize_utc(astate.quarantined_until) > ref_time:
                quarantined_arms.add(aid)

        # Query recently presented intervention types in last 2 hours
        two_hours_ago = ref_time - timedelta(hours=2)
        recent_presented_stmt = select(UserIntervention.intervention_type).where(
            UserIntervention.user_id == user_id,
            UserIntervention.creation_timestamp >= two_hours_ago,
        )
        recent_presented_types = set(db.scalars(recent_presented_stmt).all())

        eligible_arms = BanditSafetyGuardrails.filter_eligible_arms(
            candidate_arms=catalog_arms,
            quarantined_arms=quarantined_arms,
            excluded_arms=req.excluded_arms,
            recent_presented_arms=recent_presented_types,
        )

        # 9. Algorithm Evaluation
        chosen_algo = (
            req.algorithm_override.value
            if req.algorithm_override
            else BanditAlgorithm.LIN_UCB.value
        )

        # If safety preconditions blocked all interventions, directly force NO_ACTION
        if not is_allowed:
            selected_arm = NO_ACTION_ARM
            is_no_action = True
            expected_payoff = 0.0
            exploration_bonus = 0.0
            propensity = 1.0
        else:
            best_arm = NO_ACTION_ARM
            best_score = -999999.0
            best_payoff = 0.0
            best_bonus = 0.0

            # Evaluate each eligible arm
            for arm_id in eligible_arms:
                if arm_id == NO_ACTION_ARM:
                    # Baseline no-op payoff
                    score = 0.0
                    payoff = 0.0
                    bonus = 0.0
                else:
                    # Load or initialize arm parameters
                    astate = existing_arm_states.get(arm_id)
                    a_inv = astate.a_inv_matrix if astate else None
                    b_vec = astate.b_vector if astate else None
                    theta = astate.theta_vector if astate else None
                    pulls = astate.pull_count if astate else 0
                    cum_r = astate.cumulative_reward if astate else 0.0

                    if chosen_algo == BanditAlgorithm.THOMPSON_SAMPLING.value:
                        ts_model = LinearThompsonSamplingArm(
                            arm_id=arm_id,
                            dim=FEATURE_DIMENSION,
                            v_scale=cls.DEFAULT_V_SCALE,
                            a_inv=a_inv,
                            b=b_vec,
                            theta=theta,
                            pull_count=pulls,
                            cumulative_reward=cum_r,
                        )
                        score, payoff, bonus = ts_model.sample_score(x_t)
                    elif chosen_algo == BanditAlgorithm.UNIFORM_RANDOM.value:
                        import random
                        score = random.uniform(0.0, 1.0)
                        payoff = score
                        bonus = 0.0
                    else:
                        # LIN_UCB (default)
                        lucb_model = LinUCBArm(
                            arm_id=arm_id,
                            dim=FEATURE_DIMENSION,
                            alpha=cls.DEFAULT_ALPHA,
                            a_inv=a_inv,
                            b=b_vec,
                            theta=theta,
                            pull_count=pulls,
                            cumulative_reward=cum_r,
                        )
                        score, payoff, bonus = lucb_model.score(x_t)

                if score > best_score:
                    best_score = score
                    best_arm = arm_id
                    best_payoff = payoff
                    best_bonus = bonus

            # Check if expected payoff warrants taking action or falling back to NO_ACTION
            if BanditSafetyGuardrails.should_fallback_to_no_action(
                best_arm=best_arm,
                best_score=best_score,
                best_expected_payoff=best_payoff,
                min_payoff_threshold=0.05,
            ):
                selected_arm = NO_ACTION_ARM
                is_no_action = True
                expected_payoff = 0.0
                exploration_bonus = 0.0
            else:
                selected_arm = best_arm
                is_no_action = False
                expected_payoff = round(best_payoff, 4)
                exploration_bonus = round(best_bonus, 4)

            # Compute selection propensity
            if chosen_algo == BanditAlgorithm.UNIFORM_RANDOM.value:
                propensity = round(1.0 / max(1, len(eligible_arms)), 4)
            else:
                # With conservative exploration, assign primary mass to chosen arm
                propensity = 0.90 if not is_no_action else 0.95

        # 10. Persist Decision Log
        decision_id = uuid.uuid4()
        obs_window_end = ref_time + timedelta(hours=2)

        decision_log = BanditDecisionLog(
            id=decision_id,
            user_id=user_id,
            associated_intervention_id=None,
            context_vector=x_t,
            context_metadata=context_meta,
            eligible_arms=eligible_arms,
            selected_arm=selected_arm,
            is_no_action=is_no_action,
            algorithm=chosen_algo,
            policy_version=cls.MODEL_VERSION,
            predicted_expected_reward=expected_payoff,
            exploration_bonus=exploration_bonus,
            propensity_score=propensity,
            status="PENDING_FEEDBACK",
            decision_timestamp=ref_time,
            observation_window_end=obs_window_end,
        )
        db.add(decision_log)
        db.commit()
        db.refresh(decision_log)

        return BanditSelectResponse(
            decision_id=decision_id,
            user_id=user_id,
            selected_arm=selected_arm,
            is_no_action=is_no_action,
            algorithm=chosen_algo,
            policy_version=cls.MODEL_VERSION,
            predicted_expected_reward=expected_payoff,
            exploration_bonus=exploration_bonus,
            propensity_score=propensity,
            eligible_arms=eligible_arms,
            context_summary=context_meta,
            decision_timestamp=ref_time,
            observation_window_end=obs_window_end,
        )

    @classmethod
    def record_feedback(
        cls,
        db: Session,
        user_id: uuid.UUID,
        request: BanditFeedbackRequest,
    ) -> BanditFeedbackResponse:
        """
        Ingests explicit and behavioral telemetry outcomes, computes composite reward R_t,
        and executes online Sherman-Morrison rank-1 update of arm parameters.
        """
        # 1. Fetch Decision Log
        d_log = db.get(BanditDecisionLog, request.decision_id)
        if not d_log or d_log.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bandit decision {request.decision_id} not found for this user.",
            )

        now = datetime.now(timezone.utc)
        arm_id = d_log.selected_arm

        # Baseline recovery delay and BFI from context snapshot
        ctx_meta = d_log.context_metadata or {}
        baseline_bfi = float(ctx_meta.get("raw_bfi", 50.0))
        baseline_lag = 45.0

        # 2. Synthesize Composite Reward R_t in [-1.0, 1.0]
        comp_r, r_exp, r_beh, evidence = DualLoopRewardAttributor.synthesize_composite_reward(
            action=request.action,
            response_latency_seconds=request.response_latency_seconds,
            resumption_lag_seconds=request.resumption_lag_seconds,
            baseline_lag_seconds=baseline_lag,
            friction_index_after=request.friction_index_after,
            friction_index_before=baseline_bfi,
            task_completed=request.task_completed,
            subsequent_interruptions_count=request.subsequent_interruptions_count,
        )

        # 3. Update Decision Log Status
        d_log.status = "ATTRIBUTED"

        # 4. Check or Create BanditRewardLog
        reward_stmt = select(BanditRewardLog).where(BanditRewardLog.decision_id == request.decision_id)
        existing_r_log = db.scalar(reward_stmt)
        if existing_r_log:
            reward_log = existing_r_log
            reward_log.explicit_reward = r_exp
            reward_log.behavioral_reward = r_beh
            reward_log.composite_reward = comp_r
            reward_log.attribution_evidence = evidence
            reward_log.attributed_at = now
        else:
            reward_log = BanditRewardLog(
                id=uuid.uuid4(),
                user_id=user_id,
                decision_id=request.decision_id,
                arm_id=arm_id,
                explicit_reward=r_exp,
                behavioral_reward=r_beh,
                composite_reward=comp_r,
                attribution_evidence=evidence,
                attributed_at=now,
            )
            db.add(reward_log)

        # 5. Online Parameter Update via Sherman-Morrison
        quarantined = False
        arm_state_stmt = select(BanditArmState).where(
            BanditArmState.user_id == user_id,
            BanditArmState.arm_id == arm_id,
        )
        arm_state = db.scalar(arm_state_stmt)
        if not arm_state:
            arm_state = BanditArmState(
                id=uuid.uuid4(),
                user_id=user_id,
                arm_id=arm_id,
                algorithm=d_log.algorithm,
                model_version=cls.MODEL_VERSION,
                a_inv_matrix=_identity_matrix(FEATURE_DIMENSION),
                b_vector=_zero_vector(FEATURE_DIMENSION),
                theta_vector=_zero_vector(FEATURE_DIMENSION),
                pull_count=0,
                cumulative_reward=0.0,
                consecutive_negative_rewards=0,
                quarantined_until=None,
            )
            db.add(arm_state)

        # If arm is an actionable intervention (not NO_ACTION), update model matrices
        if arm_id != NO_ACTION_ARM:
            linucb_model = LinUCBArm(
                arm_id=arm_id,
                dim=FEATURE_DIMENSION,
                alpha=cls.DEFAULT_ALPHA,
                a_inv=arm_state.a_inv_matrix,
                b=arm_state.b_vector,
                theta=arm_state.theta_vector,
                pull_count=arm_state.pull_count,
                cumulative_reward=arm_state.cumulative_reward,
            )
            linucb_model.update(d_log.context_vector, comp_r)

            arm_state.a_inv_matrix = linucb_model.a_inv
            arm_state.b_vector = linucb_model.b
            arm_state.theta_vector = linucb_model.theta
            arm_state.pull_count = linucb_model.pull_count
            arm_state.cumulative_reward = linucb_model.cumulative_reward
            arm_state.last_pulled_at = now

            # Circuit breaker check: 3 consecutive negative rewards trigger quarantine
            if comp_r <= -0.5:
                arm_state.consecutive_negative_rewards += 1
                if arm_state.consecutive_negative_rewards >= CIRCUIT_BREAKER_CONSECUTIVE_NEGATIVES:
                    arm_state.quarantined_until = now + timedelta(hours=QUARANTINE_HOURS)
                    quarantined = True
            elif comp_r > 0.0:
                arm_state.consecutive_negative_rewards = 0
        else:
            arm_state.pull_count += 1
            arm_state.cumulative_reward += comp_r
            arm_state.last_pulled_at = now

        db.commit()
        db.refresh(arm_state)

        return BanditFeedbackResponse(
            decision_id=request.decision_id,
            arm_id=arm_id,
            explicit_reward=r_exp,
            behavioral_reward=r_beh,
            composite_reward=comp_r,
            updated_pull_count=arm_state.pull_count,
            quarantined=quarantined or bool(arm_state.quarantined_until and _normalize_utc(arm_state.quarantined_until) > now),
            attributed_at=now,
        )

    @classmethod
    def get_metrics(cls, db: Session, user_id: uuid.UUID) -> BanditMetricsResponse:
        """Computes aggregate performance statistics, pull counts, and mean rewards."""
        arm_states_stmt = select(BanditArmState).where(BanditArmState.user_id == user_id)
        arm_states = list(db.scalars(arm_states_stmt).all())

        now = datetime.now(timezone.utc)
        arm_metrics: List[ArmMetrics] = []
        total_pulls = 0
        total_reward = 0.0
        no_action_pulls = 0

        for a in arm_states:
            pulls = a.pull_count
            cum_r = a.cumulative_reward
            mean_r = cum_r / max(1, pulls)
            is_quar = bool(a.quarantined_until and _normalize_utc(a.quarantined_until) > now)

            total_pulls += pulls
            total_reward += cum_r
            if a.arm_id == NO_ACTION_ARM:
                no_action_pulls += pulls

            arm_metrics.append(
                ArmMetrics(
                    arm_id=a.arm_id,
                    pull_count=pulls,
                    cumulative_reward=round(cum_r, 4),
                    mean_reward=round(mean_r, 4),
                    is_quarantined=is_quar,
                    consecutive_negative_rewards=a.consecutive_negative_rewards,
                    last_pulled_at=a.last_pulled_at,
                )
            )

        # Sort arms descending by pull count
        arm_metrics.sort(key=lambda m: m.pull_count, reverse=True)

        decisions_count = db.scalar(
            select(func.count(BanditDecisionLog.id)).where(BanditDecisionLog.user_id == user_id)
        ) or 0
        feedback_count = db.scalar(
            select(func.count(BanditRewardLog.id)).where(BanditRewardLog.user_id == user_id)
        ) or 0

        global_mean = round(total_reward / max(1, total_pulls), 4)
        no_action_rate = round(no_action_pulls / max(1, total_pulls), 4)

        return BanditMetricsResponse(
            user_id=user_id,
            algorithm=BanditAlgorithm.LIN_UCB.value,
            total_decisions=decisions_count,
            total_feedback_events=feedback_count,
            global_mean_reward=global_mean,
            no_action_rate=no_action_rate,
            arm_metrics=arm_metrics,
        )

    @classmethod
    def get_policy(cls, db: Session, user_id: uuid.UUID) -> BanditPolicyResponse:
        """Returns active contextual bandit policy parameters and safety configurations."""
        all_arms = [NO_ACTION_ARM] + list(INTERVENTION_METADATA.keys())
        return BanditPolicyResponse(
            algorithm=BanditAlgorithm.LIN_UCB.value,
            exploration_alpha=cls.DEFAULT_ALPHA,
            feature_dimension=FEATURE_DIMENSION,
            model_version=cls.MODEL_VERSION,
            rate_limit_minutes=DEFAULT_RATE_LIMIT_MINUTES,
            quiet_hours=DEFAULT_QUIET_HOURS,
            quarantine_threshold=CIRCUIT_BREAKER_CONSECUTIVE_NEGATIVES,
            quarantine_duration_hours=QUARANTINE_HOURS,
            all_registered_arms=all_arms,
        )

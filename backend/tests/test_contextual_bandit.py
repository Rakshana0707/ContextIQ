"""
Unit and integration test suite for ContextIQ Contextual Bandit Engine (Phase 4.6).
Validates:
1. Cold-start user initialization (identity prior, zero payoff)
2. LinUCB online Sherman-Morrison rank-1 update correctness
3. Thompson Sampling posterior Gaussian sampling
4. Safety quiet periods & NO_ACTION fallback
5. Rate limiting & cooldown enforcement
6. Circuit breaker quarantine on 3 consecutive negative rewards
7. Dual-loop reward attribution (explicit click + downstream telemetry)
8. Offline evaluation framework (Replay & IPS estimators)
9. Tenant data isolation between users
10. REST API endpoints (/bandit/select, /feedback, /metrics, /policy)
"""
import math
import os
import sys
import uuid
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "adaptive-intelligence"))

os.environ["APP_ENV"] = "development"
os.environ.setdefault("DATABASE_URL", "sqlite:///./_test_telemetry.db")

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

import app.models
from app.db.session import Base, engine
from app.main import app
from app.models.bandit_models import BanditArmState, BanditDecisionLog, BanditRewardLog
from app.models.enums import TaskPriority, TaskStatus
from app.models.focus_window import UserFocusWindow
from app.models.task import Task
from app.models.user import User
from app.models.user_intervention import UserIntervention
from app.bandit.feature_extractor import BanditFeatureExtractor, FEATURE_DIMENSION
from app.bandit.linucb import LinUCBArm, dot_product, mat_vec_mul
from app.bandit.offline_evaluation import OfflineBanditEvaluator
from app.bandit.reward_attribution import DualLoopRewardAttributor
from app.bandit.safety_guardrails import BanditSafetyGuardrails, NO_ACTION_ARM
from app.bandit.thompson_sampling import LinearThompsonSamplingArm
from app.schemas.bandit_schemas import (
    BanditAlgorithm,
    BanditFeedbackRequest,
    BanditSelectRequest,
)
from app.services.adaptive.bandit_service import BanditService, _normalize_utc


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client():
    return TestClient(app)


def _create_user(db: Session, tz: str = "UTC", prefix: str = "bandit_user") -> User:
    uid = uuid.uuid4()
    user = User(
        id=uid,
        email=f"{prefix}_{uid.hex[:6]}@example.com",
        display_name="Bandit Tester",
        timezone=tz,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


# ---------------------------------------------------------------------------
# 1. Cold-Start User Initialization
# ---------------------------------------------------------------------------
def test_cold_start_users(db_session: Session):
    user = _create_user(db_session, prefix="cold")
    now = datetime(2026, 11, 20, 10, 0, 0, tzinfo=timezone.utc)

    req = BanditSelectRequest(as_of=now, active_hour_override=10)
    response = BanditService.select_intervention(db=db_session, user_id=user.id, request=req)

    assert response.user_id == user.id
    assert response.decision_id is not None
    assert response.algorithm == BanditAlgorithm.LIN_UCB.value
    assert len(response.eligible_arms) >= 1
    assert NO_ACTION_ARM in response.eligible_arms
    assert len(response.context_summary) > 0


# ---------------------------------------------------------------------------
# 2. LinUCB Online Update Correctness
# ---------------------------------------------------------------------------
def test_linucb_online_update_correctness():
    dim = FEATURE_DIMENSION
    arm = LinUCBArm.create_cold_start(arm_id="SUGGEST_RECOVERY_BUFFER", dim=dim, alpha=1.0)

    # Initial state: A^-1 = Identity
    for i in range(dim):
        assert arm.a_inv[i][i] == 1.0
        assert arm.b[i] == 0.0
        assert arm.theta[i] == 0.0

    # Test context vector x (all 0.5 except bias = 1.0)
    x = [0.5] * (dim - 1) + [1.0]
    initial_score, initial_payoff, initial_bonus = arm.score(x)
    assert initial_payoff == 0.0
    assert initial_bonus > 0.0  # Exploration bonus is positive

    # Update with positive reward +1.0
    arm.update(x, reward=1.0)
    assert arm.pull_count == 1
    assert arm.cumulative_reward == 1.0

    # b must be updated: b_new = b + reward * x = x
    for i in range(dim):
        assert abs(arm.b[i] - x[i]) < 1e-6

    # New score must reflect learned positive payoff
    new_score, new_payoff, new_bonus = arm.score(x)
    assert new_payoff > 0.0
    # Uncertainty / variance should decrease after observing evidence
    assert new_bonus < initial_bonus


# ---------------------------------------------------------------------------
# 3. Thompson Sampling Posterior Sampling
# ---------------------------------------------------------------------------
def test_thompson_sampling_stochasticity():
    dim = FEATURE_DIMENSION
    arm = LinearThompsonSamplingArm.create_cold_start(arm_id="BREAK_LARGE_TASK", dim=dim, v_scale=0.5)
    x = [0.4] * (dim - 1) + [1.0]

    # Two stochastic calls with different seeds should yield distinct sampled scores
    score1, payoff1, noise1 = arm.sample_score(x, seed=42)
    score2, payoff2, noise2 = arm.sample_score(x, seed=99)

    assert payoff1 == payoff2  # Mean expected payoff is identical
    assert score1 != score2    # Sampled score incorporates Gaussian noise
    assert abs(score1 - payoff1) > 0.0


# ---------------------------------------------------------------------------
# 4. Safety Quiet Hours & NO_ACTION Fallback
# ---------------------------------------------------------------------------
def test_safety_quiet_hours_and_no_action(db_session: Session):
    user = _create_user(db_session, prefix="quiet")
    # 23:00 is inside default quiet hours [22, 23, 0, 1, 2, 3, 4, 5, 6, 7]
    night_time = datetime(2026, 11, 20, 23, 0, 0, tzinfo=timezone.utc)

    # Request without override
    req_quiet = BanditSelectRequest(as_of=night_time, active_hour_override=23, quiet_hours_override=False)
    res_quiet = BanditService.select_intervention(db=db_session, user_id=user.id, request=req_quiet)
    assert res_quiet.selected_arm == NO_ACTION_ARM
    assert res_quiet.is_no_action is True

    # Request with explicit quiet_hours_override=True
    req_override = BanditSelectRequest(as_of=night_time, active_hour_override=23, quiet_hours_override=True)
    res_override = BanditService.select_intervention(db=db_session, user_id=user.id, request=req_override)
    # With override, bandit is free to consider eligible catalog arms
    assert res_override.eligible_arms is not None


# ---------------------------------------------------------------------------
# 5. Rate Limiting & Cooldown Enforcement
# ---------------------------------------------------------------------------
def test_rate_limiting_cooldown(db_session: Session):
    user = _create_user(db_session, prefix="ratelimit")
    now = datetime(2026, 11, 20, 14, 0, 0, tzinfo=timezone.utc)

    # Simulate an intervention delivered 10 minutes ago
    recent_int = UserIntervention(
        id=uuid.uuid4(),
        user_id=user.id,
        intervention_type="SUGGEST_PROTECTED_FOCUS_SESSION",
        intervention_category="FOCUS",
        title="Recent Focus Nudge",
        message="Active focus block.",
        trigger_condition="Focus Window",
        supporting_evidence={"quality": 85},
        expected_outcome="Deep work",
        estimated_effort="LOW",
        relevance_score=80.0,
        confidence=0.88,
        lifecycle_status="PRESENTED",
        creation_timestamp=now - timedelta(minutes=10),
        expiration_timestamp=now + timedelta(hours=2),
    )
    db_session.add(recent_int)
    db_session.commit()

    # Query bandit selection at 'now' (only 10 min elapsed < 45 min cooldown)
    req = BanditSelectRequest(as_of=now, active_hour_override=14)
    res = BanditService.select_intervention(db=db_session, user_id=user.id, request=req)

    # Rate limiting forces NO_ACTION
    assert res.selected_arm == NO_ACTION_ARM
    assert res.is_no_action is True


# ---------------------------------------------------------------------------
# 6. Circuit Breaker Quarantine on 3 Consecutive Negatives
# ---------------------------------------------------------------------------
def test_repeated_dismissals_circuit_breaker(db_session: Session):
    user = _create_user(db_session, prefix="breaker")
    now = datetime(2026, 11, 20, 10, 0, 0, tzinfo=timezone.utc)

    # Select arm
    req = BanditSelectRequest(as_of=now, active_hour_override=10)
    res1 = BanditService.select_intervention(db=db_session, user_id=user.id, request=req)

    chosen_arm = res1.selected_arm
    if chosen_arm == NO_ACTION_ARM:
        # Pre-seed an actionable arm to test circuit breaker
        chosen_arm = "SUGGEST_RECOVERY_BUFFER"

    # Provide 3 consecutive EXPLICIT_NEGATIVE feedbacks (reward -1.0)
    for i in range(3):
        d_log = BanditDecisionLog(
            id=uuid.uuid4(),
            user_id=user.id,
            context_vector=[0.5] * 12,
            context_metadata={},
            eligible_arms=[chosen_arm, NO_ACTION_ARM],
            selected_arm=chosen_arm,
            is_no_action=False,
            algorithm="LIN_UCB",
            policy_version="1.0.0",
            status="PENDING_FEEDBACK",
            decision_timestamp=now,
            observation_window_end=now + timedelta(hours=2),
        )
        db_session.add(d_log)
        db_session.commit()

        fb_req = BanditFeedbackRequest(
            decision_id=d_log.id,
            action="EXPLICIT_NEGATIVE",
            feedback_note="Unhelpful and repetitive",
        )
        fb_res = BanditService.record_feedback(db=db_session, user_id=user.id, request=fb_req)

    # After 3 consecutive negative rewards, arm must be quarantined
    assert fb_res.quarantined is True

    # In DB, verify arm quarantined_until is set in future
    arm_state = db_session.query(BanditArmState).filter(
        BanditArmState.user_id == user.id,
        BanditArmState.arm_id == chosen_arm,
    ).first()
    assert arm_state is not None
    assert arm_state.consecutive_negative_rewards == 3
    assert _normalize_utc(arm_state.quarantined_until) > datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# 7. Dual-Loop Reward Attribution
# ---------------------------------------------------------------------------
def test_dual_loop_reward_attribution():
    # Case A: User dismissed the suggestion (R_explicit = -0.5),
    # BUT downstream telemetry proves behavioral improvement:
    # - Resumption lag dropped from 60s baseline to 30s (+0.50 delta)
    # - BFI dropped from 70 to 40 (+0.30 delta)
    # - Target task was completed (+1.0)
    # - Zero disruptions (0.0 churn)
    comp, r_exp, r_beh, evidence = DualLoopRewardAttributor.synthesize_composite_reward(
        action="DISMISSED",
        resumption_lag_seconds=30.0,
        baseline_lag_seconds=60.0,
        friction_index_after=40.0,
        friction_index_before=70.0,
        task_completed=True,
        subsequent_interruptions_count=0,
    )

    assert r_exp == -0.5
    assert r_beh > 0.0
    # Composite reward should be positive despite dismissal because behavioral efficacy is proven
    assert comp > 0.0
    assert "composite_formula" in evidence


# ---------------------------------------------------------------------------
# 8. Offline Evaluation Framework (Replay & IPS)
# ---------------------------------------------------------------------------
def test_offline_evaluation_replay_and_ips():
    # Construct synthetic logged stream
    logged_events = []
    for i in range(100):
        # Even indices: arm A was pulled and yielded positive reward
        # Odd indices: arm B was pulled and yielded negative reward
        arm = "ARM_A" if i % 2 == 0 else "ARM_B"
        r = 0.8 if arm == "ARM_A" else -0.4
        logged_events.append({
            "context_vector": [0.5] * 12,
            "eligible_arms": ["ARM_A", "ARM_B"],
            "selected_arm": arm,
            "reward": r,
            "propensity_score": 0.5,
        })

    # Policy 1: Always chooses ARM_A
    policy_always_a = lambda x, eligible: "ARM_A"
    res_replay = OfflineBanditEvaluator.evaluate_replay(logged_events, policy_always_a, policy_name="Always_A")
    assert res_replay["matched_events"] == 50
    assert abs(res_replay["estimated_mean_reward"] - 0.8) < 1e-4

    res_ips = OfflineBanditEvaluator.evaluate_ips(logged_events, policy_always_a, policy_name="Always_A")
    assert abs(res_ips["estimated_mean_reward"] - 0.8) < 1e-4

    # Comparative evaluation
    comparison = OfflineBanditEvaluator.compare_policies(logged_events, policy_always_a, candidate_name="Always_A")
    assert comparison["is_statistically_sound"] is True
    assert len(comparison["methodological_limitations"]) == 0


# ---------------------------------------------------------------------------
# 9. Tenant Data Isolation Between Users
# ---------------------------------------------------------------------------
def test_user_isolation(db_session: Session):
    user_a = _create_user(db_session, prefix="user_a")
    user_b = _create_user(db_session, prefix="user_b")
    now = datetime(2026, 11, 20, 10, 0, 0, tzinfo=timezone.utc)

    # Decision for User A
    req = BanditSelectRequest(as_of=now, active_hour_override=10)
    res_a = BanditService.select_intervention(db=db_session, user_id=user_a.id, request=req)

    # User B attempting to provide feedback for User A's decision must raise 404
    fb_req = BanditFeedbackRequest(
        decision_id=res_a.decision_id,
        action="ACCEPTED",
    )
    with pytest.raises(HTTPException) as exc_info:
        BanditService.record_feedback(db=db_session, user_id=user_b.id, request=fb_req)
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# 10. REST API Endpoints Validation
# ---------------------------------------------------------------------------
def test_bandit_rest_api_endpoints(client: TestClient):
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    with Session(bind=engine) as session:
        user = User(
            id=user_id,
            email=f"bandit_api_{user_id.hex[:6]}@example.com",
            display_name="API Bandit Tester",
            timezone="UTC",
            is_active=True,
        )
        session.add(user)
        session.commit()

    from app.core.deps import get_current_user_id
    app.dependency_overrides[get_current_user_id] = lambda: user_id

    try:
        # 1. GET /api/v1/adaptive/bandit/policy
        res_pol = client.get("/api/v1/adaptive/bandit/policy")
        assert res_pol.status_code == 200
        data_pol = res_pol.json()
        assert data_pol["algorithm"] == "LIN_UCB"
        assert data_pol["feature_dimension"] == 12
        assert len(data_pol["all_registered_arms"]) >= 1

        # 2. POST /api/v1/adaptive/bandit/select
        select_payload = {
            "quiet_hours_override": True,
            "active_hour_override": 11,
        }
        res_sel = client.post("/api/v1/adaptive/bandit/select", json=select_payload)
        assert res_sel.status_code == 200
        data_sel = res_sel.json()
        assert "decision_id" in data_sel
        assert data_sel["user_id"] == str(user_id)
        decision_id = data_sel["decision_id"]

        # 3. POST /api/v1/adaptive/bandit/feedback
        fb_payload = {
            "decision_id": decision_id,
            "action": "ACCEPTED",
            "response_latency_seconds": 3.2,
            "task_completed": True,
            "resumption_lag_seconds": 25.0,
            "friction_index_after": 35.0,
        }
        res_fb = client.post("/api/v1/adaptive/bandit/feedback", json=fb_payload)
        assert res_fb.status_code == 200
        data_fb = res_fb.json()
        assert data_fb["decision_id"] == decision_id
        assert data_fb["composite_reward"] > 0.0

        # 4. GET /api/v1/adaptive/bandit/metrics
        res_met = client.get("/api/v1/adaptive/bandit/metrics")
        assert res_met.status_code == 200
        data_met = res_met.json()
        assert data_met["total_decisions"] >= 1
        assert data_met["total_feedback_events"] >= 1
        assert len(data_met["arm_metrics"]) >= 1

    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

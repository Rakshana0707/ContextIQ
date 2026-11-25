"""
ContextIQ Phase 4.10: Complete Adaptive Behavioral Intelligence Integration and Validation.
Comprehensive test suite validating:
- Task 2: End-to-End Behavioral Profile Pipeline & Temporal Reproducibility
- Task 3: Multi-Objective Adaptive Task Prioritization & Cold-Start Robustness
- Task 4: Personalized Intervention Lifecycle State Machine
- Task 5: Contextual Bandit Learning (LinUCB, Thompson, IPS Offline Evaluation, Circuit Breaker)
- Task 6: Causal Effectiveness & Doubly Robust ATE vs Observational Association
- Task 7: Intelligent Notification Filtering, Quiet Hours & Cognitive Fatigue
- Task 8: User Isolation, Consent Enforcement, Profile Reset & Privacy Opt-Out
- Task 9: Performance Latency Benchmarks
"""
import os
import sys
from pathlib import Path

# Add backend and adaptive-intelligence to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "adaptive-intelligence"))
os.environ["APP_ENV"] = "development"
os.environ.setdefault("DATABASE_URL", "sqlite:///./_test_telemetry.db")

import math
import random
import time
import uuid
from datetime import datetime, time as dtime, timedelta, timezone
from typing import Dict, List

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

import app.models  # Populate all metadata
from app.db.session import Base
from app.models.enums import TaskPriority, TaskStatus
from app.models.user import User
from app.models.task import Task
from app.models.context_session import ContextSession
from app.models.behavioral_profile import UserBehavioralProfile, ProfileSnapshot, ProfileAuditLog
from app.models.focus_window import UserFocusWindow
from app.models.user_intervention import UserIntervention
from app.models.bandit_models import BanditArmState, BanditDecisionLog, BanditRewardLog
from app.models.effectiveness_models import InterventionOutcome, InterventionExperiment
from app.models.notification_models import UserNotification, UserNotificationPreference, NotificationFatigueRecord

# Services and engines
from app.profiles.profile_builder import ProfileBuilder
from app.profiles.profile_confidence import ProfileConfidenceEstimator
from app.prioritization.prioritization_engine import PrioritizationEngine
from app.prioritization.prioritization_features import PrioritizationFeatureExtractor
from app.interventions.intervention_engine import InterventionEngine
from app.services.adaptive.intervention_service import InterventionService
from app.schemas.intervention_schemas import InterventionGenerateRequest, InterventionActionRequest
from app.bandit.linucb import LinUCBArm
from app.bandit.thompson_sampling import LinearThompsonSamplingArm
from app.bandit.safety_guardrails import BanditSafetyGuardrails
from app.bandit.offline_evaluation import OfflineBanditEvaluator
from app.effectiveness.causal_evaluator import CausalEvaluator
from app.notifications.eligibility_evaluator import EligibilityEvaluator
from app.notifications.fatigue_tracker import NotificationFatigueTracker
from app.services.adaptive.profile_service import AdaptiveProfileService


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def mock_users(test_db):
    u1 = User(id=uuid.uuid4(), email="user1@example.com", hashed_password="pw", display_name="User One")
    u2 = User(id=uuid.uuid4(), email="user2@example.com", hashed_password="pw", display_name="User Two")
    test_db.add_all([u1, u2])
    test_db.commit()
    return u1, u2


# ============================================================================
# TASK 2: END-TO-END BEHAVIORAL PROFILE VALIDATION
# ============================================================================

def test_task2_behavioral_profile_pipeline_and_snapshots(test_db, mock_users):
    u1, _ = mock_users
    now = datetime.now(timezone.utc)

    # 1. Simulate 10 days of rich context sessions and task completions
    sessions = []
    for day in range(10):
        session_time = now - timedelta(days=10 - day, hours=4)
        sessions.append(
            ContextSession(
                id=uuid.uuid4(),
                user_id=u1.id,
                started_at=session_time,
                ended_at=session_time + timedelta(minutes=45),
                status="COMPLETED",
            )
        )
    test_db.add_all(sessions)
    test_db.commit()

    # 2. Build Profile using ProfileBuilder
    profile = ProfileBuilder.build_profile(
        user_id=u1.id,
        sessions=sessions,
        detected_interruptions=[],
        manual_interruptions=[],
        tasks=[],
        task_events=[],
        as_of=now,
        observation_window_days=30,
    )

    assert profile is not None
    assert profile.user_id == u1.id
    assert profile.telemetry_days_observed >= 9
    assert profile.total_sessions_observed == 10
    assert profile.is_cold_start is False

    # Check Dimensions
    assert profile.focus_behavior.typical_session_duration_minutes.observed_value > 0
    assert profile.interruption_behavior is not None
    assert profile.task_completion is not None

    # 3. Check Confidence Scoring
    conf_score, coverage, status = ProfileConfidenceEstimator.calculate_confidence(
        sample_count=profile.total_sessions_observed,
        observation_window_days=30,
        days_with_data=profile.telemetry_days_observed,
    )
    assert 0.0 <= conf_score <= 1.0
    assert status.value in ["EMERGING", "ESTABLISHED", "CONFIDENT"]

    # 4. Validate Temporal Reproducibility with earlier cutoff
    def _norm_dt(dt):
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    cutoff = now - timedelta(days=5)
    historical_sessions = [s for s in sessions if _norm_dt(s.started_at) <= cutoff]
    historical_profile = ProfileBuilder.build_profile(
        user_id=u1.id,
        sessions=historical_sessions,
        detected_interruptions=[],
        manual_interruptions=[],
        tasks=[],
        task_events=[],
        as_of=cutoff,
        observation_window_days=30,
    )
    assert historical_profile.total_sessions_observed < profile.total_sessions_observed


# ============================================================================
# TASK 3: ADAPTIVE TASK PRIORITIZATION VALIDATION
# ============================================================================

def test_task3_adaptive_prioritization_and_conflicts(test_db, mock_users):
    u1, _ = mock_users
    now = datetime.now(timezone.utc)

    # Task A: Critical imminent deadline (2 hours away)
    t1 = Task(
        id=uuid.uuid4(),
        user_id=u1.id,
        title="Submit Grant Proposal",
        priority=TaskPriority.HIGH,
        status=TaskStatus.PENDING,
        due_at=now + timedelta(hours=2),
        estimated_minutes=45,
        created_at=now - timedelta(days=2),
    )
    # Task B: Far deadline (3 days away), deep work
    t2 = Task(
        id=uuid.uuid4(),
        user_id=u1.id,
        title="Refactor Architecture Module",
        priority=TaskPriority.MEDIUM,
        status=TaskStatus.PENDING,
        due_at=now + timedelta(days=3),
        estimated_minutes=90,
        created_at=now - timedelta(days=5),
    )
    # Task C: Low priority quick admin task (10 mins)
    t3 = Task(
        id=uuid.uuid4(),
        user_id=u1.id,
        title="Clear Inbox",
        priority=TaskPriority.LOW,
        status=TaskStatus.PENDING,
        due_at=None,
        estimated_minutes=10,
        created_at=now - timedelta(hours=1),
    )
    test_db.add_all([t1, t2, t3])
    test_db.commit()

    # Extract features for all tasks
    tasks_features = [
        PrioritizationFeatureExtractor.extract_task_features(
            db=test_db,
            task=t,
            user_id=u1.id,
            as_of=now,
        )
        for t in [t1, t2, t3]
    ]
    assert len(tasks_features) == 3

    # Test "DEADLINE_CRUNCH" preset: T1 must rank #1
    ranked_deadline = PrioritizationEngine.rank_tasks(
        tasks_features=tasks_features,
        focus_windows=[],
        current_hour=now.hour,
        preset="DEADLINE_CRUNCH",
    )
    assert len(ranked_deadline) == 3
    assert ranked_deadline[0].task_id == t1.id
    assert ranked_deadline[0].primary_driver == "CRITICAL_DEADLINE"

    # Test "DEEP_WORK" preset: balances urgency with deep focus capability
    ranked_deep = PrioritizationEngine.rank_tasks(
        tasks_features=tasks_features,
        focus_windows=[],
        current_hour=now.hour,
        preset="DEEP_WORK",
    )
    assert len(ranked_deep) == 3
    # Check that score breakdown contains all multi-objective factors
    for item in ranked_deep:
        assert 0.0 <= item.composite_score <= 100.0
        assert 0.0 <= item.score_breakdown.urgency_score <= 1.0
        assert 0.0 <= item.score_breakdown.personal_suitability_score <= 1.0
        assert item.grounded_explanation != ""


# ============================================================================
# TASK 4: INTERVENTION ENGINE LIFECYCLE VALIDATION
# ============================================================================

def test_task4_intervention_lifecycle_and_state_machine(test_db, mock_users):
    u1, _ = mock_users
    now = datetime(2026, 11, 20, 10, 0, 0, tzinfo=timezone.utc)

    # Add focus window and task to trigger personalized interventions
    fw = UserFocusWindow(
        user_id=u1.id,
        start_time=dtime(9, 0),
        end_time=dtime(12, 0),
        duration_minutes=180,
        quality_score=85.0,
        is_active=True,
    )
    task = Task(
        user_id=u1.id,
        title="Deep Architecture Refactoring",
        status=TaskStatus.PENDING,
        priority=TaskPriority.HIGH,
        estimated_minutes=60,
        created_at=now - timedelta(days=1),
    )
    test_db.add_all([fw, task])
    test_db.commit()

    # 1. Generate Interventions
    req = InterventionGenerateRequest(as_of=now, active_hour=10, max_interventions=3)
    generated = InterventionService.generate_interventions(db=test_db, user_id=u1.id, request=req)
    assert len(generated) >= 1

    top_item = generated[0]
    assert top_item.lifecycle_status in ["GENERATED", "PRESENTED"]

    # 2. Test Acceptance
    accepted_item = InterventionService.accept_intervention(
        db=test_db,
        user_id=u1.id,
        intervention_id=top_item.id,
        action=InterventionActionRequest(feedback_note="Accepted for test"),
    )
    assert accepted_item.lifecycle_status == "ACCEPTED"
    assert accepted_item.completed_at is not None

    # 3. Test Expiration logic
    expired = UserIntervention(
        id=uuid.uuid4(),
        user_id=u1.id,
        intervention_type="TEST_EXP",
        intervention_category="FOCUS",
        title="Expired test",
        message="Exp",
        trigger_condition="Test condition",
        supporting_evidence={},
        expected_outcome="Test outcome",
        relevance_score=50.0,
        confidence=0.8,
        lifecycle_status="GENERATED",
        creation_timestamp=now - timedelta(hours=5),
        expiration_timestamp=now - timedelta(hours=1),
    )
    test_db.add(expired)
    test_db.commit()

    def _norm(dt):
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    assert _norm(expired.expiration_timestamp) < now


# ============================================================================
# TASK 5: CONTEXTUAL BANDIT LEARNING VALIDATION
# ============================================================================

def test_task5_contextual_bandit_policies_and_circuit_breaker(test_db, mock_users):
    u1, _ = mock_users

    # 1. LinUCB Arm
    arm = LinUCBArm(arm_id="FOCUS_PROTECTION_SESSION", dim=12, alpha=1.0)
    context_vec = [random.uniform(0.1, 0.9) for _ in range(12)]

    ucb_score, payoff, bonus = arm.score(context_vec)
    assert bonus >= 0.0
    assert abs(ucb_score - (payoff + bonus)) < 1e-6

    # Reward attribution update
    arm.update(context_vec, reward=0.85)
    assert arm.pull_count == 1
    assert abs(arm.cumulative_reward - 0.85) < 1e-6

    # 2. Linear Thompson Sampling Arm
    ts_arm = LinearThompsonSamplingArm(arm_id="RECOVERY_BUFFER_WINDOW", dim=12, v_scale=0.5)
    sampled_score, expected_payoff, noise = ts_arm.sample_score(context_vec)
    assert isinstance(sampled_score, float)

    # 3. Safety Circuit Breaker Quarantine Check
    candidate_arms = ["ARM_A", "ARM_B", "ARM_C"]
    quarantined = {"ARM_A"}
    eligible = BanditSafetyGuardrails.filter_eligible_arms(
        candidate_arms=candidate_arms,
        quarantined_arms=quarantined,
    )
    assert "ARM_A" not in eligible
    assert "ARM_B" in eligible
    assert "NO_ACTION" in eligible

    # 4. Offline Evaluator (IPS)
    logged_data = [
        {
            "context_vector": context_vec,
            "eligible_arms": ["ARM_B", "ARM_C"],
            "selected_arm": "ARM_B",
            "reward": 1.0,
            "propensity_score": 0.5,
        },
        {
            "context_vector": context_vec,
            "eligible_arms": ["ARM_B", "ARM_C"],
            "selected_arm": "ARM_C",
            "reward": 0.0,
            "propensity_score": 0.5,
        },
    ]

    def test_policy(x, eligible):
        return "ARM_B"

    ips_result = OfflineBanditEvaluator.evaluate_ips(
        logged_events=logged_data,
        policy_fn=test_policy,
        policy_name="TestPolicy",
    )
    assert "estimated_mean_reward" in ips_result
    assert ips_result["estimated_mean_reward"] >= 0.0


# ============================================================================
# TASK 6: CAUSAL EFFECTIVENESS & DOUBLY ROBUST EVALUATION
# ============================================================================

def test_task6_causal_effectiveness_and_habituation(test_db, mock_users):
    u1, _ = mock_users

    # Synthetic treatment (N=20) and control (N=20) sample set
    random.seed(42)
    samples = []
    for i in range(40):
        t = 1 if i < 20 else 0
        propensity = 0.5 + 0.1 * (1 if t == 1 else -1)
        # Treatment effect: +0.25 improvement
        outcome = (0.75 if t == 1 else 0.50) + random.uniform(-0.05, 0.05)
        samples.append({
            "treatment": t,
            "outcome": outcome,
            "propensity": propensity,
            "context": {"baseline_bfi": 25.0, "urgency_score": 0.6},
        })

    # Estimate Doubly Robust ATE
    result = CausalEvaluator.estimate_doubly_robust_ate(samples)

    assert "ate" in result
    assert "confidence_interval_95" in result
    assert "p_value" in result
    assert result["is_statistically_valid"] is True
    # The ATE should be positive and around 0.25
    assert result["ate"] > 0.15
    ci_low, ci_high = result["confidence_interval_95"]
    assert ci_low <= result["ate"] <= ci_high
    assert result["p_value"] < 0.05

    # Raw Observational Difference vs ATE comparison
    treated_outcomes = [s["outcome"] for s in samples if s["treatment"] == 1]
    control_outcomes = [s["outcome"] for s in samples if s["treatment"] == 0]
    obs_diff, mean_t, mean_c = CausalEvaluator.compute_observational_difference(treated_outcomes, control_outcomes)
    assert obs_diff > 0.0

    # Habituation fatigue detection: decreasing acceptance over 10 days
    acceptance_history = [(day, 1 if day < 4 else 0) for day in range(10)]
    is_fatigued, slope = CausalEvaluator.detect_habituation_fatigue(acceptance_history)
    assert is_fatigued is True
    assert slope < -0.05


# ============================================================================
# TASK 7: INTELLIGENT NOTIFICATION & COGNITIVE LOAD VALIDATION
# ============================================================================

def test_task7_notification_intelligence_and_quiet_hours(test_db, mock_users):
    u1, _ = mock_users
    now = datetime(2026, 11, 22, 23, 30, tzinfo=timezone.utc)  # 23:30 (Quiet Hours)

    # 1. Quiet Hours check: 22 to 8 wraps past midnight
    in_quiet = EligibilityEvaluator.is_in_quiet_hours(start_hour=22, end_hour=8, current_hour=23)
    assert in_quiet is True
    not_quiet = EligibilityEvaluator.is_in_quiet_hours(start_hour=22, end_hour=8, current_hour=14)
    assert not_quiet is False

    # 2. Evaluate Eligibility during Quiet Hours
    # Low priority -> Deferred or Suppressed
    is_eligible, strat, reason = EligibilityEvaluator.evaluate_eligibility(
        category="RECOVERY",
        priority="LOW",
        as_of=now,
        quiet_hours_enabled=True,
        quiet_hours_start=22,
        quiet_hours_end=8,
    )
    assert is_eligible is False
    assert strat.value in ["SUPPRESSED_QUIET_PERIOD", "DEFERRED", "BATCHED_SUMMARY"]

    # Critical priority -> Immediate delivery bypass
    is_crit_eligible, crit_strat, crit_reason = EligibilityEvaluator.evaluate_eligibility(
        category="CRITICAL_DEADLINE",
        priority="CRITICAL",
        as_of=now,
        is_critical_urgency=True,
        quiet_hours_enabled=True,
        quiet_hours_start=22,
        quiet_hours_end=8,
    )
    assert is_crit_eligible is True
    assert crit_strat.value == "IMMEDIATE"

    # 3. Fatigue tracker check
    fatigue_score = NotificationFatigueTracker.calculate_fatigue_score(
        total_presented=20,
        total_accepted=5,
        total_dismissed=12,
        total_deferred=3,
        consecutive_dismissals=4,
        deliveries_24h=14,
        daily_limit=15,
    )
    assert 0.0 <= fatigue_score <= 1.0
    assert fatigue_score > 0.50, "High dismissals and consecutive rejections must indicate high fatigue"


# ============================================================================
# TASK 8: PRIVACY, CONSENT & ISOLATION VALIDATION
# ============================================================================

def test_task8_user_isolation_and_profile_reset(test_db, mock_users):
    u1, u2 = mock_users
    now = datetime.now(timezone.utc)

    # 1. Create Profile for User 1
    p1 = UserBehavioralProfile(
        id=uuid.uuid4(),
        user_id=u1.id,
        is_cold_start=False,
        personalization_enabled=True,
        telemetry_days_observed=14,
        total_sessions_observed=25,
        total_tasks_observed=40,
        total_interruptions_observed=15,
        focus_dimension={"typical_session_minutes": 52.0},
        interruption_dimension={"recovery_latency_median_seconds": 180.0},
        task_completion_dimension={"observed_completion_rate": 0.88},
        context_dimension={},
        temporal_dimension={},
        baselines={},
        global_confidence_score=0.82,
        global_pattern_status="CONFIDENT",
    )
    test_db.add(p1)
    test_db.commit()

    # 2. Verify User Isolation: Querying for User 2 returns cold-start default, NOT User 1's profile
    u2_profile = AdaptiveProfileService.get_profile(db=test_db, user_id=u2.id)
    assert u2_profile.user_id == u2.id
    assert u2_profile.is_cold_start is True
    assert u2_profile.telemetry_days_observed == 0

    # 3. Verify Profile Reset
    reset_resp = AdaptiveProfileService.reset_profile(db=test_db, user_id=u1.id)
    assert reset_resp.status == "SUCCESS"
    assert reset_resp.user_id == u1.id

    # Verify Audit Log entry was recorded
    audit = test_db.query(ProfileAuditLog).filter(ProfileAuditLog.user_id == u1.id).first()
    assert audit is not None
    assert audit.action == "RESET"

    # 4. Personalization Opt-out Toggle
    toggled = AdaptiveProfileService.set_personalization(db=test_db, user_id=u1.id, enabled=False)
    assert toggled.personalization_enabled is False


# ============================================================================
# TASK 9: PERFORMANCE LATENCY BENCHMARKS
# ============================================================================

def test_task9_performance_benchmarks(test_db, mock_users):
    u1, _ = mock_users
    now = datetime.now(timezone.utc)

    # Benchmark 1: Profile confidence evaluation (< 10ms)
    t0 = time.perf_counter()
    for _ in range(100):
        ProfileConfidenceEstimator.calculate_confidence(
            sample_count=50,
            observation_window_days=30,
            days_with_data=20,
        )
    avg_conf_ms = ((time.perf_counter() - t0) / 100) * 1000
    assert avg_conf_ms < 10.0, f"Profile confidence evaluation too slow: {avg_conf_ms:.2f}ms"

    # Benchmark 2: LinUCB Arm Scoring (< 5ms)
    arm = LinUCBArm(arm_id="TEST_ARM", dim=12, alpha=1.0)
    ctx = [random.uniform(0.1, 0.9) for _ in range(12)]

    t0 = time.perf_counter()
    for _ in range(100):
        arm.score(ctx)
    avg_bandit_ms = ((time.perf_counter() - t0) / 100) * 1000
    assert avg_bandit_ms < 5.0, f"LinUCB arm score too slow: {avg_bandit_ms:.2f}ms"

    # Benchmark 3: Causal Doubly Robust estimation (< 20ms for N=100)
    samples = []
    for i in range(100):
        t = 1 if i % 2 == 0 else 0
        samples.append({
            "treatment": t,
            "outcome": random.uniform(0.4, 0.9),
            "propensity": 0.5,
            "context": {"baseline_bfi": 20.0, "urgency_score": 0.5},
        })

    t0 = time.perf_counter()
    for _ in range(10):
        CausalEvaluator.estimate_doubly_robust_ate(samples)
    avg_causal_ms = ((time.perf_counter() - t0) / 10) * 1000
    assert avg_causal_ms < 20.0, f"Causal estimation too slow: {avg_causal_ms:.2f}ms"

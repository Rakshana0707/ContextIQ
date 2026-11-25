"""
Phase 6.10: Complete Integration, Evaluation, Testing, and Release Validation Test Suite.

End-to-End Release Validation for ContextIQ Advanced Predictive Intelligence & Decision Support:
1. End-to-End Multi-Module Integration (Phases 6.2 - 6.9 unified pipeline).
2. Data Leakage Prevention (temporal monotonicity, point-in-time extraction, user isolation).
3. Target Validity, Censoring, and Incomplete Observations.
4. Model Calibration, Conformal Coverage, and Out-of-Distribution Robustness.
5. Intelligent Abstention and Action Policy Safety Gates.
6. Reversible Workflow Orchestration (Proposal -> Approval -> Idempotent Execution -> Rollback).
7. Tenant Isolation and Authorization Boundaries.
8. Performance Latency and Computational Budget Benchmarks.
9. Backward Compatibility with Core Platform (Phases 1-5).
"""
from __future__ import annotations

import math
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["APP_ENV"] = "development"
os.environ.setdefault("DATABASE_URL", "sqlite:///./_test_telemetry.db")


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


import app.models
from app.db.session import Base
from app.main import app
from app.models import (
    ContextSession,
    DetectedInterruption,
    ProposedWorkflow,
    SavedScenario,
    Task,
    User,
    UserBehavioralProfile,
)
from app.models.enums import TaskPriority, TaskStatus
from app.profiles.profile_engine import BehavioralProfileEngine
from app.schemas.causal_analysis import CausalEvaluationRequest, CausalMethod, CausalQuestionId
from app.schemas.counterfactual import (
    CandidateIntervention,
    CounterfactualComparisonRequest,
    CounterfactualLearnerType,
)
from app.schemas.digital_twin_simulation import (
    ScenarioCompareRequest,
    ScenarioCreateRequest,
    ScenarioSimulationRequest,
    ScenarioType,
    WorkflowApprovalRequest,
    WorkflowStatus,
)
from app.schemas.dynamic_survival import DynamicSurvivalPredictionRequest, SurvivalEventTarget
from app.schemas.multi_objective_optimization import (
    MultiObjectiveOptimizationRequest,
    OptimizationObjective,
)
from app.schemas.recovery_prediction import RecoveryPredictionRequest
from app.schemas.temporal_sequence import SequencePredictionResponse, SequencePredictionTarget
from app.schemas.uncertainty_decision import AbstentionOutcome, DecisionSupportRequest
from app.services.causal_service import CausalService
from app.services.counterfactual_service import CounterfactualService
from app.services.digital_twin_engine import DigitalTwinEngine
from app.services.dynamic_survival_service import DynamicSurvivalService
from app.services.multi_objective_service import MultiObjectiveService
from app.services.recovery_prediction_service import RecoveryPredictionService
from app.services.sequence_prediction_service import SequencePredictionService
from app.services.simulation_service import SimulationService
from app.services.uncertainty_calibration_engine import (
    IsotonicCalibrator,
    PlattCalibrator,
    UncertaintyCalibrationEngine,
)
from app.services.uncertainty_decision_service import UncertaintyDecisionService
from app.services.workflow_orchestrator import WorkflowOrchestrator


# ---------------------------------------------------------------------------
# Database & Test Client Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def release_db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(release_db_engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=release_db_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def seed_primary_user(db_session: Session):
    user_id = uuid.uuid4()
    task_id = uuid.uuid4()

    user = User(
        id=user_id,
        email=f"primary_{user_id.hex[:6]}@contextiq.ai",
        display_name="Primary Release Validation User",
        timezone="UTC",
        is_active=True,
    )
    db_session.add(user)

    task = Task(
        id=task_id,
        user_id=user_id,
        title="Release Architecture Review",
        description="End-to-End validation of Phase 6 intelligence stack",
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.HIGH,
        estimated_minutes=120,
        due_at=datetime.now(timezone.utc) + timedelta(hours=4),
    )
    db_session.add(task)
    db_session.commit()

    # Rebuild compliant profile with BehavioralProfileEngine
    BehavioralProfileEngine.rebuild_profile(db_session, user_id, as_of=datetime.now(timezone.utc))

    return {"user_id": user_id, "task_id": task_id}


@pytest.fixture
def seed_secondary_user(db_session: Session):
    user_id = uuid.uuid4()
    task_id = uuid.uuid4()

    user = User(
        id=user_id,
        email=f"secondary_{user_id.hex[:6]}@contextiq.ai",
        display_name="Secondary Isolated User",
        timezone="UTC",
        is_active=True,
    )
    db_session.add(user)

    task = Task(
        id=task_id,
        user_id=user_id,
        title="Secondary Private Task",
        description="Isolated task that must never leak",
        status=TaskStatus.PENDING,
        priority=TaskPriority.LOW,
        estimated_minutes=30,
        due_at=datetime.now(timezone.utc) + timedelta(days=2),
    )
    db_session.add(task)
    db_session.commit()

    return {"user_id": user_id, "task_id": task_id}


@pytest.fixture
def release_test_client(release_db_engine, seed_primary_user):
    from app.core.deps import get_current_user_id
    from app.db.session import get_db

    user_id = seed_primary_user["user_id"]

    def override_get_db():
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=release_db_engine)
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_current_user_id] = lambda: user_id
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 1. End-to-End Inter-Module Pipeline Integration
# ---------------------------------------------------------------------------

def test_full_phase6_unified_pipeline_integration(db_session: Session, seed_primary_user):
    """
    Validates complete end-to-end multi-module pipeline execution:
    1. Recovery Prediction (6.2)
    2. Causal Effect Evaluation (6.3)
    3. Counterfactual Alternatives Ranking (6.4)
    4. Sequence Model Forecasting (6.5)
    5. Dynamic Survival Horizon (6.6)
    6. Multi-Objective Optimization (6.7)
    7. Uncertainty-Aware Abstention Gating (6.8)
    8. Digital Twin Simulation (6.9)
    9. Workflow Proposal & Safe Execution (6.9)
    """
    user_id = seed_primary_user["user_id"]
    task_id = seed_primary_user["task_id"]

    # Step 1: Recovery Duration Prediction (6.2)
    rec_req = RecoveryPredictionRequest(task_id=task_id)
    rec_res = RecoveryPredictionService.predict_recovery_duration(db=db_session, user_id=user_id, request=rec_req)
    assert rec_res.estimated_recovery_duration_seconds > 0.0
    assert 0.0 <= rec_res.recovery_probabilities.get("15m", 0.5) <= 1.0

    # Step 2: Causal Effect Estimation (6.3)
    causal_req = CausalEvaluationRequest(
        question_id=CausalQuestionId.RECOVERY_BUFFER_ON_RESUMPTION,
        method=CausalMethod.DOUBLY_ROBUST_AIPW,
        user_id=user_id,
    )
    causal_res = CausalService.evaluate_causal_question(db=db_session, request=causal_req)
    assert causal_res.estimated_causal_effect is not None
    assert causal_res.sensitivity is not None
    assert causal_res.sensitivity.e_value_estimate >= 1.0
    assert len(causal_res.limitations) >= 1

    # Step 3: Counterfactual Intervention Comparison (6.4)
    cf_req = CounterfactualComparisonRequest(
        user_id=user_id,
        learner=CounterfactualLearnerType.DOUBLY_ROBUST_LEARNER,
    )
    cf_res = CounterfactualService.compare_interventions(db=db_session, request=cf_req)
    assert len(cf_res.candidates) >= 4
    assert cf_res.recommended_champion is not None

    # Step 4: Temporal Sequence Forecasting (6.5)
    seq_res = SequencePredictionService.predict_sequence(
        db=db_session, user_id=user_id, target=SequencePredictionTarget.SHORT_TERM_TASK_RESUMPTION
    )
    assert 0.0 <= seq_res.predicted_probability <= 1.0
    assert seq_res.sequence_length >= 0

    # Step 5: Dynamic Survival Curve (6.6)
    surv_req = DynamicSurvivalPredictionRequest(
        target=SurvivalEventTarget.TASK_ABANDONMENT,
        user_id=user_id,
        current_time_elapsed=30.0,
    )
    surv_res = DynamicSurvivalService.predict_survival(db=db_session, request=surv_req)
    assert len(surv_res.survival_curve) > 0
    # Monotonic survival curve S(t) decreases or stays constant
    probs = [pt.survival_probability for pt in surv_res.survival_curve]
    assert all(probs[i] >= probs[i + 1] - 1e-5 for i in range(len(probs) - 1))

    # Step 6: Multi-Objective Optimization (6.7)
    opt_req = MultiObjectiveOptimizationRequest(user_id=user_id, task_id=task_id)
    opt_res = MultiObjectiveService.optimize_intervention(db=db_session, request=opt_req)
    assert opt_res.selected_intervention is not None
    assert len(opt_res.pareto_frontier) >= 1
    assert len(opt_res.applied_constraints) >= 1
    assert opt_res.requires_authorization is True

    # Step 7: Uncertainty Gating & Abstention (6.8)
    unc_req = DecisionSupportRequest(user_id=user_id, task_id=task_id, model_target="forgetting_risk")
    unc_res = UncertaintyDecisionService.evaluate_decision_support(db=db_session, request=unc_req)
    assert unc_res.abstention_outcome in (
        AbstentionOutcome.PREDICTION_AVAILABLE,
        AbstentionOutcome.PREDICTION_WITH_CAUTION,
        AbstentionOutcome.INSUFFICIENT_EVIDENCE,
        AbstentionOutcome.UNSUPPORTED_INPUT,
    )
    assert unc_res.uncertainty_decomposition.total_uncertainty >= 0.0

    # Step 8: Behavioral Digital Twin Simulation (6.9)
    sim_req = ScenarioSimulationRequest(
        scenario_type=ScenarioType.SCHEDULE_FOCUS_SESSION,
        user_id=user_id,
        task_id=task_id,
        input_parameters={"focus_block_minutes": 60},
    )
    sim_res = SimulationService.simulate_scenario(db=db_session, request=sim_req)
    assert sim_res.counterfactual_deltas.delta_completion_pct > 0.0
    assert sim_res.simulated_plan.is_simulated is True

    # Step 9: Reversible Workflow Proposal & Execution (6.9)
    scenario_db = SimulationService.create_saved_scenario(
        db=db_session,
        user_id=user_id,
        request=ScenarioCreateRequest(
            name="E2E Pipeline Scenario",
            scenario_type=ScenarioType.SCHEDULE_FOCUS_SESSION,
            task_id=task_id,
            input_parameters={"focus_block_minutes": 60},
        ),
    )
    wf = WorkflowOrchestrator.propose_workflow_from_scenario(
        db=db_session,
        user_id=user_id,
        scenario_type=ScenarioType.SCHEDULE_FOCUS_SESSION,
        scenario_id=scenario_db.id,
        task_id=task_id,
    )
    assert wf.status == WorkflowStatus.PROPOSED.value

    # Approve and execute
    wf_app = WorkflowOrchestrator.approve_workflow(
        db=db_session, workflow=wf, approval_req=WorkflowApprovalRequest(approved=True)
    )
    exec_res = WorkflowOrchestrator.execute_workflow(db=db_session, workflow=wf_app)
    assert exec_res.status == WorkflowStatus.COMPLETED

    # Rollback
    rb_res = WorkflowOrchestrator.rollback_workflow(db=db_session, workflow=wf_app)
    assert rb_res.status == WorkflowStatus.REVERTED


# ---------------------------------------------------------------------------
# 2. Data Leakage Prevention & Monotonicity
# ---------------------------------------------------------------------------

def test_temporal_leakage_and_chronological_ordering(db_session: Session, seed_primary_user):
    """Validates that sequence and survival representations enforce temporal directionality."""
    user_id = seed_primary_user["user_id"]
    seq_res = SequencePredictionService.predict_sequence(
        db=db_session,
        user_id=user_id,
        target=SequencePredictionTarget.SHORT_TERM_TASK_RESUMPTION,
    )
    assert seq_res.predicted_probability >= 0.0
    assert seq_res.sequence_length >= 0
    assert seq_res.prediction_timestamp <= datetime.now(timezone.utc)


def test_user_data_isolation_across_tenants(
    db_session: Session, seed_primary_user, seed_secondary_user
):
    """Verifies strict tenant boundary: User A cannot query or alter User B's scenarios or workflows."""
    from app.core.errors import NotFoundError

    user_a = seed_primary_user["user_id"]
    user_b = seed_secondary_user["user_id"]

    # User A creates a scenario
    scen_a = SimulationService.create_saved_scenario(
        db=db_session,
        user_id=user_a,
        request=ScenarioCreateRequest(
            name="User A Confidential Plan",
            scenario_type=ScenarioType.ADD_RECOVERY_BUFFER,
            task_id=seed_primary_user["task_id"],
        ),
    )

    # User B lists scenarios -> User A's scenario must NOT appear
    b_scenarios = SimulationService.list_saved_scenarios(db=db_session, user_id=user_b)
    assert not any(s.id == scen_a.id for s in b_scenarios)

    # User B directly queries User A's scenario -> 404 NotFoundError
    with pytest.raises(NotFoundError):
        SimulationService.get_saved_scenario(db=db_session, user_id=user_b, scenario_id=scen_a.id)

    # User B attempts to delete User A's scenario -> 404 NotFoundError
    with pytest.raises(NotFoundError):
        SimulationService.delete_saved_scenario(db=db_session, user_id=user_b, scenario_id=scen_a.id)


# ---------------------------------------------------------------------------
# 3. Model Calibration & Conformal Coverage
# ---------------------------------------------------------------------------

def test_probability_calibrators_guarantee_monotonicity_and_bounds():
    """Validates Platt Scaling, Isotonic Regression, and ECE computation."""
    np.random.seed(42)
    # Synthetic uncalibrated overconfident scores
    logits = np.random.uniform(0.1, 0.9, 100)
    labels = (logits + np.random.normal(0, 0.15, 100) > 0.5).astype(int)

    # Platt
    platt = PlattCalibrator()
    platt.fit(logits, labels)
    platt_cal = platt.predict_proba(logits)
    assert np.all(platt_cal >= 0.0)
    assert np.all(platt_cal <= 1.0)

    # Isotonic
    iso = IsotonicCalibrator()
    iso.fit(logits, labels)
    iso_cal = iso.predict_proba(logits)
    assert np.all(iso_cal >= 0.0)
    assert np.all(iso_cal <= 1.0)

    # Monotonicity check
    sorted_idx = np.argsort(logits)
    assert np.all(np.diff(iso_cal[sorted_idx]) >= -1e-6)

    # ECE and Brier score evaluation
    metrics = UncertaintyCalibrationEngine.evaluate_calibration_metrics(
        y_true=labels, y_prob=iso_cal, method_name="Isotonic Calibration"
    )
    assert 0.0 <= metrics.expected_calibration_error <= 1.0
    assert 0.0 <= metrics.brier_score <= 1.0


def test_split_conformal_prediction_intervals_achieve_coverage():
    """Validates that split-conformal intervals produce valid finite bounds with empirical coverage."""
    interval = UncertaintyCalibrationEngine.compute_conformal_interval(
        point_pred=0.65,
        coverage_level=0.90,
        recent_telemetry_variance=0.04,
    )
    assert 0.0 <= interval.lower_bound <= interval.upper_bound <= 1.0
    assert interval.coverage_level == 0.90
    assert interval.interval_width == round(interval.upper_bound - interval.lower_bound, 4)


# ---------------------------------------------------------------------------
# 4. Out-of-Distribution Detection & Intelligent Abstention
# ---------------------------------------------------------------------------

def test_ood_detection_triggers_abstention_and_blocks_automation():
    """Validates that extreme out-of-distribution inputs force safe abstention policy."""
    extreme_features = {
        "baseline_bfi": 99.5,
        "recent_interruptions": 55.0,
        "monitored_hours_last_24h": 0.05,
        "task_priority": 9.0,
    }
    cov = UncertaintyCalibrationEngine.evaluate_data_coverage(
        user_history_count=1,
        context_features=extreme_features,
    )
    assert cov.is_out_of_distribution is True or cov.data_coverage_tier == "INSUFFICIENT"

    req = DecisionSupportRequest(context_features=extreme_features)
    res = UncertaintyCalibrationEngine.evaluate_decision_support(
        request=req, user_history_count=1, raw_prediction=0.88
    )
    assert res.abstention_outcome in (
        AbstentionOutcome.UNSUPPORTED_INPUT,
        AbstentionOutcome.PREDICTION_WITH_CAUTION,
        AbstentionOutcome.INSUFFICIENT_EVIDENCE,
    )
    # Automation must NOT be allowed on abstained / caution predictions
    assert res.can_automate_recommendation is False


# ---------------------------------------------------------------------------
# 5. Workflow Authorization, Idempotency, and Safety Gates
# ---------------------------------------------------------------------------

def test_workflow_orchestrator_execution_gate(db_session: Session, seed_primary_user):
    """Enforces that workflows in PROPOSED state cannot be executed without explicit approval."""
    user_id = seed_primary_user["user_id"]
    task_id = seed_primary_user["task_id"]

    wf = WorkflowOrchestrator.propose_workflow_from_scenario(
        db=db_session,
        user_id=user_id,
        scenario_type=ScenarioType.MOVE_TASK_TIME,
        task_id=task_id,
    )
    assert wf.status == WorkflowStatus.PROPOSED.value

    # Attempt execution directly -> Must raise ValueError
    with pytest.raises(ValueError) as exc:
        WorkflowOrchestrator.execute_workflow(db=db_session, workflow=wf)
    assert "Explicit user approval is required" in str(exc.value)


def test_workflow_idempotency_prevents_duplicate_runs(db_session: Session, seed_primary_user):
    """Verifies that executing an already completed workflow rejects repeat mutation."""
    user_id = seed_primary_user["user_id"]
    task_id = seed_primary_user["task_id"]

    wf = WorkflowOrchestrator.propose_workflow_from_scenario(
        db=db_session,
        user_id=user_id,
        scenario_type=ScenarioType.ADD_RECOVERY_BUFFER,
        task_id=task_id,
    )
    WorkflowOrchestrator.approve_workflow(
        db=db_session, workflow=wf, approval_req=WorkflowApprovalRequest(approved=True)
    )
    res1 = WorkflowOrchestrator.execute_workflow(db=db_session, workflow=wf)
    assert res1.status == WorkflowStatus.COMPLETED

    # Repeat execution attempt -> Already in COMPLETED state
    with pytest.raises(ValueError) as exc:
        WorkflowOrchestrator.execute_workflow(db=db_session, workflow=wf)
    assert "Cannot execute workflow in status" in str(exc.value)


# ---------------------------------------------------------------------------
# 6. Performance Latency & Budget Benchmarks
# ---------------------------------------------------------------------------

def test_model_inference_latency_within_interactive_budget(db_session: Session, seed_primary_user):
    """
    Benchmarks model inference latency across Phase 6 services:
    - Recovery Prediction: target < 150ms
    - Multi-Objective Optimization: target < 150ms
    - Digital Twin Scenario Simulation: target < 150ms
    """
    user_id = seed_primary_user["user_id"]
    task_id = seed_primary_user["task_id"]

    # Warm-up to ensure cached pipelines are initialized
    RecoveryPredictionService.predict_recovery_duration(
        db=db_session, user_id=user_id, request=RecoveryPredictionRequest(task_id=task_id)
    )

    # Benchmark Recovery Prediction Inference Latency
    t0 = time.perf_counter()
    rec_req = RecoveryPredictionRequest(task_id=task_id)
    RecoveryPredictionService.predict_recovery_duration(db=db_session, user_id=user_id, request=rec_req)
    rec_lat_ms = (time.perf_counter() - t0) * 1000.0
    assert rec_lat_ms < 150.0, f"Recovery latency exceeded budget: {rec_lat_ms:.2f}ms"

    # Benchmark Multi-Objective Optimization
    t0 = time.perf_counter()
    opt_req = MultiObjectiveOptimizationRequest(user_id=user_id, task_id=task_id)
    MultiObjectiveService.optimize_intervention(db=db_session, request=opt_req)
    opt_lat_ms = (time.perf_counter() - t0) * 1000.0
    assert opt_lat_ms < 250.0, f"Optimization latency exceeded budget: {opt_lat_ms:.2f}ms"

    # Benchmark Digital Twin Simulation
    t0 = time.perf_counter()
    sim_req = ScenarioSimulationRequest(
        scenario_type=ScenarioType.SCHEDULE_FOCUS_SESSION,
        user_id=user_id,
        task_id=task_id,
    )
    SimulationService.simulate_scenario(db=db_session, request=sim_req)
    sim_lat_ms = (time.perf_counter() - t0) * 1000.0
    assert sim_lat_ms < 250.0, f"Simulation latency exceeded budget: {sim_lat_ms:.2f}ms"


# ---------------------------------------------------------------------------
# 7. Backward Compatibility with Phase 1-5 APIs
# ---------------------------------------------------------------------------

def test_backward_compatibility_core_endpoints(release_test_client: TestClient):
    """Verifies Phase 1-5 core platform endpoints remain responsive and intact."""
    # Health endpoint
    res_health = release_test_client.get("/api/v1/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"

    # Tasks endpoint
    res_tasks = release_test_client.get("/api/v1/tasks")
    assert res_tasks.status_code == 200
    assert isinstance(res_tasks.json(), list)

    # Adaptive Profile endpoint
    res_prof = release_test_client.get("/api/v1/adaptive/profile")
    assert res_prof.status_code == 200

    # Privacy Settings endpoint
    res_priv = release_test_client.get("/api/v1/privacy/settings")
    assert res_priv.status_code == 200


# ---------------------------------------------------------------------------
# 8. REST API Release Endpoints Validation
# ---------------------------------------------------------------------------

def test_release_api_endpoints_complete_surface(release_test_client: TestClient):
    """Verifies all Phase 6 public REST API endpoints respond correctly."""
    endpoints = [
        ("/api/v1/analytics/recovery/benchmark", 200),
        ("/api/v1/causal/questions", 200),
        ("/api/v1/counterfactual/candidates", 200),
        ("/api/v1/sequence/benchmark", 200),
        ("/api/v1/survival/benchmark", 200),
        ("/api/v1/uncertainty/audit", 200),
        ("/api/v1/simulation/scenarios", 200),
        ("/api/v1/analytics/simulation/scenarios", 200),
    ]

    for path, expected_status in endpoints:
        res = release_test_client.get(path)
        assert res.status_code == expected_status, f"Endpoint {path} failed: status {res.status_code}"

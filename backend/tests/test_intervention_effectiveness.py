"""
Unit and integration test suite for ContextIQ Intervention Effectiveness and Causal Evaluation Engine (Phase 4.7).
Validates:
1. Distinguishing user acceptance from empirical behavioral execution
2. Multi-horizon observation window selection by category
3. Observational vs. causal ATE demarcation and methodological documentation
4. Doubly Robust (DR) and IPW causal estimation correctness
5. Statistical power validation guards (N >= 20 requirement)
6. Habituation / intervention fatigue slope detection
7. Ethical holdout guardrails (never withholding < 2h deadline reminders)
8. Multi-tenant data isolation between distinct users
9. REST API endpoints (/effectiveness/overview, /interventions, /experiments, /{id})
"""
from __future__ import annotations

import math
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
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
from app.effectiveness.causal_evaluator import CausalEvaluator
from app.effectiveness.outcome_tracker import OutcomeTracker
from app.main import app
from app.models.effectiveness_models import InterventionExperiment, InterventionOutcome
from app.models.task import Task
from app.models.user import User
from app.models.user_intervention import UserIntervention
from app.schemas.effectiveness_schemas import OutcomeWindowMinutes, TreatmentStatus
from app.services.adaptive.effectiveness_service import EffectivenessService


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


def _create_user(db: Session, prefix: str = "effect_user") -> User:
    uid = uuid.uuid4()
    user = User(
        id=uid,
        email=f"{prefix}_{uid.hex[:6]}@example.com",
        display_name="Effectiveness Tester",
        timezone="UTC",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


# ---------------------------------------------------------------------------
# 1. Distinguish Acceptance from Execution
# ---------------------------------------------------------------------------
def test_distinguish_acceptance_from_execution(db_session: Session):
    user = _create_user(db_session, prefix="exec_test")
    now = datetime(2026, 11, 22, 10, 0, 0, tzinfo=timezone.utc)

    # Scenario A: User accepted, but NO downstream telemetry or activity -> was_executed = False
    outcome_a = EffectivenessService.record_outcome(
        db=db_session,
        user_id=user.id,
        intervention_type="SUGGEST_PROTECTED_FOCUS_SESSION",
        intervention_category="FOCUS",
        presented_at=now,
        user_action="ACCEPTED",
        telemetry_events=[],
        task_events=[],
    )
    assert outcome_a.user_action == "ACCEPTED"
    assert outcome_a.was_executed is False
    assert "reason" in outcome_a.execution_evidence or "NO_DOWNSTREAM_TELEMETRY" in outcome_a.execution_evidence.get("criterion", "")

    # Scenario B: User accepted, and downstream task resumption was logged within window -> was_executed = True
    task_events = [
        {
            "event_type": "RESUMED",
            "timestamp": now + timedelta(minutes=5),
            "task_id": str(uuid.uuid4()),
        }
    ]
    outcome_b = EffectivenessService.record_outcome(
        db=db_session,
        user_id=user.id,
        intervention_type="RESUME_PREVIOUS_TASK",
        intervention_category="RECOVERY",
        presented_at=now,
        user_action="ACCEPTED",
        task_events=task_events,
    )
    assert outcome_b.user_action == "ACCEPTED"
    assert outcome_b.was_executed is True
    assert outcome_b.execution_evidence["criterion"] == "TASK_RESUMPTION_LOGGED"


# ---------------------------------------------------------------------------
# 2. Multi-Horizon Window Selection
# ---------------------------------------------------------------------------
def test_multihorizon_window_selection():
    # RECOVERY interventions -> 30 min window
    rec_win = OutcomeTracker.determine_observation_window_minutes("RECOVERY")
    assert rec_win == OutcomeWindowMinutes.IMMEDIATE_RECOVERY.value == 30

    # FOCUS & CONTEXTUAL interventions -> 120 min window
    foc_win = OutcomeTracker.determine_observation_window_minutes("FOCUS")
    ctx_win = OutcomeTracker.determine_observation_window_minutes("CONTEXTUAL")
    assert foc_win == OutcomeWindowMinutes.MEDIUM_SESSION.value == 120
    assert ctx_win == OutcomeWindowMinutes.MEDIUM_SESSION.value == 120

    # TASK & WORKLOAD interventions -> 1440 min window
    task_win = OutcomeTracker.determine_observation_window_minutes("TASK")
    work_win = OutcomeTracker.determine_observation_window_minutes("WORKLOAD")
    assert task_win == OutcomeWindowMinutes.DAILY_WORKLOAD.value == 1440
    assert work_win == OutcomeWindowMinutes.DAILY_WORKLOAD.value == 1440


# ---------------------------------------------------------------------------
# 3. Observational vs. Causal Demarcation
# ---------------------------------------------------------------------------
def test_observational_vs_causal_demarcation(db_session: Session):
    user = _create_user(db_session, prefix="demarc")
    now = datetime(2026, 11, 22, 9, 0, 0, tzinfo=timezone.utc)

    # Create treated outcomes
    for i in range(5):
        EffectivenessService.record_outcome(
            db=db_session,
            user_id=user.id,
            intervention_type="SUGGEST_RECOVERY_BUFFER",
            intervention_category="RECOVERY",
            treatment_status=TreatmentStatus.TREATED.value,
            presented_at=now + timedelta(hours=i),
            user_action="ACCEPTED",
            baseline_bfi=60.0,
            observed_bfi=40.0,
            baseline_resumption_lag_seconds=45.0,
            observed_resumption_lag_seconds=15.0,
            target_task_completed=True,
        )

    # Create control holdout outcomes
    for i in range(3):
        EffectivenessService.record_outcome(
            db=db_session,
            user_id=user.id,
            intervention_type="SUGGEST_RECOVERY_BUFFER",
            intervention_category="RECOVERY",
            treatment_status=TreatmentStatus.CONTROL_HOLDOUT.value,
            presented_at=now + timedelta(hours=i + 5),
            user_action="NO_ACTION",
            baseline_bfi=60.0,
            observed_bfi=55.0,
            baseline_resumption_lag_seconds=45.0,
            observed_resumption_lag_seconds=40.0,
            target_task_completed=False,
        )

    overview = EffectivenessService.get_overview(db=db_session, user_id=user.id)
    assert overview.total_interventions == 8
    assert overview.treated_count == 5
    assert overview.control_count == 3
    # Check that overview includes the explicit methodological disclaimer
    assert "Observational differences do not establish causation" in overview.methodological_disclaimer

    comparisons = EffectivenessService.get_interventions_comparison(db=db_session, user_id=user.id)
    assert len(comparisons) == 1
    comp = comparisons[0]
    # Observational difference is demarcated from estimated ATE
    assert hasattr(comp, "unadjusted_observational_difference")
    assert hasattr(comp, "estimated_ate")
    assert comp.unadjusted_observational_difference != 0.0


# ---------------------------------------------------------------------------
# 4. Doubly Robust & IPW Estimation Correctness
# ---------------------------------------------------------------------------
def test_doubly_robust_estimation():
    # Synthetic samples where treatment adds a true effect of +0.4 to outcome
    samples = []
    # 30 treated, 20 control
    for i in range(30):
        samples.append({
            "treatment": 1,
            "outcome": 0.70 + (0.05 * (i % 3)),
            "propensity": 0.60,
            "predicted_outcome_treated": 0.72,
            "predicted_outcome_control": 0.30,
        })
    for i in range(20):
        samples.append({
            "treatment": 0,
            "outcome": 0.30 + (0.05 * (i % 3)),
            "propensity": 0.40,
            "predicted_outcome_treated": 0.70,
            "predicted_outcome_control": 0.32,
        })

    # 1. IPW estimator
    ipw_res = CausalEvaluator.estimate_ipw_ate(samples)
    assert 0.35 <= ipw_res["ate"] <= 0.48

    # 2. Doubly Robust estimator
    dr_res = CausalEvaluator.estimate_doubly_robust_ate(samples)
    assert dr_res["is_statistically_valid"] is True
    assert 0.35 <= dr_res["ate"] <= 0.48
    assert dr_res["p_value"] < 0.05
    assert dr_res["confidence_interval_95"][0] < dr_res["ate"] < dr_res["confidence_interval_95"][1]


# ---------------------------------------------------------------------------
# 5. Statistical Validation & Power Guard
# ---------------------------------------------------------------------------
def test_statistical_validation_and_power_guard():
    # Underpowered dataset: only 8 samples (N < 20)
    underpowered = [
        {"treatment": 1, "outcome": 0.8, "propensity": 0.5} for _ in range(5)
    ] + [
        {"treatment": 0, "outcome": 0.2, "propensity": 0.5} for _ in range(3)
    ]

    res_small = CausalEvaluator.estimate_doubly_robust_ate(underpowered)
    assert res_small["is_statistically_valid"] is False
    assert "Sample size underpowered" in res_small["validation_note"]

    # Powered dataset: 25 total (15 treated, 10 control)
    powered = [
        {"treatment": 1, "outcome": 0.8, "propensity": 0.5} for _ in range(15)
    ] + [
        {"treatment": 0, "outcome": 0.2, "propensity": 0.5} for _ in range(10)
    ]
    res_powered = CausalEvaluator.estimate_doubly_robust_ate(powered)
    assert res_powered["is_statistically_valid"] is True
    assert res_powered["validation_note"] is None


# ---------------------------------------------------------------------------
# 6. Habituation / Fatigue Slope Detection
# ---------------------------------------------------------------------------
def test_habituation_fatigue_detection():
    # Steadily declining acceptance over 10 days: 1, 1, 1, 1, 0, 0, 0, 0, 0, 0
    declining_history = [
        (0.0, 1),
        (1.0, 1),
        (2.0, 1),
        (3.0, 1),
        (4.0, 0),
        (5.0, 0),
        (6.0, 0),
        (7.0, 0),
        (8.0, 0),
        (9.0, 0),
    ]
    is_fatigued, slope = CausalEvaluator.detect_habituation_fatigue(declining_history)
    assert is_fatigued is True
    assert slope is not None and slope < -0.05

    # Stable high acceptance: 1, 1, 1, 1, 1, 1, 1, 1
    stable_history = [(float(i), 1) for i in range(10)]
    is_fatigued_stable, slope_stable = CausalEvaluator.detect_habituation_fatigue(stable_history)
    assert is_fatigued_stable is False
    assert slope_stable == 0.0


# ---------------------------------------------------------------------------
# 7. Ethical Holdout Safety Guardrail
# ---------------------------------------------------------------------------
def test_ethical_holdout_safety(db_session: Session):
    user = _create_user(db_session, prefix="ethical")
    now = datetime(2026, 11, 22, 10, 0, 0, tzinfo=timezone.utc)

    # Imminent deadline 1 hour away (< 2h threshold)
    imminent_deadline = now + timedelta(hours=1.0)
    can_holdout = OutcomeTracker.can_assign_to_control_holdout(
        task_due_at=imminent_deadline,
        as_of=now,
    )
    assert can_holdout is False

    # Attempting to record with CONTROL_HOLDOUT status under imminent deadline
    # must automatically override status to TREATED
    outcome = EffectivenessService.record_outcome(
        db=db_session,
        user_id=user.id,
        intervention_type="REVIEW_APPROACHING_DEADLINE",
        intervention_category="TASK",
        treatment_status=TreatmentStatus.CONTROL_HOLDOUT.value,
        baseline_task_due_at=imminent_deadline,
        presented_at=now,
        user_action="ACCEPTED",
    )
    assert outcome.treatment_status == TreatmentStatus.TREATED.value

    # Distant deadline 24 hours away (> 2h threshold) allows holdout
    distant_deadline = now + timedelta(hours=24.0)
    can_holdout_distant = OutcomeTracker.can_assign_to_control_holdout(
        task_due_at=distant_deadline,
        as_of=now,
    )
    assert can_holdout_distant is True


# ---------------------------------------------------------------------------
# 8. Tenant Data Isolation
# ---------------------------------------------------------------------------
def test_tenant_isolation(db_session: Session):
    user_a = _create_user(db_session, prefix="user_a")
    user_b = _create_user(db_session, prefix="user_b")

    outcome_a = EffectivenessService.record_outcome(
        db=db_session,
        user_id=user_a.id,
        intervention_type="SUGGEST_PROTECTED_FOCUS_SESSION",
        intervention_category="FOCUS",
        user_action="ACCEPTED",
    )

    # User A can retrieve their own outcome
    read_a = EffectivenessService.get_outcome_by_id(
        db=db_session, user_id=user_a.id, outcome_or_intervention_id=outcome_a.id
    )
    assert read_a.id == outcome_a.id

    # User B attempting to retrieve User A's outcome fails with 404
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        EffectivenessService.get_outcome_by_id(
            db=db_session, user_id=user_b.id, outcome_or_intervention_id=outcome_a.id
        )
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# 9. REST API Endpoints Verification
# ---------------------------------------------------------------------------
def test_rest_api_endpoints(client: TestClient):
    with Session(bind=engine) as session:
        user = _create_user(session, prefix="api_tester")
        exp_id = str(uuid.uuid4())
        experiment = InterventionExperiment(
            id=uuid.UUID(exp_id),
            user_id=user.id,
            experiment_name="Focus Buffer Holdout Test",
            target_intervention_type="SUGGEST_RECOVERY_BUFFER",
            control_policy="NO_ACTION_HOLDOUT",
            allocation_ratio=0.8,
            is_active=True,
            sample_size_treated=10,
            sample_size_control=5,
        )
        session.add(experiment)

        # Seed outcomes
        for i in range(6):
            is_ctrl = (i % 3 == 0)
            outcome = InterventionOutcome(
                id=uuid.uuid4(),
                user_id=user.id,
                intervention_type="SUGGEST_RECOVERY_BUFFER",
                intervention_category="RECOVERY",
                treatment_status="CONTROL_HOLDOUT" if is_ctrl else "TREATED",
                experiment_id=exp_id,
                presented_at=datetime.now(timezone.utc) - timedelta(minutes=i * 20),
                user_action="NO_ACTION" if is_ctrl else "ACCEPTED",
                was_executed=not is_ctrl,
                window_start=datetime.now(timezone.utc) - timedelta(minutes=i * 20),
                window_end=datetime.now(timezone.utc) + timedelta(minutes=30),
                observation_window_minutes=30,
                baseline_bfi=55.0,
                baseline_resumption_lag_seconds=40.0,
                baseline_hourly_interruption_rate=2.5,
                observed_bfi=40.0 if not is_ctrl else 52.0,
                observed_resumption_lag_seconds=20.0 if not is_ctrl else 38.0,
                bfi_delta=15.0 if not is_ctrl else 3.0,
                resumption_lag_delta_seconds=20.0 if not is_ctrl else 2.0,
                target_task_completed=not is_ctrl,
                composite_effectiveness_score=0.65 if not is_ctrl else -0.1,
                is_statistically_valid=True,
            )
            session.add(outcome)
        session.commit()
        created_outcome_id = outcome.id
        user_id = user.id

    from app.core.deps import get_current_user_id
    app.dependency_overrides[get_current_user_id] = lambda: user_id

    try:
        # 1. GET /api/v1/adaptive/effectiveness/overview
        res_ov = client.get("/api/v1/adaptive/effectiveness/overview")
        assert res_ov.status_code == 200
        data_ov = res_ov.json()
        assert data_ov["total_interventions"] == 6
        assert data_ov["treated_count"] == 4
        assert data_ov["control_count"] == 2
        assert "methodological_disclaimer" in data_ov

        # 2. GET /api/v1/adaptive/effectiveness/interventions
        res_int = client.get("/api/v1/adaptive/effectiveness/interventions")
        assert res_int.status_code == 200
        data_int = res_int.json()
        assert len(data_int) >= 1
        item = data_int[0]
        assert item["intervention_type"] == "SUGGEST_RECOVERY_BUFFER"
        assert "unadjusted_observational_difference" in item
        assert "estimated_ate" in item

        # 3. GET /api/v1/adaptive/effectiveness/experiments
        res_exp = client.get("/api/v1/adaptive/effectiveness/experiments")
        assert res_exp.status_code == 200
        data_exp = res_exp.json()
        assert len(data_exp) >= 1
        assert data_exp[0]["experiment_name"] == "Focus Buffer Holdout Test"

        # 4. GET /api/v1/adaptive/effectiveness/{intervention_id}
        res_single = client.get(f"/api/v1/adaptive/effectiveness/{created_outcome_id}")
        assert res_single.status_code == 200
        data_single = res_single.json()
        assert data_single["id"] == str(created_outcome_id)
        assert data_single["intervention_type"] == "SUGGEST_RECOVERY_BUFFER"

    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

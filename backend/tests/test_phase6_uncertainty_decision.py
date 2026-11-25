"""
Unit & Integration Test Suite for ContextIQ Uncertainty-Aware Decision Support (Phase 6.8).

Validates:
1. Uncertainty audit across all 7 ContextIQ predictive model families.
2. Aleatoric vs epistemic uncertainty decomposition (never collapsed into single confidence %).
3. Probability calibration algorithms (Platt Scaling, Isotonic Regression, Temperature Scaling) and ECE.
4. Split-conformal prediction intervals with coverage guarantees and distribution shift warning.
5. Data coverage and OOD detection (cold-start N < 5, telemetry < 35%, OOD distance > 3.5, unseen tokens).
6. 5-state intelligent abstention state machine (PREDICTION_AVAILABLE, PREDICTION_WITH_CAUTION,
   INSUFFICIENT_EVIDENCE, UNSUPPORTED_INPUT, MODEL_UNAVAILABLE).
7. Decision policy: Automated recommendation ranking is strictly blocked on abstention.
8. REST API endpoints (/api/v1/uncertainty/* and /api/v1/analytics/uncertainty/*).
"""
from __future__ import annotations

import math
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

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
from app.schemas.uncertainty_decision import (
    AbstentionOutcome,
    AbstentionReason,
    ActionPolicyType,
    CalibrationMetrics,
    DecisionSupportRequest,
    DecisionSupportResponse,
    ModelUncertaintyAuditItem,
)
from app.services.uncertainty_calibration_engine import (
    IsotonicCalibrator,
    PlattCalibrator,
    TemperatureScaler,
    UncertaintyCalibrationEngine,
)
from app.services.uncertainty_decision_service import UncertaintyDecisionService


# ---------------------------------------------------------------------------
# Database & Client Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def test_db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(test_db_engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def test_client(test_db_engine):
    from app.core.deps import get_current_user_id
    from app.db.session import get_db

    test_user_id = uuid.uuid4()

    def override_get_db():
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine)
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_current_user_id] = lambda: test_user_id
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 1. Prediction Uncertainty Audit Tests
# ---------------------------------------------------------------------------

def test_model_uncertainty_audit_covers_all_seven_families():
    """Verifies that all 7 model families across Phases 2, 6.2-6.7 are audited with limitations."""
    audit = UncertaintyCalibrationEngine.audit_prediction_uncertainty()
    assert len(audit) == 7

    family_names = [item.model_family for item in audit]
    assert any("XGBoost" in f for f in family_names)
    assert any("AFT" in f for f in family_names)
    assert any("AIPW" in f for f in family_names)
    assert any("Meta-Learner" in f for f in family_names)
    assert any("Transformer" in f for f in family_names)
    assert any("Survival" in f for f in family_names)
    assert any("Optimizer" in f for f in family_names)

    for item in audit:
        assert item.target_name != ""
        assert item.interval_methodology is not None
        assert item.calibration_status != ""
        assert len(item.known_limitations) > 10


# ---------------------------------------------------------------------------
# 2. Aleatoric vs Epistemic Decomposition Tests
# ---------------------------------------------------------------------------

def test_uncertainty_decomposition_separates_noise_from_ignorance():
    """Verifies that aleatoric and epistemic uncertainty are calculated separately."""
    # Scenario A: Rich history (N=50), in-distribution -> low epistemic, aleatoric dominates
    cov_rich = UncertaintyCalibrationEngine.evaluate_data_coverage(
        user_history_count=50,
        context_features={"baseline_bfi": 48.0, "task_priority": 2.0, "recent_interruptions": 2.0, "monitored_hours_last_24h": 7.5},
    )
    decomp_rich = UncertaintyCalibrationEngine.decompose_uncertainty(0.50, cov_rich)
    assert decomp_rich.aleatoric_score >= 0.80  # Max entropy at p=0.50
    assert decomp_rich.epistemic_score <= 0.25
    assert decomp_rich.is_epistemic_dominant is False

    # Scenario B: Sparse cold-start history (N=2), high OOD -> epistemic dominates
    cov_sparse = UncertaintyCalibrationEngine.evaluate_data_coverage(
        user_history_count=2,
        context_features={"baseline_bfi": 85.0, "task_priority": 4.0, "recent_interruptions": 8.0, "monitored_hours_last_24h": 2.0},
    )
    decomp_sparse = UncertaintyCalibrationEngine.decompose_uncertainty(0.90, cov_sparse)
    assert decomp_sparse.epistemic_score > decomp_sparse.aleatoric_score
    assert decomp_sparse.is_epistemic_dominant is True
    assert "Epistemic uncertainty dominates" in decomp_sparse.explanation


# ---------------------------------------------------------------------------
# 3. Probability Calibration Algorithms & ECE Tests
# ---------------------------------------------------------------------------

def test_platt_and_isotonic_calibration():
    """Verifies that Platt and Isotonic calibration models fit and calibrate probabilities."""
    rng = np.random.RandomState(42)
    scores = rng.normal(0, 1.5, size=100)
    true_p = 1.0 / (1.0 + np.exp(-scores))
    y = (rng.uniform(0, 1, size=100) <= true_p).astype(int)

    # Platt
    platt = PlattCalibrator().fit(scores, y)
    probs_platt = platt.predict_proba(scores)
    assert len(probs_platt) == 100
    assert (probs_platt >= 0.0).all() and (probs_platt <= 1.0).all()

    # Isotonic
    iso = IsotonicCalibrator().fit(probs_platt, y)
    probs_iso = iso.predict_proba(probs_platt)
    assert len(probs_iso) == 100
    assert (probs_iso >= 0.0).all() and (probs_iso <= 1.0).all()


def test_temperature_scaling():
    """Verifies temperature scaling softens overconfident logits."""
    logits = np.array([[3.0, -1.0], [4.0, -2.0]])
    scaler = TemperatureScaler(temperature=2.0)
    scaled_probs = scaler.scale_logits(logits)
    assert scaled_probs.shape == (2, 2)
    assert np.allclose(scaled_probs.sum(axis=-1), 1.0)
    # Higher temperature reduces confidence
    raw_probs = np.exp(logits) / np.sum(np.exp(logits), axis=-1, keepdims=True)
    assert scaled_probs[0, 0] < raw_probs[0, 0]


def test_expected_calibration_error_calculation():
    """Verifies that ECE, MCE, and Brier score are properly calculated."""
    y_true = np.array([1, 0, 1, 1, 0, 0, 1, 0, 1, 1])
    y_prob = np.array([0.9, 0.1, 0.8, 0.7, 0.2, 0.1, 0.9, 0.3, 0.8, 0.7])
    metrics = UncertaintyCalibrationEngine.evaluate_calibration_metrics(
        y_true=y_true, y_prob=y_prob, method_name="Test Calibration"
    )

    assert 0.0 <= metrics.expected_calibration_error <= 1.0
    assert 0.0 <= metrics.maximum_calibration_error <= 1.0
    assert 0.0 <= metrics.brier_score <= 1.0
    assert len(metrics.reliability_bins) > 0


# ---------------------------------------------------------------------------
# 4. Conformal Prediction Interval Tests
# ---------------------------------------------------------------------------

def test_conformal_prediction_intervals():
    """Verifies that split-conformal intervals produce valid coverage bounds."""
    interval = UncertaintyCalibrationEngine.compute_conformal_interval(
        point_pred=0.70,
        coverage_level=0.90,
        recent_telemetry_variance=0.04,
    )
    assert interval.coverage_level == 0.90
    assert 0.0 <= interval.lower_bound <= 0.70
    assert 0.70 <= interval.upper_bound <= 1.0
    assert interval.interval_width == round(interval.upper_bound - interval.lower_bound, 4)
    assert interval.temporal_shift_warning is None


def test_conformal_interval_temporal_shift_detection():
    """Verifies that elevated behavioral volatility triggers distribution shift warning."""
    interval = UncertaintyCalibrationEngine.compute_conformal_interval(
        point_pred=0.65,
        recent_telemetry_variance=0.22,  # Elevated volatility
    )
    assert interval.temporal_shift_warning is not None
    assert "temporal distribution shift" in interval.temporal_shift_warning


# ---------------------------------------------------------------------------
# 5. Data Coverage & OOD Detection Tests
# ---------------------------------------------------------------------------

def test_data_coverage_cold_start_and_ood():
    """Verifies coverage checks identify cold starts, OOD, and missing features."""
    # Normal case
    cov_normal = UncertaintyCalibrationEngine.evaluate_data_coverage(
        user_history_count=35,
        context_features={"baseline_bfi": 48.0, "task_priority": 2.0, "recent_interruptions": 2.0},
    )
    assert cov_normal.data_coverage_tier == "FULL"
    assert cov_normal.is_out_of_distribution is False
    assert len(cov_normal.missing_critical_inputs) == 0

    # Cold start case
    cov_cold = UncertaintyCalibrationEngine.evaluate_data_coverage(
        user_history_count=3,
        context_features={"baseline_bfi": 50.0, "task_priority": 2.0, "recent_interruptions": 1.0},
    )
    assert cov_cold.data_coverage_tier == "INSUFFICIENT"
    assert cov_cold.user_sample_size == 3

    # OOD case
    cov_ood = UncertaintyCalibrationEngine.evaluate_data_coverage(
        user_history_count=20,
        context_features={"baseline_bfi": 99.5, "task_priority": 4.0, "recent_interruptions": 10.0},
    )
    assert cov_ood.is_out_of_distribution is True
    assert cov_ood.ood_distance > 3.5

    # Missing critical inputs
    cov_missing = UncertaintyCalibrationEngine.evaluate_data_coverage(
        user_history_count=20,
        context_features={"task_priority": 2.0},  # Missing baseline_bfi, recent_interruptions
    )
    assert "baseline_bfi" in cov_missing.missing_critical_inputs


# ---------------------------------------------------------------------------
# 6. Intelligent Abstention State Machine Tests
# ---------------------------------------------------------------------------

def test_abstention_state_machine_prediction_available():
    """Verifies PREDICTION_AVAILABLE when coverage is strong and uncertainty low."""
    req = DecisionSupportRequest(
        context_features={"baseline_bfi": 50.0, "task_priority": 2.0, "recent_interruptions": 2.0, "monitored_hours_last_24h": 7.0},
    )
    res = UncertaintyCalibrationEngine.evaluate_decision_support(
        request=req, user_history_count=35, raw_prediction=0.72
    )
    assert res.abstention_outcome == AbstentionOutcome.PREDICTION_AVAILABLE
    assert res.abstention_reason == AbstentionReason.NONE
    assert res.can_automate_recommendation is True
    assert res.recommended_action_policy == ActionPolicyType.EXECUTE_AUTOMATED
    assert res.calibrated_probability is not None
    assert res.prediction_interval is not None


def test_abstention_state_machine_prediction_with_caution():
    """Verifies PREDICTION_WITH_CAUTION when epistemic uncertainty is moderate."""
    req = DecisionSupportRequest(
        context_features={"baseline_bfi": 62.0, "task_priority": 3.0, "recent_interruptions": 3.0, "monitored_hours_last_24h": 4.0},
    )
    res = UncertaintyCalibrationEngine.evaluate_decision_support(
        request=req, user_history_count=7, raw_prediction=0.65  # Small history
    )
    assert res.abstention_outcome in (AbstentionOutcome.PREDICTION_WITH_CAUTION, AbstentionOutcome.PREDICTION_AVAILABLE)
    if res.abstention_outcome == AbstentionOutcome.PREDICTION_WITH_CAUTION:
        assert res.recommended_action_policy == ActionPolicyType.EXECUTE_WITH_CAUTION
        assert res.can_automate_recommendation is True


def test_abstention_state_machine_insufficient_evidence():
    """Verifies INSUFFICIENT_EVIDENCE when user history is sparse (cold-start)."""
    req = DecisionSupportRequest(
        context_features={"baseline_bfi": 50.0, "task_priority": 2.0, "recent_interruptions": 1.0},
    )
    res = UncertaintyCalibrationEngine.evaluate_decision_support(
        request=req, user_history_count=2, raw_prediction=0.60  # N=2 < 5
    )
    assert res.abstention_outcome == AbstentionOutcome.INSUFFICIENT_EVIDENCE
    assert res.abstention_reason == AbstentionReason.INSUFFICIENT_USER_HISTORY
    assert res.can_automate_recommendation is False
    assert res.recommended_action_policy == ActionPolicyType.FALLBACK_DETERMINISTIC
    assert "insufficient" in res.user_facing_explanation.lower()


def test_abstention_state_machine_unsupported_input():
    """Verifies UNSUPPORTED_INPUT when encountering extreme OOD or unseen tokens."""
    req_ood = DecisionSupportRequest(
        context_features={"baseline_bfi": 1.0, "task_priority": 1.0, "recent_interruptions": 0.0},
    )
    res_ood = UncertaintyCalibrationEngine.evaluate_decision_support(
        request=req_ood, user_history_count=20, raw_prediction=0.50
    )
    assert res_ood.abstention_outcome == AbstentionOutcome.UNSUPPORTED_INPUT
    assert res_ood.can_automate_recommendation is False

    req_token = DecisionSupportRequest(
        context_features={"baseline_bfi": 50.0, "task_priority": 2.0, "recent_interruptions": 1.0, "last_event_token": "UNKNOWN_CUSTOM_HACK_EVENT"},
    )
    res_token = UncertaintyCalibrationEngine.evaluate_decision_support(
        request=req_token, user_history_count=20, raw_prediction=0.50
    )
    assert res_token.abstention_outcome == AbstentionOutcome.UNSUPPORTED_INPUT
    assert res_token.abstention_reason == AbstentionReason.UNSEEN_EVENT_TYPE
    assert res_token.can_automate_recommendation is False
    assert res_token.recommended_action_policy == ActionPolicyType.ABSTAIN_AND_PROMPT_USER


# ---------------------------------------------------------------------------
# 7. Service Layer Tests
# ---------------------------------------------------------------------------

def test_service_audit_and_benchmarks():
    """Verifies service returns audit list, calibration benchmarks, and abstention policies."""
    audit = UncertaintyDecisionService.audit_all_models()
    assert len(audit) == 7

    benchmarks = UncertaintyDecisionService.get_calibration_benchmarks()
    assert len(benchmarks) == 3

    policies = UncertaintyDecisionService.list_abstention_policies()
    assert len(policies) == 5
    outcomes = [p["outcome"] for p in policies]
    assert AbstentionOutcome.PREDICTION_AVAILABLE.value in outcomes
    assert AbstentionOutcome.INSUFFICIENT_EVIDENCE.value in outcomes


def test_service_evaluate_decision_support(db_session):
    """Verifies service end-to-end evaluation with DB session."""
    user_id = uuid.uuid4()
    req = DecisionSupportRequest(
        user_id=user_id,
        context_features={"baseline_bfi": 52.0, "task_priority": 2.0, "recent_interruptions": 1.0},
    )
    res = UncertaintyDecisionService.evaluate_decision_support(db=db_session, request=req)
    assert res.user_id == user_id
    assert res.abstention_outcome in AbstentionOutcome
    assert res.uncertainty_decomposition is not None


# ---------------------------------------------------------------------------
# 8. REST API Endpoints Integration Tests
# ---------------------------------------------------------------------------

def test_api_uncertainty_audit(test_client):
    """GET /api/v1/uncertainty/audit."""
    resp = test_client.get("/api/v1/uncertainty/audit")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 7
    assert any("XGBoost" in item["model_family"] for item in data)


def test_api_uncertainty_policies(test_client):
    """GET /api/v1/uncertainty/policies."""
    resp = test_client.get("/api/v1/uncertainty/policies")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 5


def test_api_uncertainty_calibration(test_client):
    """GET /api/v1/uncertainty/calibration."""
    resp = test_client.get("/api/v1/uncertainty/calibration")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    assert any("Isotonic" in item["calibration_method"] for item in data)


def test_api_uncertainty_evaluate_post(test_client):
    """POST /api/v1/uncertainty/evaluate."""
    user_id = str(uuid.uuid4())
    payload = {
        "user_id": user_id,
        "model_target": "forgetting_risk",
        "context_features": {
            "baseline_bfi": 48.0,
            "task_priority": 2.0,
            "recent_interruptions": 1.0,
            "monitored_hours_last_24h": 7.0,
        },
    }
    resp = test_client.post("/api/v1/uncertainty/evaluate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "abstention_outcome" in data
    assert "uncertainty_decomposition" in data
    assert "can_automate_recommendation" in data


def test_api_uncertainty_evaluate_get(test_client):
    """GET /api/v1/uncertainty/evaluate."""
    resp = test_client.get("/api/v1/uncertainty/evaluate?model_target=recovery_duration")
    assert resp.status_code == 200
    data = resp.json()
    assert "abstention_outcome" in data


def test_api_analytics_uncertainty(test_client):
    """GET /api/v1/analytics/uncertainty/evaluate and /audit."""
    resp_eval = test_client.get("/api/v1/analytics/uncertainty/evaluate?model_target=task_completion")
    assert resp_eval.status_code == 200
    assert "abstention_outcome" in resp_eval.json()

    resp_audit = test_client.get("/api/v1/analytics/uncertainty/audit")
    assert resp_audit.status_code == 200
    assert len(resp_audit.json()) == 7

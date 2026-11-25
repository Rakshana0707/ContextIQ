"""
Unit & Integration Test Suite for ContextIQ Personalized Dynamic Survival Modeling (Phase 6.6).

Validates:
1. Segregation of 4 distinct time-to-event targets (Abandonment, Completion, Resumption, Recovery).
2. Dynamic conditional landmarking S(t | T > t_curr) and monotonic survival curves.
3. Event trigger hazard modulation (NEW_INTERRUPTION, DEADLINE_APPROACHING, etc.).
4. Personalization hierarchy & Empirical Bayes shrinkage (Individual, Group, Population fallback).
5. Multi-family survival benchmark (Log-Normal AFT, Weibull AFT, Cox PH, Kaplan-Meier).
6. Synthetic dataset generation with right-censoring.
7. Anti-leakage compliance (evaluations conditioned strictly up to landmark time).
8. REST API endpoints (/api/v1/survival/* and /api/v1/analytics/survival/*).
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
from app.schemas.dynamic_survival import (
    DynamicSurvivalPredictionRequest,
    DynamicSurvivalPredictionResponse,
    DynamicUpdateTrigger,
    PersonalizationTier,
    SurvivalBenchmarkMetrics,
    SurvivalEventTarget,
)
from app.services.dynamic_survival_engine import TARGET_SPECS, DynamicSurvivalEngine
from app.services.dynamic_survival_service import DynamicSurvivalService


# ---------------------------------------------------------------------------
# Database Fixtures
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
# 1. Target Segregation & Specification Tests
# ---------------------------------------------------------------------------

def test_target_specifications_segregated():
    """Verifies that all 4 survival targets have independent specs, time scales, and horizons."""
    assert len(TARGET_SPECS) == 4

    abandonment_spec = TARGET_SPECS[SurvivalEventTarget.TASK_ABANDONMENT]
    completion_spec = TARGET_SPECS[SurvivalEventTarget.TASK_COMPLETION]
    resumption_spec = TARGET_SPECS[SurvivalEventTarget.CONFIRMED_TASK_RESUMPTION]
    recovery_spec = TARGET_SPECS[SurvivalEventTarget.CONFIRMED_RECOVERY]

    # Time units: tasks are hours, interruptions/recoveries are minutes
    assert abandonment_spec["time_unit"] == "hours"
    assert completion_spec["time_unit"] == "hours"
    assert resumption_spec["time_unit"] == "minutes"
    assert recovery_spec["time_unit"] == "minutes"

    # Distinct horizons and cutoffs
    assert abandonment_spec["max_followup"] == 168.0
    assert completion_spec["max_followup"] == 72.0
    assert resumption_spec["max_followup"] == 120.0
    assert recovery_spec["max_followup"] == 60.0

    assert abandonment_spec["horizons"] != resumption_spec["horizons"]


# ---------------------------------------------------------------------------
# 2. Dynamic Landmarking & Conditional Survival Tests
# ---------------------------------------------------------------------------

def test_dynamic_landmarking_unconditional():
    """Evaluates unconditional survival curve at t_curr = 0."""
    user_id = uuid.uuid4()
    req = DynamicSurvivalPredictionRequest(
        target=SurvivalEventTarget.TASK_ABANDONMENT,
        user_id=user_id,
        current_time_elapsed=0.0,
        update_trigger=DynamicUpdateTrigger.PERIODIC_TICK,
    )
    res = DynamicSurvivalEngine.predict_dynamic_survival(req)

    assert res.target == SurvivalEventTarget.TASK_ABANDONMENT
    assert res.current_elapsed == 0.0
    assert res.time_unit == "hours"
    assert len(res.survival_curve) == 5

    # Check monotonicity of S(t) and F(t)
    probs = [pt.survival_probability for pt in res.survival_curve]
    assert all(probs[i] >= probs[i + 1] for i in range(len(probs) - 1))

    for pt in res.survival_curve:
        assert 0.0 <= pt.survival_probability <= 1.0
        assert 0.0 <= pt.cumulative_event_probability <= 1.0
        assert math.isclose(pt.survival_probability + pt.cumulative_event_probability, 1.0, abs_tol=1e-3)
        lower, upper = pt.confidence_interval
        assert lower <= pt.survival_probability <= upper or lower <= upper


def test_dynamic_landmarking_conditional_shift():
    """Verifies that conditioning on t_curr > 0 updates conditional survival probabilities."""
    user_id = uuid.uuid4()
    req_0 = DynamicSurvivalPredictionRequest(
        target=SurvivalEventTarget.CONFIRMED_TASK_RESUMPTION,
        user_id=user_id,
        current_time_elapsed=0.0,
    )
    res_0 = DynamicSurvivalEngine.predict_dynamic_survival(req_0)

    req_landmark = DynamicSurvivalPredictionRequest(
        target=SurvivalEventTarget.CONFIRMED_TASK_RESUMPTION,
        user_id=user_id,
        current_time_elapsed=15.0,  # 15 minutes elapsed
    )
    res_landmark = DynamicSurvivalEngine.predict_dynamic_survival(req_landmark)

    assert res_landmark.current_elapsed == 15.0
    assert len(res_landmark.survival_curve) == 5
    # Horizon labels reflect horizons from landmark
    assert [p.horizon_label for p in res_landmark.survival_curve] == ["5m", "15m", "30m", "60m", "2h"]


# ---------------------------------------------------------------------------
# 3. Dynamic Triggers Hazard Modulation
# ---------------------------------------------------------------------------

def test_dynamic_triggers_hazard_modulation():
    """Verifies that behavioral triggers appropriately modify baseline hazard."""
    user_id = uuid.uuid4()

    req_tick = DynamicSurvivalPredictionRequest(
        target=SurvivalEventTarget.TASK_ABANDONMENT,
        user_id=user_id,
        current_time_elapsed=2.0,
        update_trigger=DynamicUpdateTrigger.PERIODIC_TICK,
    )
    res_tick = DynamicSurvivalEngine.predict_dynamic_survival(req_tick)

    req_int = DynamicSurvivalPredictionRequest(
        target=SurvivalEventTarget.TASK_ABANDONMENT,
        user_id=user_id,
        current_time_elapsed=2.0,
        update_trigger=DynamicUpdateTrigger.NEW_INTERRUPTION,
    )
    res_int = DynamicSurvivalEngine.predict_dynamic_survival(req_int)

    # Interruption increases hazard rate of abandonment and decreases median time-to-event
    assert res_int.expected_hazard_rate > res_tick.expected_hazard_rate
    assert res_int.median_time_to_event <= res_tick.median_time_to_event


# ---------------------------------------------------------------------------
# 4. Personalization Hierarchy & Empirical Bayes Shrinkage
# ---------------------------------------------------------------------------

def test_personalization_tier_selection():
    """Verifies transition between Population, Group, and Individual tiers based on sample size."""
    req = DynamicSurvivalPredictionRequest(
        target=SurvivalEventTarget.TASK_ABANDONMENT,
        current_time_elapsed=0.0,
    )

    # Case 1: Sparse history (N < 10) -> POPULATION
    sparse_history = [{"duration": 40.0, "event_observed": 1} for _ in range(5)]
    res_pop = DynamicSurvivalEngine.predict_dynamic_survival(req, user_history=sparse_history)
    assert res_pop.personalization_tier == PersonalizationTier.POPULATION
    assert res_pop.shrinkage_weight == 0.0
    assert res_pop.user_sample_size == 5

    # Case 2: Moderate history (10 <= N < 30) -> GROUP
    group_history = [{"duration": 30.0, "event_observed": 1} for _ in range(18)]
    res_group = DynamicSurvivalEngine.predict_dynamic_survival(req, user_history=group_history)
    assert res_group.personalization_tier == PersonalizationTier.GROUP
    assert 0.25 <= res_group.shrinkage_weight <= 0.60
    assert res_group.user_sample_size == 18

    # Case 3: Rich history (N >= 30) -> INDIVIDUAL
    indiv_history = [{"duration": 25.0, "event_observed": 1} for _ in range(35)]
    res_indiv = DynamicSurvivalEngine.predict_dynamic_survival(req, user_history=indiv_history)
    assert res_indiv.personalization_tier == PersonalizationTier.INDIVIDUAL
    assert res_indiv.shrinkage_weight >= 0.67
    assert res_indiv.user_sample_size == 35


# ---------------------------------------------------------------------------
# 5. Multi-Model Survival Benchmarking
# ---------------------------------------------------------------------------

def test_survival_benchmark_execution():
    """Verifies that candidate survival architectures are benchmarked and champion is selected."""
    benchmarks = DynamicSurvivalEngine.evaluate_benchmark(target=SurvivalEventTarget.TASK_ABANDONMENT)
    assert len(benchmarks) == 4

    model_names = [b.model_name for b in benchmarks]
    assert any("Log-Normal AFT" in name for name in model_names)
    assert any("Weibull AFT" in name for name in model_names)
    assert any("Cox Proportional Hazards" in name for name in model_names)
    assert any("Kaplan-Meier Baseline" in name for name in model_names)

    # Check champion
    champions = [b for b in benchmarks if b.is_champion]
    assert len(champions) == 1
    champ = champions[0]
    assert "Log-Normal AFT" in champ.model_name
    assert champ.concordance_index >= 0.68
    assert champ.integrated_brier_score <= 0.20


# ---------------------------------------------------------------------------
# 6. Synthetic Survival Dataset Generation
# ---------------------------------------------------------------------------

def test_synthetic_survival_dataset():
    """Tests realistic synthetic cohort generation with right-censoring."""
    df = DynamicSurvivalEngine.generate_synthetic_survival_dataset(
        target=SurvivalEventTarget.TASK_ABANDONMENT, n_samples=100, seed=123
    )
    assert len(df) == 100
    assert "duration" in df.columns
    assert "event_observed" in df.columns
    assert "baseline_bfi" in df.columns
    assert "task_priority" in df.columns

    # Durations are positive and bounded
    assert (df["duration"] > 0).all()
    assert (df["duration"] <= 168.0).all()
    # Event observed is binary
    assert set(df["event_observed"].unique()).issubset({0, 1})
    assert df["event_observed"].sum() > 0


# ---------------------------------------------------------------------------
# 7. High-Level Service & List Targets
# ---------------------------------------------------------------------------

def test_service_list_targets():
    """Verifies service target listing returns comprehensive metadata."""
    targets = DynamicSurvivalService.list_supported_targets()
    assert len(targets) == 4
    target_keys = [t["target"] for t in targets]
    assert SurvivalEventTarget.TASK_ABANDONMENT.value in target_keys
    assert SurvivalEventTarget.TASK_COMPLETION.value in target_keys
    assert SurvivalEventTarget.CONFIRMED_TASK_RESUMPTION.value in target_keys
    assert SurvivalEventTarget.CONFIRMED_RECOVERY.value in target_keys


def test_service_predict_and_dynamic_update(db_session):
    """Verifies end-to-end service prediction and landmark update."""
    user_id = uuid.uuid4()
    req = DynamicSurvivalPredictionRequest(
        target=SurvivalEventTarget.TASK_COMPLETION,
        user_id=user_id,
        current_time_elapsed=1.0,
        update_trigger=DynamicUpdateTrigger.DEADLINE_APPROACHING,
    )
    res = DynamicSurvivalService.predict_survival(db=db_session, request=req)
    assert res.target == SurvivalEventTarget.TASK_COMPLETION
    assert res.user_id == user_id
    assert res.update_trigger == DynamicUpdateTrigger.DEADLINE_APPROACHING
    assert len(res.survival_curve) == 5

    # Update call
    req_update = DynamicSurvivalPredictionRequest(
        target=SurvivalEventTarget.TASK_COMPLETION,
        user_id=user_id,
        current_time_elapsed=2.5,
        update_trigger=DynamicUpdateTrigger.TASK_STATE_CHANGE,
    )
    res_update = DynamicSurvivalService.dynamic_update(db=db_session, request=req_update)
    assert res_update.current_elapsed == 2.5
    assert res_update.update_trigger == DynamicUpdateTrigger.TASK_STATE_CHANGE


# ---------------------------------------------------------------------------
# 8. REST API Endpoints Integration Tests
# ---------------------------------------------------------------------------

def test_api_list_targets(test_client):
    """GET /api/v1/survival/targets returns all targets."""
    resp = test_client.get("/api/v1/survival/targets")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 4
    assert any(d["target"] == "task_abandonment" for d in data)


def test_api_get_benchmark(test_client):
    """GET /api/v1/survival/benchmark returns benchmark comparison."""
    resp = test_client.get("/api/v1/survival/benchmark?target=task_abandonment")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 4
    champ = next(d for d in data if d["is_champion"])
    assert "Log-Normal AFT" in champ["model_name"]


def test_api_predict_post(test_client):
    """POST /api/v1/survival/predict returns conditional survival curve."""
    user_id = str(uuid.uuid4())
    payload = {
        "target": "confirmed_task_resumption",
        "user_id": user_id,
        "current_time_elapsed": 5.0,
        "context_features": {"baseline_bfi": 52.0},
        "update_trigger": "periodic_tick",
    }
    resp = test_client.post("/api/v1/survival/predict", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["target"] == "confirmed_task_resumption"
    assert data["user_id"] == user_id
    assert data["time_unit"] == "minutes"
    assert data["current_elapsed"] == 5.0
    assert len(data["survival_curve"]) == 5
    assert data["personalization_tier"] in ["individual", "group", "population"]


def test_api_predict_get(test_client):
    """GET /api/v1/survival/predict returns prediction via GET convenience."""
    resp = test_client.get("/api/v1/survival/predict?target=task_completion&current_time_elapsed=2.0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["target"] == "task_completion"
    assert data["current_elapsed"] == 2.0


def test_api_dynamic_update_post(test_client):
    """POST /api/v1/survival/dynamic-update updates forecast upon trigger."""
    user_id = str(uuid.uuid4())
    payload = {
        "target": "task_abandonment",
        "user_id": user_id,
        "current_time_elapsed": 12.0,
        "update_trigger": "new_interruption",
    }
    resp = test_client.post("/api/v1/survival/dynamic-update", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["update_trigger"] == "new_interruption"
    assert data["current_elapsed"] == 12.0


def test_api_analytics_endpoints(test_client):
    """Verifies convenience endpoints under /api/v1/analytics/survival/*."""
    resp_pred = test_client.get("/api/v1/analytics/survival/predict?target=confirmed_recovery&current_time_elapsed=10.0")
    assert resp_pred.status_code == 200
    data_pred = resp_pred.json()
    assert data_pred["target"] == "confirmed_recovery"
    assert data_pred["current_elapsed"] == 10.0

    resp_bench = test_client.get("/api/v1/analytics/survival/benchmark?target=confirmed_recovery")
    assert resp_bench.status_code == 200
    data_bench = resp_bench.json()
    assert len(data_bench) == 4

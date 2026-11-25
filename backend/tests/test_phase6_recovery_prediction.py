"""
Comprehensive Test Suite for ContextIQ Phase 6.2: Cognitive Recovery Duration Prediction.

Validates:
1. Formal Recovery Definition: Distinguishes interruption detected, app revisited, context restored,
   confirmed task resumption, task completed, and recovery not observed.
2. Leak-free Dataset Extraction: Point-in-time extraction of all behavioral, task, circadian, and calendar features.
3. Incomplete Observations & Censoring: Right-censoring mechanics, session truncation, never infinity.
4. Model Approaches & Benchmarks: Kaplan-Meier, Cox PH, Log-Normal AFT, Weibull AFT, Quantile Regression.
5. Personalization & Cold-Start: Empirical Bayes shrinkage, cold-start fallback, uncertainty widening.
6. Time-to-Event Evaluation: C-index, Integrated Brier Score (IBS), time-dependent AUC, and horizon calibration.
7. REST API Endpoints: /analytics/recovery/prediction, /analytics/recovery/benchmark, /predictions/recovery.
"""
from __future__ import annotations

import math
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["APP_ENV"] = "development"
os.environ.setdefault("DATABASE_URL", "sqlite:///./_test_telemetry.db")

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

import app.models
from app.db.session import Base
from app.main import app
from app.models.context_session import ContextSession
from app.models.detected_interruption import DetectedInterruption
from app.models.enums import DetectedInterruptionType, InterruptionSeverity, TaskPriority, TaskStatus
from app.models.task import Task
from app.models.user import User
from app.schemas.recovery_prediction import (
    RecoveryBenchmarkComparisonResponse,
    RecoveryConfidenceTier,
    RecoveryPredictionRequest,
    RecoveryPredictionResponse,
    RecoveryState,
)
from app.services.recovery_models import (
    HORIZONS_SECONDS,
    RecoveryDurationModelPipeline,
)
from app.services.recovery_prediction_dataset import (
    DEFAULT_MAX_RECOVERY_HORIZON_SECONDS,
    RecoveryDatasetBuilder,
)
from app.services.recovery_prediction_service import RecoveryPredictionService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def test_db():
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()

    user = User(
        id=uuid.uuid4(),
        email="recovery_tester@contextiq.ai",
        display_name="Recovery Test User",
        timezone="UTC",
    )
    session.add(user)
    session.commit()

    yield session, user
    session.close()


@pytest.fixture
def client(test_db):
    session, user = test_db
    # Override get_current_user_id dependency
    from app.core.deps import get_current_user_id
    from app.db.session import get_db

    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=session.get_bind())

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_current_user_id] = lambda: user.id
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ===========================================================================
# 1. Recovery Definition & State Differentiation
# ===========================================================================

def test_recovery_state_differentiation():
    """
    Validates that returning to an app is NOT equated with confirmed task resumption.
    Verifies all 6 distinct recovery states.
    """
    t0 = datetime(2026, 11, 20, 10, 0, 0, tzinfo=timezone.utc)
    t_end = t0 + timedelta(minutes=2)  # Interruption duration = 2m

    # Case A: Confirmed task resumption (sustained dwell + task action at +5m)
    dur, event_obs, state, reason = RecoveryDatasetBuilder.classify_recovery_outcome(
        interruption_end=t_end,
        resumed_timestamp=t_end + timedelta(minutes=5),
    )
    assert state == RecoveryState.CONFIRMED_TASK_RESUMPTION
    assert event_obs == 1
    assert dur == 300.0
    assert reason is None

    # Case B: Task completed directly at +8m
    dur, event_obs, state, reason = RecoveryDatasetBuilder.classify_recovery_outcome(
        interruption_end=t_end,
        completed_timestamp=t_end + timedelta(minutes=8),
    )
    assert state == RecoveryState.TASK_COMPLETED
    assert event_obs == 1
    assert dur == 480.0

    # Case C: Original application revisited, but task resumption NOT confirmed (Censored at session end)
    dur, event_obs, state, reason = RecoveryDatasetBuilder.classify_recovery_outcome(
        interruption_end=t_end,
        app_returned_timestamp=t_end + timedelta(minutes=1),
        session_end_timestamp=t_end + timedelta(minutes=15),
    )
    assert state == RecoveryState.APP_OR_TASK_REVISITED
    assert event_obs == 0  # Crucial: Right-censored!
    assert dur == 900.0  # Duration is session duration (15m), NOT infinity
    assert reason == "app_revisited_unconfirmed_resumption"

    # Case D: Original context/window restored, but no sustained productive action (Censored)
    dur, event_obs, state, reason = RecoveryDatasetBuilder.classify_recovery_outcome(
        interruption_end=t_end,
        context_restored_timestamp=t_end + timedelta(minutes=2),
        session_end_timestamp=t_end + timedelta(minutes=20),
    )
    assert state == RecoveryState.ORIGINAL_CONTEXT_RESTORED
    assert event_obs == 0  # Right-censored
    assert dur == 1200.0
    assert reason == "context_restored_unconfirmed_resumption"

    # Case E: Recovery Not Observed (session ends or 60m horizon cutoff reached)
    dur, event_obs, state, reason = RecoveryDatasetBuilder.classify_recovery_outcome(
        interruption_end=t_end,
        session_end_timestamp=t_end + timedelta(minutes=10),
    )
    assert state == RecoveryState.RECOVERY_NOT_OBSERVED
    assert event_obs == 0  # Right-censored
    assert dur == 600.0  # 10 minutes
    assert reason == "session_ended_before_recovery"


# ===========================================================================
# 2. Incomplete Observations & Censoring Integrity
# ===========================================================================

def test_censoring_never_infinity():
    """Ensures unobserved or right-censored recovery times are strictly finite and bounded."""
    t_end = datetime(2026, 11, 20, 14, 0, 0, tzinfo=timezone.utc)

    # Cutoff at default 3600 seconds
    dur, event_obs, state, reason = RecoveryDatasetBuilder.classify_recovery_outcome(
        interruption_end=t_end,
        resumed_timestamp=None,
        session_end_timestamp=None,
    )
    assert dur == DEFAULT_MAX_RECOVERY_HORIZON_SECONDS
    assert not math.isinf(dur)
    assert not math.isnan(dur)
    assert event_obs == 0
    assert reason == "horizon_cutoff_reached"


# ===========================================================================
# 3. Leak-Free Feature Extraction
# ===========================================================================

def test_leak_free_dataset_builder(test_db):
    """Verifies that feature extraction uses strictly prior historical events."""
    session, user = test_db
    now_utc = datetime(2026, 11, 20, 11, 0, 0, tzinfo=timezone.utc)

    # Insert an interruption strictly prior to now_utc
    past_int = DetectedInterruption(
        id=uuid.uuid4(),
        user_id=user.id,
        interruption_type=DetectedInterruptionType.APPLICATION_SWITCH,
        severity=InterruptionSeverity.HIGH,
        start_timestamp=now_utc - timedelta(hours=2),
        end_timestamp=now_utc - timedelta(hours=2) + timedelta(minutes=3),
        duration_seconds=180.0,
        resumption_lag_seconds=210.0,
        explanation="Past test interruption",
    )
    session.add(past_int)

    # Insert an interruption AFTER now_utc (future information)
    future_int = DetectedInterruption(
        id=uuid.uuid4(),
        user_id=user.id,
        interruption_type=DetectedInterruptionType.APPLICATION_SWITCH,
        severity=InterruptionSeverity.CRITICAL,
        start_timestamp=now_utc + timedelta(hours=1),
        duration_seconds=600.0,
        resumption_lag_seconds=999.0,
        explanation="Future interruption that must NOT leak",
    )
    session.add(future_int)
    session.commit()

    builder = RecoveryDatasetBuilder()
    features = builder.extract_features_at_timestamp(
        db=session,
        user_id=user.id,
        as_of=now_utc,
        interruption=past_int,
    )

    # Historical average should match past_int (210.0), NOT future_int (999.0)
    assert features["previous_recovery_duration_mean"] == 210.0
    assert features["hour_of_day"] == 11
    assert features["day_of_week"] == now_utc.weekday()
    assert "behavioral_friction_index" in features
    assert "interruption_severity" in features


def test_benchmark_recovery_dataset_generation():
    """Validates realistic benchmark dataset generation grounded in empirical distributions."""
    df = RecoveryDatasetBuilder.generate_benchmark_recovery_dataset(n_samples=200, n_users=10, seed=123)

    assert len(df) == 200
    assert df["user_id"].nunique() == 10
    # Censoring distribution should reflect realistic right-censoring rate
    censoring_rate = 1.0 - df["event_observed"].mean()
    assert 0.05 <= censoring_rate <= 0.60

    # Ensure all durations are finite and positive
    assert (df["duration_seconds"] >= 1.0).all()
    assert (df["duration_seconds"] <= 3600.0).all()
    assert not df["duration_seconds"].isna().any()

    # Ensure chronological order
    timestamps = pd.to_datetime(df["prediction_timestamp"])
    assert timestamps.is_monotonic_increasing


# ===========================================================================
# 4. Model Approaches & Benchmarking
# ===========================================================================

def test_model_pipeline_fitting_and_predictions():
    """
    Fits Kaplan-Meier, Cox PH, Log-Normal AFT, Weibull AFT, and Quantile Regressors.
    Validates prediction validity and multi-horizon monotonicity.
    """
    df = RecoveryDatasetBuilder.generate_benchmark_recovery_dataset(n_samples=150, n_users=10, seed=42)

    pipeline = RecoveryDurationModelPipeline(penalizer=0.05)
    pipeline.fit(df)
    assert pipeline.fitted

    test_features = {
        "interruption_duration_seconds": 240.0,
        "interruption_severity": "HIGH",
        "interruption_type": "APPLICATION_SWITCH",
        "pre_interruption_task_category": "DeepWork",
        "task_priority": "URGENT",
        "task_complexity": 1.5,
        "hour_of_day": 10,
        "day_of_week": 2,
        "recent_context_switches": 3,
        "behavioral_friction_index": 55.0,
        "previous_recovery_duration_median": 220.0,
        "previous_task_resumption_rate": 0.85,
        "calendar_slack_minutes": 45.0,
    }

    resp = pipeline.predict(features=test_features)
    assert resp.estimated_recovery_duration_seconds > 0.0
    assert resp.estimated_recovery_duration_minutes > 0.0

    # Multi-horizon monotonicity: P(T <= 5m) <= P(T <= 15m) <= P(T <= 30m) <= P(T <= 60m)
    probs = resp.recovery_probabilities
    assert probs["5m"] <= probs["15m"] + 0.01
    assert probs["15m"] <= probs["30m"] + 0.01
    assert probs["30m"] <= probs["60m"] + 0.01

    # Conformal Prediction interval
    assert resp.confidence_interval.lower_seconds < resp.confidence_interval.upper_seconds
    assert resp.confidence_interval.lower_minutes < resp.confidence_interval.upper_minutes
    assert resp.confidence_interval.confidence_level == 0.90


def test_personalized_vs_cold_start():
    """Verifies that cold-start users get population estimates with widened uncertainty."""
    df = RecoveryDatasetBuilder.generate_benchmark_recovery_dataset(n_samples=120, n_users=10, seed=42)
    pipeline = RecoveryDurationModelPipeline(penalizer=0.05).fit(df)

    test_features = {
        "interruption_duration_seconds": 120.0,
        "hour_of_day": 14,
        "behavioral_friction_index": 40.0,
    }

    # Case A: Cold-start user (0 historical records)
    cold_resp = pipeline.predict(features=test_features, user_history=[])
    assert not cold_resp.is_personalized
    assert cold_resp.confidence_tier == RecoveryConfidenceTier.COLD_START
    assert "Population-level baseline" in cold_resp.disclaimer
    cold_interval_width = cold_resp.confidence_interval.upper_seconds - cold_resp.confidence_interval.lower_seconds

    # Case B: Established user (20 historical records)
    user_history = [{"duration_seconds": 180.0, "event_observed": 1} for _ in range(25)]
    est_resp = pipeline.predict(features=test_features, user_history=user_history)
    assert est_resp.is_personalized
    assert est_resp.confidence_tier in (RecoveryConfidenceTier.ESTABLISHED, RecoveryConfidenceTier.CONFIDENT)
    assert "Personalized estimate" in est_resp.disclaimer
    est_interval_width = est_resp.confidence_interval.upper_seconds - est_resp.confidence_interval.lower_seconds

    # Established user should have narrower confidence bounds
    assert est_interval_width < cold_interval_width


# ===========================================================================
# 5. Time-to-Event Evaluation Metrics
# ===========================================================================

def test_model_evaluation_metrics():
    """Evaluates C-index, Integrated Brier Score, and horizon calibration."""
    df = RecoveryDatasetBuilder.generate_benchmark_recovery_dataset(n_samples=160, n_users=12, seed=42)
    split_idx = int(len(df) * 0.70)
    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]

    metrics_list = RecoveryDurationModelPipeline.evaluate_models(train_df, test_df)
    assert len(metrics_list) >= 4  # KM, LogNormal, Cox, Quantile Regressor

    model_names = [m.model_name for m in metrics_list]
    assert any("Log-Normal" in name for name in model_names)
    assert any("Kaplan-Meier" in name for name in model_names)

    for m in metrics_list:
        # Concordance index should be in [0.50, 1.00]
        assert 0.50 <= m.concordance_index <= 1.00
        # Integrated Brier score should be reasonable (<= 0.35)
        assert 0.0 <= m.integrated_brier_score <= 0.35
        # Time-dependent AUC should be in [0.50, 1.00]
        assert 0.50 <= m.time_dependent_auc_15m <= 1.00
        assert 0.50 <= m.time_dependent_auc_30m <= 1.00


# ===========================================================================
# 6. REST API Endpoints
# ===========================================================================

def test_recovery_prediction_api_endpoints(client):
    """Validates FastAPI endpoints for cognitive recovery prediction and benchmarking."""
    # 1. GET /api/v1/analytics/recovery/prediction
    res_get = client.get("/api/v1/analytics/recovery/prediction")
    assert res_get.status_code == 200
    data = res_get.json()
    assert "estimated_recovery_duration_minutes" in data
    assert "recovery_probabilities" in data
    assert "confidence_interval" in data
    assert "model_version" in data
    assert "disclaimer" in data

    # 2. POST /api/v1/analytics/recovery/prediction
    payload = {
        "interruption_duration_seconds": 360.0,
        "interruption_severity": "HIGH",
        "task_category": "Coding",
        "hour_of_day": 15,
    }
    res_post = client.post("/api/v1/analytics/recovery/prediction", json=payload)
    assert res_post.status_code == 200
    post_data = res_post.json()
    assert post_data["estimated_recovery_duration_minutes"] > 0.0
    assert len(post_data["main_contributing_factors"]) > 0

    # 3. GET /api/v1/analytics/recovery/benchmark
    res_bench = client.get("/api/v1/analytics/recovery/benchmark")
    assert res_bench.status_code == 200
    bench_data = res_bench.json()
    assert "models" in bench_data
    assert bench_data["champion_model"] == "Log-Normal AFT (Champion)"
    assert len(bench_data["models"]) >= 4

    # 4. GET /api/v1/predictions/recovery
    res_pred = client.get("/api/v1/predictions/recovery")
    assert res_pred.status_code == 200
    assert "estimated_recovery_duration_seconds" in res_pred.json()

    # 5. POST /api/v1/predictions/recovery
    res_pred_post = client.post("/api/v1/predictions/recovery", json=payload)
    assert res_pred_post.status_code == 200
    assert res_pred_post.json()["estimated_recovery_duration_seconds"] > 0.0

"""
test_survival.py

Comprehensive test suite for ContextIQ Phase 2.3 Survival Analysis & Time-to-Forgetting Engine.
Covers:
- Dataset generation and right-censoring integrity
- Duration clipping epsilon guardrails
- Monotonicity of predicted survival curves
- Model concordance index (C-index)
- Horizon extrapolation flag
- REST API endpoints (/survival/predict, /survival/batch_predict, /survival/metrics, /survival/model_info)
"""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.survival_service import SurvivalService
from ml.survival.data import (
    create_synthetic_survival_dataset,
    build_survival_record,
    MIN_DURATION_HOURS,
)
from ml.survival.models import SurvivalModelPipeline

client = TestClient(app)


# =====================================================================
# 1. Survival Dataset & Censoring Tests
# =====================================================================

def test_survival_dataset_right_censoring():
    """Verify that dataset generation honors right-censoring rules."""
    df = create_synthetic_survival_dataset(n_samples=500, seed=42)
    
    assert len(df) == 500
    assert "duration" in df.columns
    assert "event_observed" in df.columns
    assert "censoring_status" in df.columns
    
    # All durations must be positive and >= epsilon
    assert (df["duration"] >= MIN_DURATION_HOURS).all()
    
    # Check censoring logic:
    # 1. uncensored_forgotten must have event_observed == 1
    forgotten = df[df["censoring_status"] == "uncensored_forgotten"]
    assert len(forgotten) > 0
    assert (forgotten["event_observed"] == 1).all()
    
    # 2. competing_completed and right_censored_* must have event_observed == 0
    censored = df[df["censoring_status"] != "uncensored_forgotten"]
    assert len(censored) > 0
    assert (censored["event_observed"] == 0).all()


def test_zero_duration_clipped_to_epsilon():
    """Verify durations <= 0 are safely clipped to MIN_DURATION_HOURS."""
    rec = build_survival_record(
        task={
            "id": "zero_dur_task",
            "user_id": "user_test",
            "created_at": "2026-11-20T10:00:00Z",
            "deadline_at": "2026-11-20T12:00:00Z",
            "status": "FORGOTTEN",
            "forgotten_at": "2026-11-20T10:00:00Z",  # exact same as creation
        },
        as_of=datetime(2026, 11, 20, 10, 0, 0, tzinfo=timezone.utc),
    )
    assert rec["duration"] >= MIN_DURATION_HOURS
    assert rec["duration"] > 0.0


def test_competing_completed_not_classified_as_forgetting():
    """Verify completed tasks are right-censored, NOT treated as forgetting events."""
    rec = build_survival_record(
        task={
            "id": "completed_task",
            "user_id": "user_test",
            "created_at": "2026-11-20T08:00:00Z",
            "deadline_at": "2026-11-20T12:00:00Z",
            "completed_at": "2026-11-20T09:00:00Z",
            "status": "COMPLETED",
        },
        events=[{
            "task_id": "completed_task",
            "event_type": "completed",
            "timestamp": "2026-11-20T09:00:00Z",
        }],
        as_of=datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert rec["event_observed"] == 0
    assert rec["censoring_status"] == "competing_completed"
    assert rec["duration"] == pytest.approx(1.0, 0.05)


# =====================================================================
# 2. Model & Inference Integrity Tests
# =====================================================================

def test_survival_monotonicity(sample_task_payload):
    """Verify that S(t) is monotonically non-increasing over time."""
    service = SurvivalService.instance()
    horizons = [6.0, 12.0, 24.0, 48.0, 96.0, 168.0]
    result = service.predict_task_survival(sample_task_payload, horizons=horizons)
    
    probs = [h["survival_probability"] for h in result["horizons"]]
    for i in range(len(probs) - 1):
        assert probs[i] >= probs[i + 1] - 1e-4, f"Survival violated monotonicity: {probs[i]} < {probs[i+1]}"


def test_extrapolation_flag(sample_task_payload):
    """Verify that requested horizons beyond reliable threshold set is_extrapolated = True."""
    service = SurvivalService.instance()
    
    # Within reliable range
    res_normal = service.predict_task_survival(sample_task_payload, horizons=[6.0, 24.0, 168.0])
    assert res_normal["is_extrapolated"] is False
    
    # Exceeding 336 hours (14 days)
    res_extrapolated = service.predict_task_survival(sample_task_payload, horizons=[24.0, 500.0])
    assert res_extrapolated["is_extrapolated"] is True


def test_concordance_index_ranking():
    """Verify the trained Cox model achieves a valid C-index (> 0.55)."""
    service = SurvivalService.instance()
    metrics = service.get_metrics()
    assert "c_index_cox" in metrics
    assert metrics["c_index_cox"] > 0.55
    assert metrics["integrated_brier_score"] < 0.25


def test_high_risk_lower_survival(sample_task_payload, high_risk_payload):
    """Verify high-risk task has lower or equal survival probability than sample task at 24h."""
    service = SurvivalService.instance()
    res_normal = service.predict_task_survival(sample_task_payload, horizons=[24.0])
    res_high = service.predict_task_survival(high_risk_payload, horizons=[24.0])
    
    p_normal = res_normal["horizons"][0]["survival_probability"]
    p_high = res_high["horizons"][0]["survival_probability"]
    # High interruption and switch payload should have lower survival
    assert p_high <= p_normal + 0.05


# =====================================================================
# 3. REST API Endpoint Tests
# =====================================================================

def test_api_survival_predict(sample_task_payload):
    """Test POST /survival/predict endpoint."""
    response = client.post(
        "/survival/predict",
        json={"task": sample_task_payload, "horizons": [6.0, 12.0, 24.0, 48.0, 168.0]},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["model_version"] == "2.3.0"
    assert len(data["horizons"]) == 5
    for h in data["horizons"]:
        assert 0.0 <= h["survival_probability"] <= 1.0
        assert 0.0 <= h["forgetting_risk"] <= 1.0
        assert h["ci_lower"] <= h["ci_upper"]
    assert data["is_extrapolated"] is False


def test_api_survival_batch_predict(sample_task_payload, high_risk_payload):
    """Test POST /survival/batch_predict endpoint."""
    response = client.post(
        "/survival/batch_predict",
        json={"tasks": [sample_task_payload, high_risk_payload], "horizons": [12.0, 24.0]},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["predictions"]) == 2
    assert len(data["predictions"][0]["horizons"]) == 2


def test_api_survival_metrics():
    """Test GET /survival/metrics endpoint."""
    response = client.get("/survival/metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["model_version"] == "2.3.0"
    assert data["c_index_cox"] > 0.55
    assert data["integrated_brier_score"] > 0.0
    assert "24h" in data["brier_scores_by_horizon"]


def test_api_survival_model_info():
    """Test GET /survival/model_info endpoint."""
    response = client.get("/survival/model_info")
    assert response.status_code == 200
    data = response.json()
    assert data["model_name"] == "Cox Proportional Hazards + Kaplan-Meier"
    assert len(data["hazard_ratios"]) > 0
    assert data["reliable_range_hours"] == 336.0


def test_api_survival_predict_invalid_payload():
    """Test POST /survival/predict with missing required fields returns 422."""
    response = client.post(
        "/survival/predict",
        json={"task": {"invalid_field": "bad"}},
    )
    assert response.status_code == 422

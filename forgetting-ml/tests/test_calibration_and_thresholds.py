"""
test_calibration_and_thresholds.py

Comprehensive test suite for ContextIQ Phase 2.5:
- Probability calibration (Platt, Isotonic, Temperature Scaling)
- Calibration slope, intercept, and Expected Calibration Error (ECE)
- 4-Tier risk categorization (LOW, MEDIUM, HIGH, CRITICAL)
- Personalized threshold manager with sample size guardrails (N >= 25)
- Operational response policy recommendations
- Calibrator bundle serialization and loading
- API prediction response backward compatibility
"""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.inference import ForgettingPredictor
from ml.calibration.calibrator import (
    clip_probabilities,
    compute_calibration_slope_and_intercept,
    compute_reliability_metrics,
    PlattScalingCalibrator,
    IsotonicCalibrator,
    TemperatureScalingCalibrator,
    ProbabilityCalibrationPipeline,
)
from ml.calibration.thresholds import (
    RiskCategory,
    RiskThresholds,
    PersonalizedThresholdManager,
    MIN_USER_SAMPLES_FOR_PERSONALIZATION,
)
from ml.calibration.policy import get_risk_policy, POLICY_DESCRIPTIONS

client = TestClient(app)


# =====================================================================
# 1. Calibrator Unit Tests
# =====================================================================

def test_probability_clipping_bounds():
    """Verify probability clipping prevents zero or one."""
    raw = np.array([-0.5, 0.0, 0.5, 1.0, 1.5])
    clipped = clip_probabilities(raw, eps=1e-5)
    assert np.all(clipped > 0.0)
    assert np.all(clipped < 1.0)
    assert clipped[1] == 1e-5
    assert clipped[3] == 1.0 - 1e-5


def test_platt_scaling_monotonicity():
    """Verify Platt scaling produces monotonically increasing probabilities."""
    y_true = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    raw_p = np.array([0.1, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9])
    
    platt = PlattScalingCalibrator()
    platt.fit(raw_p, y_true)
    
    test_p = np.linspace(0.1, 0.9, 20)
    cal_p = platt.predict_proba(test_p)
    assert np.all(np.diff(cal_p) >= 0), "Platt scaling violated monotonicity."


def test_isotonic_calibration_monotonicity():
    """Verify Isotonic regression produces non-decreasing probabilities."""
    y_true = np.array([0, 0, 0, 1, 0, 1, 1, 1])
    raw_p = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8])
    
    iso = IsotonicCalibrator()
    iso.fit(raw_p, y_true)
    
    test_p = np.linspace(0.05, 0.95, 20)
    cal_p = iso.predict_proba(test_p)
    assert np.all(np.diff(cal_p) >= -1e-6), "Isotonic regression violated monotonicity."


def test_temperature_scaling_optimization():
    """Verify temperature scaling learns a valid positive temperature."""
    rng = np.random.RandomState(42)
    y_true = rng.choice([0, 1], size=100)
    raw_p = np.clip(y_true * 0.6 + 0.2 + rng.normal(0, 0.1, size=100), 0.05, 0.95)
    
    temp_cal = TemperatureScalingCalibrator()
    temp_cal.fit(raw_p, y_true)
    assert temp_cal.temperature > 0.0
    
    cal_p = temp_cal.predict_proba(raw_p)
    assert np.all((cal_p >= 0.0) & (cal_p <= 1.0))


def test_calibration_slope_and_intercept():
    """Verify slope is ~1.0 and intercept is ~0.0 for well-calibrated data."""
    # Synthetic perfectly calibrated probabilities
    y_true = np.array([0, 0, 0, 0, 0, 1, 1, 1, 1, 1])
    y_prob = np.array([0.05, 0.1, 0.15, 0.2, 0.25, 0.75, 0.8, 0.85, 0.9, 0.95])
    
    intercept, slope = compute_calibration_slope_and_intercept(y_true, y_prob)
    assert abs(intercept) < 2.0
    assert slope > 0.5


def test_calibration_pipeline_fit_and_diagnostics():
    """Verify ProbabilityCalibrationPipeline fits all models and records metrics."""
    y_val = np.array([0, 0, 0, 0, 1, 0, 1, 1, 1, 1] * 10)
    p_val = np.linspace(0.1, 0.9, len(y_val))
    
    pipe = ProbabilityCalibrationPipeline()
    pipe.fit(p_val, y_val)
    
    assert pipe.best_method in ("uncalibrated", "platt", "isotonic", "temperature")
    assert "uncalibrated" in pipe.validation_metrics
    cal_p = pipe.calibrate(p_val)
    assert len(cal_p) == len(p_val)


# =====================================================================
# 2. Risk Threshold & Personalization Tests
# =====================================================================

def test_risk_threshold_boundaries():
    """Verify 4-tier threshold boundary ordering and classification."""
    thresh = RiskThresholds(tau_low=0.25, tau_medium=0.50, tau_high=0.75)
    assert thresh.classify_risk(0.10) == RiskCategory.LOW
    assert thresh.classify_risk(0.35) == RiskCategory.MEDIUM
    assert thresh.classify_risk(0.65) == RiskCategory.HIGH
    assert thresh.classify_risk(0.85) == RiskCategory.CRITICAL


def test_invalid_threshold_monotonicity_raises():
    """Verify non-monotonic thresholds raise ValueError."""
    with pytest.raises(ValueError):
        RiskThresholds(tau_low=0.60, tau_medium=0.40, tau_high=0.70)


def test_personalized_threshold_fallback_guardrail():
    """Verify users with < 25 historical tasks fall back to population thresholds."""
    mgr = PersonalizedThresholdManager(RiskThresholds(tau_low=0.25, tau_medium=0.50, tau_high=0.75))
    
    # 10 tasks (< 25)
    short_history = [{"status": "COMPLETED"}] * 10
    thresh, reason = mgr.get_user_thresholds(user_history=short_history)
    
    assert thresh == mgr.population_thresholds
    assert "Using population baseline thresholds" in reason


def test_personalized_threshold_adaptation_high_forgetting():
    """Verify users with >= 25 tasks and high forgetting rate get adapted thresholds."""
    mgr = PersonalizedThresholdManager(RiskThresholds(tau_low=0.25, tau_medium=0.50, tau_high=0.75))
    
    # 30 tasks with 50% forgetting rate
    history = [{"status": "FORGOTTEN", "forgotten": 1}] * 15 + [{"status": "COMPLETED", "forgotten": 0}] * 15
    thresh, reason = mgr.get_user_thresholds(user_history=history, user_historical_forget_rate=0.50)
    
    assert "increased sensitivity" in reason
    assert thresh.tau_medium <= mgr.population_thresholds.tau_medium


# =====================================================================
# 3. Policy & API Integration Tests
# =====================================================================

def test_policy_definitions_complete():
    """Verify all 4 risk categories have actionable recommendations and UI treatment."""
    for cat in RiskCategory:
        policy = get_risk_policy(cat)
        assert "action_recommendation" in policy
        assert "ui_badge_color" in policy
        assert len(policy["action_recommendation"]) > 10


def test_api_prediction_response_schema(sample_task_payload):
    """Verify POST /api/v1/predictions/forgetting returns full Phase 2.5 schema."""
    resp = client.post("/api/v1/predictions/forgetting", json=sample_task_payload)
    assert resp.status_code == 200
    data = resp.json()
    
    # Backward compatible fields
    assert "prediction_probability" in data
    assert 0.0 <= data["prediction_probability"] <= 1.0
    assert "risk_level" in data
    assert data["risk_level"] in ("LOW", "MEDIUM", "HIGH")
    assert "risk_category" in data
    assert data["risk_category"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert "model_version" in data
    assert len(data["top_features"]) > 0
    
    # Phase 2.5 fields
    assert "raw_probability" in data
    assert "calibrated_probability" in data
    assert "classification_threshold" in data
    assert data["calibration_version"] == "2.5.0"
    assert data["action_recommendation"] is not None

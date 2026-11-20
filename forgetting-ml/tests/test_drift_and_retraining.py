"""
test_drift_and_retraining.py

Comprehensive test suite for ContextIQ Phase 2.8:
- Statistical drift detection (PSI, KS-test, JS-divergence, missingness tracking)
- Stable vs gradual vs sudden drift simulations
- Baseline reference data profiling and production observation buffer
- False-positive mitigation via compound retraining triggers
- 10-step controlled retraining pipeline with Champion vs Challenger gate
- Mandatory human approval gate (candidate not promoted automatically)
- Model rollback, integrity checking, and deployment ledger auditing
- FastAPI monitoring API endpoints validation
"""

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app
from ml.monitoring.drift_detector import (
    DriftDetector,
    compute_js_divergence,
    compute_ks_test,
    compute_psi,
)
from ml.monitoring.reference_store import ReferenceStore
from ml.monitoring.retraining_pipeline import ControlledRetrainingPipeline
from ml.monitoring.rollback import ModelRollbackManager
from ml.monitoring.triggers import RetrainingTriggerPolicy

client = TestClient(app)


# =====================================================================
# 1. Statistical Drift Function Unit Tests
# =====================================================================

def test_psi_stable_distribution():
    """Verify PSI is near 0.0 when baseline and target distributions match."""
    np.random.seed(42)
    baseline = np.random.normal(loc=10.0, scale=2.0, size=2000)
    target = np.random.normal(loc=10.0, scale=2.0, size=2000)

    psi = compute_psi(baseline, target)
    assert psi < 0.05, f"Expected stable PSI < 0.05, got {psi}"


def test_psi_sudden_distribution_drift():
    """Verify PSI exceeds 0.20 when mean shifts substantially."""
    np.random.seed(42)
    baseline = np.random.normal(loc=10.0, scale=2.0, size=2000)
    target = np.random.normal(loc=14.0, scale=2.0, size=2000)  # +2 std dev shift

    psi = compute_psi(baseline, target)
    assert psi >= 0.20, f"Expected drift PSI >= 0.20, got {psi}"


def test_ks_test_detects_numerical_shift():
    """Verify Kolmogorov-Smirnov test identifies distribution differences."""
    np.random.seed(42)
    b = np.random.exponential(scale=2.0, size=1000)
    t = np.random.exponential(scale=5.0, size=1000)

    stat, pval = compute_ks_test(b, t)
    assert pval < 0.001
    assert stat > 0.20


def test_js_divergence_categorical():
    """Verify Jensen-Shannon divergence detects category frequency shifts."""
    b_dist = {"Work": 0.50, "Personal": 0.30, "Academic": 0.20}
    t_dist = {"Work": 0.10, "Personal": 0.20, "Academic": 0.70}  # Shifted

    jsd = compute_js_divergence(b_dist, t_dist)
    assert jsd > 0.15, f"Expected JSD > 0.15 for shifted categories, got {jsd}"


def test_missingness_rate_drift():
    """Verify missingness detector identifies spikes in NaN values."""
    s1 = pd.Series([1.0, 2.0, 3.0, 4.0] * 100)
    s2 = pd.Series([1.0, np.nan, np.nan, 4.0] * 100)  # 50% missing

    res = DriftDetector.evaluate_missingness("test_feat", s1, s2, threshold=0.05)
    assert res["missingness_drift"] is True
    assert res["missing_delta"] >= 0.40


# =====================================================================
# 2. Reference Store & Profile Management Tests
# =====================================================================

def test_reference_profile_lifecycle(tmp_path):
    """Verify creating, saving, and reloading baseline reference profile."""
    profile_file = tmp_path / "test_profile.json"
    buffer_file = tmp_path / "test_buffer.jsonl"
    store = ReferenceStore(profile_path=profile_file, buffer_path=buffer_file)

    df = pd.DataFrame({
        "deadline_distance_hours": [6.0, 12.0, 24.0, 48.0] * 25,
        "task_category": ["Work", "Personal", "Health", "Household"] * 25,
    })

    prof = store.build_and_save_profile(df, model_name="test_model", model_version="1.0.0")
    assert profile_file.exists()
    assert "numeric_features" in prof
    assert "categorical_features" in prof

    reloaded = store.load_profile()
    assert reloaded["model_version"] == "1.0.0"


def test_production_observation_buffer(tmp_path):
    """Verify recording and querying production observation buffer."""
    buf_file = tmp_path / "test_buffer.jsonl"
    store = ReferenceStore(buffer_path=buf_file)

    task = {"task_id": "T1", "deadline_distance_hours": 8.0, "interruptions_today": 3}
    store.append_observation(task, predicted_prob=0.35, risk_category="MEDIUM")

    df_win = store.get_production_window()
    assert len(df_win) == 1
    assert df_win.iloc[0]["task_id"] == "T1"
    assert df_win.iloc[0]["predicted_prob"] == 0.35

    store.clear_buffer()
    assert not buf_file.exists()


# =====================================================================
# 3. Compound Triggers & False-Alarm Prevention Tests
# =====================================================================

def test_single_feature_drift_does_not_trigger_retraining():
    """Verify single isolated feature drift alert generates WARNING but NO retraining trigger."""
    policy = RetrainingTriggerPolicy(min_drifted_features_for_trigger=2)

    feature_drift = {
        "drifted_features_count": 1,  # Only 1 feature drifted
        "moderate_features_count": 0,
    }

    decision = policy.evaluate(feature_drift_result=feature_drift)
    assert decision["retraining_recommended"] is False
    assert "MONITOR" in decision["recommended_action"]


def test_compound_drift_triggers_retraining():
    """Verify dual feature drift + prediction drift triggers retraining recommendation."""
    policy = RetrainingTriggerPolicy(min_drifted_features_for_trigger=2)

    feature_drift = {"drifted_features_count": 3, "moderate_features_count": 1}
    pred_drift = {"probability_psi": 0.25, "category_js_divergence": 0.18}

    decision = policy.evaluate(
        feature_drift_result=feature_drift,
        prediction_drift_result=pred_drift,
    )
    assert decision["retraining_recommended"] is True
    assert decision["urgency"] == "HIGH"


def test_concept_drift_triggers_immediate_retraining():
    """Verify ground-truth performance degradation immediately recommends retraining."""
    policy = RetrainingTriggerPolicy()

    concept_drift = {
        "concept_drift_detected": True,
        "pr_auc_relative_drop": 0.15,
    }

    decision = policy.evaluate(concept_drift_result=concept_drift)
    assert decision["retraining_recommended"] is True
    assert "RETRAIN_IMMEDIATE" in decision["recommended_action"]


# =====================================================================
# 4. Controlled Retraining Pipeline & Human Approval Gate Tests
# =====================================================================

def test_retraining_pipeline_creates_pending_approval_candidate(tmp_path):
    """Verify retraining produces challenger artifact and stops at Human Approval Gate."""
    challenger_path = tmp_path / "test_challenger.joblib"
    status_path = tmp_path / "test_retraining_status.json"

    pipeline = ControlledRetrainingPipeline(
        challenger_path=challenger_path,
        status_path=status_path,
    )

    result = pipeline.run_candidate_pipeline(new_version="1.2.0")

    assert result["status"] == "PENDING_APPROVAL"
    assert result["candidate_version"] == "1.2.0"
    assert challenger_path.exists()
    assert status_path.exists()
    assert "champion_metrics" in result
    assert "challenger_metrics" in result


def test_human_approval_gate_promotion(tmp_path):
    """Verify candidate is only deployed when explicitly approved by human operator."""
    champion_path = tmp_path / "active_model.joblib"
    challenger_path = tmp_path / "test_challenger.joblib"
    status_path = tmp_path / "test_retraining_status.json"

    # Create dummy initial champion
    dummy_bundle = {
        "model": None, "raw_model": None, "preprocessor": None,
        "model_name": "logreg", "model_version": "1.0.0",
        "threshold": 0.5, "calibrated": True,
        "categorical_features": [], "numeric_features": [],
        "feature_names_transformed": [],
    }
    import joblib
    joblib.dump(dummy_bundle, champion_path)

    pipeline = ControlledRetrainingPipeline(
        champion_path=champion_path,
        challenger_path=challenger_path,
        status_path=status_path,
    )

    # Run pipeline to generate candidate
    pipeline.run_candidate_pipeline(new_version="1.2.0")

    # Before approval: active model remains v1.0.0
    active_before = joblib.load(champion_path)
    assert active_before["model_version"] == "1.0.0"

    # Execute explicit human approval
    deploy_res = pipeline.approve_and_deploy_challenger(approved_by="Lead Data Scientist")
    assert deploy_res["status"] == "PROMOTED_AND_DEPLOYED"
    assert deploy_res["deployed_version"] == "1.2.0"

    # After approval: active model is promoted to v1.2.0
    active_after = joblib.load(champion_path)
    assert active_after["model_version"] == "1.2.0"


# =====================================================================
# 5. Model Rollback & Ledger Tests
# =====================================================================

def test_model_rollback_restores_previous_version(tmp_path):
    """Verify model rollback restores archived previous version and updates ledger."""
    active_path = tmp_path / "active_bundle.joblib"
    archive_dir = tmp_path / "archive"
    ledger_path = tmp_path / "ledger.json"

    import joblib
    mgr = ModelRollbackManager(
        active_bundle_path=active_path,
        archive_dir=archive_dir,
        ledger_path=ledger_path,
    )

    # 1. Create v1.0.0 active bundle and archive it
    v1_bundle = {
        "model": "v1_obj", "raw_model": "v1_obj", "preprocessor": "pre",
        "model_name": "logreg", "model_version": "1.0.0",
        "threshold": 0.5, "calibrated": True,
        "categorical_features": [], "numeric_features": [],
        "feature_names_transformed": [],
    }
    joblib.dump(v1_bundle, active_path)
    mgr.archive_current_model(version_label="1.0.0")

    # 2. Promote v2.0.0 to active
    v2_bundle = dict(v1_bundle)
    v2_bundle["model_version"] = "2.0.0"
    joblib.dump(v2_bundle, active_path)

    # Verify active is v2.0.0
    assert joblib.load(active_path)["model_version"] == "2.0.0"

    # 3. Trigger Rollback
    rollback_res = mgr.rollback(approved_by="Ops Lead", reason="Spike in FPR")
    assert rollback_res["status"] == "ROLLBACK_SUCCESSFUL"
    assert rollback_res["restored_version"] == "1.0.0"

    # 4. Verify restored active bundle is v1.0.0
    assert joblib.load(active_path)["model_version"] == "1.0.0"

    # 5. Verify ledger entry
    history = mgr.get_deployment_history()
    assert len(history) >= 1
    assert history[0]["event_type"] == "ROLLBACK"


# =====================================================================
# 6. API Endpoints Tests
# =====================================================================

def test_monitoring_status_endpoint():
    """Verify GET /api/v1/monitoring/status."""
    resp = client.get("/api/v1/monitoring/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "model_name" in data
    assert "model_version" in data
    assert data["status"] == "HEALTHY"


def test_monitoring_drift_report_endpoint():
    """Verify GET /api/v1/monitoring/drift/report."""
    resp = client.get("/api/v1/monitoring/drift/report")
    assert resp.status_code == 200
    data = resp.json()
    assert "overall_status" in data
    assert "feature_details" in data
    assert "retraining_trigger_recommendation" in data


def test_monitoring_history_endpoint():
    """Verify GET /api/v1/monitoring/history."""
    resp = client.get("/api/v1/monitoring/history")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_events" in data
    assert "history" in data

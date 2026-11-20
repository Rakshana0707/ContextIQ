"""
test_benchmark_models.py

Unit and integration tests for ContextIQ Phase 2.4:
- Candidate model instantiation (all 7 models)
- Pipeline construction and fit reproducibility
- Model serialization and loading consistency
- Missing feature handling and imputation
- Inference latency measurement
- Experiment registry persistence and schema compliance
- Classification threshold optimization
"""

import io
import tempfile
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import pytest

from ml.features.feature_spec import ALL_RAW_FEATURES, DEFAULT_SPEC
from ml.training.benchmark_models import (
    MODEL_NAMES,
    create_model_instance,
    build_candidate_pipeline,
    measure_inference_latency,
    measure_model_size_kb,
)
from ml.training.hpo import (
    sample_parameter_candidates,
    find_optimal_threshold,
)
from ml.experiments.registry import (
    ExperimentRegistry,
    compute_expected_calibration_error,
)


@pytest.fixture(scope="module")
def sample_training_data():
    """Generates synthetic minimal data for pipeline fit/predict tests."""
    rng = np.random.RandomState(42)
    n = 60
    data = {
        "task_category": rng.choice(["Work", "Academic", "Personal"], size=n),
        "priority": rng.choice(["LOW", "MEDIUM", "HIGH"], size=n),
        "location": rng.choice(["Home", "Office", "Campus"], size=n),
        "weekday": rng.randint(0, 7, size=n),
        "hour": rng.randint(8, 20, size=n),
        "deadline_distance_hours": rng.uniform(1.0, 48.0, size=n),
        "previous_completion_count": rng.randint(0, 50, size=n),
        "previous_forgetting_count": rng.randint(0, 20, size=n),
        "historical_completion_rate": rng.uniform(0.1, 0.9, size=n),
        "historical_forgetting_rate": rng.uniform(0.05, 0.6, size=n),
        "task_frequency": rng.uniform(0.01, 0.5, size=n),
        "tasks_today": rng.randint(1, 10, size=n),
        "interruptions_today": rng.randint(0, 8, size=n),
        "recent_context_switches": rng.randint(0, 10, size=n),
        "avg_interruption_duration": rng.uniform(1.0, 30.0, size=n),
        "avg_session_duration": rng.uniform(5.0, 60.0, size=n),
        "forgotten": rng.choice([0, 1], size=n, p=[0.7, 0.3]),
    }
    return pd.DataFrame(data)


# =====================================================================
# 1. Model Creation & Pipeline Construction Tests
# =====================================================================

@pytest.mark.parametrize("model_name", MODEL_NAMES)
def test_all_models_instantiate_and_fit(model_name, sample_training_data):
    """Verify each candidate architecture instantiates and fits successfully."""
    X = sample_training_data[[c for c in ALL_RAW_FEATURES if c in sample_training_data.columns]]
    y = sample_training_data["forgotten"]

    # Use small iterations/estimators for test speed
    custom_params = {}
    if model_name in ("random_forest", "xgboost", "lightgbm"):
        custom_params["n_estimators"] = 5
    elif model_name == "catboost":
        custom_params["iterations"] = 5
    elif model_name == "hist_gbm":
        custom_params["max_iter"] = 5
    elif model_name == "ebm":
        custom_params["outer_bags"] = 2
        custom_params["inner_bags"] = 0

    pipe = build_candidate_pipeline(model_name, custom_params=custom_params)
    pipe.fit(X, y)
    probs = pipe.predict_proba(X)[:, 1]

    assert len(probs) == len(X)
    assert np.all((probs >= 0.0) & (probs <= 1.0))


# =====================================================================
# 2. Reproducibility & Determinism Tests
# =====================================================================

def test_pipeline_reproducibility(sample_training_data):
    """Verify that identical seeds yield identical probability predictions."""
    X = sample_training_data[[c for c in ALL_RAW_FEATURES if c in sample_training_data.columns]]
    y = sample_training_data["forgotten"]

    pipe1 = build_candidate_pipeline("lightgbm", custom_params={"n_estimators": 10, "random_state": 42})
    pipe1.fit(X, y)
    probs1 = pipe1.predict_proba(X)[:, 1]

    pipe2 = build_candidate_pipeline("lightgbm", custom_params={"n_estimators": 10, "random_state": 42})
    pipe2.fit(X, y)
    probs2 = pipe2.predict_proba(X)[:, 1]

    np.testing.assert_allclose(probs1, probs2, rtol=1e-5, atol=1e-5)


# =====================================================================
# 3. Serialization & Loading Tests
# =====================================================================

def test_model_serialization_and_reloading(sample_training_data):
    """Verify models can be serialized to disk/bytes and reloaded with identical predictions."""
    X = sample_training_data[[c for c in ALL_RAW_FEATURES if c in sample_training_data.columns]]
    y = sample_training_data["forgotten"]

    pipe = build_candidate_pipeline("hist_gbm", custom_params={"max_iter": 10, "random_state": 42})
    pipe.fit(X, y)
    orig_probs = pipe.predict_proba(X)[:, 1]

    buf = io.BytesIO()
    joblib.dump(pipe, buf)
    buf.seek(0)
    loaded_pipe = joblib.load(buf)
    loaded_probs = loaded_pipe.predict_proba(X)[:, 1]

    np.testing.assert_allclose(orig_probs, loaded_probs, rtol=1e-5, atol=1e-5)


# =====================================================================
# 4. Missing Feature Robustness Tests
# =====================================================================

def test_missing_feature_imputation(sample_training_data):
    """Verify that NaN values in numeric features are imputed cleanly by the pipeline."""
    X = sample_training_data[[c for c in ALL_RAW_FEATURES if c in sample_training_data.columns]].copy()
    y = sample_training_data["forgotten"]

    pipe = build_candidate_pipeline("logistic_regression", custom_params={"max_iter": 50})
    pipe.fit(X, y)

    # Introduce NaNs in test inference
    X_nan = X.copy()
    X_nan.loc[0:5, "historical_forgetting_rate"] = np.nan
    X_nan.loc[2:7, "avg_interruption_duration"] = np.nan

    probs = pipe.predict_proba(X_nan)[:, 1]
    assert len(probs) == len(X_nan)
    assert not np.isnan(probs).any()


# =====================================================================
# 5. Operational Latency & Threshold Tests
# =====================================================================

def test_latency_measurement(sample_training_data):
    """Verify inference latency measurement utility returns valid positive millisecond timings."""
    X = sample_training_data[[c for c in ALL_RAW_FEATURES if c in sample_training_data.columns]]
    y = sample_training_data["forgotten"]

    pipe = build_candidate_pipeline("logistic_regression")
    pipe.fit(X, y)

    latency = measure_inference_latency(pipe, X.head(20), n_runs=10)
    assert latency["single_latency_ms"] > 0.0
    assert latency["batch_latency_ms"] > 0.0
    assert latency["single_latency_ms"] < 200.0  # reasonable CPU bound

    size_kb = measure_model_size_kb(pipe)
    assert size_kb > 0.0


def test_optimal_threshold_tuning():
    """Verify threshold finder optimizes F1 on validation predictions."""
    y_true = np.array([0, 0, 0, 1, 1, 1, 1, 0, 0, 1])
    y_prob = np.array([0.1, 0.2, 0.15, 0.8, 0.75, 0.6, 0.45, 0.3, 0.25, 0.9])

    best_t, best_f1 = find_optimal_threshold(y_true, y_prob, metric="f1")
    assert 0.1 <= best_t <= 0.9
    assert best_f1 > 0.7


# =====================================================================
# 6. Experiment Registry Tests
# =====================================================================

def test_experiment_registry_persistence():
    """Verify experiment registry logs, persists, and formats summary DataFrames."""
    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = Path(tmpdir) / "test_registry.json"
        reg = ExperimentRegistry(json_path=json_path)

        reg.log_experiment(
            experiment_id="TEST-001",
            model_type="lightgbm",
            hyperparameters={"n_estimators": 100},
            metrics={"pr_auc": 0.452, "roc_auc": 0.665, "f1": 0.485},
            operational={"training_duration_s": 2.5, "single_latency_ms": 1.1},
        )

        assert json_path.exists()
        reloaded_reg = ExperimentRegistry(json_path=json_path)
        assert len(reloaded_reg.records) == 1
        assert reloaded_reg.records[0]["experiment_id"] == "TEST-001"

        df_summary = reloaded_reg.get_summary_dataframe()
        assert len(df_summary) == 1
        assert "PR-AUC" in df_summary.columns


def test_expected_calibration_error():
    """Verify Expected Calibration Error (ECE) is bounded in [0, 1]."""
    y_true = np.array([0, 0, 1, 1, 0, 1, 0, 1])
    y_prob = np.array([0.1, 0.2, 0.8, 0.9, 0.3, 0.7, 0.2, 0.85])
    ece = compute_expected_calibration_error(y_true, y_prob, n_bins=5)
    assert 0.0 <= ece <= 1.0

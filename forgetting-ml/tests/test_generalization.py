"""
test_generalization.py

Comprehensive test suite for ContextIQ Phase 2.6:
- Group-aware and spatiotemporal splitting (Scenarios A, B, C, D)
- Strict user-disjointness assertions
- Cold-start tier assignment and Empirical Bayes shrinkage
- Prediction interval calculation
- Bootstrap 95% confidence intervals
- Subgroup performance slicing and cohort aggregation (no PII)
- Fairness and disparity analysis (FPR / FNR parity)
- Robustness stress testing under adversarial conditions
- API prediction response cold-start field integration
"""

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.inference import ForgettingPredictor
from ml.evaluation.cold_start import (
    ColdStartAssessment,
    ColdStartStrategy,
    ColdStartTier,
    POPULATION_PRIOR_ALPHA,
    POPULATION_PRIOR_BETA,
)
from ml.evaluation.fairness import evaluate_group_fairness
from ml.evaluation.generalization_splits import (
    build_scenario_d_learning_curve,
    scenario_a_temporal_split,
    scenario_b_user_split,
    scenario_c_user_and_time_split,
)
from ml.evaluation.robustness import (
    evaluate_bootstrap_uncertainty,
    run_robustness_stress_tests,
)
from ml.evaluation.subgroups import compute_slice_metrics, evaluate_all_subgroups

client = TestClient(app)


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def mock_dataset():
    """Generates synthetic dataset for testing split logic."""
    rows = []
    users = [f"U{i:03d}" for i in range(1, 21)]  # 20 users
    dates = pd.date_range("2025-01-01", periods=30).strftime("%Y-%m-%d").tolist()

    for u in users:
        for d in dates:
            for t in range(2):
                rows.append({
                    "task_id": f"{u}-{d}-T{t}",
                    "user_id": u,
                    "date": d,
                    "weekday": 1,
                    "hour": 10,
                    "task_category": "Work" if t == 0 else "Personal",
                    "priority": "HIGH" if t == 0 else "LOW",
                    "location": "Office",
                    "deadline_distance_hours": 12.0,
                    "previous_completion_count": 5,
                    "previous_forgetting_count": 2,
                    "historical_completion_rate": 0.71,
                    "historical_forgetting_rate": 0.29,
                    "task_frequency": 2.0,
                    "tasks_today": 2,
                    "interruptions_today": 3,
                    "recent_context_switches": 4,
                    "avg_interruption_duration": 10.0,
                    "avg_session_duration": 30.0,
                    "forgotten": np.random.choice([0, 1], p=[0.7, 0.3]),
                })
    return pd.DataFrame(rows)


# =====================================================================
# 1. Splitting Logic Tests
# =====================================================================

def test_scenario_a_temporal_split(mock_dataset):
    """Verify Scenario A splits strictly chronologically across all users."""
    tr, val, te = scenario_a_temporal_split(mock_dataset, train_frac=0.7, val_frac=0.15)
    assert max(tr["date"]) < min(val["date"])
    assert max(val["date"]) < min(te["date"])
    assert len(tr) + len(val) + len(te) == len(mock_dataset)


def test_scenario_b_user_split(mock_dataset):
    """Verify Scenario B guarantees strict user disjointness."""
    tr, val, te = scenario_b_user_split(mock_dataset, test_user_frac=0.20, val_user_frac=0.10)
    tr_users = set(tr["user_id"])
    val_users = set(val["user_id"])
    te_users = set(te["user_id"])

    assert tr_users.isdisjoint(te_users), "Train and Test users overlap in Scenario B!"
    assert tr_users.isdisjoint(val_users), "Train and Val users overlap in Scenario B!"
    assert val_users.isdisjoint(te_users), "Val and Test users overlap in Scenario B!"


def test_scenario_c_spatiotemporal_split(mock_dataset):
    """Verify Scenario C guarantees both disjoint users AND future evaluation dates."""
    tr, val, te = scenario_c_user_and_time_split(
        mock_dataset, test_user_frac=0.20, train_date_frac=0.70
    )
    tr_users = set(tr["user_id"])
    te_users = set(te["user_id"])

    # Disjoint users
    assert tr_users.isdisjoint(te_users), "Scenario C user leakage!"
    # Disjoint dates
    assert max(tr["date"]) < min(te["date"]), "Scenario C temporal leakage!"


def test_scenario_d_learning_curve(mock_dataset):
    """Verify Scenario D constructs learning curve trajectory partitions."""
    curve = build_scenario_d_learning_curve(mock_dataset, sample_sizes=[0, 5, 10])
    for n in [0, 5, 10]:
        assert n in curve
        assert "simulated_history_size" in curve[n].columns
        assert (curve[n]["simulated_history_size"] == n).all()


# =====================================================================
# 2. Cold-Start Strategy & Empirical Bayes Shrinkage Tests
# =====================================================================

def test_cold_start_tier_assignment():
    """Verify 3-tier cold start assignment based on sample depth."""
    cs = ColdStartStrategy(min_established_samples=25)

    # Tier 1: N = 0
    t1 = cs.assess_user(0, 0)
    assert t1.is_cold_start is True
    assert t1.cold_start_tier == ColdStartTier.UNSEEN_USER
    assert t1.sample_count == 0
    assert t1.confidence_interval_width == 0.18

    # Tier 2: 1 <= N < 25
    t2 = cs.assess_user(8, 2)  # N = 10
    assert t2.is_cold_start is True
    assert t2.cold_start_tier == ColdStartTier.EARLY_USER
    assert t2.sample_count == 10
    assert 0.08 <= t2.confidence_interval_width < 0.18

    # Tier 3: N >= 25
    t3 = cs.assess_user(25, 5)  # N = 30
    assert t3.is_cold_start is False
    assert t3.cold_start_tier == ColdStartTier.ESTABLISHED_USER
    assert t3.sample_count == 30
    assert t3.confidence_interval_width == 0.05


def test_empirical_bayes_shrinkage_behavior():
    """Verify empirical Bayes pulls sparse user data toward population prior."""
    cs = ColdStartStrategy(min_established_samples=25)
    pop_mean = POPULATION_PRIOR_ALPHA / (POPULATION_PRIOR_ALPHA + POPULATION_PRIOR_BETA)

    # For N=0, rate is exactly population mean
    t1 = cs.assess_user(0, 0)
    assert pytest.approx(t1.shrunk_forgetting_rate, 0.001) == pop_mean

    # For N=2 with 100% forgetting (k=2), shrinkage pulls it significantly downward
    t2 = cs.assess_user(previous_completions=0, previous_forgettings=2)
    expected_shrunk = (2 + POPULATION_PRIOR_ALPHA) / (2 + POPULATION_PRIOR_ALPHA + POPULATION_PRIOR_BETA)
    assert pytest.approx(t2.shrunk_forgetting_rate, 0.001) == expected_shrunk
    assert t2.shrunk_forgetting_rate < 0.50  # Strongly shrunk from 1.0 down toward ~0.395


def test_prediction_interval_bounds():
    """Verify interval calculation respects [0.0, 1.0] probability constraints."""
    cs = ColdStartStrategy()
    assessment = cs.assess_user(0, 0)  # width = 0.18

    # Near 0 boundary
    low, high = cs.calculate_prediction_interval(0.05, assessment)
    assert low == 0.0
    assert high == 0.23

    # Near 1 boundary
    low, high = cs.calculate_prediction_interval(0.95, assessment)
    assert low == 0.77
    assert high == 1.0


# =====================================================================
# 3. Bootstrap & Subgroups Tests
# =====================================================================

def test_bootstrap_uncertainty_ci_ordering():
    """Verify bootstrap 95% confidence intervals are mathematically ordered."""
    np.random.seed(42)
    y_true = np.array([0, 0, 0, 0, 0, 1, 1, 1, 0, 1] * 10)
    y_prob = np.array([0.1, 0.2, 0.15, 0.3, 0.25, 0.8, 0.75, 0.9, 0.35, 0.85] * 10)

    cis = evaluate_bootstrap_uncertainty(y_true, y_prob, n_bootstraps=50)
    for metric in ["pr_auc", "roc_auc", "brier_score"]:
        assert metric in cis
        res = cis[metric]
        assert res["ci_lower"] <= res["point"] + 1e-4
        assert res["point"] <= res["ci_upper"] + 1e-4


def test_subgroup_evaluation(mock_dataset):
    """Verify behavioral subgroup slicing covers all dimensions."""
    n = len(mock_dataset)
    y_prob = np.random.uniform(0.1, 0.9, size=n)
    subgroups = evaluate_all_subgroups(mock_dataset, y_prob)

    assert "task_category" in subgroups
    assert "priority" in subgroups
    assert "deadline_distance" in subgroups
    assert "interruption_frequency" in subgroups
    assert "user_volume_cohort" in subgroups
    assert "Work" in subgroups["task_category"]


def test_fairness_disparity_calculation(mock_dataset):
    """Verify fairness calculation outputs parity metrics and disparity ratios."""
    n = len(mock_dataset)
    mock_dataset["_prob"] = np.random.uniform(0.1, 0.9, size=n)
    fairness = evaluate_group_fairness(
        mock_dataset,
        group_col="task_category",
        y_true_col="forgotten",
        y_prob_col="_prob",
    )
    assert "overall_baseline" in fairness
    assert "groups" in fairness
    assert "max_fpr_disparity_ratio" in fairness
    assert "fairness_flag" in fairness


# =====================================================================
# 4. API Integration Tests (Cold-Start Fields)
# =====================================================================

def test_api_prediction_includes_cold_start_fields(sample_task_payload):
    """Verify prediction endpoint returns cold-start assessment and confidence intervals."""
    # Test cold-start payload (0 previous completions)
    cold_payload = dict(sample_task_payload)
    cold_payload["previous_completion_count"] = 0
    cold_payload["previous_forgetting_count"] = 0

    response = client.post("/api/v1/predictions/forgetting", json=cold_payload)
    assert response.status_code == 200
    data = response.json()

    assert "is_cold_start" in data
    assert "cold_start_tier" in data
    assert "confidence_interval" in data
    assert data["is_cold_start"] is True
    assert data["cold_start_tier"] == "UNSEEN_USER"
    assert len(data["confidence_interval"]) == 2
    assert data["confidence_interval"][0] <= data["prediction_probability"] <= data["confidence_interval"][1]


def test_api_prediction_established_user(sample_task_payload):
    """Verify prediction endpoint recognizes established users (N >= 25)."""
    est_payload = dict(sample_task_payload)
    est_payload["previous_completion_count"] = 30
    est_payload["previous_forgetting_count"] = 5

    response = client.post("/api/v1/predictions/forgetting", json=est_payload)
    assert response.status_code == 200
    data = response.json()

    assert data["is_cold_start"] is False
    assert data["cold_start_tier"] == "ESTABLISHED_USER"

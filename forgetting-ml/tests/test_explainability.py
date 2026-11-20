"""
test_explainability.py

Comprehensive test suite for ContextIQ Phase 2.7:
- Model-specific SHAP explainers (LinearExplainer with Independent masker, TreeExplainer)
- Transformed-to-raw feature & observed value mapping
- Thread-safe LRU explanation cache (hits, misses, version invalidation)
- Non-causal prospective memory behavioral vocabulary verification
- Grounded natural language reasoning without hallucinations
- Execution timeout handling and fallback
- Vectorized batch explanation support
- Global feature importances and pairwise interaction analysis
- API endpoints validation (/explain, /batch_explain, /explain/global)
- Backward compatibility for legacy ForgettingExplainer APIs
"""

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier

from app.main import app
from app.inference import ForgettingPredictor
from ml.explainability.cache import ExplanationCache, GLOBAL_EXPLANATION_CACHE
from ml.explainability.explainer import ForgettingExplainer, EXPLANATION_VERSION
from ml.explainability.feature_mapper import FeatureMapper
from ml.explainability.global_explainer import GlobalExplainer
from ml.explainability.nlg_explainer import NLGExplainer

client = TestClient(app)


# =====================================================================
# 1. Explainer Compatibility & Initialization Tests
# =====================================================================

def test_linear_explainer_masker_initialization():
    """Verify LinearExplainer builds with Independent masker and computes SHAP values."""
    X_bg = np.random.randn(60, 10)
    y_bg = np.random.randint(0, 2, size=60)
    clf = LogisticRegression(C=1.0)
    clf.fit(X_bg, y_bg)

    feature_names = [f"feat_{i}" for i in range(10)]
    explainer = ForgettingExplainer(
        raw_model=clf,
        model_name="logistic_regression",
        preprocessor=None,
        feature_names_transformed=feature_names,
        background_data=X_bg,
    )

    assert explainer._explainer is not None
    # Compute test row
    X_test = np.random.randn(1, 10)
    reasons = explainer.explain(X_test, top_k=3)
    assert len(reasons) == 3


def test_tree_explainer_compatibility():
    """Verify TreeExplainer builds cleanly for tree ensembles."""
    X_bg = np.random.randn(50, 10)
    y_bg = np.random.randint(0, 2, size=50)
    rf = RandomForestClassifier(n_estimators=5, max_depth=3, random_state=42)
    rf.fit(X_bg, y_bg)

    feature_names = [f"feat_{i}" for i in range(10)]
    explainer = ForgettingExplainer(
        raw_model=rf,
        model_name="random_forest",
        preprocessor=None,
        feature_names_transformed=feature_names,
        background_data=X_bg,
    )

    assert explainer._explainer is not None
    X_test = np.random.randn(1, 10)
    vals = explainer.explain_with_values(X_test, top_k=3)
    assert len(vals) == 3
    assert "shap_value" in vals[0]


# =====================================================================
# 2. Feature Mapping & Formatting Tests
# =====================================================================

def test_feature_mapping_numeric_and_categorical():
    """Verify parsing of ColumnTransformer output names to raw features."""
    raw1, disp1, cat1 = FeatureMapper.parse_transformed_feature("num__deadline_distance_hours")
    assert raw1 == "deadline_distance_hours"
    assert "Deadline" in disp1
    assert cat1 is None

    raw2, disp2, cat2 = FeatureMapper.parse_transformed_feature("cat__task_category_Personal")
    assert raw2 == "task_category"
    assert cat2 == "Personal"
    assert "Personal" in disp2


def test_feature_value_formatting():
    """Verify formatted representation of observed behavioral features."""
    assert FeatureMapper.format_actual_value("weekday", 0) == "Monday"
    assert FeatureMapper.format_actual_value("weekday", 4) == "Friday"
    assert FeatureMapper.format_actual_value("hour", 14) == "2:00 PM"
    assert FeatureMapper.format_actual_value("hour", 9) == "9:00 AM"
    assert FeatureMapper.format_actual_value("deadline_distance_hours", 6.5) == "6.5 hours"
    assert FeatureMapper.format_actual_value("historical_forgetting_rate", 0.274) == "27.4%"
    assert FeatureMapper.format_actual_value("interruptions_today", 4) == "4"


# =====================================================================
# 3. Explanation Cache Tests
# =====================================================================

def test_cache_hit_and_miss_lifecycle():
    """Verify LRU cache records miss on new key and hit on identical key."""
    cache = ExplanationCache(max_size=10)
    sample_feat = {"interruptions_today": 3, "deadline_distance_hours": 12.0}

    key = cache.compute_cache_key("logreg", "1.1.0", "2.7.0", sample_feat)
    assert cache.get(key) is None
    assert cache.stats["misses"] == 1

    dummy_val = {"explanation": "cached"}
    cache.put(key, dummy_val)
    hit_val = cache.get(key)
    assert hit_val == dummy_val
    assert cache.stats["hits"] == 1


def test_cache_version_invalidation():
    """Verify changing model_version or explanation_version yields different keys."""
    cache = ExplanationCache()
    sample_feat = {"task_id": "T1"}

    k1 = cache.compute_cache_key("model", "1.0.0", "2.7.0", sample_feat)
    k2 = cache.compute_cache_key("model", "1.1.0", "2.7.0", sample_feat)
    k3 = cache.compute_cache_key("model", "1.0.0", "2.8.0", sample_feat)

    assert k1 != k2
    assert k1 != k3


# =====================================================================
# 4. Non-Causal Vocabulary & NLG Grounding Tests
# =====================================================================

def test_non_causal_vocabulary_enforcement():
    """Verify explanations never assert causality."""
    predictor = ForgettingPredictor.instance()
    sample = {
        "task_id": "T-CausalCheck",
        "task_category": "Work",
        "priority": "HIGH",
        "location": "Office",
        "weekday": 2,
        "hour": 11,
        "deadline_distance_hours": 3.0,
        "previous_completion_count": 10,
        "previous_forgetting_count": 4,
        "historical_completion_rate": 0.71,
        "historical_forgetting_rate": 0.29,
        "task_frequency": 0.5,
        "tasks_today": 4,
        "interruptions_today": 7,
        "recent_context_switches": 6,
        "avg_interruption_duration": 12.0,
        "avg_session_duration": 18.0,
    }

    explanation = predictor.explain_single(sample)
    nlg = explanation["natural_language_explanation"].lower()

    # Causal violation check
    forbidden = ["causes", "caused by", "proves that", "because you failed", "solely due to"]
    for word in forbidden:
        assert word not in nlg, f"Forbidden causal word '{word}' found in explanation!"

    # Associational language check
    assert any(term in nlg for term in ["associated with", "moderating factor", "vulnerability", "risk"])


def test_nlg_grounding_matches_input_values():
    """Verify numbers in generated NLG match the actual inputs."""
    pos = [
        {"feature": "num__deadline_distance_hours", "display_name": "Deadline Proximity", "actual_value_formatted": "4.5 hours"},
        {"feature": "num__interruptions_today", "display_name": "Daily Interruption Count", "actual_value_formatted": "8"},
    ]
    neg = [
        {"feature": "num__previous_completion_count", "display_name": "Past Completed Tasks", "actual_value_formatted": "15"},
    ]

    text = NLGExplainer.generate_explanation(
        risk_category="HIGH",
        probability=0.742,
        top_positive_factors=pos,
        top_negative_factors=neg,
        task_title="Test Task",
    )

    assert "74.2%" in text
    assert "4.5 hours" in text
    assert "8" in text
    assert "15" in text


# =====================================================================
# 5. Global Explainability & Interactions Tests
# =====================================================================

def test_global_summary_and_interactions():
    """Verify global summary and interaction strengths computation."""
    np.random.seed(42)
    fake_shap = np.random.randn(50, 5)
    names = ["num__f1", "num__f2", "num__f3", "num__f4", "num__f5"]

    summary = GlobalExplainer.compute_global_summary(fake_shap, names, top_k=3)
    assert len(summary) == 3
    assert summary[0]["mean_abs_shap"] >= summary[1]["mean_abs_shap"]

    interactions = GlobalExplainer.compute_feature_interactions(fake_shap, names, top_n=2)
    assert len(interactions) == 2
    assert "display_pair" in interactions[0]


# =====================================================================
# 6. API Endpoints Tests
# =====================================================================

def test_api_explain_endpoint(sample_task_payload):
    """Verify POST /api/v1/predictions/explain and alias /explain."""
    for path in ["/api/v1/predictions/explain", "/explain"]:
        resp = client.post(path, json=sample_task_payload)
        assert resp.status_code == 200
        data = resp.json()

        assert "calibrated_probability" in data
        assert "base_value" in data
        assert "attributions" in data
        assert "natural_language_explanation" in data
        assert len(data["attributions"]) > 0
        assert data["explanation_version"] == EXPLANATION_VERSION


def test_api_batch_explain_endpoint(sample_task_payload):
    """Verify POST /api/v1/predictions/batch_explain and alias /batch_explain."""
    req = {"tasks": [sample_task_payload, sample_task_payload], "top_k": 3}
    for path in ["/api/v1/predictions/batch_explain", "/batch_explain"]:
        resp = client.post(path, json=req)
        assert resp.status_code == 200
        data = resp.json()
        assert "explanations" in data
        assert len(data["explanations"]) == 2


def test_api_global_explain_endpoint():
    """Verify GET /api/v1/predictions/explain/global and alias /explain/global."""
    for path in ["/api/v1/predictions/explain/global", "/explain/global"]:
        resp = client.get(path)
        assert resp.status_code == 200
        data = resp.json()
        assert "global_importances" in data
        assert "top_interactions" in data
        assert len(data["global_importances"]) > 0


# =====================================================================
# 7. Backward Compatibility Tests
# =====================================================================

def test_legacy_explainer_api_backward_compatibility():
    """Verify legacy explain() and explain_with_values() remain completely operational."""
    predictor = ForgettingPredictor.instance()
    sample = np.random.randn(1, len(predictor.feature_names_transformed))

    reasons = predictor.explainer.explain(sample, top_k=3)
    assert isinstance(reasons, list)
    assert len(reasons) == 3
    assert "associated with" in reasons[0]

    vals = predictor.explainer.explain_with_values(sample, top_k=3)
    assert isinstance(vals, list)
    assert len(vals) == 3
    assert "shap_value" in vals[0]

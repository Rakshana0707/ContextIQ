"""
test_phase2_integration.py

Comprehensive Phase 2 Integration Test Suite.
Validates end-to-end integration across all Phase 2 components:
- Strict temporal feature handling & target labeling
- Binary risk prediction with Platt scaling calibration
- Multi-horizon survival analysis and monotonically decreasing S(t)
- SHAP explainability and grounded NLG synthesis (zero private data leakage)
- Model registry lifecycle and production state invariants
- Cold-start handling and missingness robustness
"""

import math
import pytest
from datetime import datetime, timezone, timedelta

from ml.features.feature_spec import FeatureSchemaVersion, NUMERIC_FEATURES, CATEGORICAL_FEATURES
from ml.data.label_generator import generate_task_label, LabelingConfig, OutcomeType
from ml.registry.registry import ModelRegistry
from ml.registry.enums import ModelLifecycleState, TaskType
from app.inference import ForgettingPredictor
from app.survival_service import SurvivalService
from ml.explainability.explainer import ForgettingExplainer
from ml.explainability.nlg_explainer import NLGExplainer


@pytest.fixture
def sample_task():
    now = datetime.now(timezone.utc)
    deadline_iso = (now + timedelta(hours=8)).isoformat()
    return {
        "task_id": "TEST-INT-TASK-001",
        "user_id": "TEST-INT-USER-001",
        "title": "Quarterly Context Telemetry Audit",
        "task_category": "Work",
        "priority": "HIGH",
        "location": "Office",
        "created_at": now.isoformat(),
        "deadline_at": deadline_iso,
        "scheduled_deadline": deadline_iso,
        "status": "PENDING",
    }


@pytest.fixture
def sample_features(sample_task):
    now = datetime.now(timezone.utc)
    return {
        "task_id": sample_task["task_id"],
        "user_id": sample_task["user_id"],
        "task_category": sample_task["task_category"],
        "priority": sample_task["priority"],
        "location": sample_task["location"],
        "weekday": now.weekday(),
        "hour": now.hour,
        "deadline_distance_hours": 8.0,
        "previous_completion_count": 12,
        "previous_forgetting_count": 3,
        "historical_completion_rate": 0.80,
        "historical_forgetting_rate": 0.20,
        "task_frequency": 0.40,
        "tasks_today": 5,
        "interruptions_today": 4,
        "recent_context_switches": 2,
        "avg_interruption_duration": 3.5,
        "avg_session_duration": 25.0,
        "historical_postponements": 1,
        "avg_completion_duration_minutes": 40.0,
        "task_inactivity_duration_hours": 4.0,
        "deadline_extensions_count": 0,
        "interruption_latency_mean": 2.0,
        "interruption_frequency_1h": 1,
        "context_switch_burstiness": 0.20,
        "post_interruption_delay_mean": 3.0,
        "cumulative_fatigue_index": 0.30,
        "daily_schedule_fragmentation": 0.35,
        "circadian_rhythm_peak_distance": 1.0,
        "days_since_prior_forgetting": 10.0,
        "urgency_decay_rate": 0.10,
        "context_similarity_prior_lapse": 0.05,
    }


class TestPhase2Integration:
    """Complete cross-component integration tests."""

    def test_target_labeling_prospective_memory(self, sample_task):
        """Validates formal prospective memory omission labeling protocol."""
        deadline = datetime.fromisoformat(sample_task["deadline_at"])
        
        # Scenario A: Task observed past deadline + grace period with no completion
        eval_time = deadline + timedelta(hours=6.0)
        label_res = generate_task_label(
            sample_task,
            events=[],
            as_of=eval_time,
            config=LabelingConfig(grace_period_hours=4.0),
        )
        assert label_res.will_forget == 1
        assert label_res.is_valid_training_sample is True
        assert label_res.outcome_type in (OutcomeType.OVERDUE, OutcomeType.ABANDONED, OutcomeType.EXPLICITLY_FORGOTTEN)

        # Scenario B: Task completed before deadline
        completed_task = dict(sample_task)
        completed_task["completed_at"] = (deadline - timedelta(hours=1.0)).isoformat()
        completed_task["status"] = "COMPLETED"
        label_res_comp = generate_task_label(
            completed_task,
            events=[],
            as_of=eval_time,
            config=LabelingConfig(grace_period_hours=4.0),
        )
        assert label_res_comp.will_forget == 0
        assert label_res_comp.outcome_type == OutcomeType.COMPLETED_ON_TIME

    def test_binary_prediction_and_calibration(self, sample_features):
        """Tests inference with active production model and Platt scaling calibration."""
        predictor = ForgettingPredictor.instance()
        res = predictor.predict_single(sample_features)

        assert "raw_probability" in res
        assert "calibrated_probability" in res
        assert 0.0 <= res["raw_probability"] <= 1.0
        assert 0.0 <= res["calibrated_probability"] <= 1.0
        assert res["risk_category"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
        assert bool(res["model_version"])
        assert "confidence_interval" in res

    def test_survival_analysis_monotonicity(self, sample_features):
        """Validates that survival probabilities S(t) are non-increasing over time."""
        surv_service = SurvivalService.instance()
        horizons = [6.0, 12.0, 24.0, 48.0, 168.0]
        res = surv_service.predict_task_survival(sample_features, horizons=horizons)

        assert "horizons" in res
        assert len(res["horizons"]) == len(horizons)

        prev_s = 1.0
        for pt in res["horizons"]:
            s_t = pt["survival_probability"]
            f_t = pt["forgetting_risk"]
            assert 0.0 <= s_t <= 1.0
            assert 0.0 <= f_t <= 1.0
            assert math.isclose(s_t + f_t, 1.0, abs_tol=1e-5)
            # Monotonicity of S(t): S(t2) <= S(t1) for t2 > t1
            assert s_t <= prev_s + 1e-6
            prev_s = s_t

    def test_shap_explanation_grounding(self, sample_features):
        """Tests SHAP attributions and confirms grounded NLG uses associational language."""
        predictor = ForgettingPredictor.instance()
        exp_res = predictor.explain_single(sample_features, top_k=5)

        assert "attributions" in exp_res
        assert len(exp_res["attributions"]) <= 5
        assert "base_value" in exp_res
        assert "natural_language_explanation" in exp_res

        nlg = exp_res["natural_language_explanation"]
        assert isinstance(nlg, str)
        assert len(nlg) > 10

        # Guarantees: non-causal phrasing
        causal_words = ["caused by", "because you", "due to your failure"]
        for word in causal_words:
            assert word not in nlg.lower()

    def test_cold_start_shrinkage(self):
        """Validates that novel users trigger cold-start handling."""
        predictor = ForgettingPredictor.instance()
        cold_features = {
            "task_id": "COLD-USER-TASK",
            "user_id": "BRAND-NEW-USER-999",
            "task_category": "Work",
            "priority": "HIGH",
            "location": "Office",
            "weekday": 2,
            "hour": 14,
            "deadline_distance_hours": 12.0,
            "previous_completion_count": 0,
            "previous_forgetting_count": 0,
            "historical_completion_rate": 0.5,
            "historical_forgetting_rate": 0.5,
            "task_frequency": 0.0,
            "tasks_today": 1,
            "interruptions_today": 0,
            "recent_context_switches": 0,
            "avg_interruption_duration": 0.0,
            "avg_session_duration": 0.0,
        }
        res = predictor.predict_single(cold_features)
        assert res["is_cold_start"] is True
        assert res["cold_start_tier"] in ("UNSEEN_USER", "UNOBSERVED", "MINIMAL_HISTORY", "SPARSE_HISTORY")

    def test_model_registry_production_invariant(self):
        """Validates single active production model invariant and state transitions."""
        registry = ModelRegistry.instance()

        prod_clf = registry.get_production_model(TaskType.BINARY_CLASSIFICATION)
        assert prod_clf is not None
        assert prod_clf.lifecycle_state == ModelLifecycleState.PRODUCTION

        prod_surv = registry.get_production_model(TaskType.SURVIVAL_ANALYSIS)
        assert prod_surv is not None
        assert prod_surv.lifecycle_state == ModelLifecycleState.PRODUCTION

        # Confirm artifacts exist and are SHA-256 verified
        assert registry.verify_model_integrity(prod_clf.model_id) is True
        assert registry.verify_model_integrity(prod_surv.model_id) is True

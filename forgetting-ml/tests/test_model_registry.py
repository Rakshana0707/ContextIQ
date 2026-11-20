"""
test_model_registry.py

Comprehensive test suite for ContextIQ Phase 2.9:
- Centralized model registry and metadata catalog
- 8-stage lifecycle state machine transitions and illegal jump rejection
- Single active production model per task type invariant
- Versioned artifact storage with SHA-256 checksum verification
- Detection of corrupted artifacts (bit rot / tampering)
- Immutability / overwrite protection
- Feature schema compatibility enforcement
- Model rollback and deployment audit ledger
- Survival model distinct registration and coexistence
- Experiment registry promotion bridge (Phase 2.4 integration)
- Inference latency measurement and dynamic version routing
- Administrative API security and RBAC authentication
"""

import json
from pathlib import Path
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.inference import ForgettingPredictor
from ml.registry.artifact_store import ArtifactStore, compute_file_sha256
from ml.registry.enums import ModelFamily, ModelLifecycleState, TaskType
from ml.registry.models import (
    ArtifactNotFoundError,
    ArtifactOverwriteError,
    ChecksumMismatchError,
    InvalidStateTransitionError,
    ModelMetadata,
    ModelRegistryError,
    SchemaMismatchError,
)
from ml.registry.registry import ModelRegistry
from ml.features.feature_spec import CATEGORICAL_FEATURES, NUMERIC_FEATURES

client = TestClient(app)
ADMIN_HEADERS = {"X-Admin-Key": "contextiq-admin-secret"}


# =====================================================================
# 1. Registry & Catalog Lifecycle Tests
# =====================================================================

def test_model_registration_and_catalog(tmp_path):
    """Verify registering a model, persisting catalog, and reloading from disk."""
    cat_file = tmp_path / "catalog.json"
    audit_file = tmp_path / "audit.jsonl"
    reg = ModelRegistry(catalog_path=cat_file, audit_path=audit_file)

    meta = ModelMetadata(
        model_id="clf_test_v1.0.0",
        model_name="test_model",
        model_version="1.0.0",
        model_family=ModelFamily.LINEAR,
        task_type=TaskType.BINARY_CLASSIFICATION,
        training_dataset_version="1.0.0",
        feature_schema_version="2.2.0",
        target_definition_version="2.1.0",
        training_timestamp="2026-11-20T12:00:00Z",
        registered_at="2026-11-20T12:05:00Z",
        artifact_location="artifacts/test.joblib",
        artifact_checksum="abc123sha",
        lifecycle_state=ModelLifecycleState.DEVELOPMENT,
        evaluation_metrics={"pr_auc": 0.50},
    )

    reg.register_model(meta)
    assert cat_file.exists()
    assert meta.model_id in reg._models

    # Reload new registry instance from same file
    reg2 = ModelRegistry(catalog_path=cat_file, audit_path=audit_file)
    reloaded = reg2.get_model("clf_test_v1.0.0")
    assert reloaded is not None
    assert reloaded.model_name == "test_model"
    assert reloaded.evaluation_metrics["pr_auc"] == 0.50


def test_duplicate_version_registration_rejected(tmp_path):
    """Verify that registering duplicate model_name + model_version is rejected."""
    cat_file = tmp_path / "catalog.json"
    reg = ModelRegistry(catalog_path=cat_file)

    meta1 = ModelMetadata(
        model_id="clf_test_v1.0.0",
        model_name="test_classifier",
        model_version="1.0.0",
        model_family=ModelFamily.TREE,
        task_type=TaskType.BINARY_CLASSIFICATION,
        training_dataset_version="1.0.0",
        feature_schema_version="2.2.0",
        target_definition_version="2.1.0",
        training_timestamp="2026-11-20T12:00:00Z",
        registered_at="2026-11-20T12:05:00Z",
        artifact_location="artifacts/test1.joblib",
        artifact_checksum="abc1",
    )
    reg.register_model(meta1)

    meta2 = ModelMetadata(
        model_id="clf_test_v1.0.0_dup",
        model_name="test_classifier",
        model_version="1.0.0",
        model_family=ModelFamily.TREE,
        task_type=TaskType.BINARY_CLASSIFICATION,
        training_dataset_version="1.0.0",
        feature_schema_version="2.2.0",
        target_definition_version="2.1.0",
        training_timestamp="2026-11-20T12:00:00Z",
        registered_at="2026-11-20T12:05:00Z",
        artifact_location="artifacts/test2.joblib",
        artifact_checksum="abc2",
    )
    with pytest.raises(ModelRegistryError, match="already exists"):
        reg.register_model(meta2)


# =====================================================================
# 2. Lifecycle State Machine & Transition Invariants
# =====================================================================

def test_lifecycle_state_machine_valid_progression(tmp_path):
    """Verify step-by-step legal transition through the entire lifecycle."""
    cat_file = tmp_path / "catalog.json"
    reg = ModelRegistry(catalog_path=cat_file)

    meta = ModelMetadata(
        model_id="clf_fsm_v1.0.0",
        model_name="fsm_model",
        model_version="1.0.0",
        model_family=ModelFamily.LINEAR,
        task_type=TaskType.BINARY_CLASSIFICATION,
        training_dataset_version="1.0.0",
        feature_schema_version="2.2.0",
        target_definition_version="2.1.0",
        training_timestamp="2026-11-20T12:00:00Z",
        registered_at="2026-11-20T12:05:00Z",
        artifact_location="artifacts/test.joblib",
        artifact_checksum="dummy",
        lifecycle_state=ModelLifecycleState.DEVELOPMENT,
    )
    reg.register_model(meta)

    # Dev -> Training
    m = reg.transition_state("clf_fsm_v1.0.0", ModelLifecycleState.TRAINING)
    assert m.lifecycle_state == ModelLifecycleState.TRAINING

    # Training -> Validation
    m = reg.transition_state("clf_fsm_v1.0.0", ModelLifecycleState.VALIDATION)
    assert m.lifecycle_state == ModelLifecycleState.VALIDATION

    # Validation -> Candidate
    m = reg.transition_state("clf_fsm_v1.0.0", ModelLifecycleState.CANDIDATE)
    assert m.lifecycle_state == ModelLifecycleState.CANDIDATE

    # Candidate -> Approved
    m = reg.approve_model("clf_fsm_v1.0.0", actor="Senior Lead", rationale="Passed benchmarks")
    assert m.lifecycle_state == ModelLifecycleState.APPROVED
    assert m.approved_by == "Senior Lead"


def test_illegal_lifecycle_transitions_rejected(tmp_path):
    """Verify that jumping states or promoting rejected models raises InvalidStateTransitionError."""
    cat_file = tmp_path / "catalog.json"
    reg = ModelRegistry(catalog_path=cat_file)

    meta = ModelMetadata(
        model_id="clf_illegal_v1.0.0",
        model_name="illegal_model",
        model_version="1.0.0",
        model_family=ModelFamily.LINEAR,
        task_type=TaskType.BINARY_CLASSIFICATION,
        training_dataset_version="1.0.0",
        feature_schema_version="2.2.0",
        target_definition_version="2.1.0",
        training_timestamp="2026-11-20T12:00:00Z",
        registered_at="2026-11-20T12:05:00Z",
        artifact_location="artifacts/test.joblib",
        artifact_checksum="dummy",
        lifecycle_state=ModelLifecycleState.DEVELOPMENT,
    )
    reg.register_model(meta)

    # Illegal: DEVELOPMENT -> PRODUCTION directly
    with pytest.raises(InvalidStateTransitionError):
        reg.transition_state("clf_illegal_v1.0.0", ModelLifecycleState.PRODUCTION)

    # Legal: DEVELOPMENT -> REJECTED
    reg.transition_state("clf_illegal_v1.0.0", ModelLifecycleState.REJECTED)

    # Illegal: REJECTED is terminal, cannot transition to anything
    with pytest.raises(InvalidStateTransitionError):
        reg.transition_state("clf_illegal_v1.0.0", ModelLifecycleState.PRODUCTION)


def test_single_active_production_invariant(tmp_path):
    """Verify promoting a model to PRODUCTION automatically archives the previous production model."""
    cat_file = tmp_path / "catalog.json"
    reg = ModelRegistry(catalog_path=cat_file)

    meta1 = ModelMetadata(
        model_id="clf_champ_v1.0.0",
        model_name="model1",
        model_version="1.0.0",
        model_family=ModelFamily.LINEAR,
        task_type=TaskType.BINARY_CLASSIFICATION,
        training_dataset_version="1.0.0",
        feature_schema_version="2.2.0",
        target_definition_version="2.1.0",
        training_timestamp="2026-11-20T12:00:00Z",
        registered_at="2026-11-20T12:05:00Z",
        artifact_location="artifacts/test1.joblib",
        artifact_checksum="dummy1",
        lifecycle_state=ModelLifecycleState.APPROVED,
    )
    meta2 = ModelMetadata(
        model_id="clf_challenger_v2.0.0",
        model_name="model2",
        model_version="2.0.0",
        model_family=ModelFamily.TREE,
        task_type=TaskType.BINARY_CLASSIFICATION,
        training_dataset_version="1.0.0",
        feature_schema_version="2.2.0",
        target_definition_version="2.1.0",
        training_timestamp="2026-11-20T12:00:00Z",
        registered_at="2026-11-20T12:05:00Z",
        artifact_location="artifacts/test2.joblib",
        artifact_checksum="dummy2",
        lifecycle_state=ModelLifecycleState.APPROVED,
    )
    reg.register_model(meta1)
    reg.register_model(meta2)

    # Promote meta1 to PRODUCTION
    reg.transition_state("clf_champ_v1.0.0", ModelLifecycleState.PRODUCTION)
    assert reg.get_production_model(TaskType.BINARY_CLASSIFICATION).model_id == "clf_champ_v1.0.0"

    # Promote meta2 to PRODUCTION -> meta1 must become ARCHIVED
    reg.transition_state("clf_challenger_v2.0.0", ModelLifecycleState.PRODUCTION)
    assert reg.get_production_model(TaskType.BINARY_CLASSIFICATION).model_id == "clf_challenger_v2.0.0"
    assert reg.get_model("clf_champ_v1.0.0").lifecycle_state == ModelLifecycleState.ARCHIVED


# =====================================================================
# 3. Artifact Store, Checksum Integrity & Schema Validation
# =====================================================================

def test_artifact_store_checksum_and_save_load(tmp_path):
    """Verify versioned saving, SHA-256 calculation, and loading."""
    store = ArtifactStore(base_dir=tmp_path / "models")
    bundle = {
        "model": "model_obj",
        "categorical_features": list(CATEGORICAL_FEATURES),
        "numeric_features": list(NUMERIC_FEATURES),
    }

    path, checksum = store.save_artifact(
        bundle=bundle,
        task_type=TaskType.BINARY_CLASSIFICATION,
        model_name="logreg",
        version="1.5.0",
    )
    assert path.exists()
    assert len(checksum) == 64  # Hexadecimal SHA-256 length

    loaded = store.load_artifact(path, expected_checksum=checksum)
    assert loaded["model"] == "model_obj"


def test_artifact_overwrite_protection(tmp_path):
    """Verify that saving an existing version without overwrite=True raises ArtifactOverwriteError."""
    store = ArtifactStore(base_dir=tmp_path / "models")
    bundle = {"model": "dummy"}

    store.save_artifact(bundle, TaskType.BINARY_CLASSIFICATION, "logreg", "1.0.0")

    with pytest.raises(ArtifactOverwriteError):
        store.save_artifact(bundle, TaskType.BINARY_CLASSIFICATION, "logreg", "1.0.0", overwrite=False)

    # Allowed with explicit overwrite=True
    path, checksum = store.save_artifact(bundle, TaskType.BINARY_CLASSIFICATION, "logreg", "1.0.0", overwrite=True)
    assert path.exists()


def test_corrupted_artifact_detection(tmp_path):
    """Verify that bit rot or tampered artifact raises ChecksumMismatchError."""
    store = ArtifactStore(base_dir=tmp_path / "models")
    bundle = {"model": "pristine_weights"}

    path, original_checksum = store.save_artifact(bundle, TaskType.BINARY_CLASSIFICATION, "logreg", "2.0.0")

    # Tamper with file bytes
    with open(path, "ab") as f:
        f.write(b"CORRUPTED_BYTES")

    with pytest.raises(ChecksumMismatchError, match="Integrity check failed"):
        store.load_artifact(path, expected_checksum=original_checksum)


def test_schema_compatibility_validation(tmp_path):
    """Verify that bundles missing required feature columns raise SchemaMismatchError."""
    store = ArtifactStore(base_dir=tmp_path / "models")
    invalid_bundle = {
        "categorical_features": ["task_category"],
        "numeric_features": ["deadline_distance_hours"],  # Missing all other 27 features
    }

    with pytest.raises(SchemaMismatchError, match="missing expected features"):
        store.verify_feature_schema(invalid_bundle)


# =====================================================================
# 4. Model Rollback & Audit Ledger Tests
# =====================================================================

def test_model_rollback_lifecycle(tmp_path):
    """Verify rolling back restores target version to PRODUCTION and updates audit ledger."""
    cat_file = tmp_path / "catalog.json"
    audit_file = tmp_path / "audit.jsonl"
    store = ArtifactStore(base_dir=tmp_path / "models")
    reg = ModelRegistry(catalog_path=cat_file, audit_path=audit_file, artifact_store=store)

    # Save real bundles for v1.0.0 and v2.0.0
    b1 = {"model": "v1"}
    p1, c1 = store.save_artifact(b1, TaskType.BINARY_CLASSIFICATION, "logreg", "1.0.0")
    b2 = {"model": "v2"}
    p2, c2 = store.save_artifact(b2, TaskType.BINARY_CLASSIFICATION, "logreg", "2.0.0")

    meta1 = ModelMetadata(
        model_id="clf_logreg_v1.0.0",
        model_name="logreg",
        model_version="1.0.0",
        model_family=ModelFamily.LINEAR,
        task_type=TaskType.BINARY_CLASSIFICATION,
        training_dataset_version="1.0.0",
        feature_schema_version="2.2.0",
        target_definition_version="2.1.0",
        training_timestamp="2026-11-20T12:00:00Z",
        registered_at="2026-11-20T12:00:00Z",
        artifact_location=str(p1),
        artifact_checksum=c1,
        lifecycle_state=ModelLifecycleState.ARCHIVED,
    )
    meta2 = ModelMetadata(
        model_id="clf_logreg_v2.0.0",
        model_name="logreg",
        model_version="2.0.0",
        model_family=ModelFamily.LINEAR,
        task_type=TaskType.BINARY_CLASSIFICATION,
        training_dataset_version="1.0.0",
        feature_schema_version="2.2.0",
        target_definition_version="2.1.0",
        training_timestamp="2026-11-20T13:00:00Z",
        registered_at="2026-11-20T13:00:00Z",
        artifact_location=str(p2),
        artifact_checksum=c2,
        lifecycle_state=ModelLifecycleState.APPROVED,
    )
    reg.register_model(meta1)
    reg.register_model(meta2)
    reg.promote_to_production("clf_logreg_v2.0.0")

    # Execute rollback to v1.0.0
    restored, prev = reg.rollback(
        task_type=TaskType.BINARY_CLASSIFICATION,
        target_version="1.0.0",
        actor="Ops Lead",
        reason="Performance degradation in v2",
    )

    assert restored.model_version == "1.0.0"
    assert restored.lifecycle_state == ModelLifecycleState.PRODUCTION
    assert prev.model_version == "2.0.0"
    assert prev.lifecycle_state == ModelLifecycleState.ARCHIVED

    # Verify audit log recorded rollback
    assert audit_file.exists()
    with open(audit_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        events = [json.loads(l) for l in lines]
        rollback_events = [e for e in events if e["event_type"] == "MODEL_ROLLBACK"]
        assert len(rollback_events) == 1
        assert rollback_events[0]["details"]["restored_version"] == "1.0.0"


# =====================================================================
# 5. Survival Model Separation & Coexistence Tests
# =====================================================================

def test_survival_model_separate_registration():
    """Verify survival models are registered distinctly under TaskType.SURVIVAL_ANALYSIS."""
    reg = ModelRegistry.instance()
    clf_prod = reg.get_production_model(TaskType.BINARY_CLASSIFICATION)
    surv_prod = reg.get_production_model(TaskType.SURVIVAL_ANALYSIS)

    assert clf_prod is not None
    assert surv_prod is not None
    assert clf_prod.task_type == TaskType.BINARY_CLASSIFICATION
    assert surv_prod.task_type == TaskType.SURVIVAL_ANALYSIS
    assert surv_prod.model_family == ModelFamily.SURVIVAL
    assert "concordance_index" in surv_prod.evaluation_metrics


# =====================================================================
# 6. Experiment Tracking Promotion Bridge
# =====================================================================

def test_experiment_tracking_promotion(tmp_path):
    """Verify promoting a Phase 2.4 experiment creates a candidate model entry."""
    cat_file = tmp_path / "catalog_exp.json"
    audit_file = tmp_path / "audit_exp.jsonl"
    reg = ModelRegistry(catalog_path=cat_file, audit_path=audit_file)

    cand = reg.register_from_experiment(
        experiment_id="EXP-LOGI-1795181342",
        model_version="1.9.9",
        target_state=ModelLifecycleState.CANDIDATE,
    )
    assert cand.model_version == "1.9.9"
    assert cand.lifecycle_state == ModelLifecycleState.CANDIDATE
    assert cand.experiment_id == "EXP-LOGI-1795181342"
    assert cand.evaluation_metrics["pr_auc"] >= 0.40


# =====================================================================
# 7. Enhanced Inference: Latency & Dynamic Version Routing
# =====================================================================

def test_inference_latency_measurement():
    """Verify inference attaches latency measurement in ms."""
    predictor = ForgettingPredictor.instance()
    task = {
        "task_category": "Work",
        "priority": "HIGH",
        "location": "Office",
        "weekday": 2,
        "hour": 14,
        "deadline_distance_hours": 6.0,
        "previous_completion_count": 8,
        "previous_forgetting_count": 1,
        "historical_completion_rate": 0.88,
        "historical_forgetting_rate": 0.12,
        "task_frequency": 0.45,
        "tasks_today": 5,
        "interruptions_today": 3,
        "recent_context_switches": 2,
        "avg_interruption_duration": 4.5,
        "avg_session_duration": 30.0,
        "historical_postponements": 1,
        "avg_completion_duration_minutes": 45.0,
        "task_inactivity_duration_hours": 12.0,
        "deadline_extensions_count": 0,
        "interruption_latency_mean": 2.5,
        "interruption_frequency_1h": 1,
        "context_switch_burstiness": 0.2,
        "post_interruption_delay_mean": 3.0,
        "cumulative_fatigue_index": 0.35,
        "daily_schedule_fragmentation": 0.28,
        "circadian_rhythm_peak_distance": 1.5,
        "days_since_prior_forgetting": 14.0,
        "urgency_decay_rate": 0.15,
        "context_similarity_prior_lapse": 0.10,
    }

    res = predictor.predict_single(task)
    assert "inference_latency_ms" in res
    assert res["inference_latency_ms"] >= 0.0


def test_versioned_inference_selection():
    """Verify dynamic predictor routing respects version request with production fallback."""
    p_default = ForgettingPredictor.get_predictor_for_version(None)
    p_v11 = ForgettingPredictor.get_predictor_for_version("1.1.0")
    p_unknown = ForgettingPredictor.get_predictor_for_version("9.9.9")

    assert p_default.model_version == "1.1.0"
    assert p_v11.model_version == "1.1.0"
    assert p_unknown.model_version == "1.1.0"  # Graceful fallback


# =====================================================================
# 8. Administrative API Endpoints & Auth Verification
# =====================================================================

def test_models_public_endpoints():
    """Verify public model listing and health check."""
    # List models
    r = client.get("/models")
    assert r.status_code == 200
    data = r.json()
    assert data["total_models"] >= 2
    assert "models" in data

    # Production models
    r_prod = client.get("/models/production")
    assert r_prod.status_code == 200
    prod_data = r_prod.json()
    assert "binary_classification" in prod_data
    assert "survival_analysis" in prod_data

    # Metrics summary
    r_met = client.get("/models/metrics")
    assert r_met.status_code == 200
    met_data = r_met.json()
    assert "total_models" in met_data

    # Health check
    r_health = client.get("/models/health")
    assert r_health.status_code == 200
    health_data = r_health.json()
    assert health_data["status"] == "HEALTHY"


def test_admin_auth_protection_on_lifecycle_endpoints():
    """Verify unauthorized requests (missing X-Admin-Key) return 401."""
    # Attempt approval without admin auth
    r_unauth = client.post("/models/clf_logreg_v1.1.0/approve", json={"approved_by": "Hacker"})
    assert r_unauth.status_code == 401

    # Attempt rollback without admin auth
    r_roll_unauth = client.post(
        "/models/clf_logreg_v1.1.0/rollback",
        json={"target_version": "1.0.0"},
    )
    assert r_roll_unauth.status_code == 401


def test_batch_prediction_with_version_and_latency():
    """Verify POST /batch_predict returns total_latency_ms and model_version."""
    task = {
        "task_category": "Work",
        "priority": "HIGH",
        "location": "Office",
        "weekday": 2,
        "hour": 14,
        "deadline_distance_hours": 6.0,
        "previous_completion_count": 8,
        "previous_forgetting_count": 1,
        "historical_completion_rate": 0.88,
        "historical_forgetting_rate": 0.12,
        "task_frequency": 0.45,
        "tasks_today": 5,
        "interruptions_today": 3,
        "recent_context_switches": 2,
        "avg_interruption_duration": 4.5,
        "avg_session_duration": 30.0,
        "historical_postponements": 1,
        "avg_completion_duration_minutes": 45.0,
        "task_inactivity_duration_hours": 12.0,
        "deadline_extensions_count": 0,
        "interruption_latency_mean": 2.5,
        "interruption_frequency_1h": 1,
        "context_switch_burstiness": 0.2,
        "post_interruption_delay_mean": 3.0,
        "cumulative_fatigue_index": 0.35,
        "daily_schedule_fragmentation": 0.28,
        "circadian_rhythm_peak_distance": 1.5,
        "days_since_prior_forgetting": 14.0,
        "urgency_decay_rate": 0.15,
        "context_similarity_prior_lapse": 0.10,
    }

    req_payload = {
        "tasks": [task, task],
        "version": "1.1.0",
    }
    resp = client.post("/batch_predict", json=req_payload)
    assert resp.status_code == 200
    res_data = resp.json()
    assert len(res_data["predictions"]) == 2
    assert res_data["total_latency_ms"] >= 0.0
    assert res_data["model_version"] == "1.1.0"

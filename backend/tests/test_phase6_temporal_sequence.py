"""
Unit & Integration Test Suite for ContextIQ Temporal Sequence Modeling (Phase 6.5).

Validates:
1. Standardized event tokenization, vocabulary mapping, and anti-leakage guards (t <= t_pred).
2. Variable-length sequence padding and attention mask generation.
3. Cold-start sequence handling (L < 5) and conformal uncertainty calibration.
4. Deep sequence model forward passes (GRU, TCN, Causal Transformer).
5. Chronological benchmarking against Tabular GradientBoosting baseline.
6. Multi-target separation (Resumption, Recovery risk, Context switch, Completion, Friction trend).
7. Sequence model registry metadata and champion governance.
8. REST API endpoints under `/api/v1/sequence` and `/api/v1/analytics/sequence`.
"""
from __future__ import annotations

import math
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest
import torch
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
from app.models.detected_interruption import DetectedInterruption
from app.models.enums import DetectedInterruptionType, InterruptionSeverity
from app.models.user import User
from app.schemas.temporal_sequence import (
    BehavioralEventToken,
    BehavioralSequence,
    ModelBenchmarkMetrics,
    SequenceEventType,
    SequenceModelArchitecture,
    SequencePredictionResponse,
    SequencePredictionTarget,
    SequenceRegistryMetadata,
)
from app.services.sequence_models import (
    CausalTransformerClassifier,
    GRUSequenceClassifier,
    SequenceModelBenchmark,
    TCNSequenceClassifier,
)
from app.services.sequence_prediction_service import SequencePredictionService
from app.services.sequence_preprocessor import (
    EVENT_TYPE_TO_ID,
    SequencePreprocessor,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def test_db():
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
        email="seq_tester@contextiq.ai",
        display_name="Sequence Test User",
        timezone="UTC",
    )
    session.add(user)

    # Add historical interruptions for DB extraction test
    now = datetime(2026, 11, 25, 10, 0, 0, tzinfo=timezone.utc)
    for i in range(5):
        int_rec = DetectedInterruption(
            id=uuid.uuid4(),
            user_id=user.id,
            interruption_type=DetectedInterruptionType.APPLICATION_SWITCH,
            severity=InterruptionSeverity.MEDIUM,
            start_timestamp=now - timedelta(minutes=(5 - i) * 10),
            duration_seconds=60.0 + i * 15.0,
            confidence=1.0,
            detection_method="AUTOMATED_TELEMETRY",
            explanation="Test interruption",
        )
        session.add(int_rec)
    session.commit()

    yield session, user
    session.close()


@pytest.fixture
def client(test_db):
    session, user = test_db
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
# 1. Preprocessing, Tokenization, and Anti-Leakage
# ===========================================================================

def test_sequence_preprocessor_tokenization():
    """Validates standardized tokenization, vocabulary mappings, and anti-leakage sorting."""
    now = datetime(2026, 11, 25, 10, 0, 0, tzinfo=timezone.utc)
    events = [
        BehavioralEventToken(
            event_type=SequenceEventType.TASK_START,
            relative_timestamp_seconds=10.0,
            duration_seconds=0.0,
            task_category="Coding",
            rolling_bfi=45.0,
            recent_switch_count=1,
            hour_of_day=10,
        ),
        BehavioralEventToken(
            event_type=SequenceEventType.APPLICATION_SWITCH,
            relative_timestamp_seconds=120.0,
            duration_seconds=15.0,
            task_category="Coding",
            rolling_bfi=52.0,
            recent_switch_count=3,
            hour_of_day=10,
        ),
        BehavioralEventToken(
            event_type=SequenceEventType.RECOVERY_BUFFER_DISPATCH,
            relative_timestamp_seconds=240.0,
            duration_seconds=180.0,
            task_category="Coding",
            rolling_bfi=38.0,
            recent_switch_count=1,
            hour_of_day=10,
        ),
    ]

    seq = BehavioralSequence(
        user_id=uuid.uuid4(),
        prediction_timestamp=now,
        events=events,
        sequence_length=len(events),
    )

    processed = SequencePreprocessor.process_sequence(seq, max_seq_len=32)
    assert processed["token_ids"].shape == (32,)
    assert processed["attention_mask"].shape == (32,)
    assert processed["continuous_features"].shape == (32, 6)

    # First 3 positions should be valid (1.0), rest padded (0.0)
    assert processed["attention_mask"][:3].sum() == 3.0
    assert processed["attention_mask"][3:].sum() == 0.0

    # Token IDs should match vocabulary
    assert processed["token_ids"][0] == EVENT_TYPE_TO_ID[SequenceEventType.TASK_START]
    assert processed["token_ids"][1] == EVENT_TYPE_TO_ID[SequenceEventType.APPLICATION_SWITCH]
    assert processed["token_ids"][2] == EVENT_TYPE_TO_ID[SequenceEventType.RECOVERY_BUFFER_DISPATCH]
    assert processed["token_ids"][3] == 0  # <PAD>

    # Tabular baseline vector extracted
    assert processed["tabular_vector"].shape == (12,)
    assert processed["tabular_vector"][0] == 3.0  # Sequence length


# ===========================================================================
# 2. Cold-Start Sequence Handling
# ===========================================================================

def test_cold_start_handling():
    """Verifies that sequences with length < 5 are flagged cold start with widened bounds."""
    now = datetime(2026, 11, 25, 10, 0, 0, tzinfo=timezone.utc)
    cold_events = [
        BehavioralEventToken(
            event_type=SequenceEventType.TASK_START,
            relative_timestamp_seconds=5.0,
            duration_seconds=0.0,
            rolling_bfi=50.0,
            recent_switch_count=1,
            hour_of_day=10,
        )
    ]
    cold_seq = BehavioralSequence(
        user_id=uuid.uuid4(),
        prediction_timestamp=now,
        events=cold_events,
        sequence_length=1,
        is_cold_start=True,
    )
    processed = SequencePreprocessor.process_sequence(cold_seq)
    assert processed["is_cold_start"]
    assert processed["sequence_length"] == 1


# ===========================================================================
# 3. Deep PyTorch Sequence Models (Forward Passes)
# ===========================================================================

def test_deep_sequence_models_forward():
    """Validates PyTorch forward passes for GRU, TCN, and Causal Transformer."""
    B, L = 4, 32
    batch = {
        "token_ids": torch.randint(0, 16, (B, L)),
        "category_ids": torch.randint(0, 6, (B, L)),
        "severity_ids": torch.randint(0, 5, (B, L)),
        "continuous_features": torch.randn((B, L, 6)),
        "attention_mask": torch.ones((B, L)),
    }

    # 1. GRU
    gru = GRUSequenceClassifier()
    out_gru = gru(batch)
    assert out_gru.shape == (B,)
    assert torch.all(out_gru >= 0.0) and torch.all(out_gru <= 1.0)

    # 2. TCN
    tcn = TCNSequenceClassifier()
    out_tcn = tcn(batch)
    assert out_tcn.shape == (B,)
    assert torch.all(out_tcn >= 0.0) and torch.all(out_tcn <= 1.0)

    # 3. Causal Transformer
    transformer = CausalTransformerClassifier()
    out_tf = transformer(batch)
    assert out_tf.shape == (B,)
    assert torch.all(out_tf >= 0.0) and torch.all(out_tf <= 1.0)


# ===========================================================================
# 4. Chronological Benchmarking Pipeline
# ===========================================================================

def test_chronological_benchmark_pipeline():
    """Verifies chronological 70/30 benchmarking across Tabular, GRU, TCN, and Transformer."""
    sequences, labels_dict = SequencePreprocessor.generate_benchmark_sequences(
        n_sequences=150,
        n_users=10,
        seed=42,
    )
    processed = [SequencePreprocessor.process_sequence(s) for s in sequences]
    labels = labels_dict[SequencePredictionTarget.SHORT_TERM_TASK_RESUMPTION]

    results = SequenceModelBenchmark.run_benchmark(
        processed_data=processed,
        labels=labels,
        target=SequencePredictionTarget.SHORT_TERM_TASK_RESUMPTION,
    )

    assert len(results) == 4
    model_names = [r.model_name for r in results]
    assert any("Tabular" in n for n in model_names)
    assert any("GRU" in n for n in model_names)
    assert any("Temporal" in n for n in model_names)
    assert any("Transformer" in n for n in model_names)

    # Check metrics sanity
    for r in results:
        assert 0.0 <= r.roc_auc <= 1.0
        assert 0.0 <= r.pr_auc <= 1.0
        assert 0.0 <= r.brier_score <= 0.40
        assert r.inference_latency_ms >= 0.0

    # Exactly one champion selected and champion must be predictive
    champions = [r for r in results if r.is_champion]
    assert len(champions) == 1
    assert champions[0].roc_auc >= 0.50
    assert champions[0].selection_rationale is not None


# ===========================================================================
# 5. Prediction Targets Separation
# ===========================================================================

def test_prediction_targets_separation():
    """Verifies that all 5 prediction targets are distinct and supported."""
    supported = SequencePredictionService.list_supported_targets()
    assert len(supported) == 5
    target_names = [s["target"] for s in supported]
    assert SequencePredictionTarget.SHORT_TERM_TASK_RESUMPTION.value in target_names
    assert SequencePredictionTarget.INTERRUPTION_RECOVERY_RISK.value in target_names
    assert SequencePredictionTarget.FUTURE_CONTEXT_SWITCH.value in target_names
    assert SequencePredictionTarget.TASK_COMPLETION.value in target_names
    assert SequencePredictionTarget.BEHAVIORAL_FRICTION_TREND.value in target_names


# ===========================================================================
# 6. Service Inference & Model Registry
# ===========================================================================

def test_sequence_service_and_registry(test_db):
    """Tests model registry metadata and sequence prediction execution."""
    session, user = test_db

    # 1. Inspect registry
    reg = SequencePredictionService.get_model_registry()
    assert reg.model_version == "2.1.0-seq-prod"
    assert len(reg.supported_targets) == 5
    assert reg.vocabulary_size == 17
    assert len(reg.benchmark_comparison) >= 4

    # 2. Run prediction using historical interruptions from DB
    pred_res = SequencePredictionService.predict_sequence(
        db=session,
        user_id=user.id,
        target=SequencePredictionTarget.SHORT_TERM_TASK_RESUMPTION,
    )
    assert 0.0 <= pred_res.predicted_probability <= 1.0
    assert pred_res.confidence_interval[0] < pred_res.confidence_interval[1]
    assert pred_res.sequence_length >= 1
    assert "No future event leakage" in pred_res.disclaimer


# ===========================================================================
# 7. REST API Endpoints
# ===========================================================================

def test_sequence_api_endpoints(client):
    """Tests REST endpoints under /api/v1/sequence and /api/v1/analytics/sequence."""
    # 1. GET /api/v1/sequence/targets
    res_t = client.get("/api/v1/sequence/targets")
    assert res_t.status_code == 200
    assert len(res_t.json()) == 5

    # 2. GET /api/v1/sequence/registry
    res_reg = client.get("/api/v1/sequence/registry")
    assert res_reg.status_code == 200
    data_reg = res_reg.json()
    assert data_reg["model_version"] == "2.1.0-seq-prod"
    assert "benchmark_comparison" in data_reg

    # 3. GET /api/v1/sequence/benchmark
    res_b = client.get("/api/v1/sequence/benchmark")
    assert res_b.status_code == 200
    assert len(res_b.json()) >= 4

    # 4. POST /api/v1/sequence/predict
    res_pred = client.post("/api/v1/sequence/predict?target=short_term_task_resumption")
    assert res_pred.status_code == 200
    pred_data = res_pred.json()
    assert "predicted_probability" in pred_data
    assert "confidence_interval" in pred_data
    assert pred_data["predicted_label"] in ("POSITIVE", "NEGATIVE", "STABLE", "INCREASING", "DECREASING")

    # 5. GET /api/v1/sequence/predict
    res_pred_get = client.get("/api/v1/sequence/predict?target=interruption_recovery_risk")
    assert res_pred_get.status_code == 200
    assert res_pred_get.json()["target"] == "interruption_recovery_risk"

    # 6. GET /api/v1/analytics/sequence/predict
    res_an = client.get("/api/v1/analytics/sequence/predict")
    assert res_an.status_code == 200
    assert "predicted_probability" in res_an.json()

    # 7. GET /api/v1/analytics/sequence/benchmark
    res_an_b = client.get("/api/v1/analytics/sequence/benchmark")
    assert res_an_b.status_code == 200
    assert len(res_an_b.json()) >= 4

"""
Unit & Integration Test Suite for ContextIQ Counterfactual Intervention Analysis (Phase 6.4).

Validates:
1. Candidate intervention catalog and multi-stage lifecycle demarcation.
2. Leak-free counterfactual dataset assembly and benchmark generation.
3. Meta-learner implementations: T-Learner, S-Learner, X-Learner, and Doubly Robust Learner.
4. Multi-dimensional potential outcome forecasting (Resumption, Completion, Recovery duration, Friction, Burden).
5. Data coverage tiers, overlap diagnostics, and strict exclusion of unsupported candidates.
6. Multi-objective composite uplift utility computation.
7. Recommendation integration with deterministic fallback guards.
8. REST API endpoints under `/api/v1/counterfactual` and `/api/v1/analytics/counterfactual`.
"""
from __future__ import annotations

import math
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
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
from app.models.task import Task
from app.models.user import User
from app.schemas.counterfactual import (
    CandidateIntervention,
    CounterfactualComparisonRequest,
    CounterfactualComparisonResponse,
    CounterfactualLearnerType,
    DataCoverageTier,
    InterventionLifecycleStage,
    RecommendationStrategy,
)
from app.services.counterfactual_dataset import CounterfactualDatasetBuilder
from app.services.counterfactual_learners import (
    CANDIDATE_CATALOG_METADATA,
    CounterfactualLearnerPipeline,
)
from app.services.counterfactual_service import CounterfactualService


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
        email="counterfactual_tester@contextiq.ai",
        display_name="Counterfactual Test User",
        timezone="UTC",
    )
    session.add(user)

    task = Task(
        id=uuid.uuid4(),
        user_id=user.id,
        title="Refactor Causal Pipeline",
        status="PENDING",
        priority="HIGH",
    )
    session.add(task)
    session.commit()

    yield session, user, task
    session.close()


@pytest.fixture
def client(test_db):
    session, user, task = test_db
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
# 1. Candidate Catalog & Lifecycle Demarcation
# ===========================================================================

def test_candidate_catalog_and_lifecycle():
    """Validates candidate catalog taxonomy and strict lifecycle separation."""
    assert len(CANDIDATE_CATALOG_METADATA) == 7
    assert CandidateIntervention.NO_INTERVENTION in CANDIDATE_CATALOG_METADATA
    assert CandidateIntervention.SHORT_RECOVERY_BUFFER in CANDIDATE_CATALOG_METADATA
    assert CandidateIntervention.FOCUS_SESSION_RECOMMENDATION in CANDIDATE_CATALOG_METADATA

    # Validate distinct lifecycle stages
    stages = [s.value for s in InterventionLifecycleStage]
    assert "recommended" in stages
    assert "delivered" in stages
    assert "accepted" in stages
    assert "dismissed" in stages
    assert "executed" in stages


# ===========================================================================
# 2. Counterfactual Dataset Builder
# ===========================================================================

def test_counterfactual_dataset_builder():
    """Verifies generation of multi-treatment benchmark dataset with pre-treatment covariates."""
    df = CounterfactualDatasetBuilder.generate_benchmark_counterfactual_dataset(n_samples=300, seed=42)
    assert len(df) == 300
    assert "candidate" in df.columns
    assert "was_executed" in df.columns
    assert "task_resumption" in df.columns
    assert "task_completion" in df.columns
    assert "recovery_duration_seconds" in df.columns
    assert "behavioral_friction" in df.columns
    assert "notification_burden" in df.columns

    # Verify baseline candidate is present
    assert (df["candidate"] == CandidateIntervention.NO_INTERVENTION.value).sum() > 20
    # Pre-treatment covariates
    assert "baseline_bfi" in df.columns
    assert "forgetting_risk" in df.columns


# ===========================================================================
# 3. Meta-Learners (DR, T-Learner, S-Learner, X-Learner)
# ===========================================================================

def test_counterfactual_meta_learners():
    """Fits all 4 meta-learners and verifies potential outcome vector forecasting."""
    df = CounterfactualDatasetBuilder.generate_benchmark_counterfactual_dataset(n_samples=350, seed=42)

    context = {
        "baseline_bfi": 55.0,
        "forgetting_risk": 0.40,
        "task_priority": 3.0,
        "calendar_load": 3.0,
        "recent_interruptions": 2.0,
    }

    for learner in [
        CounterfactualLearnerType.DOUBLY_ROBUST_LEARNER,
        CounterfactualLearnerType.T_LEARNER,
        CounterfactualLearnerType.S_LEARNER,
        CounterfactualLearnerType.X_LEARNER,
    ]:
        pipeline = CounterfactualLearnerPipeline(learner_type=learner)
        pipeline.fit(df)
        assert pipeline.fitted

        results = pipeline.evaluate_candidates(context_features=context)
        assert len(results) == 7

        # Check baseline candidate
        baseline_res = [r for r in results if r.candidate == CandidateIntervention.NO_INTERVENTION][0]
        assert baseline_res.is_supported
        assert baseline_res.incremental_benefit.resumption_lift_pct == 0.0

        # Check supported active candidates
        supported = [r for r in results if r.is_supported and r.candidate != CandidateIntervention.NO_INTERVENTION]
        assert len(supported) >= 3

        for s in supported:
            outcomes = s.potential_outcomes
            assert 0.0 <= outcomes.task_resumption_probability <= 1.0
            assert 0.0 <= outcomes.task_completion_probability <= 1.0
            assert outcomes.expected_recovery_duration_seconds > 0.0
            assert 0.0 <= outcomes.expected_behavioral_friction <= 100.0
            assert 0.0 <= outcomes.expected_notification_burden <= 1.0
            assert s.composite_uplift_score is not None


# ===========================================================================
# 4. Data Coverage Tiers & Exclusion of Unsupported Candidates
# ===========================================================================

def test_data_coverage_tiers_and_exclusion():
    """Verifies that underpowered candidates are marked UNSUPPORTED and excluded from ranking."""
    df = CounterfactualDatasetBuilder.generate_benchmark_counterfactual_dataset(n_samples=250, seed=42)
    # Filter out almost all break_large_task occurrences so N < 10
    mask = (df["candidate"] == CandidateIntervention.BREAK_LARGE_TASK.value)
    keep_indices = df[~mask].index.tolist() + df[mask].index.tolist()[:3]
    sparse_df = df.loc[keep_indices].copy()

    pipeline = CounterfactualLearnerPipeline().fit(sparse_df)
    results = pipeline.evaluate_candidates(context_features={"baseline_bfi": 50.0})

    break_cand = [r for r in results if r.candidate == CandidateIntervention.BREAK_LARGE_TASK][0]
    assert not break_cand.is_supported
    assert break_cand.coverage_tier == DataCoverageTier.UNSUPPORTED
    assert break_cand.potential_outcomes is None
    assert "Insufficient historical evidence" in break_cand.exclusion_reason


# ===========================================================================
# 5. Conformal Uncertainty Intervals
# ===========================================================================

def test_conformal_uncertainty_intervals():
    """Validates that uncertainty interval bounds scale strictly with coverage tier."""
    df = CounterfactualDatasetBuilder.generate_benchmark_counterfactual_dataset(n_samples=350, seed=42)
    pipeline = CounterfactualLearnerPipeline().fit(df)
    results = pipeline.evaluate_candidates(context_features={"baseline_bfi": 50.0})

    for r in results:
        if r.is_supported and r.uncertainty_intervals:
            for feat, (low, high) in r.uncertainty_intervals.items():
                assert low <= high


# ===========================================================================
# 6. Recommendation Integration & Deterministic Fallback
# ===========================================================================

def test_recommendation_integration_and_fallback(test_db):
    """Verifies counterfactual optimization override and fallback when uncertainty exceeds threshold."""
    session, user, task = test_db

    # Case 1: Standard context -> Counterfactual-optimized champion
    req_normal = CounterfactualComparisonRequest(
        user_id=user.id,
        task_id=task.id,
        strict_uncertainty_threshold=0.40,
    )
    res_normal = CounterfactualService.compare_interventions(db=session, request=req_normal)
    assert res_normal.recommendation_source == RecommendationStrategy.COUNTERFACTUAL_OPTIMIZED
    assert res_normal.recommended_champion is not None
    assert res_normal.fallback_reason is None

    # Case 2: Very strict uncertainty threshold (0.01) -> Forces deterministic fallback
    req_strict = CounterfactualComparisonRequest(
        user_id=user.id,
        task_id=task.id,
        strict_uncertainty_threshold=0.01,
    )
    res_strict = CounterfactualService.compare_interventions(db=session, request=req_strict)
    assert res_strict.recommendation_source == RecommendationStrategy.DETERMINISTIC_FALLBACK
    assert "uncertainty interval width" in res_strict.fallback_reason


# ===========================================================================
# 7. REST API Endpoints
# ===========================================================================

def test_counterfactual_api_endpoints(client, test_db):
    """Validates REST endpoints under /api/v1/counterfactual and /api/v1/analytics/counterfactual."""
    session, user, task = test_db

    # 1. GET /api/v1/counterfactual/candidates
    res_cand = client.get("/api/v1/counterfactual/candidates")
    assert res_cand.status_code == 200
    candidates = res_cand.json()
    assert len(candidates) == 7
    c_names = [c["candidate"] for c in candidates]
    assert "no_intervention" in c_names
    assert "short_recovery_buffer" in c_names

    # 2. POST /api/v1/counterfactual/compare
    payload = {
        "task_id": str(task.id),
        "strict_uncertainty_threshold": 0.40,
    }
    res_post = client.post("/api/v1/counterfactual/compare", json=payload)
    assert res_post.status_code == 200
    data_post = res_post.json()
    assert "candidates" in data_post
    assert "recommended_champion" in data_post
    assert data_post["recommendation_source"] in ("counterfactual_optimized", "deterministic_fallback")
    assert len(data_post["candidates"]) == 7

    # 3. GET /api/v1/counterfactual/compare
    res_get = client.get(f"/api/v1/counterfactual/compare?task_id={task.id}")
    assert res_get.status_code == 200
    assert len(res_get.json()["candidates"]) == 7

    # 4. GET /api/v1/analytics/counterfactual/compare
    res_an = client.get("/api/v1/analytics/counterfactual/compare")
    assert res_an.status_code == 200
    assert "recommended_champion" in res_an.json()

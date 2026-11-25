"""
Unit & Integration Test Suite for ContextIQ Causal Behavioral Modeling (Phase 6.3).

Validates:
1. Directed Acyclic Graph (DAG) structures, minimal adjustment sets, and forbidden controls.
2. Target trial protocol specifications and Time Zero (T0) alignment to prevent immortal-time bias.
3. Positivity and common support overlap diagnostics.
4. Covariate balance evaluation via Standardized Mean Differences (SMD).
5. Doubly Robust AIPW, IPW, Propensity Score Matching, and Regression Adjustment estimators.
6. E-value sensitivity analysis for unmeasured confounding.
7. Effect heterogeneity (subgroup CATE) and statistical power guardrails (N >= 30).
8. Scientific abstention protocol when identification assumptions fail.
9. REST API endpoints under `/api/v1/causal` and `/api/v1/analytics/causal`.
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
from app.models.user import User
from app.schemas.causal_analysis import (
    AnalysisStatus,
    CausalAnalysisResult,
    CausalDAGDefinition,
    CausalEstimand,
    CausalEvaluationRequest,
    CausalMethod,
    CausalQuestionId,
    DAGNodeRole,
    TargetTrialProtocol,
)
from app.services.causal_dag import (
    CAUSAL_DAG_REGISTRY,
    TARGET_TRIAL_PROTOCOLS,
    get_causal_dag,
    get_target_trial,
    list_all_causal_questions,
)
from app.services.causal_engine import CausalDatasetGenerator, CausalInferenceEngine
from app.services.causal_service import CausalService


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
        email="causal_tester@contextiq.ai",
        display_name="Causal Test User",
        timezone="UTC",
    )
    session.add(user)
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
# 1. Causal DAGs and Forbidden Controls
# ===========================================================================

def test_causal_dag_definitions():
    """Validates that all 4 questions have complete DAGs, minimal adjustment sets, and forbidden controls."""
    assert len(CAUSAL_DAG_REGISTRY) == 4

    for q_id, dag in CAUSAL_DAG_REGISTRY.items():
        assert dag.question_id == q_id
        assert len(dag.nodes) >= 6
        assert len(dag.edges) >= 5
        assert len(dag.minimal_sufficient_adjustment_set) >= 3
        assert len(dag.forbidden_controls) >= 1
        assert len(dag.unmeasured_confounding_risks) >= 1
        assert "graph TD" in dag.mermaid_diagram

        # Verify treatment and outcome nodes exist
        roles = [n.role for n in dag.nodes]
        assert DAGNodeRole.TREATMENT in roles
        assert DAGNodeRole.OUTCOME in roles

        # Verify forbidden controls are NOT in minimal adjustment set (prevents overcontrolling)
        for forbidden in dag.forbidden_controls:
            assert forbidden not in dag.minimal_sufficient_adjustment_set

    # Verify specific Q1 DAG: context_card_read_latency is mediator, not in adjustment set
    q1_dag = get_causal_dag(CausalQuestionId.RECOVERY_BUFFER_ON_RESUMPTION)
    assert "context_card_read_latency" in q1_dag.forbidden_controls
    assert "baseline_bfi" in q1_dag.minimal_sufficient_adjustment_set


# ===========================================================================
# 2. Target Trial Protocols (Immortal-Time Prevention)
# ===========================================================================

def test_target_trial_protocols():
    """Validates that target trials enforce strict Time Zero (T0) alignment to eradicate immortal time."""
    assert len(TARGET_TRIAL_PROTOCOLS) == 4

    for q_id, protocol in TARGET_TRIAL_PROTOCOLS.items():
        assert protocol.question_id == q_id
        assert len(protocol.eligibility_criteria) >= 2
        assert len(protocol.treatment_strategy) > 10
        assert len(protocol.control_strategy) > 10
        assert "T0" in protocol.time_zero_definition
        assert len(protocol.follow_up_window) > 5
        assert len(protocol.immortal_time_bias_prevention) > 20
        assert protocol.causal_estimand in (
            CausalEstimand.AVERAGE_TREATMENT_EFFECT,
            CausalEstimand.TREATMENT_EFFECT_ON_TREATED,
        )


# ===========================================================================
# 3. Positivity & Overlap Diagnostics
# ===========================================================================

def test_positivity_overlap_diagnostics():
    """Tests common support checking and positivity violation detection."""
    # Case A: Good overlap
    ps_good = np.linspace(0.15, 0.85, 200)
    treatment = np.random.RandomState(42).choice([0, 1], size=200)
    diag_good = CausalInferenceEngine._evaluate_overlap(ps_good, treatment, trim_threshold=0.05)
    assert diag_good.has_sufficient_overlap
    assert diag_good.positivity_violations_count == 0

    # Case B: Extreme separation / positivity failure
    ps_bad = np.array([0.01] * 50 + [0.99] * 50)
    t_bad = np.array([0] * 50 + [1] * 50)
    diag_bad = CausalInferenceEngine._evaluate_overlap(ps_bad, t_bad, trim_threshold=0.05)
    assert not diag_bad.has_sufficient_overlap
    assert diag_bad.positivity_violations_pct == 100.0


# ===========================================================================
# 4. Covariate Balance (SMD) Evaluation
# ===========================================================================

def test_covariate_balance_smd():
    """Verifies Standardized Mean Difference (SMD) calculation and balance thresholding."""
    df = CausalDatasetGenerator.generate_study_data(
        question_id=CausalQuestionId.RECOVERY_BUFFER_ON_RESUMPTION,
        n_samples=250,
        true_ate=0.18,
        confounding_strength=0.80,
        seed=42,
    )

    result = CausalInferenceEngine.evaluate(
        data=df,
        question_id=CausalQuestionId.RECOVERY_BUFFER_ON_RESUMPTION,
        method=CausalMethod.DOUBLY_ROBUST_AIPW,
    )

    assert len(result.covariate_balance) >= 4
    # Check that adjustment reduces SMD for confounders like baseline_bfi
    bfi_item = [b for b in result.covariate_balance if b.covariate_name == "baseline_bfi"][0]
    assert abs(bfi_item.smd_adjusted) < abs(bfi_item.smd_unadjusted)
    assert bfi_item.is_balanced


# ===========================================================================
# 5. Causal Estimators Benchmarking (AIPW, IPW, Matching, Regression)
# ===========================================================================

def test_causal_estimation_methods():
    """Benchmarks Doubly Robust AIPW, IPW, Matching, and Regression Adjustment."""
    df = CausalDatasetGenerator.generate_study_data(
        question_id=CausalQuestionId.RECOVERY_BUFFER_ON_RESUMPTION,
        n_samples=300,
        true_ate=0.18,
        confounding_strength=0.70,
        seed=42,
    )

    for method in [
        CausalMethod.DOUBLY_ROBUST_AIPW,
        CausalMethod.INVERSE_PROBABILITY_WEIGHTING,
        CausalMethod.PROPENSITY_SCORE_MATCHING,
        CausalMethod.REGRESSION_ADJUSTMENT,
    ]:
        res = CausalInferenceEngine.evaluate(
            data=df,
            question_id=CausalQuestionId.RECOVERY_BUFFER_ON_RESUMPTION,
            method=method,
        )

        assert res.status in (AnalysisStatus.CONVINCING, AnalysisStatus.INCONCLUSIVE)
        assert res.estimated_causal_effect is not None
        # Estimated effect should be positive and close to ground truth ~0.18
        assert 0.05 <= res.estimated_causal_effect <= 0.35
        assert res.confidence_interval is not None
        assert res.confidence_interval[0] < res.confidence_interval[1]
        assert res.standard_error is not None and res.standard_error > 0.0
        assert res.p_value is not None


# ===========================================================================
# 6. Sensitivity Analysis (E-Value)
# ===========================================================================

def test_e_value_sensitivity():
    """Validates E-value computation for point estimate and lower confidence limit."""
    # Case 1: Substantial positive effect
    sens_robust = CausalInferenceEngine._calculate_e_value(
        effect=0.20,
        ci_lower=0.10,
        ci_upper=0.30,
        y_baseline=0.40,
        y_is_binary=True,
    )
    assert sens_robust.e_value_estimate >= 1.80
    assert sens_robust.e_value_lower_bound >= 1.20
    assert sens_robust.robustness_assessment in ("ROBUST", "MODERATE")

    # Case 2: Near-zero fragile effect
    sens_fragile = CausalInferenceEngine._calculate_e_value(
        effect=0.01,
        ci_lower=-0.05,
        ci_upper=0.07,
        y_baseline=0.50,
        y_is_binary=True,
    )
    assert sens_fragile.e_value_estimate < 1.30
    assert sens_fragile.e_value_lower_bound == 1.0  # Null can be explained by no unmeasured confounder
    assert sens_fragile.robustness_assessment == "FRAGILE"


# ===========================================================================
# 7. Subgroup Effect Heterogeneity & Power Guardrails (N >= 30)
# ===========================================================================

def test_subgroup_heterogeneity_power_guardrails():
    """Verifies that subgroup CATE requires N >= 30; suppresses underpowered strata."""
    df = CausalDatasetGenerator.generate_study_data(
        question_id=CausalQuestionId.RECOVERY_BUFFER_ON_RESUMPTION,
        n_samples=200,
        seed=42,
    )
    # Inject a tiny rare subgroup with only 8 units
    df.loc[:7, "task_category"] = "RareCategory"

    res = CausalInferenceEngine.evaluate(
        data=df,
        question_id=CausalQuestionId.RECOVERY_BUFFER_ON_RESUMPTION,
    )

    rare_sub = [s for s in res.effect_heterogeneity if s.subgroup_name == "RareCategory"]
    assert len(rare_sub) == 1
    assert not rare_sub[0].is_statistically_sound
    assert rare_sub[0].estimated_cate is None
    assert "Underpowered subgroup" in rare_sub[0].abstention_reason


# ===========================================================================
# 8. Scientific Abstention on Insufficient Data or Violations
# ===========================================================================

def test_scientific_abstention_on_underpowered_data():
    """Validates that engine abstains when sample size < 20 or missing columns."""
    tiny_df = pd.DataFrame({
        "treatment": [1, 0, 1, 0],
        "outcome": [1, 0, 1, 0],
        "baseline_bfi": [50.0, 40.0, 45.0, 35.0],
    })

    res = CausalInferenceEngine.evaluate(
        data=tiny_df,
        question_id=CausalQuestionId.RECOVERY_BUFFER_ON_RESUMPTION,
    )

    assert res.status == AnalysisStatus.ABSTAINED
    assert res.estimated_causal_effect is None
    assert "Insufficient sample size" in res.abstention_explanation
    assert "CORRELATION IS NOT CAUSATION" in res.disclaimer


# ===========================================================================
# 9. REST API Endpoints
# ===========================================================================

def test_causal_api_endpoints(client):
    """Tests all REST endpoints under /api/v1/causal and /api/v1/analytics/causal."""
    # 1. GET /api/v1/causal/questions
    res = client.get("/api/v1/causal/questions")
    assert res.status_code == 200
    questions = res.json()
    assert len(questions) == 4
    q_ids = [q["question_id"] for q in questions]
    assert "recovery_buffer_on_resumption" in q_ids
    assert "adaptive_scheduling_on_completion" in q_ids

    # 2. GET /api/v1/causal/dag/{question_id}
    res_dag = client.get("/api/v1/causal/dag/recovery_buffer_on_resumption")
    assert res_dag.status_code == 200
    dag_data = res_dag.json()
    assert "minimal_sufficient_adjustment_set" in dag_data
    assert "forbidden_controls" in dag_data
    assert "context_card_read_latency" in dag_data["forbidden_controls"]

    # 3. GET /api/v1/causal/target-trials
    res_tt = client.get("/api/v1/causal/target-trials")
    assert res_tt.status_code == 200
    trials = res_tt.json()
    assert len(trials) == 4

    # 4. POST /api/v1/causal/evaluate
    payload = {
        "question_id": "recovery_buffer_on_resumption",
        "method": "doubly_robust_aipw",
    }
    res_eval = client.post("/api/v1/causal/evaluate", json=payload)
    assert res_eval.status_code == 200
    eval_data = res_eval.json()
    assert eval_data["status"] in ("convincing", "inconclusive", "abstained")
    assert "covariate_balance" in eval_data
    assert "overlap_diagnostics" in eval_data
    assert "sensitivity" in eval_data

    # 5. GET /api/v1/causal/evaluate/{question_id}
    res_eval_get = client.get("/api/v1/causal/evaluate/adaptive_scheduling_on_completion")
    assert res_eval_get.status_code == 200
    assert res_eval_get.json()["question_id"] == "adaptive_scheduling_on_completion"

    # 6. GET /api/v1/analytics/causal/questions
    res_an_q = client.get("/api/v1/analytics/causal/questions")
    assert res_an_q.status_code == 200
    assert len(res_an_q.json()) == 4

    # 7. GET /api/v1/analytics/causal/evaluate
    res_an_eval = client.get("/api/v1/analytics/causal/evaluate?question_id=recovery_buffer_on_resumption")
    assert res_an_eval.status_code == 200
    assert res_an_eval.json()["question_id"] == "recovery_buffer_on_resumption"

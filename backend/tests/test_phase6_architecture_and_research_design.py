"""
Test Suite for ContextIQ Phase 6: Advanced Predictive Intelligence Architecture & Research Design.

Validates:
1. Target Definitions: All 7 Phase 6 predictive and survival targets are formally specified.
2. Cognitive Grounding Invariant: Inactivity and application switches are never conflated with cognitive interruption or resumption.
3. Causal Research Specification: DAGs, backdoor sets, and CATE contracts.
4. Statistical Power & Data Readiness Calculations: Exact mathematical verification of sample size formulas, Kish's Neff, EPV, and E-values.
5. Service Boundaries & Contracts: Conformal intervals, OPE, Pareto optimization, and trajectory schemas.
6. Documentation Artifact Integrity: Ensures Phase 6 markdown documentation files exist and meet architectural standards.
7. Backward Compatibility: Ensures Phase 1-5 database models and services remain intact.
"""
from __future__ import annotations

import math
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Add backend to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["APP_ENV"] = "development"
os.environ.setdefault("DATABASE_URL", "sqlite:///./_test_telemetry.db")

from app.schemas.predictive_intelligence import (
    CensoringType,
    CognitiveGroundingVerification,
    CognitiveStateVector,
    ConformalPredictionInterval,
    DAGNode,
    DAGSpecification,
    DataReadinessStatus,
    ModelingParadigm,
    OPEResult,
    ParetoScheduleProposal,
    PredictionTargetName,
    RecoveryPredictionRequest,
    RecoveryPredictionResponse,
    TargetDefinitionSpec,
    calculate_e_value,
    calculate_events_per_variable,
    calculate_kish_effective_sample_size,
    calculate_two_sample_required_n,
)


# ===========================================================================
# 1. Target Definition Specifications & Invariants
# ===========================================================================

def test_phase6_target_definitions():
    """Validates that all 7 prediction targets are properly defined with observation and outcome windows."""
    targets = [
        TargetDefinitionSpec(
            target_name=PredictionTargetName.COGNITIVE_RECOVERY_DURATION,
            unit_of_analysis="Interruption Episode",
            prediction_timestamp_description="At disruption termination",
            observation_window_minutes=120,
            outcome_window_minutes=60,
            label_construction_formula="inf { t >= 0 | Dwell >= 45s and ProductiveAction }",
            censoring_conditions=[CensoringType.RIGHT_CENSORED_ADMINISTRATIVE, CensoringType.RIGHT_CENSORED_COMPETING_RISK],
            exclusion_criteria=["Disruption < 15s", "No active task prior to disruption"],
            known_biases=["Survivorship bias", "Instrumentation bias"],
        ),
        TargetDefinitionSpec(
            target_name=PredictionTargetName.PROBABILITY_TASK_RESUMPTION,
            unit_of_analysis="Interruption Episode",
            prediction_timestamp_description="At interruption onset",
            observation_window_minutes=60,
            outcome_window_minutes=30,
            label_construction_formula="I(T_rec <= H and Status in {IN_PROGRESS, COMPLETED})",
            censoring_conditions=[CensoringType.RIGHT_CENSORED_USER_LOGOFF],
            exclusion_criteria=["Tasks completed before interruption onset"],
            known_biases=["Procrastination bias", "Self-selection bias"],
        ),
        TargetDefinitionSpec(
            target_name=PredictionTargetName.PROBABILITY_TASK_COMPLETION,
            unit_of_analysis="Task Instance",
            prediction_timestamp_description="Focus window start or morning sync",
            observation_window_minutes=1440,
            outcome_window_minutes=1440,
            label_construction_formula="I(exists t in W_out : Event == TASK_COMPLETED)",
            censoring_conditions=[CensoringType.RIGHT_CENSORED_POSTPONED],
            exclusion_criteria=["Deleted or cancelled tasks"],
            known_biases=["Outcome reporting bias"],
        ),
        TargetDefinitionSpec(
            target_name=PredictionTargetName.TIME_TO_FORGETTING,
            unit_of_analysis="Task Lifecycle",
            prediction_timestamp_description="Task creation timestamp",
            observation_window_minutes=10080,
            outcome_window_minutes=10080,
            label_construction_formula="inf { t >= 0 | Outcome in {EXPLICITLY_FORGOTTEN, ABANDONED} }",
            censoring_conditions=[CensoringType.RIGHT_CENSORED_ADMINISTRATIVE, CensoringType.RIGHT_CENSORED_COMPETING_RISK],
            exclusion_criteria=["Duration < 36s (0.01h)"],
            known_biases=["Inactivity conflation"],
        ),
        TargetDefinitionSpec(
            target_name=PredictionTargetName.EXPECTED_INTERVENTION_EFFECTIVENESS,
            unit_of_analysis="Intervention Opportunity",
            prediction_timestamp_description="Immediately prior to intervention dispatch",
            observation_window_minutes=30,
            outcome_window_minutes=30,
            label_construction_formula="0.35 * Delta_Lag + 0.30 * Delta_BFI + 0.25 * I(Resumed) - 0.10 * Disruption",
            censoring_conditions=[CensoringType.RIGHT_CENSORED_USER_LOGOFF],
            exclusion_criteria=["Critical deadlines < 2h"],
            known_biases=["Hawthorne / Novelty effect"],
        ),
        TargetDefinitionSpec(
            target_name=PredictionTargetName.EXPECTED_BEHAVIORAL_FRICTION,
            unit_of_analysis="Work Session",
            prediction_timestamp_description="At session initialization",
            observation_window_minutes=1440,
            outcome_window_minutes=240,
            label_construction_formula="100 * (0.30*P_lapse + 0.25*IntNorm + 0.20*SwitchNorm + 0.15*RecNorm + 0.10*VarNorm)",
            censoring_conditions=[CensoringType.RIGHT_CENSORED_ADMINISTRATIVE],
            exclusion_criteria=["Sessions < 5 minutes"],
            known_biases=["Tool-switching inflation"],
        ),
        TargetDefinitionSpec(
            target_name=PredictionTargetName.EXPECTED_NOTIFICATION_BURDEN,
            unit_of_analysis="Notification Dispatch Event",
            prediction_timestamp_description="Immediately before enqueue",
            observation_window_minutes=60,
            outcome_window_minutes=5,
            label_construction_formula="I(Action in {DISMISSED, NEGATIVE}) + 0.5 * I(SwitchAway)",
            censoring_conditions=[CensoringType.RIGHT_CENSORED_ADMINISTRATIVE],
            exclusion_criteria=["Silent background notifications"],
            known_biases=["Attention blindness"],
        ),
    ]
    assert len(targets) == 7
    target_names = {t.target_name for t in targets}
    assert len(target_names) == 7


# ===========================================================================
# 2. Cognitive Grounding Axiom Verification
# ===========================================================================

def test_cognitive_grounding_axiom():
    """
    Enforces the rule: Inactivity, application switching, or device return
    must NEVER be treated as definitive evidence of cognitive interruption or task resumption.
    """
    # Case 1: Inactivity alone (reading/thinking quiet state) -> NOT a genuine cognitive interruption
    quiet_reading = CognitiveGroundingVerification(
        has_sustained_dwell=False,
        dwell_seconds=240.0,
        has_productive_task_mutation=False,
        has_meaningful_interaction=False,
        is_idle_only=True,
    )
    assert not quiet_reading.is_genuine_cognitive_interruption

    # Case 2: Transient Alt-Tab glance (< 3s) -> NOT cognitive resumption
    transient_glance = CognitiveGroundingVerification(
        has_sustained_dwell=False,
        dwell_seconds=2.5,
        has_productive_task_mutation=False,
        has_meaningful_interaction=False,
        is_transient_glance=True,
    )
    assert not transient_glance.is_grounded_resumption

    # Case 3: App switch to IDE but no productive action (staring blankly) -> NOT cognitive resumption
    staring_blankly = CognitiveGroundingVerification(
        has_sustained_dwell=True,
        dwell_seconds=50.0,
        has_productive_task_mutation=False,
        has_meaningful_interaction=False,
    )
    assert not staring_blankly.is_grounded_resumption

    # Case 4: Sustained dwell + productive action (editing code / task event) -> GROUNDED RESUMPTION
    grounded_resumption = CognitiveGroundingVerification(
        has_sustained_dwell=True,
        dwell_seconds=60.0,
        has_productive_task_mutation=True,
        has_meaningful_interaction=True,
    )
    assert grounded_resumption.is_grounded_resumption


# ===========================================================================
# 3. Causal DAG Specifications
# ===========================================================================

def test_causal_dag_specifications():
    """Validates structural DAG specifications for ContextIQ causal research questions."""
    q1_dag = DAGSpecification(
        name="Q1_Intervention_On_Task_Resumption",
        nodes=[
            DAGNode(name="Intervention_A", node_type="TREATMENT"),
            DAGNode(name="Task_Resumption_Y", node_type="OUTCOME"),
            DAGNode(name="Cognitive_State_U", node_type="UNOBSERVED_CONFOUNDER"),
            DAGNode(name="Baseline_BFI_X1", node_type="OBSERVED_CONFOUNDER"),
            DAGNode(name="Task_Priority_X2", node_type="OBSERVED_CONFOUNDER"),
            DAGNode(name="Disruption_Duration_X3", node_type="OBSERVED_CONFOUNDER"),
            DAGNode(name="Reaction_Time_M", node_type="MEDIATOR"),
        ],
        edges=[
            ("Intervention_A", "Task_Resumption_Y"),
            ("Intervention_A", "Reaction_Time_M"),
            ("Reaction_Time_M", "Task_Resumption_Y"),
            ("Baseline_BFI_X1", "Intervention_A"),
            ("Baseline_BFI_X1", "Task_Resumption_Y"),
            ("Task_Priority_X2", "Intervention_A"),
            ("Task_Priority_X2", "Task_Resumption_Y"),
            ("Cognitive_State_U", "Task_Resumption_Y"),
        ],
        backdoor_adjustment_set=["Baseline_BFI_X1", "Task_Priority_X2", "Disruption_Duration_X3"],
        unobserved_confounders=["Cognitive_State_U"],
    )
    assert q1_dag.name.startswith("Q1")
    assert len(q1_dag.nodes) == 7
    assert len(q1_dag.backdoor_adjustment_set) == 3


# ===========================================================================
# 4. Statistical Power & Data Readiness Mathematical Formulas
# ===========================================================================

def test_power_and_sample_size_calculations():
    """Validates statistical sample size and power calculation helpers against exact analytical benchmarks."""
    # Two-sample difference in means (alpha=0.05, power=0.80)
    # For d = 0.20: N = 2 * ((1.96 + 0.8416) / 0.20)^2 = 2 * (2.8016 / 0.20)^2 = 2 * 14.008^2 = 2 * 196.224 = 392.45 -> ceil = 393
    n_small = calculate_two_sample_required_n(effect_size_d=0.20, alpha=0.05, power=0.80)
    assert n_small == 393

    # For d = 0.50: N = 2 * ((1.96 + 0.8416) / 0.50)^2 = 2 * (5.6032)^2 = 2 * 31.396 = 62.79 -> ceil = 63
    n_medium = calculate_two_sample_required_n(effect_size_d=0.50, alpha=0.05, power=0.80)
    assert n_medium == 63

    # Test error handling
    with pytest.raises(ValueError):
        calculate_two_sample_required_n(effect_size_d=-0.1)


def test_kish_effective_sample_size():
    """Validates Kish's Neff calculation for importance weights."""
    # Equal weights -> Neff == N
    weights_equal = [1.0] * 100
    assert calculate_kish_effective_sample_size(weights_equal) == 100.0

    # Extreme weights -> Neff collapses
    weights_skewed = [10.0] + [0.1] * 99
    # sum = 10 + 9.9 = 19.9; sum_sq = 100 + 99 * 0.01 = 100.99
    # Neff = 19.9^2 / 100.99 = 396.01 / 100.99 = 3.92
    neff_skewed = calculate_kish_effective_sample_size(weights_skewed)
    assert neff_skewed < 5.0
    assert neff_skewed == 3.92


def test_events_per_variable():
    """Validates EPV rule calculation for survival modeling."""
    # survival_tasks.csv empirical evidence: 2231 events across 8 covariates
    epv_tasks = calculate_events_per_variable(observed_events=2231, num_covariates=8)
    assert epv_tasks == 278.88
    assert epv_tasks >= 10.0  # Ready for Cox PH

    # detected_interruptions in test db: 28 events across 8 covariates
    epv_interruptions = calculate_events_per_variable(observed_events=28, num_covariates=8)
    assert epv_interruptions == 3.50
    assert epv_interruptions < 10.0  # NOT ready for Cox PH


def test_e_value_sensitivity_bounds():
    """Validates Ding & VanderWeele E-value computation for unmeasured confounding."""
    # RR = 1.5 -> E-val = 1.5 + sqrt(1.5 * 0.5) = 1.5 + sqrt(0.75) = 1.5 + 0.8660 = 2.366
    e_val_1 = calculate_e_value(point_estimate_rr=1.5)
    assert e_val_1 == 2.366

    # RR = 2.0 -> E-val = 2.0 + sqrt(2.0 * 1.0) = 2.0 + 1.414 = 3.414
    e_val_2 = calculate_e_value(point_estimate_rr=2.0)
    assert e_val_2 == 3.414

    # RR = 0.5 (protective) -> inverted RR = 2.0 -> E-val = 3.414
    e_val_prot = calculate_e_value(point_estimate_rr=0.5)
    assert e_val_prot == 3.414


# ===========================================================================
# 5. Service Boundaries & Schema Contracts
# ===========================================================================

def test_conformal_interval_validation():
    """Validates conformal prediction interval schema and invariant checks."""
    valid_interval = ConformalPredictionInterval(
        point_estimate=12.5,
        lower_bound=8.0,
        upper_bound=18.0,
        confidence_level=0.90,
        nonconformity_metric="absolute_residual",
    )
    assert valid_interval.point_estimate == 12.5

    with pytest.raises(ValueError, match="cannot exceed upper bound"):
        ConformalPredictionInterval(
            point_estimate=12.5,
            lower_bound=20.0,
            upper_bound=15.0,
            confidence_level=0.90,
            nonconformity_metric="absolute_residual",
        )


def test_recovery_prediction_contracts():
    """Validates Recovery Prediction Service request and response schemas."""
    user_id = uuid.uuid4()
    int_id = uuid.uuid4()
    req = RecoveryPredictionRequest(
        user_id=user_id,
        interruption_id=int_id,
        disruption_duration_seconds=120.0,
        baseline_bfi=42.5,
        context_switch_count_trailing_hour=4,
        hour_of_day=14,
    )
    assert req.hour_of_day == 14

    resp = RecoveryPredictionResponse(
        user_id=user_id,
        interruption_id=int_id,
        predicted_recovery_minutes=ConformalPredictionInterval(
            point_estimate=14.0,
            lower_bound=9.0,
            upper_bound=21.0,
            confidence_level=0.90,
            nonconformity_metric="studentized_residual",
        ),
        resumption_probability_15m=0.72,
        resumption_probability_30m=0.88,
        cognitive_grounding_verified=True,
        recommended_recovery_buffer_minutes=18.0,
    )
    assert resp.resumption_probability_15m == 0.72
    assert resp.cognitive_grounding_verified


def test_off_policy_evaluation_contracts():
    """Validates Counterfactual Evaluation OPE schema contracts."""
    ope = OPEResult(
        policy_name="LinUCB_v2_Contextual",
        estimated_value_snips=0.68,
        estimated_value_doubly_robust=0.71,
        effective_sample_size=312.4,
        weight_variance=0.18,
        is_statistically_reliable=True,
    )
    assert ope.effective_sample_size > 250.0
    assert ope.is_statistically_reliable


def test_pareto_scheduling_contracts():
    """Validates Multi-Objective Optimization Pareto scheduling proposal schema."""
    proposal = ParetoScheduleProposal(
        proposal_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        task_id=uuid.uuid4(),
        assigned_start=datetime.now(timezone.utc),
        assigned_end=datetime.now(timezone.utc) + timedelta(minutes=45),
        allocated_recovery_buffer_minutes=15.0,
        objective_scores={"urgency": 0.85, "hazard": 0.32, "fatigue": 0.25, "friction": 0.18},
        is_pareto_optimal=True,
        conformal_risk_bound=0.08,
    )
    assert proposal.is_pareto_optimal
    assert "hazard" in proposal.objective_scores


# ===========================================================================
# 6. Documentation Artifact Integrity
# ===========================================================================

def test_phase6_documentation_files_exist():
    """Verifies that all three Phase 6.1 specification documents exist and have substantial content."""
    root_dir = Path(__file__).resolve().parents[2]
    arch_doc = root_dir / "docs" / "phase-6" / "PHASE_6_ARCHITECTURE.md"
    research_doc = root_dir / "docs" / "phase-6" / "RESEARCH_DESIGN.md"
    readiness_doc = root_dir / "docs" / "phase-6" / "DATA_READINESS.md"

    for doc_path in (arch_doc, research_doc, readiness_doc):
        assert doc_path.exists(), f"Missing required document: {doc_path}"
        content = doc_path.read_text(encoding="utf-8")
        assert len(content) > 3000, f"Document {doc_path.name} is too short ({len(content)} chars)"

    # Verify specific architectural sections in PHASE_6_ARCHITECTURE.md
    arch_content = arch_doc.read_text(encoding="utf-8")
    assert "Recovery Prediction Service" in arch_content
    assert "Causal Analysis Service" in arch_content
    assert "Counterfactual Evaluation Service" in arch_content
    assert "Sequential Prediction Service" in arch_content
    assert "Personalized Survival Service" in arch_content
    assert "Multi-Objective Optimization Service" in arch_content
    assert "Uncertainty and Decision Support Service" in arch_content
    assert "Behavioral Simulation Service" in arch_content
    assert "mermaid" in arch_content

    # Verify specific sections in RESEARCH_DESIGN.md
    res_content = research_doc.read_text(encoding="utf-8")
    assert "Cognitive Recovery Duration" in res_content
    assert "Probability of Successful Task Resumption" in res_content
    assert "Time-to-Forgetting" in res_content
    assert "Cognitive Grounding Axiom" in res_content
    assert "Doubly Robust Off-Policy Evaluation" in res_content
    assert "Conformal Prediction" in res_content

    # Verify specific sections in DATA_READINESS.md
    readiness_content = readiness_doc.read_text(encoding="utf-8")
    assert "tasks_raw.csv" in readiness_content
    assert "survival_tasks.csv" in readiness_content
    assert "Events Per Variable" in readiness_content
    assert "Kish's Effective Sample Size" in readiness_content


# ===========================================================================
# 7. Backward Compatibility Check
# ===========================================================================

def test_phase1_to_5_models_backward_compatibility():
    """Ensures existing models from Phase 1 through Phase 5 can be imported and initialized without errors."""
    import app.models
    from app.models.task import Task
    from app.models.context_session import ContextSession
    from app.models.detected_interruption import DetectedInterruption
    from app.models.behavioral_profile import UserBehavioralProfile
    from app.models.user_intervention import UserIntervention
    from app.models.bandit_models import BanditArmState, BanditDecisionLog
    from app.models.effectiveness_models import InterventionOutcome
    from app.models.external_calendar_event import ExternalCalendarEvent
    from app.models.schedule_proposal import ScheduleProposal

    task = Task(id=uuid.uuid4(), title="Test Phase 6 Compatibility Task")
    assert task.title == "Test Phase 6 Compatibility Task"

    session = ContextSession(id=uuid.uuid4(), user_id=uuid.uuid4())
    assert session is not None

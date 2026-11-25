"""
Causal Behavioral Modeling and Confounding Analysis Schemas (ContextIQ Phase 6.3).

Defines:
- Causal research questions and estimands.
- Target trial protocols avoiding immortal-time bias.
- Directed Acyclic Graph (DAG) structures, adjustment sets, and forbidden controls.
- Overlap and common support diagnostics.
- Covariate balance metrics (Standardized Mean Differences - SMD).
- Doubly robust and propensity-based estimation outputs.
- E-value sensitivity analysis for unmeasured confounding.
- Effect heterogeneity (CATE) with statistical power guards.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field


class CausalQuestionId(str, Enum):
    RECOVERY_BUFFER_ON_RESUMPTION = "recovery_buffer_on_resumption"
    ADAPTIVE_SCHEDULING_ON_COMPLETION = "adaptive_scheduling_on_completion"
    PERSONALIZED_REMINDER_ON_ABANDONMENT = "personalized_reminder_on_abandonment"
    NOTIFICATION_TIMING_ON_FRICTION = "notification_timing_on_friction"


class CausalEstimand(str, Enum):
    AVERAGE_TREATMENT_EFFECT = "average_treatment_effect"  # ATE: E[Y(1) - Y(0)]
    TREATMENT_EFFECT_ON_TREATED = "treatment_effect_on_treated"  # ATT: E[Y(1) - Y(0) | A=1]
    CONDITIONAL_AVERAGE_TREATMENT_EFFECT = "conditional_average_treatment_effect"  # CATE: E[Y(1) - Y(0) | X=x]


class CausalMethod(str, Enum):
    DOUBLY_ROBUST_AIPW = "doubly_robust_aipw"
    INVERSE_PROBABILITY_WEIGHTING = "inverse_probability_weighting"
    PROPENSITY_SCORE_MATCHING = "propensity_score_matching"
    REGRESSION_ADJUSTMENT = "regression_adjustment"


class AnalysisStatus(str, Enum):
    CONVINCING = "convincing"          # Sufficient sample, overlap, balance, and sensitivity
    INCONCLUSIVE = "inconclusive"      # Imbalance remaining or weak sensitivity
    ABSTAINED = "abstained"            # Violations of positivity, power < minimum, or severe confounding


class DAGNodeRole(str, Enum):
    TREATMENT = "treatment"
    OUTCOME = "outcome"
    PRE_TREATMENT_CONFOUNDER = "pre_treatment_confounder"
    POST_TREATMENT_MEDIATOR = "post_treatment_mediator"  # MUST NOT be controlled for
    COLLIDER = "collider"                                # MUST NOT be controlled for
    EFFECT_MODIFIER = "effect_modifier"
    UNMEASURED_CONFOUNDER = "unmeasured_confounder"


class DAGNode(BaseModel):
    name: str = Field(..., description="Unique node variable name")
    role: DAGNodeRole = Field(..., description="Role in causal DAG")
    description: str = Field(..., description="Behavioral description")
    measurement_source: str = Field(..., description="Telemetry, database, or unmeasured")


class DAGEdge(BaseModel):
    from_node: str = Field(..., description="Source node name")
    to_node: str = Field(..., description="Target node name")
    description: str = Field(..., description="Causal mechanism description")


class CausalDAGDefinition(BaseModel):
    question_id: CausalQuestionId = Field(..., description="Target causal question")
    title: str = Field(..., description="Human-readable title")
    nodes: List[DAGNode] = Field(default_factory=list)
    edges: List[DAGEdge] = Field(default_factory=list)
    minimal_sufficient_adjustment_set: List[str] = Field(
        ..., description="Variables that MUST be conditioned on to block all backdoor paths"
    )
    forbidden_controls: List[str] = Field(
        ..., description="Variables that MUST NOT be conditioned on (colliders, post-treatment mediators)"
    )
    unmeasured_confounding_risks: List[str] = Field(
        ..., description="Identified unmeasured confounders that threaten exchangeability"
    )
    mermaid_diagram: str = Field(..., description="Mermaid diagram string representing the DAG")


class TargetTrialProtocol(BaseModel):
    question_id: CausalQuestionId = Field(..., description="Target causal question")
    title: str = Field(..., description="Trial title")
    eligibility_criteria: List[str] = Field(..., description="Explicit eligibility conditions")
    treatment_strategy: str = Field(..., description="Specific, unambiguous active treatment strategy")
    control_strategy: str = Field(..., description="Specific holdout or comparison strategy")
    time_zero_definition: str = Field(
        ..., description="Unambiguous Time Zero (T0) alignment to avoid immortal-time bias"
    )
    follow_up_window: str = Field(..., description="Fixed duration after T0 for outcome observation")
    outcome_definition: str = Field(..., description="Objective, non-leaking outcome metric")
    causal_estimand: CausalEstimand = Field(..., description="Primary estimand (e.g. ATE, ATT)")
    analysis_plan: str = Field(..., description="Statistical identification and adjustment strategy")
    immortal_time_bias_prevention: str = Field(
        ..., description="Explicit protocol preventing immortal-time bias"
    )


class CovariateBalanceItem(BaseModel):
    covariate_name: str = Field(..., description="Feature name")
    mean_treated: float = Field(..., description="Mean in treated cohort")
    mean_control: float = Field(..., description="Mean in control cohort")
    smd_unadjusted: float = Field(..., description="Standardized mean difference before adjustment")
    smd_adjusted: float = Field(..., description="Standardized mean difference after adjustment")
    is_balanced: bool = Field(..., description="True if |smd_adjusted| <= 0.10")


class OverlapDiagnostics(BaseModel):
    common_support_min: float = Field(..., description="Lower bound of common support")
    common_support_max: float = Field(..., description="Upper bound of common support")
    treated_propensity_mean: float = Field(..., description="Average propensity score among treated")
    control_propensity_mean: float = Field(..., description="Average propensity score among control")
    positivity_violations_count: int = Field(
        ..., description="Number of observations with propensity < eps or > 1-eps"
    )
    positivity_violations_pct: float = Field(
        ..., description="Percentage of observations outside safe overlap bounds"
    )
    has_sufficient_overlap: bool = Field(..., description="True if common support is adequate for inference")


class SensitivityAnalysis(BaseModel):
    e_value_estimate: float = Field(
        ..., description="E-value for the point estimate: min association strength to explain away effect"
    )
    e_value_lower_bound: float = Field(
        ..., description="E-value for the confidence interval bound closest to the null"
    )
    interpretation: str = Field(..., description="Practical interpretation of E-value against known biases")
    robustness_assessment: str = Field(
        ..., description="ROBUST, MODERATE, or FRAGILE against plausible unmeasured confounding"
    )


class SubgroupCATE(BaseModel):
    subgroup_name: str = Field(..., description="Name of the evaluated stratum")
    dimension: str = Field(..., description="Stratification dimension")
    sample_size_treated: int = Field(..., description="Treated count in stratum")
    sample_size_control: int = Field(..., description="Control count in stratum")
    estimated_cate: Optional[float] = Field(None, description="Stratum-specific conditional treatment effect")
    ci_lower: Optional[float] = Field(None, description="Lower 95% confidence limit")
    ci_upper: Optional[float] = Field(None, description="Upper 95% confidence limit")
    is_statistically_sound: bool = Field(
        ..., description="False if underpowered (N < 30) or overlap violated"
    )
    abstention_reason: Optional[str] = Field(None, description="Explanation when abstaining from CATE claim")


class CausalEvaluationRequest(BaseModel):
    question_id: CausalQuestionId = Field(..., description="Target causal question")
    method: CausalMethod = Field(
        default=CausalMethod.DOUBLY_ROBUST_AIPW, description="Preferred causal estimation method"
    )
    user_id: Optional[uuid.UUID] = Field(None, description="Filter to individual user if powered, else population")
    as_of: Optional[datetime] = Field(None, description="Evaluation timestamp cutoff")
    caliper: float = Field(default=0.20, description="Matching caliper as fraction of propensity SD")
    trim_propensity_threshold: float = Field(
        default=0.05, description="Positivity clipping threshold [eps, 1-eps]"
    )


class CausalAnalysisResult(BaseModel):
    question_id: CausalQuestionId = Field(..., description="Causal research question")
    title: str = Field(..., description="Human-readable title")
    status: AnalysisStatus = Field(..., description="CONVINCING, INCONCLUSIVE, or ABSTAINED")
    method_used: CausalMethod = Field(..., description="Statistical estimation method")
    target_trial: TargetTrialProtocol = Field(..., description="Target trial protocol specification")

    sample_size_treated: int = Field(..., description="Number of treated units")
    sample_size_control: int = Field(..., description="Number of control units")
    total_sample_size: int = Field(..., description="Total analyzed units")

    raw_observational_difference: float = Field(
        ..., description="Unadjusted observational difference mean(Y_T) - mean(Y_C)"
    )
    estimated_causal_effect: Optional[float] = Field(
        None, description="Adjusted causal treatment effect (e.g. ATE / ATT)"
    )
    confidence_interval: Optional[Tuple[float, float]] = Field(
        None, description="95% confidence interval [lower, upper]"
    )
    standard_error: Optional[float] = Field(None, description="Standard error of causal estimate")
    p_value: Optional[float] = Field(None, description="Two-tailed p-value against null effect")

    covariate_balance: List[CovariateBalanceItem] = Field(
        default_factory=list, description="Covariate balance table before and after adjustment"
    )
    overlap_diagnostics: OverlapDiagnostics = Field(..., description="Propensity overlap evaluation")
    sensitivity: Optional[SensitivityAnalysis] = Field(
        None, description="E-value sensitivity analysis for unmeasured confounding"
    )
    effect_heterogeneity: List[SubgroupCATE] = Field(
        default_factory=list, description="Subgroup conditional treatment effects (CATE)"
    )

    identification_assumptions: List[str] = Field(
        ..., description="Explicit identification assumptions required for causal validity"
    )
    limitations: List[str] = Field(
        ..., description="Methodological and measurement limitations"
    )
    abstention_explanation: Optional[str] = Field(
        None, description="Reason for abstaining or reporting inconclusive"
    )
    disclaimer: str = Field(
        default=(
            "CORRELATION IS NOT CAUSATION. Causal claims are valid strictly under the stated "
            "unverifiable identification assumptions (conditional exchangeability, positivity, "
            "consistency, and SUTVA). Predictive associations and feature weights must never be "
            "interpreted as causal intervention effects."
        ),
        description="Scientific integrity disclaimer",
    )

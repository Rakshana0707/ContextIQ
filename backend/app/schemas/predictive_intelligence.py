"""
Predictive Intelligence & Research Design Schemas for ContextIQ Phase 6.

Defines:
1. Target definitions for the 7 Phase 6 predictive and survival targets.
2. Cognitive Grounding criteria (distinguishing interface switching/inactivity from cognitive interruption/resumption).
3. Service contracts for the 8 Phase 6 architecture boundaries.
4. Statistical power, sample-size, and causal sensitivity helper functions.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PredictionTargetName(str, Enum):
    COGNITIVE_RECOVERY_DURATION = "cognitive_recovery_duration"
    PROBABILITY_TASK_RESUMPTION = "probability_task_resumption"
    PROBABILITY_TASK_COMPLETION = "probability_task_completion"
    TIME_TO_FORGETTING = "time_to_forgetting"
    EXPECTED_INTERVENTION_EFFECTIVENESS = "expected_intervention_effectiveness"
    EXPECTED_BEHAVIORAL_FRICTION = "expected_behavioral_friction"
    EXPECTED_NOTIFICATION_BURDEN = "expected_notification_burden"


class CensoringType(str, Enum):
    UNCENSORED_EVENT_OBSERVED = "uncensored_event_observed"
    RIGHT_CENSORED_ADMINISTRATIVE = "right_censored_administrative"
    RIGHT_CENSORED_COMPETING_RISK = "right_censored_competing_risk"
    RIGHT_CENSORED_POSTPONED = "right_censored_postponed"
    RIGHT_CENSORED_USER_LOGOFF = "right_censored_user_logoff"


class ModelingParadigm(str, Enum):
    SURVIVAL_ANALYSIS = "survival_analysis"
    INDIVIDUAL_LEVEL_MIXED_EFFECTS = "individual_level_mixed_effects"
    TEMPORAL_SEQUENCE_LEARNING = "temporal_sequence_learning"
    CAUSAL_INFERENCE = "causal_inference"
    COUNTERFACTUAL_ESTIMATION = "counterfactual_estimation"
    INTERVENTION_EFFECTIVENESS = "intervention_effectiveness"


class DataReadinessStatus(str, Enum):
    READY = "ready"
    MARGINAL = "marginal"
    INSUFFICIENT = "insufficient"


# ---------------------------------------------------------------------------
# Target Specification Models
# ---------------------------------------------------------------------------

class TargetDefinitionSpec(BaseModel):
    """Rigorous specification for a Phase 6 prediction or survival target."""
    target_name: PredictionTargetName
    unit_of_analysis: str
    prediction_timestamp_description: str
    observation_window_minutes: int
    outcome_window_minutes: int
    label_construction_formula: str
    censoring_conditions: List[CensoringType]
    exclusion_criteria: List[str]
    known_biases: List[str]
    requires_cognitive_grounding: bool = True


class CognitiveGroundingVerification(BaseModel):
    """
    Validates whether an observed event satisfies the Cognitive Grounding Axiom:
    Inactivity, application switching, or device return must NEVER be treated as
    definitive evidence of cognitive interruption or task resumption.
    """
    has_sustained_dwell: bool
    dwell_seconds: float
    has_productive_task_mutation: bool
    has_meaningful_interaction: bool
    is_idle_only: bool = False
    is_transient_glance: bool = False

    @property
    def is_grounded_resumption(self) -> bool:
        """Grounded resumption requires sustained dwell (>= 45s) and productive action, not just app activation."""
        if self.is_transient_glance or self.is_idle_only:
            return False
        return self.has_sustained_dwell and (self.has_productive_task_mutation or self.has_meaningful_interaction)

    @property
    def is_genuine_cognitive_interruption(self) -> bool:
        """Genuine cognitive interruption cannot be inferred purely from idle inactivity without corroboration."""
        if self.is_transient_glance:
            return False
        if self.is_idle_only:
            # Inactivity alone is ambiguous sensor drop-out, not cognitive interruption
            return False
        return self.has_sustained_dwell


# ---------------------------------------------------------------------------
# Service Contracts (Phase 6 Service Boundaries)
# ---------------------------------------------------------------------------

class ConformalPredictionInterval(BaseModel):
    """Calibrated prediction interval guaranteeing 1 - alpha finite-sample coverage."""
    point_estimate: float
    lower_bound: float
    upper_bound: float
    confidence_level: float = Field(default=0.90, ge=0.50, le=0.99)
    nonconformity_metric: str

    @model_validator(mode="after")
    def validate_bounds(self) -> "ConformalPredictionInterval":
        if self.lower_bound > self.upper_bound:
            raise ValueError(f"Lower bound ({self.lower_bound}) cannot exceed upper bound ({self.upper_bound})")
        return self


class RecoveryPredictionRequest(BaseModel):
    user_id: uuid.UUID
    interruption_id: uuid.UUID
    task_id: Optional[uuid.UUID] = None
    disruption_duration_seconds: float
    baseline_bfi: float
    context_switch_count_trailing_hour: int
    hour_of_day: int = Field(ge=0, le=23)


class RecoveryPredictionResponse(BaseModel):
    user_id: uuid.UUID
    interruption_id: uuid.UUID
    predicted_recovery_minutes: ConformalPredictionInterval
    resumption_probability_15m: float = Field(ge=0.0, le=1.0)
    resumption_probability_30m: float = Field(ge=0.0, le=1.0)
    cognitive_grounding_verified: bool
    recommended_recovery_buffer_minutes: float


class CATEEstimationResult(BaseModel):
    treatment_arm: str
    control_arm: str
    cate_estimate: float
    ci_lower: float
    ci_upper: float
    p_value: float = Field(ge=0.0, le=1.0)
    sample_size_treated: int
    sample_size_control: int
    e_value: float = Field(ge=1.0)
    propensity_overlap_passed: bool
    sutva_risk_flag: bool = False


class DAGNode(BaseModel):
    name: str
    node_type: str  # TREATMENT, OUTCOME, OBSERVED_CONFOUNDER, UNOBSERVED_CONFOUNDER, MEDIATOR, COLLIDER


class DAGSpecification(BaseModel):
    name: str
    nodes: List[DAGNode]
    edges: List[Tuple[str, str]]
    backdoor_adjustment_set: List[str]
    unobserved_confounders: List[str]


class OPEResult(BaseModel):
    policy_name: str
    estimated_value_snips: float
    estimated_value_doubly_robust: float
    effective_sample_size: float
    weight_variance: float
    is_statistically_reliable: bool


class CognitiveStateVector(BaseModel):
    user_id: uuid.UUID
    timestamp: datetime
    focus_depth: float = Field(ge=0.0, le=1.0)
    cognitive_fatigue: float = Field(ge=0.0, le=1.0)
    context_stability: float = Field(ge=0.0, le=1.0)
    attention_collapse_hazard: float = Field(ge=0.0, le=1.0)


class ParetoScheduleProposal(BaseModel):
    proposal_id: uuid.UUID
    user_id: uuid.UUID
    task_id: uuid.UUID
    assigned_start: datetime
    assigned_end: datetime
    allocated_recovery_buffer_minutes: float
    objective_scores: Dict[str, float]  # Urgency, Hazard, Fatigue, Calendar Friction
    is_pareto_optimal: bool = True
    conformal_risk_bound: float


# ---------------------------------------------------------------------------
# Statistical & Causal Calculation Utilities
# ---------------------------------------------------------------------------

def calculate_two_sample_required_n(
    effect_size_d: float,
    alpha: float = 0.05,
    power: float = 0.80,
) -> int:
    """
    Computes minimum sample size per arm for two-sample difference in means.
    Formula: N = 2 * ((z_{1 - alpha/2} + z_{power}) / d)^2
    """
    if effect_size_d <= 0.0:
        raise ValueError("Effect size Cohen's d must be strictly positive.")

    # Approximate inverse normal CDF constants
    z_alpha = 1.96 if abs(alpha - 0.05) < 0.01 else (2.576 if abs(alpha - 0.01) < 0.005 else 1.645)
    z_power = 0.8416 if abs(power - 0.80) < 0.01 else (1.2816 if abs(power - 0.90) < 0.01 else 0.5244)

    n_per_arm = 2.0 * math.pow((z_alpha + z_power) / effect_size_d, 2.0)
    return int(math.ceil(n_per_arm))


def calculate_kish_effective_sample_size(weights: Sequence[float]) -> float:
    """
    Calculates Kish's effective sample size for importance weighted samples:
    N_eff = (sum(w_i))^2 / sum(w_i^2)
    """
    if not weights:
        return 0.0
    sum_w = sum(weights)
    sum_sq_w = sum(w * w for w in weights)
    if sum_sq_w == 0.0:
        return 0.0
    return round((sum_w * sum_w) / sum_sq_w, 2)


def calculate_events_per_variable(observed_events: int, num_covariates: int) -> float:
    """
    Calculates Events Per Variable (EPV) for survival/binary logistic modeling.
    Peduzzi et al. guideline requires EPV >= 10.
    """
    if num_covariates <= 0:
        raise ValueError("Covariates count must be >= 1.")
    return round(float(observed_events) / float(num_covariates), 2)


def calculate_e_value(point_estimate_rr: float) -> float:
    """
    Calculates Ding & VanderWeele E-value for a Risk Ratio or Hazard Ratio:
    E-value = RR + sqrt(RR * (RR - 1))  if RR >= 1
    If RR < 1, invert RR first.
    """
    if point_estimate_rr <= 0.0:
        raise ValueError("Risk ratio must be strictly positive.")
    rr = point_estimate_rr if point_estimate_rr >= 1.0 else (1.0 / point_estimate_rr)
    e_val = rr + math.sqrt(rr * (rr - 1.0))
    return round(e_val, 3)

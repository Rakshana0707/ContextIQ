"""
Uncertainty-Aware Decision Support and Intelligent Abstention Schemas (ContextIQ Phase 6.8).

Defines:
- 5 Typed Abstention Outcomes (PREDICTION_AVAILABLE, PREDICTION_WITH_CAUTION,
  INSUFFICIENT_EVIDENCE, UNSUPPORTED_INPUT, MODEL_UNAVAILABLE).
- Explicit Abstention Reasons (Cold-start, OOD features, low telemetry quality, unseen events).
- Aleatoric vs Epistemic Uncertainty Decomposition.
- Calibration Assessment Schemas (ECE, MCE, Brier score, Reliability diagram bins).
- Conformal Prediction Interval Representations.
- Data Coverage & OOD Audit Indicators.
- Safe Decision Automation Policies.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field


class AbstentionOutcome(str, Enum):
    PREDICTION_AVAILABLE = "PREDICTION_AVAILABLE"          # High confidence, verified coverage; full automation permitted
    PREDICTION_WITH_CAUTION = "PREDICTION_WITH_CAUTION"    # Moderate uncertainty; action allowed with visible user caveat
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"        # Sparse user history / degraded telemetry; automated ranking withheld
    UNSUPPORTED_INPUT = "UNSUPPORTED_INPUT"                # Extreme OOD inputs or unseen events; system explicitly declines
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"                # Model uncalibrated, service offline, or data corrupted


class AbstentionReason(str, Enum):
    NONE = "NONE"
    INSUFFICIENT_USER_HISTORY = "INSUFFICIENT_USER_HISTORY"      # N_u < 5 (cold-start)
    OUT_OF_DISTRIBUTION = "OUT_OF_DISTRIBUTION"                  # Covariates violate training support (high Mahalanobis distance)
    LOW_TELEMETRY_QUALITY = "LOW_TELEMETRY_QUALITY"              # Monitored active hours ratio < 0.35
    UNSEEN_EVENT_TYPE = "UNSEEN_EVENT_TYPE"                      # Event tokens absent from vocabulary
    MISSING_CRITICAL_INPUTS = "MISSING_CRITICAL_INPUTS"          # Essential behavioral features absent
    HIGH_EPISTEMIC_UNCERTAINTY = "HIGH_EPISTEMIC_UNCERTAINTY"    # Model knowledge variance exceeds safety threshold
    UNSUPPORTED_INTERVENTION = "UNSUPPORTED_INTERVENTION"        # Lack of causal common support / overlap
    MODEL_UNCALIBRATED = "MODEL_UNCALIBRATED"                    # Expected Calibration Error exceeds tolerance (ECE > 0.15)


class UncertaintyType(str, Enum):
    ALEATORIC = "ALEATORIC"  # Inherent stochastic cognitive variability (cannot be eliminated with more data)
    EPISTEMIC = "EPISTEMIC"  # Model/data scarcity uncertainty (reducible with further observations)
    COMBINED = "COMBINED"


class ActionPolicyType(str, Enum):
    EXECUTE_AUTOMATED = "EXECUTE_AUTOMATED"                # Automatically rank and present interventions
    EXECUTE_WITH_CAUTION = "EXECUTE_WITH_CAUTION"          # Present recommendation with prominent uncertainty caveat
    FALLBACK_DETERMINISTIC = "FALLBACK_DETERMINISTIC"      # Suppress automated ML; use safe rule-based heuristic
    ABSTAIN_AND_PROMPT_USER = "ABSTAIN_AND_PROMPT_USER"    # Abstain completely; prompt user for clarification


class UncertaintyDecomposition(BaseModel):
    """
    Explicit breakdown of uncertainty into aleatoric (irreducible randomness)
    and epistemic (knowledge deficit / data sparsity).
    Never collapsed into an ambiguous single confidence percentage.
    """
    aleatoric_score: float = Field(..., ge=0.0, le=1.0, description="Inherent stochastic variability score")
    epistemic_score: float = Field(..., ge=0.0, le=1.0, description="Knowledge/data deficit score")
    total_uncertainty: float = Field(..., ge=0.0, le=1.0, description="Combined uncertainty metric")
    is_epistemic_dominant: bool = Field(..., description="True if epistemic uncertainty exceeds aleatoric")
    explanation: str = Field(..., description="Plain-language explanation of dominant uncertainty source")


class ReliabilityBin(BaseModel):
    bin_index: int
    bin_center: float
    observed_frequency: float
    predicted_frequency: float
    sample_count: int


class CalibrationMetrics(BaseModel):
    """Comprehensive calibration evaluation on held-out validation data."""
    calibration_method: str = Field(..., description="Platt Scaling, Isotonic Regression, or Temperature Scaling")
    expected_calibration_error: float = Field(..., ge=0.0, le=1.0, description="Expected Calibration Error (ECE)")
    maximum_calibration_error: float = Field(..., ge=0.0, le=1.0, description="Maximum Calibration Error (MCE)")
    brier_score: float = Field(..., ge=0.0, le=1.0, description="Proper scoring rule Brier score")
    is_well_calibrated: bool = Field(..., description="True if ECE < 0.08")
    reliability_bins: List[ReliabilityBin] = Field(default_factory=list, description="Calibration curve histogram")


class ConformalPredictionInterval(BaseModel):
    """Statistically valid finite-sample conformal prediction interval."""
    coverage_level: float = Field(default=0.90, description="Nominal marginal coverage probability (1 - alpha)")
    lower_bound: float = Field(..., description="Lower interval bound")
    upper_bound: float = Field(..., description="Upper interval bound")
    interval_width: float = Field(..., description="Width of prediction interval: upper - lower")
    calibration_sample_size: int = Field(..., description="Number of calibration residuals used")
    temporal_shift_warning: Optional[str] = Field(
        None, description="Notice if recent telemetry violates exchangeability assumption"
    )


class DataCoverageAudit(BaseModel):
    """Validation of input feature support and telemetry reliability."""
    user_sample_size: int = Field(..., description="Historical observations for this user")
    telemetry_quality_score: float = Field(..., ge=0.0, le=1.0, description="Continuity of monitored active hours")
    ood_distance: float = Field(..., ge=0.0, description="Normalized Mahalanobis or z-score distance from training support")
    is_out_of_distribution: bool = Field(..., description="True if input falls outside model training envelope")
    unseen_event_types: List[str] = Field(default_factory=list, description="Event tokens absent from vocabulary")
    missing_critical_inputs: List[str] = Field(default_factory=list, description="Unpopulated essential features")
    data_coverage_tier: str = Field(..., description="FULL, MODERATE, SPARSE, or INSUFFICIENT")


class ModelUncertaintyAuditItem(BaseModel):
    """Audit entry documenting uncertainty representation for an individual ContextIQ model family."""
    model_family: str = Field(..., description="Model name or architecture")
    target_name: str = Field(..., description="Prediction target")
    exposes_interval: bool = Field(..., description="Exposes conformal, quantile, or AFT bounds")
    interval_methodology: Optional[str] = Field(None, description="Quantile, Bootstrap, Conformal, or AFT parametric")
    decomposes_uncertainty: bool = Field(..., description="Separates aleatoric from epistemic")
    calibration_status: str = Field(..., description="Status of probability calibration (e.g. Platt, Isotonic, KM)")
    abstention_supported: bool = Field(..., description="Supports explicit abstention outcomes")
    known_limitations: str = Field(..., description="Documentation of failure modes and shift vulnerabilities")


class DecisionSupportRequest(BaseModel):
    user_id: Optional[uuid.UUID] = Field(None, description="Target User UUID")
    task_id: Optional[uuid.UUID] = Field(None, description="Active Task UUID if applicable")
    model_target: str = Field(
        default="forgetting_risk",
        description="Target model: forgetting_risk, recovery_duration, task_completion, or intervention_effectiveness",
    )
    context_features: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Point-in-time behavioral covariates"
    )
    strict_coverage_check: bool = Field(default=True, description="Enforce strict OOD and cold-start rejection")


class DecisionSupportResponse(BaseModel):
    decision_id: str = Field(..., description="Unique evaluation ID")
    user_id: uuid.UUID = Field(..., description="User ID")
    evaluated_at: datetime = Field(..., description="Evaluation timestamp")
    model_name: str = Field(..., description="Evaluated model architecture")
    
    # Intelligent Abstention Core
    abstention_outcome: AbstentionOutcome = Field(..., description="System decision outcome")
    abstention_reason: AbstentionReason = Field(..., description="Primary reason for outcome")
    can_automate_recommendation: bool = Field(..., description="True if automated decisioning is safe to execute")
    recommended_action_policy: ActionPolicyType = Field(..., description="Policy directive for downstream engines")

    # Prediction Estimates (Nullable if abstained)
    point_prediction: Optional[float] = Field(None, description="Raw model point forecast (if available)")
    calibrated_probability: Optional[float] = Field(None, description="Calibrated probability (if applicable)")

    # Uncertainty & Intervals
    uncertainty_decomposition: UncertaintyDecomposition = Field(
        ..., description="Decomposed aleatoric vs epistemic metrics"
    )
    prediction_interval: Optional[ConformalPredictionInterval] = Field(
        None, description="Valid prediction interval with stated coverage"
    )

    # Coverage & Audit
    data_coverage: DataCoverageAudit = Field(..., description="Telemetry and feature support audit")
    calibration_metrics: Optional[CalibrationMetrics] = Field(
        None, description="Calibration performance on held-out validation set"
    )

    user_facing_explanation: str = Field(..., description="Transparent user-facing explanation")
    disclaimer: str = Field(
        default="ContextIQ abstains from automated recommendations when data coverage is insufficient or uncertainty is excessive. Uncertainty is distinct from prediction probability.",
        description="Scientific and ethical governance notice",
    )

"""
schemas.py

Pydantic models defining the API contract. These mirror ml/features/feature_spec.py
exactly so that API validation and model feature construction never drift apart.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from ml.features.feature_spec import CATEGORY_DOMAIN, PRIORITY_DOMAIN, LOCATION_DOMAIN


class TaskFeatures(BaseModel):
    """Single task observation / prediction point."""

    task_id: Optional[str] = Field(None, description="Optional client-supplied task identifier")
    task_category: str = Field(..., description=f"One of {CATEGORY_DOMAIN}")
    priority: str = Field(..., description=f"One of {PRIORITY_DOMAIN}")
    location: str = Field(..., description=f"One of {LOCATION_DOMAIN}")

    weekday: int = Field(..., ge=0, le=6, description="0=Monday ... 6=Sunday")
    hour: int = Field(..., ge=0, le=23)
    deadline_distance_hours: float = Field(..., ge=0, description="Hours until deadline")

    previous_completion_count: int = Field(..., ge=0)
    previous_forgetting_count: int = Field(..., ge=0)
    historical_completion_rate: float = Field(..., ge=0, le=1)
    historical_forgetting_rate: float = Field(..., ge=0, le=1)
    task_frequency: float = Field(..., ge=0, le=1)

    tasks_today: int = Field(..., ge=0)
    interruptions_today: int = Field(..., ge=0)
    recent_context_switches: int = Field(..., ge=0)
    avg_interruption_duration: float = Field(..., ge=0)
    avg_session_duration: float = Field(..., ge=0)

    @field_validator("task_category")
    @classmethod
    def validate_category(cls, v):
        if v not in CATEGORY_DOMAIN:
            raise ValueError(f"task_category must be one of {CATEGORY_DOMAIN}")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v):
        if v not in PRIORITY_DOMAIN:
            raise ValueError(f"priority must be one of {PRIORITY_DOMAIN}")
        return v

    @field_validator("location")
    @classmethod
    def validate_location(cls, v):
        if v not in LOCATION_DOMAIN:
            raise ValueError(f"location must be one of {LOCATION_DOMAIN}")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task_id": "Lab Record",
                "task_category": "Academic",
                "priority": "HIGH",
                "location": "Campus",
                "weekday": 2,
                "hour": 14,
                "deadline_distance_hours": 18.0,
                "previous_completion_count": 12,
                "previous_forgetting_count": 8,
                "historical_completion_rate": 0.4,
                "historical_forgetting_rate": 0.55,
                "task_frequency": 0.3,
                "tasks_today": 5,
                "interruptions_today": 4,
                "recent_context_switches": 6,
                "avg_interruption_duration": 8.5,
                "avg_session_duration": 22.0,
            }
        }
    )


class PredictionResponse(BaseModel):
    task: Optional[str] = None
    prediction_probability: float  # Calibrated probability (backward-compatible)
    raw_probability: Optional[float] = None
    calibrated_probability: Optional[float] = None
    risk_level: str  # Backward-compatible 3-tier (LOW, MEDIUM, HIGH)
    risk_category: Optional[str] = None  # Phase 2.5 4-tier (LOW, MEDIUM, HIGH, CRITICAL)
    classification_threshold: Optional[float] = None
    calibration_version: str = "2.5.0"
    model_version: str
    top_features: List[str]
    action_recommendation: Optional[str] = None
    is_cold_start: bool = False
    cold_start_tier: Optional[str] = None
    confidence_interval: Optional[List[float]] = None
    inference_latency_ms: Optional[float] = None

    model_config = {'protected_namespaces': ()}


class BatchPredictionRequest(BaseModel):
    tasks: List[TaskFeatures]
    version: Optional[str] = None  # Optional version selection


class BatchPredictionResponse(BaseModel):
    predictions: List[PredictionResponse]
    total_latency_ms: Optional[float] = None
    model_version: Optional[str] = None

    model_config = {'protected_namespaces': ()}


class HealthResponse(BaseModel):
    status: str
    model_version: str
    model_name: str

    model_config = {'protected_namespaces': ()}


# =====================================================================
# Survival Analysis Schemas (Phase 2.3)
# =====================================================================

class SurvivalHorizonPrediction(BaseModel):
    horizon_hours: float
    survival_probability: float
    forgetting_risk: float
    ci_lower: float
    ci_upper: float


class SurvivalPredictionRequest(BaseModel):
    task: TaskFeatures
    horizons: Optional[List[float]] = Field(
        default=[6.0, 12.0, 24.0, 48.0, 168.0],
        description="List of forecast horizons in hours (e.g. [6, 12, 24, 48, 168])",
    )


class SurvivalPredictionResponse(BaseModel):
    task_id: Optional[str] = None
    prediction_timestamp: str
    horizons: List[SurvivalHorizonPrediction]
    median_survival_hours: Optional[float] = None
    model_version: str = "2.3.0"
    reliable_horizon_max_hours: float = 336.0
    is_extrapolated: bool = False

    model_config = {'protected_namespaces': ()}


class BatchSurvivalRequest(BaseModel):
    tasks: List[TaskFeatures]
    horizons: Optional[List[float]] = None


class BatchSurvivalResponse(BaseModel):
    predictions: List[SurvivalPredictionResponse]


class SurvivalMetricsResponse(BaseModel):
    model_version: str
    c_index_cox: float
    integrated_brier_score: float
    brier_scores_by_horizon: Dict[str, float]

    model_config = {'protected_namespaces': ()}


class SurvivalModelInfoResponse(BaseModel):
    model_name: str
    model_version: str
    hazard_ratios: Dict[str, float]
    supported_horizons_hours: List[float]
    reliable_range_hours: float

    model_config = {'protected_namespaces': ()}


# =====================================================================
# Explainability Schemas (Phase 2.7)
# =====================================================================

class FeatureAttribution(BaseModel):
    feature: str
    raw_feature: str
    display_name: str
    actual_value: Optional[Any] = None
    actual_value_formatted: Optional[str] = None
    shap_value: float
    direction: str
    magnitude: float
    description: str


class ExplanationResponse(BaseModel):
    task_id: Optional[str] = None
    calibrated_probability: float
    raw_probability: float
    base_value: float
    risk_category: str
    attributions: List[FeatureAttribution]
    all_attributions_count: int
    top_positive_factors: List[FeatureAttribution]
    top_negative_factors: List[FeatureAttribution]
    natural_language_explanation: str
    model_name: str
    model_version: str
    explanation_version: str = "2.7.0"
    is_cached: bool = False

    model_config = {'protected_namespaces': ()}


class BatchExplanationRequest(BaseModel):
    tasks: List[TaskFeatures]
    top_k: Optional[int] = 5


class BatchExplanationResponse(BaseModel):
    explanations: List[ExplanationResponse]


class GlobalFeatureImportanceItem(BaseModel):
    rank: int
    feature: str
    raw_feature: str
    display_name: str
    mean_abs_shap: float
    relative_importance_pct: float
    description: str


class GlobalInteractionItem(BaseModel):
    feature_a: str
    feature_b: str
    display_pair: str
    co_attribution_strength: float


class GlobalExplanationResponse(BaseModel):
    model_name: str
    model_version: str
    explanation_version: str = "2.7.0"
    global_importances: List[GlobalFeatureImportanceItem]
    top_interactions: List[GlobalInteractionItem]

    model_config = {'protected_namespaces': ()}


# =====================================================================
# Model Monitoring & Retraining Schemas (Phase 2.8)
# =====================================================================

class FeatureDriftItem(BaseModel):
    feature: str
    feature_type: str
    psi: Optional[float] = None
    ks_statistic: Optional[float] = None
    ks_p_value: Optional[float] = None
    js_divergence: Optional[float] = None
    drift_level: str  # "STABLE", "MODERATE", "DRIFT"
    missing_delta: Optional[float] = None


class DriftReportResponse(BaseModel):
    timestamp: str
    model_name: str
    model_version: str
    overall_status: str  # "STABLE", "MODERATE_WARNING", "DRIFT_DETECTED"
    feature_drift_status: str
    drifted_features_count: int
    moderate_features_count: int
    total_features_evaluated: int
    feature_details: Dict[str, Any]
    prediction_drift: Optional[Dict[str, Any]] = None
    concept_drift: Optional[Dict[str, Any]] = None
    retraining_trigger_recommendation: Optional[Dict[str, Any]] = None

    model_config = {'protected_namespaces': ()}


class RetrainingTriggerRequest(BaseModel):
    candidate_version: Optional[str] = "1.2.0"
    candidate_model_type: Optional[str] = "logistic_regression"


class RetrainingStatusResponse(BaseModel):
    status: str  # "IDLE", "PENDING_APPROVAL", "DEPLOYED", "REJECTED"
    candidate_version: Optional[str] = None
    current_champion_version: Optional[str] = None
    candidate_model_type: Optional[str] = None
    created_at: Optional[str] = None
    champion_metrics: Optional[Dict[str, float]] = None
    challenger_metrics: Optional[Dict[str, float]] = None
    delta_pr_auc: Optional[float] = None
    meets_promotion_criteria: Optional[bool] = None
    recommendation: Optional[str] = None
    reason: Optional[str] = None
    approved_by: Optional[str] = None
    deployed_at: Optional[str] = None

    model_config = {'protected_namespaces': ()}


class RetrainingApprovalRequest(BaseModel):
    approved_by: Optional[str] = "MLOps Admin"
    rationale: Optional[str] = "Approved challenger after temporal validation"


class RollbackRequest(BaseModel):
    target_version: Optional[str] = None
    approved_by: Optional[str] = "MLOps Admin"
    reason: Optional[str] = "Manual rollback initiated"


class RollbackResponse(BaseModel):
    status: str
    previous_version: str
    restored_version: str
    restored_from: str
    event: Dict[str, Any]

    model_config = {'protected_namespaces': ()}


class DeploymentHistoryResponse(BaseModel):
    total_events: int
    history: List[Dict[str, Any]]


# =====================================================================
# Model Registry Schemas (Phase 2.9)
# =====================================================================

class ModelMetadataResponse(BaseModel):
    model_id: str
    model_name: str
    model_version: str
    model_family: str
    task_type: str
    training_dataset_version: str
    feature_schema_version: str
    target_definition_version: str
    training_timestamp: str
    registered_at: str
    artifact_location: str
    artifact_checksum: str
    lifecycle_state: str
    updated_at: str
    evaluation_metrics: Dict[str, Any] = Field(default_factory=dict)
    calibration_config: Dict[str, Any] = Field(default_factory=dict)
    shap_compatibility: Dict[str, Any] = Field(default_factory=dict)
    description: Optional[str] = None
    experiment_id: Optional[str] = None
    approved_by: Optional[str] = None
    approval_notes: Optional[str] = None

    model_config = {'protected_namespaces': ()}


class ModelListResponse(BaseModel):
    total_models: int
    models: List[ModelMetadataResponse]

    model_config = {'protected_namespaces': ()}


class ModelApprovalRequest(BaseModel):
    approved_by: Optional[str] = "Lead Data Scientist"
    rationale: Optional[str] = "Approved after passing performance and calibration thresholds"


class ModelTransitionRequest(BaseModel):
    new_state: str
    actor: Optional[str] = "MLOps Admin"
    notes: Optional[str] = None


class ModelRegistryRollbackRequest(BaseModel):
    task_type: Optional[str] = "binary_classification"
    target_version: str
    approved_by: Optional[str] = "MLOps Admin"
    reason: Optional[str] = "Operational rollback triggered via Model Registry"


class ModelHealthResponse(BaseModel):
    status: str
    total_registered_models: int
    active_production_models: Dict[str, Any]
    integrity_verification: Dict[str, bool]

    model_config = {'protected_namespaces': ()}


class ModelMetricsSummaryResponse(BaseModel):
    total_models: int
    production_models: Dict[str, Any]
    models_by_state: Dict[str, int]
    models_by_family: Dict[str, int]

    model_config = {'protected_namespaces': ()}



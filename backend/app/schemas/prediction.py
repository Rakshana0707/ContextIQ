"""
Pydantic v2 schemas for predictive intelligence, forgetting risk, survival analysis,
and behavioral explainability (Phase 3.8).
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class RiskCategory(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TelemetryCoverageStatus(str, Enum):
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"


class SurvivalEstimatePoint(BaseModel):
    horizon_hours: float = Field(..., description="Prediction horizon in hours")
    survival_probability: float = Field(..., ge=0.0, le=1.0, description="Estimated probability S(t)")
    forgetting_risk: float = Field(..., ge=0.0, le=1.0, description="Estimated forgetting probability 1 - S(t)")
    ci_lower: float = Field(..., ge=0.0, le=1.0, description="Lower bound of 95% confidence interval")
    ci_upper: float = Field(..., ge=0.0, le=1.0, description="Upper bound of 95% confidence interval")


class BehavioralIndicators(BaseModel):
    recent_interruption_frequency: float = Field(..., description="Observed interruptions per hour in last 24h")
    median_resumption_lag_seconds: float = Field(..., description="Median recovery delay after interruptions")
    behavioral_friction_index: float = Field(..., ge=0.0, le=100.0, description="Calibrated Behavioral Friction Index")
    recovery_variability_std: float = Field(..., description="Standard deviation in recovery lags")
    session_fragmentation: float = Field(..., ge=0.0, le=1.0, description="Observed session fragmentation score")
    return_to_app_delay_seconds: float = Field(..., description="Delay to return to active work application")


class FeatureAvailability(BaseModel):
    telemetry_coverage: TelemetryCoverageStatus = Field(..., description="Quality tier of telemetry history")
    coverage_ratio: float = Field(..., ge=0.0, le=1.0, description="Ratio of monitored to expected active hours")
    is_cold_start: bool = Field(..., description="True if insufficient telemetry history required baseline imputation")
    observed_features: List[str] = Field(default_factory=list, description="Features derived from observed user activity")
    imputed_features: List[str] = Field(default_factory=list, description="Features imputed from population baselines")


class PredictionReason(BaseModel):
    feature: str = Field(..., description="Feature display name")
    impact: float = Field(..., description="Directional impact on risk score (-1.0 to 1.0)")
    description: str = Field(..., description="Human-intelligible behavioral explanation")
    is_observed: bool = Field(default=True, description="Whether reason is derived from direct telemetry")


class TaskPredictionResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    id: str = Field(..., description="Prediction record UUID")
    task_id: str = Field(..., description="Target task UUID")
    task_title: str = Field(..., description="Title of the predicted task")
    forgetting_probability: float = Field(..., ge=0.0, le=1.0, description="Probability of forgetting (0.0 to 1.0)")
    risk_score: float = Field(..., ge=0.0, le=100.0, description="Scaled risk score (0 to 100)")
    risk_category: RiskCategory = Field(..., description="Calibrated risk category")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Model confidence score")
    confidence_discount_applied: bool = Field(..., description="Whether confidence was penalized due to cold start")
    survival_estimates: List[SurvivalEstimatePoint] = Field(default_factory=list, description="Multi-horizon survival curve")
    median_survival_hours: Optional[float] = Field(None, description="Estimated time in hours until S(t) <= 0.5")
    behavioral_indicators: BehavioralIndicators = Field(..., description="Key observed behavioral telemetry metrics")
    feature_availability: FeatureAvailability = Field(..., description="Feature availability and telemetry coverage metadata")
    reasons: List[PredictionReason] = Field(default_factory=list, description="SHAP and evidence-backed reason attributions")
    model_version: str = Field(..., description="Model and feature schema version")
    prediction_timestamp: datetime = Field(..., description="UTC timestamp when prediction was computed")
    cognitive_disclaimer: str = Field(
        default="Behavioral indicators reflect observable application focus, switching, and idle patterns, not direct cognitive or mental state measurements.",
        description="Disclaimer establishing non-invasive behavioral framing"
    )


class ForgettingPrediction(BaseModel):
    """Backward-compatible response model matching the original Phase 1/2 API contract."""
    id: str
    taskId: str
    taskTitle: str
    riskScore: float
    riskLevel: str
    reasons: List[PredictionReason]
    generatedAt: str
    modelVersion: str
    telemetryCoverage: Optional[str] = None
    survivalEstimates: Optional[List[SurvivalEstimatePoint]] = None

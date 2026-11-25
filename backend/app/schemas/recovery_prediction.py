"""
Pydantic Schemas for Cognitive Recovery Duration Prediction (Phase 6.2).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator


class RecoveryState(str, Enum):
    """
    Granular states of cognitive recovery following an interruption.
    Distinguishes hardware/application return from confirmed task resumption.
    """
    INTERRUPTION_DETECTED = "INTERRUPTION_DETECTED"
    APP_OR_TASK_REVISITED = "APP_OR_TASK_REVISITED"
    ORIGINAL_CONTEXT_RESTORED = "ORIGINAL_CONTEXT_RESTORED"
    CONFIRMED_TASK_RESUMPTION = "CONFIRMED_TASK_RESUMPTION"
    TASK_COMPLETED = "TASK_COMPLETED"
    RECOVERY_NOT_OBSERVED = "RECOVERY_NOT_OBSERVED"


class RecoveryConfidenceTier(str, Enum):
    COLD_START = "COLD_START"
    EMERGING = "EMERGING"
    ESTABLISHED = "ESTABLISHED"
    CONFIDENT = "CONFIDENT"


class RecoveryContributingFactor(BaseModel):
    feature_name: str
    impact_minutes: float
    direction: str  # "INCREASES_RECOVERY" | "DECREASES_RECOVERY"
    explanation: str


class RecoveryPredictionInterval(BaseModel):
    lower_seconds: float
    upper_seconds: float
    lower_minutes: float
    upper_minutes: float
    confidence_level: float = 0.90

    @model_validator(mode="after")
    def check_bounds(self) -> "RecoveryPredictionInterval":
        if self.lower_seconds > self.upper_seconds:
            raise ValueError("lower_seconds cannot exceed upper_seconds")
        return self


class RecoveryPredictionRequest(BaseModel):
    user_id: Optional[uuid.UUID] = None
    interruption_id: Optional[uuid.UUID] = None
    task_id: Optional[uuid.UUID] = None
    interruption_duration_seconds: Optional[float] = None
    interruption_type: Optional[str] = "APPLICATION_SWITCH"
    interruption_severity: Optional[str] = "MEDIUM"
    task_category: Optional[str] = "DeepWork"
    task_priority: Optional[str] = "MEDIUM"
    task_complexity: Optional[float] = 1.0
    hour_of_day: Optional[int] = None
    day_of_week: Optional[int] = None
    recent_context_switches: Optional[int] = None
    as_of: Optional[datetime] = None


class RecoveryPredictionResponse(BaseModel):
    user_id: uuid.UUID
    prediction_timestamp: datetime
    estimated_recovery_duration_seconds: float
    estimated_recovery_duration_minutes: float
    median_recovery_duration_minutes: float
    recovery_probabilities: Dict[str, float]  # e.g. {"5m": 0.32, "15m": 0.68, "30m": 0.89, "60m": 0.97}
    confidence_interval: RecoveryPredictionInterval
    confidence_tier: RecoveryConfidenceTier
    is_personalized: bool
    model_version: str
    main_contributing_factors: List[RecoveryContributingFactor] = Field(default_factory=list)
    recovery_state_at_prediction: RecoveryState = RecoveryState.INTERRUPTION_DETECTED
    disclaimer: str = (
        "Estimates reflect empirical behavioral re-engagement delays, "
        "not neurological exhaustion or diagnostic clinical state."
    )


class RecoveryDatasetRecord(BaseModel):
    """
    Leak-free time-to-event recovery observation.
    """
    interruption_id: str
    user_id: str
    task_id: Optional[str] = None
    prediction_timestamp: datetime
    interruption_duration_seconds: float
    interruption_type: str
    interruption_severity: str
    pre_interruption_task_category: str
    task_priority: str
    task_complexity: float = 1.0
    previous_recovery_duration_mean: float
    previous_recovery_duration_median: float
    hour_of_day: int
    day_of_week: int
    recent_context_switches: int
    behavioral_friction_index: float
    previous_task_resumption_rate: float
    has_calendar_event_next_hour: bool = False
    calendar_slack_minutes: float = 60.0
    device_type: str = "DESKTOP"

    # Outcome & Censoring labels
    duration_seconds: float
    event_observed: int  # 1 = confirmed resumption, 0 = censored
    recovery_state: RecoveryState
    censoring_reason: Optional[str] = None


class RecoveryBenchmarkMetrics(BaseModel):
    model_name: str
    concordance_index: float
    integrated_brier_score: float
    time_dependent_auc_15m: float
    time_dependent_auc_30m: float
    brier_score_15m: float
    brier_score_30m: float
    sample_size_train: int
    sample_size_test: int


class RecoveryBenchmarkComparisonResponse(BaseModel):
    evaluation_timestamp: datetime
    split_method: str
    models: List[RecoveryBenchmarkMetrics]
    champion_model: str
    data_readiness_status: str

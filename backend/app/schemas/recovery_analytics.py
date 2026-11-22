import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ResumptionDelayTiers(BaseModel):
    """
    Granular three-tier resumption delay breakdown distinguishing
    hardware input, application window return, and confirmed task focus.
    """
    return_to_device_delay_seconds: Optional[float] = None
    return_to_app_delay_seconds: Optional[float] = None
    confirmed_task_resumption_delay_seconds: Optional[float] = None
    is_estimated: bool = True
    sample_count: int = 0


class RecoveryMetricsResponse(BaseModel):
    user_id: uuid.UUID
    period_days: int

    # Core resumption statistics
    mean_resumption_lag_seconds: Optional[float] = None
    median_resumption_lag_seconds: Optional[float] = None
    recovery_time_variability: Optional[float] = None  # Standard deviation of resumption lag
    coefficient_of_variation: Optional[float] = None

    # Frequency & Density
    interruption_frequency: float = 0.0  # Interruptions per active hour
    interruption_density: float = 0.0    # Ratio of session time in interruption state
    context_switching_frequency: float = 0.0  # Context switches per hour
    consecutive_interruption_count: int = 0   # Max interruption cluster (< 5m apart)
    average_focus_duration_minutes: Optional[float] = None

    # Granular delays
    delays_by_tier: ResumptionDelayTiers

    # Categorical recovery costs
    recovery_cost_by_category: Dict[str, float] = Field(default_factory=dict)
    recovery_cost_by_application: Dict[str, float] = Field(default_factory=dict)

    # Scientific disclaimer
    disclaimer: str = (
        "Behavioral proxies reflect observed interface activity and recovery intervals, "
        "not direct cognitive or mental state."
    )


class BehavioralFrictionResponse(BaseModel):
    user_id: uuid.UUID
    period_days: int
    overall_score: float  # Bounded [0, 100]

    # Sub-scores
    forgetting_score: float
    interruption_score: float
    context_switch_score: float
    recovery_score: float
    variability_score: float

    telemetry_adjusted: bool = True
    explanation: str
    contributing_factors: List[str] = Field(default_factory=list)


class ContextSliceMetrics(BaseModel):
    observation_count: int
    mean_resumption_lag_seconds: Optional[float] = None
    interruption_count: int
    insufficient_data: bool = False


class InterruptionTrendsResponse(BaseModel):
    user_id: uuid.UUID
    period_days: int

    by_time_of_day: Dict[str, ContextSliceMetrics] = Field(default_factory=dict)
    by_day_of_week: Dict[str, ContextSliceMetrics] = Field(default_factory=dict)
    by_application_context: Dict[str, ContextSliceMetrics] = Field(default_factory=dict)
    by_interruption_type: Dict[str, ContextSliceMetrics] = Field(default_factory=dict)
    hourly_interruption_density: Dict[int, float] = Field(default_factory=dict)


class PersonalBaselineResponse(BaseModel):
    user_id: uuid.UUID
    baseline_period_days: int = 14

    # Baseline averages
    baseline_mean_resumption_lag: Optional[float] = None
    baseline_friction_score: Optional[float] = None
    baseline_interruption_frequency: Optional[float] = None

    # Current period metrics
    current_mean_resumption_lag: Optional[float] = None
    current_friction_score: Optional[float] = None
    current_interruption_frequency: Optional[float] = None

    # Comparative ratios (Current / Baseline)
    resumption_lag_ratio: Optional[float] = None
    friction_ratio: Optional[float] = None
    interruption_frequency_ratio: Optional[float] = None

    trend_direction: str = "INSUFFICIENT_DATA"  # IMPROVING, STABLE, ELEVATED_FRICTION, INSUFFICIENT_DATA
    has_sufficient_history: bool = False

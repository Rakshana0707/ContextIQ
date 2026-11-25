"""
Personalized Dynamic Survival and Time-to-Event Schemas (ContextIQ Phase 6.6).

Defines:
- 4 Separate Survival Event Targets: Task abandonment, Task completion, Confirmed task resumption, Confirmed recovery.
- Personalization Tiers: Individual, Group-level, Population baseline.
- Dynamic update triggers: Interruption, Deadline approach, State change, User interaction, Context change.
- Multi-horizon survival curves S(t) and cumulative hazard F(t) with conformal uncertainty bounds.
- Model registry and time-to-event benchmark metrics (C-index, Time-dependent AUC, IBS).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field


class SurvivalEventTarget(str, Enum):
    TASK_ABANDONMENT = "task_abandonment"                      # Prospective memory lapse / abandonment
    TASK_COMPLETION = "task_completion"                        # Successful task completion on time
    CONFIRMED_TASK_RESUMPTION = "confirmed_task_resumption"    # Active grounded resumption after disruption
    CONFIRMED_RECOVERY = "confirmed_recovery"                  # Cognitive recovery back to baseline throughput


class PersonalizationTier(str, Enum):
    INDIVIDUAL = "individual"    # N_u >= 30: fully personalized empirical Bayes
    GROUP = "group"              # 10 <= N_u < 30: hierarchical partial pooling by category/role
    POPULATION = "population"    # N_u < 10: calibrated population baseline with widened uncertainty


class DynamicUpdateTrigger(str, Enum):
    NEW_INTERRUPTION = "new_interruption"
    DEADLINE_APPROACHING = "deadline_approaching"
    TASK_STATE_CHANGE = "task_state_change"
    USER_INTERACTION = "user_interaction"
    CONTEXT_CHANGE = "context_change"
    CALENDAR_CONFLICT = "calendar_conflict"
    PERIODIC_TICK = "periodic_tick"


class SurvivalCurvePoint(BaseModel):
    """Single point along survival curve S(t)."""
    horizon_value: float = Field(..., description="Time horizon value (hours or minutes)")
    horizon_label: str = Field(..., description="Human-readable label (e.g. '15m', '1h', '24h')")
    survival_probability: float = Field(..., ge=0.0, le=1.0, description="S(t) = P(T > t)")
    cumulative_event_probability: float = Field(..., ge=0.0, le=1.0, description="F(t) = 1 - S(t)")
    confidence_interval: Tuple[float, float] = Field(
        ..., description="90% conformal / asymptotic uncertainty interval [lower, upper]"
    )


class DynamicSurvivalPredictionRequest(BaseModel):
    target: SurvivalEventTarget = Field(..., description="Target time-to-event outcome")
    user_id: Optional[uuid.UUID] = Field(None, description="User UUID")
    task_id: Optional[uuid.UUID] = Field(None, description="Associated task UUID if applicable")
    current_time_elapsed: float = Field(
        default=0.0, ge=0.0, description="Elapsed time t_curr since sequence/task initialization"
    )
    context_features: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Point-in-time features at update timestamp"
    )
    update_trigger: DynamicUpdateTrigger = Field(
        default=DynamicUpdateTrigger.PERIODIC_TICK, description="Trigger for dynamic evaluation"
    )


class DynamicSurvivalPredictionResponse(BaseModel):
    target: SurvivalEventTarget = Field(..., description="Target time-to-event outcome")
    user_id: uuid.UUID = Field(..., description="User ID")
    task_id: Optional[uuid.UUID] = Field(None, description="Target task ID if applicable")
    last_updated_at: datetime = Field(..., description="Evaluation timestamp")
    time_unit: str = Field(..., description="'hours' or 'minutes' or 'seconds'")
    current_elapsed: float = Field(..., description="Elapsed time t_curr when prediction was made")
    update_trigger: DynamicUpdateTrigger = Field(..., description="Trigger initiating update")

    # Point estimates
    median_time_to_event: Optional[float] = Field(
        None, description="Estimated median time T_50% until event occurrence"
    )
    expected_hazard_rate: float = Field(..., description="Instantaneous baseline hazard lambda(t)")

    # Full Survival Curve
    survival_curve: List[SurvivalCurvePoint] = Field(
        ..., description="Dynamic conditional survival points S(t | T > t_curr)"
    )

    # Personalization governance
    personalization_tier: PersonalizationTier = Field(..., description="INDIVIDUAL, GROUP, or POPULATION")
    shrinkage_weight: float = Field(
        ..., ge=0.0, le=1.0, description="Empirical Bayes weight w_u assigned to individual history"
    )
    user_sample_size: int = Field(..., description="Number of historical events observed for user")
    data_sufficiency_score: float = Field(
        ..., ge=0.0, le=1.0, description="Data readiness metric for personalization"
    )

    model_name: str = Field(..., description="Underlying model architecture used")
    model_version: str = Field(..., description="Model version in registry")
    disclaimer: str = Field(
        default="Dynamic survival estimates reflect conditional probability given survival to current time. No future information leakage.",
        description="Scientific integrity notice",
    )


class SurvivalBenchmarkMetrics(BaseModel):
    model_name: str = Field(..., description="Model architecture")
    target: SurvivalEventTarget = Field(..., description="Evaluated target")
    concordance_index: float = Field(..., ge=0.0, le=1.0, description="Harrell's C-index")
    integrated_brier_score: float = Field(..., ge=0.0, le=1.0, description="Integrated Brier Score (lower is better)")
    time_dependent_auc_horizon_1: float = Field(..., ge=0.0, le=1.0, description="Time-dependent AUC at first horizon")
    time_dependent_auc_horizon_2: float = Field(..., ge=0.0, le=1.0, description="Time-dependent AUC at second horizon")
    horizon_calibration_error: float = Field(..., ge=0.0, le=1.0, description="Absolute calibration error")
    is_champion: bool = Field(default=False, description="True if selected as champion for this target")
    selection_rationale: Optional[str] = Field(None, description="Champion selection rationale")

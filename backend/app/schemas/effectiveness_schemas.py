"""
Pydantic v2 schemas for ContextIQ Intervention Effectiveness and Causal Evaluation Engine (Phase 4.7).
Defines schemas for outcome tracking, observational vs. causal effect comparisons,
experimental holdout reports, and effectiveness overviews.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


class OutcomeWindowMinutes(int, Enum):
    IMMEDIATE_RECOVERY = 30
    MEDIUM_SESSION = 120
    DAILY_WORKLOAD = 1440


class TreatmentStatus(str, Enum):
    TREATED = "TREATED"
    CONTROL_HOLDOUT = "CONTROL_HOLDOUT"
    OBSERVATIONAL = "OBSERVATIONAL"


class InterventionOutcomeRead(ORMBase):
    id: uuid.UUID
    user_id: uuid.UUID
    intervention_id: Optional[uuid.UUID] = None
    decision_id: Optional[uuid.UUID] = None
    intervention_type: str
    intervention_category: str
    treatment_status: str
    experiment_id: Optional[str] = None

    presented_at: datetime
    user_action: str
    action_timestamp: Optional[datetime] = None
    was_executed: bool
    execution_timestamp: Optional[datetime] = None
    execution_evidence: Dict[str, Any] = Field(default_factory=dict)

    window_start: datetime
    window_end: datetime
    observation_window_minutes: int

    baseline_bfi: float
    baseline_resumption_lag_seconds: float
    baseline_hourly_interruption_rate: float
    observed_bfi: Optional[float] = None
    observed_resumption_lag_seconds: Optional[float] = None
    observed_hourly_interruption_rate: Optional[float] = None

    target_task_completed: bool
    task_completed_at: Optional[datetime] = None
    adhered_to_deadline: Optional[bool] = None
    postponed_after_intervention: bool
    focus_session_minutes: Optional[float] = None

    bfi_delta: Optional[float] = None
    resumption_lag_delta_seconds: Optional[float] = None
    interruption_rate_delta: Optional[float] = None
    composite_effectiveness_score: float
    user_reported_usefulness: Optional[float] = None
    confounders_detected: List[Dict[str, Any]] = Field(default_factory=list)
    is_statistically_valid: bool
    created_at: datetime


class InterventionTypeComparison(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    intervention_type: str
    intervention_category: str
    sample_size_treated: int
    sample_size_control: int
    acceptance_rate: float
    execution_rate: float
    execution_to_acceptance_gap: float
    unadjusted_observational_difference: float
    estimated_ate: Optional[float] = None
    confidence_interval_95: Optional[List[float]] = None
    p_value: Optional[float] = None
    estimation_method: str = "DOUBLY_ROBUST_IPW"
    is_statistically_valid: bool = False
    validation_note: Optional[str] = None
    is_fatigued: bool = False
    fatigue_slope: Optional[float] = None


class InterventionEffectivenessOverview(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    total_interventions: int
    treated_count: int
    control_count: int
    accepted_count: int
    acceptance_rate: float
    executed_count: int
    execution_rate: float
    execution_to_acceptance_gap: float
    mean_bfi_reduction: float
    mean_resumption_lag_reduction_seconds: float
    task_completion_lift: float
    overall_causal_ate: Optional[float] = None
    top_effective_interventions: List[str] = Field(default_factory=list)
    fatigued_interventions: List[str] = Field(default_factory=list)
    methodological_disclaimer: str = (
        "Observational differences do not establish causation. "
        "Estimated ATE is calculated via Doubly Robust / IPW estimators "
        "incorporating randomized holdouts and propensity adjustments."
    )


class InterventionExperimentRead(ORMBase):
    id: uuid.UUID
    user_id: uuid.UUID
    experiment_name: str
    target_intervention_type: str
    control_policy: str
    allocation_ratio: float
    is_active: bool
    sample_size_treated: int
    sample_size_control: int
    estimated_ate: Optional[float] = None
    p_value: Optional[float] = None
    start_date: datetime
    end_date: Optional[datetime] = None
    created_at: datetime


class InterventionRecordOutcomeRequest(BaseModel):
    outcome_id: Optional[uuid.UUID] = None
    intervention_id: Optional[uuid.UUID] = None
    user_action: Optional[str] = None
    was_executed: Optional[bool] = None
    observed_bfi: Optional[float] = None
    observed_resumption_lag_seconds: Optional[float] = None
    target_task_completed: Optional[bool] = None
    user_reported_usefulness: Optional[float] = Field(None, ge=1.0, le=5.0)

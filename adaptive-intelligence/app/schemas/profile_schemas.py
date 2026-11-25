"""
Pydantic v2 schemas for ContextIQ Personal Behavioral Profile & Digital Twin (Phase 4.2).
Strictly separates observed empirical measurements from speculative traits,
providing confidence ratings, observation windows, and data provenance for all metrics.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PatternStatus(str, Enum):
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    EMERGING = "EMERGING"
    ESTABLISHED = "ESTABLISHED"


class MetricConfidence(BaseModel):
    """
    Standard envelope wrapping every empirical behavioral measurement with statistical confidence,
    observation count, coverage ratio, and data provenance.
    """
    observed_value: Any = Field(description="Empirically measured value (scalar, dict, or distribution)")
    observation_count: int = Field(ge=0, description="Number of observed telemetry records or events")
    observation_window_days: int = Field(ge=1, description="Temporal window of observation (e.g. 7, 30, 90)")
    last_updated: datetime = Field(description="Timestamp when this metric was last evaluated")
    confidence_level: float = Field(ge=0.0, le=1.0, description="Statistical confidence score [0.0 - 1.0]")
    data_coverage: float = Field(ge=0.0, le=1.0, description="Coverage ratio across observed active days")
    pattern_status: PatternStatus = Field(description="ESTABLISHED, EMERGING, or INSUFFICIENT_EVIDENCE")
    data_provenance: List[str] = Field(default_factory=list, description="Source models (e.g. ['context_sessions', 'task_events'])")


# Dimension A: Focus Behavior
class FocusBehaviorDimension(BaseModel):
    typical_session_duration_minutes: MetricConfidence = Field(
        description="Median duration of focused desktop work sessions"
    )
    session_duration_variability_minutes: MetricConfidence = Field(
        description="Interquartile range (IQR) of focused session durations"
    )
    max_uninterrupted_duration_minutes: MetricConfidence = Field(
        description="90th percentile uninterrupted focus stretch"
    )
    focus_stability_score: MetricConfidence = Field(
        description="Consistency of focus duration across active days [0 - 100]"
    )


# Dimension B: Interruption Behavior
class InterruptionBehaviorDimension(BaseModel):
    interruption_frequency_hourly: MetricConfidence = Field(
        description="Mean and median disruptions per hour of active focus"
    )
    interruption_type_distribution: MetricConfidence = Field(
        description="Normalized breakdown across app switches, idle interruptions, and external disruptions"
    )
    interruption_sensitivity_index: MetricConfidence = Field(
        description="Composite Interruption Sensitivity Index (ISI) [0.0 - 1.0]"
    )
    recovery_duration_distribution: MetricConfidence = Field(
        description="Log-normal parameters (mu, sigma), median lag, and p90 recovery seconds"
    )


# Dimension C: Task Completion
class TaskCompletionDimension(BaseModel):
    task_completion_rate: MetricConfidence = Field(
        description="Ratio of tasks completed vs created within observation window"
    )
    postponement_frequency: MetricConfidence = Field(
        description="Average number of due-date shifts or postponements per scheduled task"
    )
    deadline_adherence_rate: MetricConfidence = Field(
        description="Percentage of tasks completed prior to or on deadline"
    )
    completion_duration_by_category: MetricConfidence = Field(
        description="Median completion duration in minutes mapped by task category tag"
    )


# Dimension D: Context Behavior
class ContextBehaviorDimension(BaseModel):
    location_work_patterns: MetricConfidence = Field(
        description="Distribution of focused minutes and completion rates across physical locations"
    )
    application_transition_frequency: MetricConfidence = Field(
        description="Hourly frequency of desktop window switches during sessions"
    )
    context_switch_overhead_seconds: MetricConfidence = Field(
        description="Empirical resumption delay following inter-application context switches"
    )
    task_category_preferences: MetricConfidence = Field(
        description="Normalized distribution of tasks created and engaged across categories"
    )


# Dimension E: Temporal Behavior
class TemporalBehaviorDimension(BaseModel):
    active_daily_hours: MetricConfidence = Field(
        description="Typical active hours range [start_hour, end_hour] and peak focus window"
    )
    day_of_week_patterns: MetricConfidence = Field(
        description="Average focus minutes and completion velocity by weekday (Monday=0 ... Sunday=6)"
    )
    hourly_completion_density: MetricConfidence = Field(
        description="Circadian density distribution of task completions across hours 0-23"
    )


class BaselinesSummary(BaseModel):
    """Robust statistical summaries serving as personal behavioral baselines."""
    median_focus_duration_minutes: float = Field(ge=0.0)
    typical_recovery_duration_seconds: float = Field(ge=0.0)
    historical_completion_probability: float = Field(ge=0.0, le=1.0)
    typical_interruption_density_hourly: float = Field(ge=0.0)
    baseline_behavioral_friction_index: float = Field(ge=0.0, le=100.0)


class DigitalTwinProfileRead(BaseModel):
    """Consolidated digital twin response representation."""
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    profile_version: str
    is_cold_start: bool
    personalization_enabled: bool
    global_confidence_score: float = Field(ge=0.0, le=1.0)
    global_pattern_status: PatternStatus
    telemetry_days_observed: int = Field(ge=0)
    total_sessions_observed: int = Field(ge=0)
    total_tasks_observed: int = Field(ge=0)
    total_interruptions_observed: int = Field(ge=0)

    focus_behavior: FocusBehaviorDimension
    interruption_behavior: InterruptionBehaviorDimension
    task_completion: TaskCompletionDimension
    context_behavior: ContextBehaviorDimension
    temporal_behavior: TemporalBehaviorDimension
    baselines: BaselinesSummary

    last_rebuilt_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ProfileSnapshotRead(BaseModel):
    """Read representation of an immutable historical profile snapshot."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    profile_version: str
    snapshot_timestamp: datetime
    source_data_cutoff: datetime
    feature_schema_version: str
    observation_window_days: int
    trigger_reason: str
    snapshot_data: Dict[str, Any]
    created_at: datetime


class ProfileResetResponse(BaseModel):
    status: str
    message: str
    user_id: uuid.UUID
    reset_at: datetime


class PersonalizationToggleRequest(BaseModel):
    enabled: bool


class PersonalizationToggleResponse(BaseModel):
    status: str
    personalization_enabled: bool
    user_id: uuid.UUID
    updated_at: datetime

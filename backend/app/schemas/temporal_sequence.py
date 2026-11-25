"""
Temporal Behavioral Sequence Modeling Schemas (ContextIQ Phase 6.5).

Defines:
- Standardized event vocabulary and tokens (privacy-safe, no document contents).
- Sequence-based behavioral event representations.
- Prediction targets (Resumption, Recovery risk, Context switch, Completion, Friction trend).
- Candidate model architectures: Tabular baseline, GRU, TCN, Transformer.
- Benchmark evaluation metrics, calibration scores, and model registry schemas.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field


class SequenceEventType(str, Enum):
    PAD = "<PAD>"
    UNK = "<UNK>"
    TASK_CREATE = "TASK_CREATE"
    TASK_START = "TASK_START"
    TASK_PAUSE = "TASK_PAUSE"
    TASK_RESUME = "TASK_RESUME"
    TASK_COMPLETE = "TASK_COMPLETE"
    APPLICATION_SWITCH = "APPLICATION_SWITCH"
    INTERRUPTION_DETECTED = "INTERRUPTION_DETECTED"
    RECOVERY_BUFFER_DISPATCH = "RECOVERY_BUFFER_DISPATCH"
    NOTIFICATION_DELIVERED = "NOTIFICATION_DELIVERED"
    NOTIFICATION_DISMISSED = "NOTIFICATION_DISMISSED"
    CALENDAR_MEETING_START = "CALENDAR_MEETING_START"
    CALENDAR_MEETING_END = "CALENDAR_MEETING_END"
    FOCUS_WINDOW_START = "FOCUS_WINDOW_START"
    FOCUS_WINDOW_END = "FOCUS_WINDOW_END"
    IDLE_TIMEOUT = "IDLE_TIMEOUT"


class SequencePredictionTarget(str, Enum):
    SHORT_TERM_TASK_RESUMPTION = "short_term_task_resumption"  # P(Resumed within 15m)
    INTERRUPTION_RECOVERY_RISK = "interruption_recovery_risk"  # P(Recovery lag > 10m)
    FUTURE_CONTEXT_SWITCH = "future_context_switch"            # P(Switch within 5m)
    TASK_COMPLETION = "task_completion"                        # P(Completed on time)
    BEHAVIORAL_FRICTION_TREND = "behavioral_friction_trend"    # INCREASING / STABLE / DECREASING


class SequenceModelArchitecture(str, Enum):
    TABULAR_GRADIENT_BOOSTING = "tabular_gradient_boosting"
    GRU_RECURRENT = "gru_recurrent"
    TEMPORAL_CONVOLUTIONAL_NETWORK = "temporal_convolutional_network"
    CAUSAL_TRANSFORMER = "causal_transformer"


class BehavioralEventToken(BaseModel):
    """
    Leakage-safe, privacy-preserving behavioral event representation.
    Explicitly excludes sensitive application content, document text, or keystroke logs.
    """
    event_type: SequenceEventType = Field(..., description="Standardized event token")
    relative_timestamp_seconds: float = Field(
        ..., ge=0.0, description="Elapsed seconds since sequence initialization t_0"
    )
    duration_seconds: float = Field(
        default=0.0, ge=0.0, description="Observed event duration (e.g. meeting or interruption)"
    )
    task_category: str = Field(
        default="General", description="High-level category: Coding, DeepWork, Admin, Meeting, General"
    )
    context_hash: Optional[str] = Field(
        default=None, description="Anonymized session or window identifier"
    )
    interruption_severity: str = Field(
        default="NONE", description="NONE, LOW, MEDIUM, HIGH, CRITICAL"
    )
    rolling_bfi: float = Field(
        default=50.0, ge=0.0, le=100.0, description="Trailing Behavioral Friction Index at event timestamp"
    )
    recent_switch_count: int = Field(
        default=0, ge=0, description="Context switches in trailing 15 minutes"
    )
    hour_of_day: int = Field(default=12, ge=0, le=23, description="Circadian hour (0-23)")


class BehavioralSequence(BaseModel):
    """Ordered chronological sequence of user activity up to prediction timestamp."""
    user_id: uuid.UUID = Field(..., description="User UUID")
    prediction_timestamp: datetime = Field(..., description="Time zero t_pred cutoff (strictly past data)")
    events: List[BehavioralEventToken] = Field(
        ..., description="Chronologically sorted events (strictly t_i <= t_pred)"
    )
    sequence_length: int = Field(..., description="Number of observed events in sequence")
    is_cold_start: bool = Field(
        default=False, description="True if sequence_length < 5 (limited historical data)"
    )


class ModelBenchmarkMetrics(BaseModel):
    model_name: str = Field(..., description="Architecture name")
    target: SequencePredictionTarget = Field(..., description="Evaluated target")
    roc_auc: float = Field(..., ge=0.0, le=1.0, description="Area under ROC curve")
    pr_auc: float = Field(..., ge=0.0, le=1.0, description="Area under Precision-Recall curve")
    brier_score: float = Field(..., ge=0.0, le=1.0, description="Brier calibration score (lower is better)")
    log_loss: float = Field(..., ge=0.0, description="Cross-entropy log loss")
    training_time_seconds: float = Field(..., description="Wall-clock training duration")
    inference_latency_ms: float = Field(..., description="Single-sequence inference latency in milliseconds")
    is_champion: bool = Field(default=False, description="True if selected as production champion")
    selection_rationale: Optional[str] = Field(None, description="Why this model was chosen or passed over")


class SequencePredictionResponse(BaseModel):
    target: SequencePredictionTarget = Field(..., description="Prediction target")
    user_id: uuid.UUID = Field(..., description="User ID")
    prediction_timestamp: datetime = Field(..., description="As-of prediction timestamp")
    predicted_probability: float = Field(
        ..., ge=0.0, le=1.0, description="Point-in-time calibrated forecast probability"
    )
    predicted_label: str = Field(..., description="Binary or categorical outcome label")
    confidence_interval: Tuple[float, float] = Field(
        ..., description="90% uncertainty interval [lower, upper]"
    )
    sequence_length: int = Field(..., description="Length of input history used")
    is_cold_start: bool = Field(..., description="True if history is short (< 5 events)")
    model_architecture: SequenceModelArchitecture = Field(..., description="Model architecture used")
    model_version: str = Field(..., description="Version of model in registry")
    top_temporal_attributions: List[Dict[str, Any]] = Field(
        default_factory=list, description="Recent events with highest attention/feature attribution"
    )
    disclaimer: str = Field(
        default="Sequence prediction derived strictly from historical event sequences (t <= t_pred). No future event leakage.",
        description="Scientific integrity disclosure",
    )


class SequenceRegistryMetadata(BaseModel):
    model_version: str = Field(..., description="Semantic model registry version")
    champion_architecture: SequenceModelArchitecture = Field(..., description="Production champion model")
    supported_targets: List[SequencePredictionTarget] = Field(..., description="Supported targets")
    max_sequence_length: int = Field(default=32, description="Maximum padded sequence window")
    vocabulary_size: int = Field(..., description="Event token vocabulary size")
    training_snapshot_size: int = Field(..., description="Samples in training dataset")
    trained_at: datetime = Field(..., description="Model training timestamp")
    benchmark_comparison: List[ModelBenchmarkMetrics] = Field(..., description="Candidate models benchmark")

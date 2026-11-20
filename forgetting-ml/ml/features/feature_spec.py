"""
feature_spec.py

Single source of truth for the feature contract used across training and
inference. Both the training pipeline and the FastAPI inference layer
import from this module so they can never drift apart.

Phase 2.2 introduces:
- FeatureSchemaVersion (V1_1 baseline vs V2_2 enhanced temporal)
- Enhanced temporal features for micro-delays, resumption lag, and task age
- Backward compatibility guarantees
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict


class FeatureSchemaVersion(str, Enum):
    V1_1 = "v1.1"  # Baseline: 16 raw features -> 29 transformed features
    V2_2 = "v2.2"  # Enhanced temporal & micro-delay features


# =====================================================================
# Schema v1.1 — Baseline Contract (Immutable)
# =====================================================================

# Categorical features (one-hot encoded)
CATEGORICAL_FEATURES: List[str] = [
    "task_category",
    "priority",
    "location",
]

# Numeric features (used as-is / scaled for linear model)
NUMERIC_FEATURES: List[str] = [
    "weekday",
    "hour",
    "deadline_distance_hours",
    "previous_completion_count",
    "previous_forgetting_count",
    "historical_completion_rate",
    "historical_forgetting_rate",
    "task_frequency",
    "tasks_today",
    "interruptions_today",
    "recent_context_switches",
    "avg_interruption_duration",
    "avg_session_duration",
]

ALL_RAW_FEATURES: List[str] = CATEGORICAL_FEATURES + NUMERIC_FEATURES

TARGET_COLUMN = "forgotten"

# Allowed value domains for categorical inputs - used for API validation
CATEGORY_DOMAIN = [
    "Academic", "Work", "Personal", "Health", "Household", "Social", "Finance",
]
PRIORITY_DOMAIN = ["LOW", "MEDIUM", "HIGH"]
LOCATION_DOMAIN = ["Home", "Campus", "Office", "Commute", "Gym", "Other"]


# =====================================================================
# Schema v2.2 — Enhanced Temporal Features
# =====================================================================

ENHANCED_TEMPORAL_NUMERIC_FEATURES: List[str] = [
    # Task history & metacognition
    "previous_postponement_count",
    "category_completion_rate",
    "avg_completion_duration_minutes",
    "task_inactivity_hours",
    # Interruption & resumption micro-delays
    "recent_interruption_frequency",
    "avg_resumption_lag_seconds",
    "median_resumption_lag_seconds",
    "consecutive_interruption_count",
    "resumption_lag_std_seconds",
    # Contextual behavior
    "location_completion_rate",
    "context_switch_frequency_24h",
    "avg_switching_recovery_cost",
    # Temporal & Circadian
    "task_age_hours",
    "is_weekend",
    "is_peak_focus_hours",
]

V2_2_NUMERIC_FEATURES: List[str] = NUMERIC_FEATURES + ENHANCED_TEMPORAL_NUMERIC_FEATURES
V2_2_ALL_RAW_FEATURES: List[str] = CATEGORICAL_FEATURES + V2_2_NUMERIC_FEATURES


# Human-readable descriptions used by the explainability layer to translate
# a raw feature name + direction into a natural-language reason string.
FEATURE_DESCRIPTIONS: Dict[str, str] = {
    # Baseline features
    "historical_forgetting_rate": "historical forgetting rate for this user",
    "historical_completion_rate": "historical completion rate for this user",
    "previous_forgetting_count": "number of previously forgotten tasks",
    "previous_completion_count": "number of previously completed tasks",
    "task_frequency": "how often this task category recurs for this user",
    "interruptions_today": "number of interruptions experienced today",
    "recent_context_switches": "recent context switches",
    "avg_interruption_duration": "average interruption duration",
    "avg_session_duration": "average focused session duration",
    "deadline_distance_hours": "time remaining until the task deadline",
    "tasks_today": "number of tasks scheduled today",
    "weekday": "day of the week",
    "hour": "hour of day the task was logged",
    "task_category": "task category",
    "priority": "task priority",
    "location": "task location context",
    # Enhanced v2.2 features
    "previous_postponement_count": "number of prior task deadline postponements",
    "category_completion_rate": "historical completion rate for this specific category",
    "avg_completion_duration_minutes": "average time required to complete tasks",
    "task_inactivity_hours": "hours elapsed since user's last recorded action",
    "recent_interruption_frequency": "interruption rate per hour in the last 24h",
    "avg_resumption_lag_seconds": "average cognitive recovery delay after an interruption",
    "median_resumption_lag_seconds": "median resumption lag after disruptions",
    "consecutive_interruption_count": "number of closely spaced consecutive disruptions",
    "resumption_lag_std_seconds": "variability in recovery time across interruptions",
    "location_completion_rate": "historical completion rate at this physical location",
    "context_switch_frequency_24h": "rate of task context switches in the last 24h",
    "avg_switching_recovery_cost": "cognitive switching recovery penalty score",
    "task_age_hours": "hours elapsed since task was created",
    "is_weekend": "whether the task is scheduled on a weekend",
    "is_peak_focus_hours": "whether the task coincides with peak cognitive focus hours",
}


@dataclass(frozen=True)
class FeatureSpec:
    version: FeatureSchemaVersion = FeatureSchemaVersion.V1_1
    categorical: List[str] = field(default_factory=lambda: list(CATEGORICAL_FEATURES))
    numeric: List[str] = field(default_factory=lambda: list(NUMERIC_FEATURES))
    target: str = TARGET_COLUMN


DEFAULT_SPEC = FeatureSpec()
SPEC_V2_2 = FeatureSpec(
    version=FeatureSchemaVersion.V2_2,
    categorical=list(CATEGORICAL_FEATURES),
    numeric=list(V2_2_NUMERIC_FEATURES),
    target=TARGET_COLUMN,
)

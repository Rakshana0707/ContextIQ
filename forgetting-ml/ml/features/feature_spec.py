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
    V2_3 = "v2.3"  # Automated behavioral telemetry & calibrated friction


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


# =====================================================================
# Schema v2.3 — Automated Behavioral Telemetry & Calibrated Friction
# =====================================================================

AUTOMATED_TELEMETRY_NUMERIC_FEATURES: List[str] = [
    "behavioral_friction_index",
    "telemetry_coverage_ratio",
    "application_transition_frequency",
    "session_fragmentation_score",
    "time_since_last_activity_hours",
    "interruption_density",
    "return_to_app_delay_seconds",
]

V2_3_NUMERIC_FEATURES: List[str] = V2_2_NUMERIC_FEATURES + AUTOMATED_TELEMETRY_NUMERIC_FEATURES
V2_3_ALL_RAW_FEATURES: List[str] = CATEGORICAL_FEATURES + V2_3_NUMERIC_FEATURES


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
    # Automated v2.3 telemetry features
    "behavioral_friction_index": "overall behavioral friction index reflecting multitasking strain",
    "telemetry_coverage_ratio": "ratio of expected observation time monitored by telemetry agent",
    "application_transition_frequency": "frequency of desktop application switches per hour",
    "session_fragmentation_score": "proportion of work time broken by interruptions or brief switches",
    "time_since_last_activity_hours": "hours elapsed since last observed desktop activity or task event",
    "interruption_density": "percentage of active work session time lost to interruptions",
    "return_to_app_delay_seconds": "elapsed time to return to primary work application after an interruption",
}

# Population baseline medians used for cold-start imputation
POPULATION_FEATURE_DEFAULTS: Dict[str, float] = {
    "behavioral_friction_index": 35.0,
    "telemetry_coverage_ratio": 0.0,
    "application_transition_frequency": 4.0,
    "session_fragmentation_score": 0.25,
    "time_since_last_activity_hours": 2.0,
    "interruption_density": 0.15,
    "recent_interruption_frequency": 1.5,
    "avg_resumption_lag_seconds": 45.0,
    "median_resumption_lag_seconds": 40.0,
    "consecutive_interruption_count": 1.0,
    "resumption_lag_std_seconds": 15.0,
    "context_switch_frequency_24h": 6.0,
    "return_to_app_delay_seconds": 30.0,
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
SPEC_V2_3 = FeatureSpec(
    version=FeatureSchemaVersion.V2_3,
    categorical=list(CATEGORICAL_FEATURES),
    numeric=list(V2_3_NUMERIC_FEATURES),
    target=TARGET_COLUMN,
)

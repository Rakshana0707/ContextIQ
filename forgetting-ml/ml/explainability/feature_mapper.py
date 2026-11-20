"""
feature_mapper.py

Maps transformed ColumnTransformer feature indices and names back to their
original raw input features, human-friendly titles, actual observed values,
and prospective memory descriptions (Phase 2.7).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from ml.features.feature_spec import (
    CATEGORY_DOMAIN,
    FEATURE_DESCRIPTIONS,
    LOCATION_DOMAIN,
    PRIORITY_DOMAIN,
)

# Friendly display titles for raw features
DISPLAY_NAMES: Dict[str, str] = {
    "historical_forgetting_rate": "Historical Forgetting Rate",
    "historical_completion_rate": "Historical Completion Rate",
    "previous_forgetting_count": "Past Forgetting Incidents",
    "previous_completion_count": "Past Completed Tasks",
    "task_frequency": "Task Recurrence Frequency",
    "interruptions_today": "Daily Interruption Count",
    "recent_context_switches": "Recent Context Switches",
    "avg_interruption_duration": "Avg Interruption Duration",
    "avg_session_duration": "Avg Session Focus Duration",
    "deadline_distance_hours": "Deadline Proximity",
    "tasks_today": "Total Tasks Today",
    "weekday": "Day of Week",
    "hour": "Time of Day",
    "task_category": "Task Category",
    "priority": "Task Priority",
    "location": "Location Context",
    # Enhanced v2.2
    "previous_postponement_count": "Prior Postponements",
    "category_completion_rate": "Category Completion Rate",
    "avg_completion_duration_minutes": "Avg Task Duration",
    "task_inactivity_hours": "Inactivity Duration",
    "recent_interruption_frequency": "Interruption Rate (24h)",
    "avg_resumption_lag_seconds": "Resumption Lag",
    "median_resumption_lag_seconds": "Median Resumption Lag",
    "consecutive_interruption_count": "Consecutive Interruptions",
    "resumption_lag_std_seconds": "Resumption Lag Variance",
    "location_completion_rate": "Location Completion Rate",
    "context_switch_frequency_24h": "Context Switch Frequency",
    "avg_switching_recovery_cost": "Switching Recovery Cost",
    "task_age_hours": "Task Age",
    "is_weekend": "Weekend Factor",
    "is_peak_focus_hours": "Peak Focus Hours",
}

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class FeatureMapper:
    """Translates ColumnTransformer feature representations back to intuitive raw context."""

    @staticmethod
    def parse_transformed_feature(transformed_name: str) -> Tuple[str, str, Optional[str]]:
        """
        Parses a transformed column name into:
        (raw_feature_name, display_title, optional_category_value)
        
        Examples:
        - "num__deadline_distance_hours" -> ("deadline_distance_hours", "Deadline Proximity", None)
        - "cat__task_category_Personal"  -> ("task_category", "Task Category (Personal)", "Personal")
        """
        if transformed_name.startswith("num__"):
            raw = transformed_name[len("num__"):]
            display = DISPLAY_NAMES.get(raw, raw.replace("_", " ").title())
            return raw, display, None

        if transformed_name.startswith("cat__"):
            cat_body = transformed_name[len("cat__"):]
            for base in ("task_category", "priority", "location"):
                if cat_body.startswith(base + "_"):
                    val = cat_body[len(base) + 1:]
                    base_display = DISPLAY_NAMES.get(base, base.replace("_", " ").title())
                    display = f"{base_display}: {val}"
                    return base, display, val
            return cat_body, cat_body, None

        return transformed_name, transformed_name, None

    @classmethod
    def format_actual_value(cls, raw_feature_name: str, value: Any) -> str:
        """Formats an actual raw feature value into human-friendly text."""
        if value is None:
            return "N/A"

        if raw_feature_name == "weekday" and isinstance(value, int) and 0 <= value <= 6:
            return WEEKDAY_NAMES[value]

        if raw_feature_name == "hour" and isinstance(value, (int, float)):
            h = int(value)
            suffix = "AM" if h < 12 else "PM"
            display_h = 12 if h in (0, 12) else h % 12
            return f"{display_h}:00 {suffix}"

        if raw_feature_name == "deadline_distance_hours" and isinstance(value, (int, float)):
            return f"{float(value):.1f} hours"

        if raw_feature_name in ("historical_forgetting_rate", "historical_completion_rate", "task_frequency"):
            return f"{float(value):.1%}"

        if raw_feature_name in ("avg_interruption_duration", "avg_session_duration"):
            return f"{float(value):.1f} min"

        if raw_feature_name in ("interruptions_today", "recent_context_switches", "tasks_today",
                                "previous_completion_count", "previous_forgetting_count"):
            return str(int(value))

        return str(value)

    @classmethod
    def get_feature_description(cls, raw_feature_name: str) -> str:
        """Returns the behavioral description for the raw feature."""
        return FEATURE_DESCRIPTIONS.get(
            raw_feature_name,
            f"Observed behavioral metric: {raw_feature_name.replace('_', ' ')}",
        )

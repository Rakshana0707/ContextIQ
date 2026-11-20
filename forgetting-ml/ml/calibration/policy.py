"""
policy.py

Operational Risk Response Policy Engine (Phase 2.5).
Defines standard actionable recommendations and automated triage suggestions
for each risk category. These are system guidance recommendations, not destructive
task modifications.
"""

from __future__ import annotations

from typing import Any, Dict
from ml.calibration.thresholds import RiskCategory


POLICY_DESCRIPTIONS: Dict[RiskCategory, Dict[str, Any]] = {
    RiskCategory.LOW: {
        "label": "Low Risk",
        "action_recommendation": "Normal task visibility. No intervention required.",
        "ui_badge_color": "green",
        "notification_channel": None,
        "scheduling_suggestion": "Maintain planned execution schedule.",
    },
    RiskCategory.MEDIUM: {
        "label": "Medium Risk",
        "action_recommendation": "Display gentle in-app reminder in upcoming task feed.",
        "ui_badge_color": "yellow",
        "notification_channel": "in_app_feed",
        "scheduling_suggestion": "Consider completing during next focus block.",
    },
    RiskCategory.HIGH: {
        "label": "High Risk",
        "action_recommendation": "Suggest reviewing task priority or breaking into smaller subtasks.",
        "ui_badge_color": "orange",
        "notification_channel": "push_notification",
        "scheduling_suggestion": "Reschedule to earlier morning focus window or simplify scope.",
    },
    RiskCategory.CRITICAL: {
        "label": "Critical Risk",
        "action_recommendation": "Suggest immediate user attention; surface prominent persistent banner.",
        "ui_badge_color": "red",
        "notification_channel": "priority_alert",
        "scheduling_suggestion": "Address immediately or formally postpone deadline to avoid unmanaged lapse.",
    },
}


def get_risk_policy(category: RiskCategory) -> Dict[str, Any]:
    """Returns the operational response metadata for a given risk category."""
    return POLICY_DESCRIPTIONS.get(category, POLICY_DESCRIPTIONS[RiskCategory.LOW])

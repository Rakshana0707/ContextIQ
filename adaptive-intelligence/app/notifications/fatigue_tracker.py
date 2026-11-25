"""
Notification Fatigue Tracker for ContextIQ (Phase 4.8).
Mirror for adaptive-intelligence.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class NotificationFatigueTracker:
    FATIGUE_THRESHOLD_MODERATE: float = 0.40
    FATIGUE_THRESHOLD_HIGH: float = 0.70
    FATIGUE_THRESHOLD_CRITICAL: float = 0.85

    @classmethod
    def calculate_fatigue_score(
        cls,
        total_presented: int,
        total_accepted: int,
        total_dismissed: int,
        total_deferred: int,
        consecutive_dismissals: int,
        deliveries_24h: int,
        daily_limit: int = 12,
        annoyance_reports_count: int = 0,
        average_annoyance_level: Optional[float] = None,
    ) -> float:
        if total_presented <= 0:
            return 0.0

        dismissal_ratio = float(total_dismissed) / max(1.0, float(total_presented))
        consec_penalty = min(1.0, float(consecutive_dismissals) / 3.0)
        vol_saturation = min(1.0, float(deliveries_24h) / max(1.0, float(daily_limit)))

        annoyance_factor = 0.0
        if annoyance_reports_count > 0 and average_annoyance_level is not None:
            annoyance_factor = max(0.0, min(1.0, (average_annoyance_level - 1.0) / 4.0))

        raw_score = (
            0.35 * dismissal_ratio
            + 0.25 * consec_penalty
            + 0.25 * vol_saturation
            + 0.15 * annoyance_factor
        )

        return round(max(0.0, min(1.0, raw_score)), 3)

    @classmethod
    def get_fatigue_level(cls, score: float) -> str:
        if score >= cls.FATIGUE_THRESHOLD_CRITICAL:
            return "CRITICAL"
        if score >= cls.FATIGUE_THRESHOLD_HIGH:
            return "HIGH"
        if score >= cls.FATIGUE_THRESHOLD_MODERATE:
            return "MODERATE"
        return "LOW"

    @classmethod
    def should_escalate_cooldown(cls, fatigue_score: float) -> bool:
        return fatigue_score >= cls.FATIGUE_THRESHOLD_HIGH

    @classmethod
    def should_force_batch_summary(cls, fatigue_score: float, priority: str) -> bool:
        if priority.upper() in ("CRITICAL", "HIGH"):
            return False
        return fatigue_score >= cls.FATIGUE_THRESHOLD_HIGH

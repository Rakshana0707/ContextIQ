"""
Confidence estimation and pattern status classification for ContextIQ Profile Engine.
Evaluates statistical reliability based on sample size, active temporal coverage,
and dispersion, ensuring small-sample telemetry is never misidentified as established traits.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple

from app.schemas.profile_schemas import MetricConfidence, PatternStatus

# Sample size thresholds
MIN_EMERGING_SAMPLES = 7
MIN_ESTABLISHED_SAMPLES = 30

# Temporal coverage thresholds (active days observed / window days)
MIN_EMERGING_COVERAGE = 0.20
MIN_ESTABLISHED_COVERAGE = 0.65


class ProfileConfidenceEstimator:
    """Calculates statistical confidence scores and pattern status for behavioral metrics."""

    @staticmethod
    def calculate_confidence(
        sample_count: int,
        observation_window_days: int = 30,
        days_with_data: int = 0,
        variance_ratio: Optional[float] = None,
    ) -> Tuple[float, float, PatternStatus]:
        """
        Computes (confidence_score, data_coverage, pattern_status).
        """
        if sample_count <= 0:
            return 0.0, 0.0, PatternStatus.INSUFFICIENT_EVIDENCE

        effective_window = max(1, observation_window_days)
        coverage = min(1.0, max(0.0, days_with_data / effective_window))

        sample_conf = 1.0 - math.exp(-sample_count / 15.0)

        stability = 1.0
        if variance_ratio is not None and not math.isnan(variance_ratio):
            stability = max(0.0, 1.0 - min(1.0, variance_ratio))

        raw_confidence = 0.50 * sample_conf + 0.35 * coverage + 0.15 * stability
        confidence_score = round(max(0.0, min(1.0, raw_confidence)), 3)

        if sample_count >= MIN_ESTABLISHED_SAMPLES and coverage >= MIN_ESTABLISHED_COVERAGE:
            status = PatternStatus.ESTABLISHED
        elif sample_count >= MIN_EMERGING_SAMPLES and coverage >= MIN_EMERGING_COVERAGE:
            status = PatternStatus.EMERGING
        else:
            status = PatternStatus.INSUFFICIENT_EVIDENCE

        return confidence_score, round(coverage, 3), status

    @classmethod
    def wrap_metric(
        cls,
        observed_value: Any,
        sample_count: int,
        observation_window_days: int = 30,
        days_with_data: int = 0,
        data_provenance: Optional[List[str]] = None,
        last_updated: Optional[datetime] = None,
        variance_ratio: Optional[float] = None,
    ) -> MetricConfidence:
        """Helper to create a fully validated MetricConfidence object."""
        now = last_updated or datetime.now(timezone.utc)
        conf_score, coverage, status = cls.calculate_confidence(
            sample_count=sample_count,
            observation_window_days=observation_window_days,
            days_with_data=days_with_data,
            variance_ratio=variance_ratio,
        )

        return MetricConfidence(
            observed_value=observed_value,
            observation_count=sample_count,
            observation_window_days=observation_window_days,
            last_updated=now,
            confidence_level=conf_score,
            data_coverage=coverage,
            pattern_status=status,
            data_provenance=data_provenance or ["telemetry"],
        )

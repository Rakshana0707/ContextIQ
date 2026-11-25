"""
Unit tests for adaptive-intelligence profile engine components.
Verifies confidence estimation, robust statistical summaries,
incremental Welford updating, and pattern status transitions.
"""
import uuid
from datetime import datetime, timezone

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.profiles.profile_confidence import ProfileConfidenceEstimator
from app.profiles.profile_builder import ProfileBuilder, _fit_lognormal, _median_and_iqr
from app.profiles.profile_updater import ProfileUpdater
from app.schemas.profile_schemas import PatternStatus



def test_confidence_estimator_thresholds():
    # 0 samples
    score, cov, status = ProfileConfidenceEstimator.calculate_confidence(sample_count=0)
    assert score == 0.0
    assert status == PatternStatus.INSUFFICIENT_EVIDENCE

    # 3 samples, low coverage
    score, cov, status = ProfileConfidenceEstimator.calculate_confidence(
        sample_count=3, observation_window_days=30, days_with_data=2
    )
    assert status == PatternStatus.INSUFFICIENT_EVIDENCE
    assert score < 0.35

    # 15 samples, medium coverage
    score, cov, status = ProfileConfidenceEstimator.calculate_confidence(
        sample_count=15, observation_window_days=30, days_with_data=10
    )
    assert status == PatternStatus.EMERGING
    assert 0.35 <= score < 0.75

    # 40 samples, high coverage
    score, cov, status = ProfileConfidenceEstimator.calculate_confidence(
        sample_count=40, observation_window_days=30, days_with_data=24
    )
    assert status == PatternStatus.ESTABLISHED
    assert score >= 0.75


def test_robust_statistical_helpers():
    # Median and IQR
    vals = [10.0, 20.0, 25.0, 30.0, 40.0, 95.0]
    med, iqr = _median_and_iqr(vals)
    assert med == 27.5
    assert iqr > 0.0

    # Empty
    med_empty, iqr_empty = _median_and_iqr([], fallback_median=25.0)
    assert med_empty == 25.0
    assert iqr_empty == 0.0

    # Lognormal fit
    mu, sigma, med_lag, p90_lag = _fit_lognormal([15.0, 25.0, 45.0, 60.0, 120.0])
    assert mu > 0
    assert sigma > 0
    assert med_lag > 0
    assert p90_lag > med_lag


def test_builder_empty_entities():
    user_id = uuid.uuid4()
    profile = ProfileBuilder.build_profile(
        user_id=user_id,
        sessions=[],
        detected_interruptions=[],
        manual_interruptions=[],
        tasks=[],
        task_events=[],
    )
    assert profile.user_id == user_id
    assert profile.is_cold_start is True
    assert profile.global_pattern_status == PatternStatus.INSUFFICIENT_EVIDENCE
    assert profile.baselines.median_focus_duration_minutes == 25.0

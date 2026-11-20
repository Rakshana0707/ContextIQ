"""
cold_start.py

Cold-Start Strategy & Empirical Bayes Shrinkage Engine (Phase 2.6).
Handles users with zero or insufficient historical task observations without
fabricating behavioral history:
1. Tier 1: Unseen User (N = 0) -> Population baseline prior, wide uncertainty bounds.
2. Tier 2: Early User (1 <= N < 25) -> Empirical Bayes shrinkage toward population mean.
3. Tier 3: Established User (N >= 25) -> Fully personalized behavioral profile.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

POPULATION_PRIOR_ALPHA = 2.74  # Forgetting rate ~ 27.4%
POPULATION_PRIOR_BETA = 7.26   # Total pseudo-counts = 10.0


class ColdStartTier(str, Enum):
    UNSEEN_USER = "UNSEEN_USER"          # N = 0
    EARLY_USER = "EARLY_USER"            # 1 <= N < 25
    ESTABLISHED_USER = "ESTABLISHED_USER"  # N >= 25


@dataclass
class ColdStartAssessment:
    is_cold_start: bool
    cold_start_tier: ColdStartTier
    sample_count: int
    shrunk_forgetting_rate: float
    confidence_interval_width: float
    recommendation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_cold_start": self.is_cold_start,
            "cold_start_tier": self.cold_start_tier.value,
            "sample_count": self.sample_count,
            "shrunk_forgetting_rate": round(self.shrunk_forgetting_rate, 4),
            "confidence_interval_width": round(self.confidence_interval_width, 4),
            "recommendation": self.recommendation,
        }


class ColdStartStrategy:
    """Evaluates task history depth and computes empirical Bayes shrinkage."""

    def __init__(
        self,
        min_established_samples: int = 25,
        alpha_prior: float = POPULATION_PRIOR_ALPHA,
        beta_prior: float = POPULATION_PRIOR_BETA,
    ):
        self.min_samples = min_established_samples
        self.alpha = alpha_prior
        self.beta = beta_prior
        self.population_mean = alpha_prior / (alpha_prior + beta_prior)

    def assess_user(
        self,
        previous_completions: int = 0,
        previous_forgettings: int = 0,
        raw_historical_rate: Optional[float] = None,
    ) -> ColdStartAssessment:
        n = max(0, int(previous_completions) + int(previous_forgettings))
        k = max(0, int(previous_forgettings))

        if n == 0:
            # Tier 1: Unseen User
            return ColdStartAssessment(
                is_cold_start=True,
                cold_start_tier=ColdStartTier.UNSEEN_USER,
                sample_count=0,
                shrunk_forgetting_rate=self.population_mean,
                confidence_interval_width=0.18,  # High epistemic uncertainty
                recommendation="Using population baseline priors; confidence intervals widened.",
            )
        elif n < self.min_samples:
            # Tier 2: Early User (Empirical Bayes Shrinkage)
            # Shrunk rate = (k + alpha) / (n + alpha + beta)
            shrunk_rate = (k + self.alpha) / (n + self.alpha + self.beta)
            # Uncertainty scales down smoothly with sqrt(n)
            ci_width = max(0.08, 0.18 - 0.10 * (np.sqrt(n) / np.sqrt(self.min_samples)))
            return ColdStartAssessment(
                is_cold_start=True,
                cold_start_tier=ColdStartTier.EARLY_USER,
                sample_count=n,
                shrunk_forgetting_rate=float(shrunk_rate),
                confidence_interval_width=float(ci_width),
                recommendation=f"Empirical Bayes shrinkage applied across {n} observations.",
            )
        else:
            # Tier 3: Established User
            emp_rate = (k / n) if raw_historical_rate is None else raw_historical_rate
            return ColdStartAssessment(
                is_cold_start=False,
                cold_start_tier=ColdStartTier.ESTABLISHED_USER,
                sample_count=n,
                shrunk_forgetting_rate=float(emp_rate),
                confidence_interval_width=0.05,  # Low epistemic uncertainty
                recommendation="Established profile: full personal behavioral weighting applied.",
            )

    def calculate_prediction_interval(
        self,
        prob: float,
        assessment: ColdStartAssessment,
    ) -> Tuple[float, float]:
        """Calculates confidence bounds [lower, upper] based on sample maturity."""
        half_w = assessment.confidence_interval_width
        lower = max(0.0, round(prob - half_w, 4))
        upper = min(1.0, round(prob + half_w, 4))
        return (lower, upper)

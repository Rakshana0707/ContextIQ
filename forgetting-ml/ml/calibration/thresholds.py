"""
thresholds.py

Intelligent Risk Threshold Optimization and Personalized Policy Manager.
Replaces arbitrary cutoffs with:
1. Utility/Cost-sensitive threshold selection (C_FN vs C_FP)
2. Precision-constrained F1 optimization
3. 4-tier risk categories: LOW, MEDIUM, HIGH, CRITICAL
4. Personalized threshold manager with sample size guardrails (N >= 25)
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score, confusion_matrix

MIN_USER_SAMPLES_FOR_PERSONALIZATION = 25


class RiskCategory(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class RiskThresholds:
    """Configurable probability cutoffs defining risk boundaries."""
    tau_low: float = 0.25      # Below this: LOW
    tau_medium: float = 0.45   # tau_low to tau_medium: MEDIUM
    tau_high: float = 0.70     # tau_medium to tau_high: HIGH; Above this: CRITICAL

    def __post_init__(self):
        if not (0.0 < self.tau_low < self.tau_medium < self.tau_high < 1.0):
            raise ValueError(
                f"Thresholds must be strictly monotonic in (0, 1): "
                f"{self.tau_low} < {self.tau_medium} < {self.tau_high}"
            )

    def classify_risk(self, probability: float) -> RiskCategory:
        """Categorizes a calibrated probability into a 4-tier risk level."""
        p = float(probability)
        if p < self.tau_low:
            return RiskCategory.LOW
        elif p < self.tau_medium:
            return RiskCategory.MEDIUM
        elif p < self.tau_high:
            return RiskCategory.HIGH
        else:
            return RiskCategory.CRITICAL

    def to_dict(self) -> Dict[str, float]:
        return {
            "tau_low": self.tau_low,
            "tau_medium": self.tau_medium,
            "tau_high": self.tau_high,
        }


def optimize_classification_threshold(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    cost_fp: float = 1.0,
    cost_fn: float = 3.0,
    min_precision: float = 0.35,
    n_steps: int = 100,
) -> Dict[str, Any]:
    """
    Finds the optimal decision threshold balancing expected misclassification cost
    and minimum acceptable precision:
        Cost = cost_fp * FP + cost_fn * FN
    """
    candidate_thresholds = np.linspace(0.10, 0.90, n_steps)
    best_t = 0.5
    min_cost = float("inf")
    best_metrics = {}

    for t in candidate_thresholds:
        preds = (y_prob >= t).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_true, preds, labels=[0, 1]).ravel()
        cost = float(cost_fp * fp + cost_fn * fn)
        prec = float(precision_score(y_true, preds, zero_division=0))
        rec = float(recall_score(y_true, preds, zero_division=0))
        f1 = float(f1_score(y_true, preds, zero_division=0))

        # Precision constraint
        if prec >= min_precision and cost < min_cost:
            min_cost = cost
            best_t = float(t)
            best_metrics = {
                "threshold": round(best_t, 3),
                "expected_cost": round(cost, 2),
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "f1": round(f1, 4),
            }

    # Fallback if constraint too tight
    if not best_metrics:
        best_t = 0.45
        preds = (y_prob >= best_t).astype(int)
        prec = float(precision_score(y_true, preds, zero_division=0))
        rec = float(recall_score(y_true, preds, zero_division=0))
        f1 = float(f1_score(y_true, preds, zero_division=0))
        best_metrics = {
            "threshold": best_t,
            "expected_cost": float("inf"),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
        }

    return best_metrics


def derive_population_risk_thresholds(
    y_val_true: np.ndarray,
    y_val_prob: np.ndarray,
) -> RiskThresholds:
    """
    Derives the population-level 4-tier risk boundaries:
    - tau_medium: optimal F1 / cost-sensitive threshold
    - tau_low: threshold targeting 85% recall (early sensitive warning)
    - tau_high: threshold targeting 65% precision (high-confidence alert)
    """
    threshold_grid = np.linspace(0.10, 0.90, 81)
    
    # 1. tau_medium via cost-sensitive optimization
    cost_opt = optimize_classification_threshold(y_val_true, y_val_prob, cost_fp=1.0, cost_fn=3.0)
    tau_medium = cost_opt["threshold"]

    # 2. tau_low: earliest threshold where recall is at least 0.85
    tau_low = 0.25
    for t in threshold_grid:
        preds = (y_val_prob >= t).astype(int)
        rec = recall_score(y_val_true, preds, zero_division=0)
        if rec >= 0.85 and t < tau_medium:
            tau_low = float(t)

    # 3. tau_high: threshold where precision is at least 0.60
    tau_high = 0.70
    for t in reversed(threshold_grid):
        preds = (y_val_prob >= t).astype(int)
        prec = precision_score(y_val_true, preds, zero_division=0)
        if prec >= 0.55 and t > tau_medium:
            tau_high = float(t)
            break

    # Safety monotonicity guarantee
    if tau_low >= tau_medium:
        tau_low = round(tau_medium * 0.6, 2)
    if tau_high <= tau_medium:
        tau_high = round(tau_medium + (1.0 - tau_medium) * 0.5, 2)

    return RiskThresholds(
        tau_low=round(tau_low, 3),
        tau_medium=round(tau_medium, 3),
        tau_high=round(tau_high, 3),
    )


class PersonalizedThresholdManager:
    """
    Manages personalized thresholds per user with strict minimum sample guardrails.
    """

    def __init__(self, population_thresholds: Optional[RiskThresholds] = None):
        self.population_thresholds = population_thresholds or RiskThresholds()
        self.min_samples_required = MIN_USER_SAMPLES_FOR_PERSONALIZATION

    def get_user_thresholds(
        self,
        user_history: Optional[List[Dict[str, Any]]] = None,
        user_historical_forget_rate: Optional[float] = None,
    ) -> Tuple[RiskThresholds, str]:
        """
        Calculates user-specific thresholds if sufficient history exists.
        Returns:
            (RiskThresholds, reason_string)
        """
        n_samples = len(user_history) if user_history is not None else 0

        # Guardrail: Insufficient history falls back to population
        if n_samples < self.min_samples_required:
            reason = (
                f"User has {n_samples} resolved tasks (minimum {self.min_samples_required} required). "
                "Using population baseline thresholds."
            )
            return self.population_thresholds, reason

        # User has sufficient samples: adapt thresholds
        # If user has a high historical forgetting rate (> 0.40), lower tau_medium to intervene earlier
        # If user has a low forgetting rate (< 0.15), raise tau_medium to avoid alert fatigue
        base = self.population_thresholds
        h_rate = user_historical_forget_rate
        if h_rate is None and user_history:
            forgotten = sum(1 for t in user_history if t.get("status") in ("FORGOTTEN", "ABANDONED") or t.get("forgotten") == 1)
            h_rate = forgotten / max(1, n_samples)

        if h_rate is not None:
            if h_rate > 0.35:
                # High risk profile: more sensitive alert thresholds
                adj_low = max(0.15, base.tau_low - 0.05)
                adj_med = max(adj_low + 0.10, base.tau_medium - 0.05)
                adj_high = max(adj_med + 0.15, base.tau_high - 0.05)
                reason = f"Personalized for high-forgetting history ({h_rate:.2f}): increased sensitivity."
            elif h_rate < 0.15:
                # Highly reliable user: reduce alert frequency
                adj_low = min(0.35, base.tau_low + 0.05)
                adj_med = min(adj_low + 0.20, base.tau_medium + 0.05)
                adj_high = min(0.85, base.tau_high + 0.05)
                reason = f"Personalized for low-forgetting history ({h_rate:.2f}): reduced alert frequency."
            else:
                adj_low, adj_med, adj_high = base.tau_low, base.tau_medium, base.tau_high
                reason = f"Personalized for balanced history ({h_rate:.2f}): matching baseline."

            personalized = RiskThresholds(
                tau_low=round(adj_low, 3),
                tau_medium=round(adj_med, 3),
                tau_high=round(adj_high, 3),
            )
            return personalized, reason

        return self.population_thresholds, "Using population baseline thresholds."

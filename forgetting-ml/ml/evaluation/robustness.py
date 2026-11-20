"""
robustness.py

Robustness Stress Testing and Statistical Uncertainty Estimation (Phase 2.6).
Implements:
1. Adversarial input corruption & extreme value stress testing.
2. Bootstrap resampling for 95% Confidence Intervals.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from ml.features.feature_spec import ALL_RAW_FEATURES
from ml.training.config import SEED


def evaluate_bootstrap_uncertainty(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bootstraps: int = 250,
    confidence_level: float = 0.95,
    seed: int = SEED,
) -> Dict[str, Dict[str, float]]:
    """
    Computes empirical bootstrap confidence intervals for PR-AUC, ROC-AUC, and Brier Score.
    """
    n_samples = len(y_true)
    rng = np.random.RandomState(seed)

    boot_pr_aucs = []
    boot_roc_aucs = []
    boot_briers = []

    alpha = 1.0 - confidence_level
    lower_pct = (alpha / 2.0) * 100.0
    upper_pct = (1.0 - alpha / 2.0) * 100.0

    for _ in range(n_bootstraps):
        idx = rng.randint(0, n_samples, size=n_samples)
        y_b = y_true[idx]
        p_b = y_prob[idx]

        if len(np.unique(y_b)) < 2:
            continue

        boot_pr_aucs.append(float(average_precision_score(y_b, p_b)))
        boot_roc_aucs.append(float(roc_auc_score(y_b, p_b)))
        boot_briers.append(float(brier_score_loss(y_b, p_b)))

    def _summary(arr: List[float], orig_metric: float) -> Dict[str, float]:
        if not arr:
            return {"point": orig_metric, "std": 0.0, "ci_lower": orig_metric, "ci_upper": orig_metric}
        return {
            "point": round(float(orig_metric), 4),
            "std": round(float(np.std(arr)), 4),
            "ci_lower": round(float(np.percentile(arr, lower_pct)), 4),
            "ci_upper": round(float(np.percentile(arr, upper_pct)), 4),
        }

    return {
        "pr_auc": _summary(boot_pr_aucs, average_precision_score(y_true, y_prob)),
        "roc_auc": _summary(boot_roc_aucs, roc_auc_score(y_true, y_prob)),
        "brier_score": _summary(boot_briers, brier_score_loss(y_true, y_prob)),
    }


def run_robustness_stress_tests(
    pipeline: Any,
    test_df: pd.DataFrame,
    target_col: str = "forgotten",
) -> Dict[str, Any]:
    """
    Executes adversarial perturbations and extreme case evaluations against a trained pipeline.
    """
    raw_feature_cols = [c for c in ALL_RAW_FEATURES if c in test_df.columns]
    y_true = test_df[target_col].values
    baseline_probs = pipeline.predict_proba(test_df[raw_feature_cols])[:, 1]
    baseline_pr_auc = float(average_precision_score(y_true, baseline_probs))

    stress_results = {
        "baseline_pr_auc": round(baseline_pr_auc, 4),
        "tests": {},
    }

    # 1. Random Feature Dropout (10%, 25%, 50% NaNs)
    for rate in [0.10, 0.25, 0.50]:
        df_dropout = test_df[raw_feature_cols].copy()
        mask = np.random.RandomState(42).rand(*df_dropout.shape) < rate
        # Drop only numeric columns to simulate missing signals
        num_cols = [c for c in df_dropout.columns if c not in ("task_category", "priority", "location")]
        for c in num_cols:
            df_dropout.loc[mask[:, df_dropout.columns.get_loc(c)], c] = np.nan

        probs = pipeline.predict_proba(df_dropout)[:, 1]
        score = float(average_precision_score(y_true, probs))
        stress_results["tests"][f"feature_dropout_{int(rate*100)}pct"] = {
            "pr_auc": round(score, 4),
            "retention_ratio": round(score / max(1e-4, baseline_pr_auc), 2),
            "status": "PASS" if score >= baseline_pr_auc * 0.70 else "DEGRADED",
        }

    # 2. Sparse Behavioral History (New User Simulator: 0 prior completions/forgetting)
    df_sparse = test_df[raw_feature_cols].copy()
    for col in ["previous_completion_count", "previous_forgetting_count"]:
        if col in df_sparse.columns:
            df_sparse[col] = 0
    if "historical_forgetting_rate" in df_sparse.columns:
        df_sparse["historical_forgetting_rate"] = 0.30  # default population prior

    probs_sparse = pipeline.predict_proba(df_sparse)[:, 1]
    score_sparse = float(average_precision_score(y_true, probs_sparse))
    stress_results["tests"]["sparse_history_cold_start"] = {
        "pr_auc": round(score_sparse, 4),
        "retention_ratio": round(score_sparse / max(1e-4, baseline_pr_auc), 2),
        "status": "PASS" if score_sparse >= baseline_pr_auc * 0.75 else "DEGRADED",
    }

    # 3. Extreme Interruption Spikes (50 interruptions today, 25 context switches)
    df_extreme_int = test_df[raw_feature_cols].copy()
    if "interruptions_today" in df_extreme_int.columns:
        df_extreme_int["interruptions_today"] = 50
    if "recent_context_switches" in df_extreme_int.columns:
        df_extreme_int["recent_context_switches"] = 25

    probs_ext = pipeline.predict_proba(df_extreme_int)[:, 1]
    stress_results["tests"]["extreme_interruption_spike"] = {
        "mean_risk_increase": round(float(np.mean(probs_ext) - np.mean(baseline_probs)), 4),
        "monotonic_response": bool(np.mean(probs_ext) > np.mean(baseline_probs)),
        "status": "PASS" if np.mean(probs_ext) > np.mean(baseline_probs) else "INVERTED",
    }

    # 4. Massive Resumption Lag (3600s cognitive recovery delay)
    df_lag = test_df[raw_feature_cols].copy()
    if "avg_interruption_duration" in df_lag.columns:
        df_lag["avg_interruption_duration"] = 60.0  # 1 hour

    probs_lag = pipeline.predict_proba(df_lag)[:, 1]
    stress_results["tests"]["massive_interruption_lag"] = {
        "mean_risk_increase": round(float(np.mean(probs_lag) - np.mean(baseline_probs)), 4),
        "status": "PASS" if np.mean(probs_lag) >= np.mean(baseline_probs) - 0.05 else "FAIL",
    }

    # 5. Missing / No-Deadline Tasks (Inf or NaN deadline distance)
    df_no_deadline = test_df[raw_feature_cols].copy()
    if "deadline_distance_hours" in df_no_deadline.columns:
        df_no_deadline["deadline_distance_hours"] = np.nan

    probs_nd = pipeline.predict_proba(df_no_deadline)[:, 1]
    score_nd = float(average_precision_score(y_true, probs_nd))
    stress_results["tests"]["missing_deadline_hours"] = {
        "pr_auc": round(score_nd, 4),
        "status": "PASS" if score_nd >= baseline_pr_auc * 0.80 else "DEGRADED",
    }

    return stress_results

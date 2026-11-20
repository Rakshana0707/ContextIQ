"""
drift_detector.py

Statistical drift detection engine for ContextIQ (Phase 2.8).
Implements:
1. Population Stability Index (PSI) for numerical and continuous feature distributions.
2. Two-sample Kolmogorov-Smirnov (KS) tests for numerical distribution shifts.
3. Jensen-Shannon (JS) divergence for categorical distributions and risk categories.
4. Missingness rate deviation tracking.
5. Prediction drift monitoring (calibrated probabilities and risk tiers).
6. Concept drift detection (ground-truth performance degradation).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
from scipy.spatial.distance import jensenshannon
from scipy.stats import ks_2samp
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

# PSI Thresholds
PSI_STABLE_THRESHOLD = 0.10
PSI_MODERATE_THRESHOLD = 0.20

# KS Test Alpha
KS_ALPHA = 0.05

# Jensen-Shannon Threshold
JS_DRIFT_THRESHOLD = 0.15

# Missingness Delta Threshold
MISSING_DELTA_THRESHOLD = 0.05


def compute_psi(
    baseline: np.ndarray,
    target: np.ndarray,
    n_bins: int = 10,
    epsilon: float = 1e-4,
) -> float:
    """
    Computes Population Stability Index (PSI) between baseline and target distributions.
    
    PSI = sum((target_pct - baseline_pct) * ln(target_pct / baseline_pct))
    
    Interpretations:
    - PSI < 0.10: No significant distribution change (STABLE).
    - 0.10 <= PSI < 0.20: Moderate distribution change (MODERATE).
    - PSI >= 0.20: Significant distribution shift (DRIFT).
    """
    b = np.asarray(baseline, dtype=float)
    t = np.asarray(target, dtype=float)
    b = b[np.isfinite(b)]
    t = t[np.isfinite(t)]

    if len(b) < 10 or len(t) < 10:
        return 0.0

    # Derive bin edges from baseline quantiles to ensure balanced reference bins
    quantiles = np.linspace(0.0, 100.0, n_bins + 1)
    bin_edges = np.percentile(b, quantiles)
    # Deduplicate in case of low-variance features
    bin_edges = np.unique(bin_edges)
    if len(bin_edges) < 2:
        return 0.0

    bin_edges[0] = -np.inf
    bin_edges[-1] = np.inf

    b_counts, _ = np.histogram(b, bins=bin_edges)
    t_counts, _ = np.histogram(t, bins=bin_edges)

    # Convert to proportions with smoothing
    b_pct = b_counts / float(len(b))
    t_pct = t_counts / float(len(t))

    b_pct = np.clip(b_pct, epsilon, 1.0)
    t_pct = np.clip(t_pct, epsilon, 1.0)

    # Renormalize
    b_pct /= np.sum(b_pct)
    t_pct /= np.sum(t_pct)

    psi_val = np.sum((t_pct - b_pct) * np.log(t_pct / b_pct))
    return float(round(max(0.0, float(psi_val)), 4))


def compute_ks_test(
    baseline: np.ndarray,
    target: np.ndarray,
) -> Tuple[float, float]:
    """
    Computes two-sample Kolmogorov-Smirnov test statistic D and p-value.
    """
    b = np.asarray(baseline, dtype=float)
    t = np.asarray(target, dtype=float)
    b = b[np.isfinite(b)]
    t = t[np.isfinite(t)]

    if len(b) < 10 or len(t) < 10:
        return 0.0, 1.0

    res = ks_2samp(b, t)
    return float(round(res.statistic, 4)), float(round(res.pvalue, 6))


def compute_js_divergence(
    baseline_dist: Dict[str, float],
    target_dist: Dict[str, float],
    epsilon: float = 1e-4,
) -> float:
    """
    Computes Jensen-Shannon divergence between two discrete probability distributions.
    Bounded in [0, 1].
    """
    all_keys = sorted(set(baseline_dist.keys()) | set(target_dist.keys()))
    if not all_keys:
        return 0.0

    p = np.array([baseline_dist.get(k, 0.0) for k in all_keys], dtype=float)
    q = np.array([target_dist.get(k, 0.0) for k in all_keys], dtype=float)

    # Add smoothing and normalize
    p = np.clip(p, epsilon, None)
    q = np.clip(q, epsilon, None)
    p /= np.sum(p)
    q /= np.sum(q)

    js_val = float(jensenshannon(p, q, base=2))
    return float(round(max(0.0, min(1.0, js_val)), 4))


class DriftDetector:
    """Comprehensive behavioral and model drift detection engine."""

    @classmethod
    def evaluate_numerical_feature(
        cls,
        feature_name: str,
        baseline_vals: np.ndarray,
        target_vals: np.ndarray,
    ) -> Dict[str, Any]:
        psi = compute_psi(baseline_vals, target_vals)
        ks_stat, ks_pval = compute_ks_test(baseline_vals, target_vals)

        if psi >= PSI_MODERATE_THRESHOLD or (ks_pval < KS_ALPHA and ks_stat >= 0.20):
            drift_level = "DRIFT"
        elif psi >= PSI_STABLE_THRESHOLD or ks_pval < KS_ALPHA:
            drift_level = "MODERATE"
        else:
            drift_level = "STABLE"

        return {
            "feature": feature_name,
            "feature_type": "numeric",
            "psi": psi,
            "ks_statistic": ks_stat,
            "ks_p_value": ks_pval,
            "drift_level": drift_level,
            "baseline_mean": round(float(np.nanmean(baseline_vals)), 3),
            "target_mean": round(float(np.nanmean(target_vals)), 3),
            "baseline_std": round(float(np.nanstd(baseline_vals)), 3),
            "target_std": round(float(np.nanstd(target_vals)), 3),
        }

    @classmethod
    def evaluate_categorical_feature(
        cls,
        feature_name: str,
        baseline_series: pd.Series,
        target_series: pd.Series,
    ) -> Dict[str, Any]:
        b_counts = baseline_series.value_counts(normalize=True).to_dict()
        t_counts = target_series.value_counts(normalize=True).to_dict()

        js_div = compute_js_divergence(b_counts, t_counts)

        if js_div >= JS_DRIFT_THRESHOLD:
            drift_level = "DRIFT"
        elif js_div >= (JS_DRIFT_THRESHOLD * 0.6):
            drift_level = "MODERATE"
        else:
            drift_level = "STABLE"

        return {
            "feature": feature_name,
            "feature_type": "categorical",
            "js_divergence": js_div,
            "drift_level": drift_level,
            "baseline_distribution": {k: round(v, 4) for k, v in b_counts.items()},
            "target_distribution": {k: round(v, 4) for k, v in t_counts.items()},
        }

    @classmethod
    def evaluate_missingness(
        cls,
        feature_name: str,
        baseline_series: pd.Series,
        target_series: pd.Series,
        threshold: float = MISSING_DELTA_THRESHOLD,
    ) -> Dict[str, Any]:
        b_miss = float(baseline_series.isna().mean())
        t_miss = float(target_series.isna().mean())
        delta = abs(t_miss - b_miss)

        return {
            "feature": feature_name,
            "baseline_missing_rate": round(b_miss, 4),
            "target_missing_rate": round(t_miss, 4),
            "missing_delta": round(delta, 4),
            "missingness_drift": bool(delta >= threshold),
        }

    @classmethod
    def evaluate_feature_drift(
        cls,
        baseline_df: pd.DataFrame,
        target_df: pd.DataFrame,
        numeric_features: List[str],
        categorical_features: List[str],
    ) -> Dict[str, Any]:
        """Runs full feature drift analysis across all features."""
        feature_reports = {}
        drifted_count = 0
        moderate_count = 0

        # 1. Numeric features
        for f in numeric_features:
            if f in baseline_df.columns and f in target_df.columns:
                res = cls.evaluate_numerical_feature(
                    f, baseline_df[f].values, target_df[f].values
                )
                miss = cls.evaluate_missingness(f, baseline_df[f], target_df[f])
                res["missingness"] = miss
                feature_reports[f] = res
                if res["drift_level"] == "DRIFT":
                    drifted_count += 1
                elif res["drift_level"] == "MODERATE":
                    moderate_count += 1

        # 2. Categorical features
        for f in categorical_features:
            if f in baseline_df.columns and f in target_df.columns:
                res = cls.evaluate_categorical_feature(
                    f, baseline_df[f], target_df[f]
                )
                miss = cls.evaluate_missingness(f, baseline_df[f], target_df[f])
                res["missingness"] = miss
                feature_reports[f] = res
                if res["drift_level"] == "DRIFT":
                    drifted_count += 1
                elif res["drift_level"] == "MODERATE":
                    moderate_count += 1

        status = "STABLE"
        if drifted_count >= 2:
            status = "DRIFT_DETECTED"
        elif drifted_count == 1 or moderate_count >= 3:
            status = "MODERATE_WARNING"

        return {
            "status": status,
            "drifted_features_count": drifted_count,
            "moderate_features_count": moderate_count,
            "total_features_evaluated": len(feature_reports),
            "feature_details": feature_reports,
        }

    @classmethod
    def evaluate_prediction_drift(
        cls,
        baseline_probs: np.ndarray,
        target_probs: np.ndarray,
        baseline_categories: Optional[List[str]] = None,
        target_categories: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Monitors shifts in predicted forgetting risk probabilities and risk tiers."""
        prob_psi = compute_psi(baseline_probs, target_probs)
        ks_stat, ks_pval = compute_ks_test(baseline_probs, target_probs)

        b_mean = float(np.mean(baseline_probs))
        t_mean = float(np.mean(target_probs))

        cat_js = 0.0
        b_cat_dist = {}
        t_cat_dist = {}
        if baseline_categories and target_categories:
            b_cat_dist = pd.Series(baseline_categories).value_counts(normalize=True).to_dict()
            t_cat_dist = pd.Series(target_categories).value_counts(normalize=True).to_dict()
            cat_js = compute_js_divergence(b_cat_dist, t_cat_dist)

        if prob_psi >= PSI_MODERATE_THRESHOLD or cat_js >= JS_DRIFT_THRESHOLD:
            status = "PREDICTION_DRIFT_DETECTED"
        elif prob_psi >= PSI_STABLE_THRESHOLD or cat_js >= (JS_DRIFT_THRESHOLD * 0.6):
            status = "MODERATE_SHIFT"
        else:
            status = "STABLE"

        return {
            "status": status,
            "probability_psi": prob_psi,
            "ks_statistic": ks_stat,
            "ks_p_value": ks_pval,
            "category_js_divergence": cat_js,
            "baseline_mean_probability": round(b_mean, 4),
            "target_mean_probability": round(t_mean, 4),
            "mean_probability_delta": round(t_mean - b_mean, 4),
            "baseline_category_distribution": {k: round(v, 4) for k, v in b_cat_dist.items()},
            "target_category_distribution": {k: round(v, 4) for k, v in t_cat_dist.items()},
        }

    @classmethod
    def evaluate_concept_drift(
        cls,
        y_true: np.ndarray,
        y_prob: np.ndarray,
        baseline_pr_auc: float,
        baseline_roc_auc: Optional[float] = None,
        baseline_brier: Optional[float] = None,
        degradation_threshold: float = 0.10,
    ) -> Dict[str, Any]:
        """
        Evaluates concept drift when ground-truth labels become available.
        Flags drift if current PR-AUC degrades relative to the baseline champion model.
        """
        if len(y_true) < 20 or len(np.unique(y_true)) < 2:
            return {
                "status": "INSUFFICIENT_LABELED_DATA",
                "sample_count": len(y_true),
                "concept_drift_detected": False,
            }

        curr_pr_auc = float(average_precision_score(y_true, y_prob))
        curr_roc_auc = float(roc_auc_score(y_true, y_prob))
        curr_brier = float(brier_score_loss(y_true, y_prob))

        pr_auc_drop = (baseline_pr_auc - curr_pr_auc) / max(1e-4, baseline_pr_auc)
        concept_drift = bool(pr_auc_drop >= degradation_threshold)

        return {
            "status": "CONCEPT_DRIFT_DETECTED" if concept_drift else "STABLE",
            "concept_drift_detected": concept_drift,
            "sample_count": len(y_true),
            "baseline_pr_auc": round(baseline_pr_auc, 4),
            "current_pr_auc": round(curr_pr_auc, 4),
            "pr_auc_relative_drop": round(pr_auc_drop, 4),
            "current_roc_auc": round(curr_roc_auc, 4),
            "current_brier_score": round(curr_brier, 4),
            "degradation_threshold": degradation_threshold,
        }

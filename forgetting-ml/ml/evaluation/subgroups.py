"""
subgroups.py

Fine-grained subgroup slicing and performance disaggregation (Phase 2.6).
Evaluates discrimination and calibration across behavioral slices:
- Task Category
- Task Priority
- Deadline Distance
- Interruption Frequency
- User Activity Volume Cohorts
- User Tenure Cohorts

Privacy Guardrail:
Aggregates strictly at cohort level. Zero identifiable per-user outputs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def compute_slice_metrics(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    threshold: float = 0.50,
) -> Dict[str, Any]:
    """Computes comprehensive performance metrics on a slice."""
    n = len(y_true)
    if n == 0 or len(np.unique(y_true)) < 2:
        return {
            "n_samples": n,
            "forgetting_rate": round(float(np.mean(y_true)), 4) if n > 0 else 0.0,
            "pr_auc": None,
            "roc_auc": None,
            "f1": None,
            "precision": None,
            "recall": None,
            "brier_score": round(float(brier_score_loss(y_true, y_prob)), 4) if n > 0 else None,
        }

    preds = (y_prob >= threshold).astype(int)
    return {
        "n_samples": n,
        "forgetting_rate": round(float(np.mean(y_true)), 4),
        "pr_auc": round(float(average_precision_score(y_true, y_prob)), 4),
        "roc_auc": round(float(roc_auc_score(y_true, y_prob)), 4),
        "f1": round(float(f1_score(y_true, preds, zero_division=0)), 4),
        "precision": round(float(precision_score(y_true, preds, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, preds, zero_division=0)), 4),
        "brier_score": round(float(brier_score_loss(y_true, y_prob)), 4),
    }


def evaluate_all_subgroups(
    df: pd.DataFrame,
    y_prob: np.ndarray,
    target_col: str = "forgotten",
    threshold: float = 0.50,
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """
    Disaggregates performance across all behavioral dimensions.
    """
    eval_df = df.copy()
    eval_df["_y_prob"] = y_prob
    eval_df["_y_true"] = eval_df[target_col].values

    subgroup_reports: Dict[str, Dict[str, Dict[str, Any]]] = {}

    # 1. By Task Category
    cat_results = {}
    if "task_category" in eval_df.columns:
        for cat, group in eval_df.groupby("task_category"):
            cat_results[str(cat)] = compute_slice_metrics(
                group["_y_true"].values, group["_y_prob"].values, threshold
            )
    subgroup_reports["task_category"] = cat_results

    # 2. By Task Priority
    prio_results = {}
    if "priority" in eval_df.columns:
        for prio, group in eval_df.groupby("priority"):
            prio_results[str(prio)] = compute_slice_metrics(
                group["_y_true"].values, group["_y_prob"].values, threshold
            )
    subgroup_reports["priority"] = prio_results

    # 3. By Deadline Distance Bucket
    dd_results = {}
    if "deadline_distance_hours" in eval_df.columns:
        dd = eval_df["deadline_distance_hours"]
        eval_df["_dd_bucket"] = pd.cut(
            dd,
            bins=[-np.inf, 6.0, 24.0, np.inf],
            labels=["Short (<=6h)", "Medium (6-24h)", "Long (>24h)"],
        )
        for b, group in eval_df.groupby("_dd_bucket", observed=False):
            dd_results[str(b)] = compute_slice_metrics(
                group["_y_true"].values, group["_y_prob"].values, threshold
            )
    subgroup_reports["deadline_distance"] = dd_results

    # 4. By Interruption Frequency Bucket
    int_results = {}
    if "interruptions_today" in eval_df.columns:
        ints = eval_df["interruptions_today"]
        eval_df["_int_bucket"] = pd.cut(
            ints,
            bins=[-np.inf, 2, 5, np.inf],
            labels=["Low (<=2)", "Medium (3-5)", "High (>=6)"],
        )
        for b, group in eval_df.groupby("_int_bucket", observed=False):
            int_results[str(b)] = compute_slice_metrics(
                group["_y_true"].values, group["_y_prob"].values, threshold
            )
    subgroup_reports["interruption_frequency"] = int_results

    # 5. By User Volume Cohort (Aggregated, no PII)
    if "user_id" in eval_df.columns:
        user_counts = eval_df["user_id"].value_counts()
        eval_df["_user_volume"] = eval_df["user_id"].map(user_counts)
        eval_df["_vol_cohort"] = pd.cut(
            eval_df["_user_volume"],
            bins=[-np.inf, 50, 150, np.inf],
            labels=["Low Volume (<=50)", "Medium Volume (51-150)", "High Volume (>150)"],
        )
        vol_results = {}
        for b, group in eval_df.groupby("_vol_cohort", observed=False):
            vol_results[str(b)] = compute_slice_metrics(
                group["_y_true"].values, group["_y_prob"].values, threshold
            )
        subgroup_reports["user_volume_cohort"] = vol_results

    return subgroup_reports

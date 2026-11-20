"""
fairness.py

Fairness and Disparity Evaluation Engine (Phase 2.6).
Analyzes prediction quality and error distribution across behavioral subgroups
to ensure algorithmic equity and avoid disparate impact:
- False Positive Rate (FPR) parity
- False Negative Rate (FNR) parity
- Equal Opportunity / Recall parity
- Predictive Parity (Precision)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix


def evaluate_group_fairness(
    df: pd.DataFrame,
    group_col: str,
    y_true_col: str,
    y_prob_col: str,
    threshold: float = 0.50,
) -> Dict[str, Any]:
    """
    Computes confusion matrix rates across categorical subgroups and checks for disparity.
    """
    group_stats = {}
    overall_y_true = df[y_true_col].values
    overall_y_prob = df[y_prob_col].values
    overall_preds = (overall_y_prob >= threshold).astype(int)

    tn, fp, fn, tp = confusion_matrix(overall_y_true, overall_preds, labels=[0, 1]).ravel()
    overall_fpr = float(fp / max(1, fp + tn))
    overall_fnr = float(fn / max(1, fn + tp))
    overall_tpr = float(tp / max(1, tp + fn))

    for g_val, group in df.groupby(group_col):
        g_y_true = group[y_true_col].values
        g_y_prob = group[y_prob_col].values
        g_preds = (g_y_prob >= threshold).astype(int)

        if len(g_y_true) < 10 or len(np.unique(g_y_true)) < 2:
            continue

        g_tn, g_fp, g_fn, g_tp = confusion_matrix(g_y_true, g_preds, labels=[0, 1]).ravel()
        fpr = float(g_fp / max(1, g_fp + g_tn))
        fnr = float(g_fn / max(1, g_fn + g_tp))
        tpr = float(g_tp / max(1, g_tp + g_fn))
        prec = float(g_tp / max(1, g_tp + g_fp))

        group_stats[str(g_val)] = {
            "n_samples": len(group),
            "fpr": round(fpr, 4),
            "fnr": round(fnr, 4),
            "recall_tpr": round(tpr, 4),
            "precision": round(prec, 4),
            "fpr_disparity_ratio": round(fpr / max(1e-4, overall_fpr), 2),
            "fnr_disparity_ratio": round(fnr / max(1e-4, overall_fnr), 2),
        }

    # Summary disparity metric: max/min ratio across groups
    fpr_values = [v["fpr"] for v in group_stats.values() if v["fpr"] > 0]
    fnr_values = [v["fnr"] for v in group_stats.values() if v["fnr"] > 0]
    max_fpr_disparity = round(max(fpr_values) / max(1e-4, min(fpr_values)), 2) if fpr_values else 1.0
    max_fnr_disparity = round(max(fnr_values) / max(1e-4, min(fnr_values)), 2) if fnr_values else 1.0

    return {
        "group_dimension": group_col,
        "overall_baseline": {
            "fpr": round(overall_fpr, 4),
            "fnr": round(overall_fnr, 4),
            "recall": round(overall_tpr, 4),
        },
        "groups": group_stats,
        "max_fpr_disparity_ratio": max_fpr_disparity,
        "max_fnr_disparity_ratio": max_fnr_disparity,
        "fairness_flag": "ACCEPTABLE" if (max_fpr_disparity < 2.5 and max_fnr_disparity < 2.5) else "DISPARITY_DETECTED",
    }

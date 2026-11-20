"""
hpo.py

Hyperparameter optimization and class imbalance treatment for tabular model benchmarking.
Strict constraints:
- Walk-forward chronological cross-validation on train splits only (zero leakage).
- Fixed random seeds for deterministic reproducibility.
- Never touches the test set during tuning.
- Compares class weights and threshold optimization.
"""

from __future__ import annotations

import itertools
import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score

from ml.features.feature_spec import ALL_RAW_FEATURES
from ml.training.config import SEED, BENCHMARK_HPO_GRIDS, THRESHOLD_TUNING
from ml.training.splits import time_series_cv_splits
from ml.training.benchmark_models import build_candidate_pipeline


def sample_parameter_candidates(
    param_grid: Dict[str, list],
    n_iter: int = 4,
    seed: int = SEED,
) -> List[Dict[str, Any]]:
    """Deterministically samples up to n_iter parameter combinations from a grid."""
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    all_combos = [dict(zip(keys, v)) for v in itertools.product(*values)]
    
    if len(all_combos) <= n_iter:
        return all_combos
    
    rng = np.random.RandomState(seed)
    chosen_indices = rng.choice(len(all_combos), size=n_iter, replace=False)
    return [all_combos[i] for i in chosen_indices]


def tune_model_hyperparameters(
    model_name: str,
    train_df: pd.DataFrame,
    n_iter: int = 4,
    n_splits: int = 3,
    seed: int = SEED,
    timeout_seconds: float = 120.0,
) -> Tuple[Dict[str, Any], float, List[Dict[str, Any]]]:
    """
    Performs randomized search over hyperparameter grid using walk-forward chronological CV.
    Evaluates PR-AUC on training folds only.
    """
    grid = BENCHMARK_HPO_GRIDS.get(model_name, {})
    if not grid:
        return {}, 0.0, []

    candidates = sample_parameter_candidates(grid, n_iter=n_iter, seed=seed)
    feature_cols = [c for c in ALL_RAW_FEATURES if c in train_df.columns]
    target_col = "forgotten" if "forgotten" in train_df.columns else "will_forget"

    best_params = candidates[0]
    best_pr_auc = -1.0
    tuning_history = []
    t_start = time.perf_counter()

    for idx, params in enumerate(candidates):
        if (time.perf_counter() - t_start) > timeout_seconds:
            break

        fold_scores = []
        try:
            for fold_train, fold_val in time_series_cv_splits(train_df, n_splits=n_splits):
                pipe = build_candidate_pipeline(model_name, custom_params=params)
                pipe.fit(fold_train[feature_cols], fold_train[target_col])
                val_probs = pipe.predict_proba(fold_val[feature_cols])[:, 1]
                score = float(average_precision_score(fold_val[target_col], val_probs))
                fold_scores.append(score)
        except Exception as e:
            # If a candidate fails (e.g. incompatible parameter combo), skip it
            continue

        if fold_scores:
            mean_score = float(np.mean(fold_scores))
            std_score = float(np.std(fold_scores))
            tuning_history.append({
                "trial": idx + 1,
                "params": params,
                "mean_cv_pr_auc": round(mean_score, 4),
                "std_cv_pr_auc": round(std_score, 4),
            })
            if mean_score > best_pr_auc:
                best_pr_auc = mean_score
                best_params = params

    return best_params, max(0.0, best_pr_auc), tuning_history


def evaluate_imbalance_strategies(
    model_name: str,
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    base_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Compares class imbalance handling approaches on validation data:
    1. Unweighted / Default
    2. Balanced class weights
    3. Controlled 1:2 undersampling of the majority class (train fold only)
    """
    feature_cols = [c for c in ALL_RAW_FEATURES if c in train_df.columns]
    target_col = "forgotten" if "forgotten" in train_df.columns else "will_forget"
    results = {}

    # Strategy 1: Standard / Default
    p_def = (base_params or {}).copy()
    if "class_weight" in p_def:
        del p_def["class_weight"]
    if "auto_class_weights" in p_def:
        del p_def["auto_class_weights"]

    try:
        pipe_def = build_candidate_pipeline(model_name, p_def)
        pipe_def.fit(train_df[feature_cols], train_df[target_col])
        probs_def = pipe_def.predict_proba(val_df[feature_cols])[:, 1]
        results["unweighted"] = {
            "pr_auc": round(float(average_precision_score(val_df[target_col], probs_def)), 4),
            "f1": round(float(f1_score(val_df[target_col], (probs_def >= 0.5).astype(int), zero_division=0)), 4),
        }
    except Exception:
        results["unweighted"] = {"pr_auc": 0.0, "f1": 0.0}

    # Strategy 2: Balanced weights
    p_bal = (base_params or {}).copy()
    if model_name in ("logistic_regression", "random_forest", "lightgbm", "hist_gbm"):
        p_bal["class_weight"] = "balanced"
    elif model_name == "catboost":
        p_bal["auto_class_weights"] = "Balanced"

    try:
        pipe_bal = build_candidate_pipeline(model_name, p_bal)
        pipe_bal.fit(train_df[feature_cols], train_df[target_col])
        probs_bal = pipe_bal.predict_proba(val_df[feature_cols])[:, 1]
        results["balanced_weights"] = {
            "pr_auc": round(float(average_precision_score(val_df[target_col], probs_bal)), 4),
            "f1": round(float(f1_score(val_df[target_col], (probs_bal >= 0.5).astype(int), zero_division=0)), 4),
        }
    except Exception:
        results["balanced_weights"] = {"pr_auc": 0.0, "f1": 0.0}

    # Strategy 3: Controlled Undersampling (majority to 2:1 ratio) strictly on train_df
    pos_df = train_df[train_df[target_col] == 1]
    neg_df = train_df[train_df[target_col] == 0]
    target_neg_count = min(len(neg_df), len(pos_df) * 2)
    neg_sampled = neg_df.sample(n=target_neg_count, random_state=SEED)
    under_train_df = pd.concat([pos_df, neg_sampled]).sort_values("date").reset_index(drop=True)

    try:
        pipe_under = build_candidate_pipeline(model_name, p_def)
        pipe_under.fit(under_train_df[feature_cols], under_train_df[target_col])
        probs_under = pipe_under.predict_proba(val_df[feature_cols])[:, 1]
        results["controlled_undersampling"] = {
            "pr_auc": round(float(average_precision_score(val_df[target_col], probs_under)), 4),
            "f1": round(float(f1_score(val_df[target_col], (probs_under >= 0.5).astype(int), zero_division=0)), 4),
        }
    except Exception:
        results["controlled_undersampling"] = {"pr_auc": 0.0, "f1": 0.0}

    return results


def find_optimal_threshold(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    metric: str = "f1",
) -> Tuple[float, float]:
    """Sweeps candidate decision thresholds to maximize validation F1."""
    thresholds = np.linspace(
        THRESHOLD_TUNING.get("min_threshold", 0.1),
        THRESHOLD_TUNING.get("max_threshold", 0.9),
        THRESHOLD_TUNING.get("n_thresholds", 81),
    )
    best_t = 0.5
    best_score = -1.0

    for t in thresholds:
        preds = (y_prob >= t).astype(int)
        if metric == "f1":
            score = float(f1_score(y_true, preds, zero_division=0))
        elif metric == "recall":
            score = float(recall_score(y_true, preds, zero_division=0))
        elif metric == "precision":
            score = float(precision_score(y_true, preds, zero_division=0))
        else:
            score = float(np.mean(preds == y_true))

        if score > best_score:
            best_score = score
            best_t = float(t)

    return round(best_t, 3), round(best_score, 4)

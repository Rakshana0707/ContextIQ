"""
benchmark_models.py

Factory and wrapper utilities for candidate tabular models in ContextIQ:
1. Logistic Regression (Baseline)
2. Random Forest (Baseline)
3. XGBoost (Baseline)
4. LightGBM (Gradient Boosting)
5. CatBoost (Categorical Gradient Boosting)
6. HistGradientBoosting (Scikit-Learn Histogram GBDT)
7. Explainable Boosting Machine (EBM via Microsoft InterpretML)
"""

from __future__ import annotations

import io
import time
from typing import Any, Dict, List, Optional, Tuple
import joblib
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier
import lightgbm as lgb
from catboost import CatBoostClassifier
from interpret.glassbox import ExplainableBoostingClassifier

from ml.features.feature_spec import DEFAULT_SPEC, FeatureSpec
from ml.preprocessing.pipeline import build_preprocessor
from ml.training.config import (
    SEED,
    LogisticRegressionParams,
    RandomForestParams,
    XGBoostParams,
    LightGBMParams,
    CatBoostParams,
    HistGBMParams,
    EBMParams,
)

MODEL_NAMES = [
    "logistic_regression",
    "random_forest",
    "xgboost",
    "lightgbm",
    "catboost",
    "hist_gbm",
    "ebm",
]


def create_model_instance(
    model_name: str,
    custom_params: Optional[Dict[str, Any]] = None,
) -> BaseEstimator:
    """Instantiates a raw classifier with default or custom hyperparameters."""
    params = custom_params.copy() if custom_params else {}

    if model_name == "logistic_regression":
        base_p = LogisticRegressionParams().to_dict()
        base_p.update(params)
        return LogisticRegression(**base_p)

    elif model_name == "random_forest":
        base_p = RandomForestParams().to_dict()
        base_p.update(params)
        return RandomForestClassifier(**base_p)

    elif model_name == "xgboost":
        base_p = XGBoostParams().to_dict()
        base_p.update(params)
        return XGBClassifier(**base_p)

    elif model_name == "lightgbm":
        base_p = LightGBMParams().to_dict()
        base_p.update(params)
        return lgb.LGBMClassifier(**base_p)

    elif model_name == "catboost":
        base_p = CatBoostParams().to_dict()
        base_p.update(params)
        return CatBoostClassifier(**base_p)

    elif model_name == "hist_gbm":
        base_p = HistGBMParams().to_dict()
        base_p.update(params)
        return HistGradientBoostingClassifier(**base_p)

    elif model_name == "ebm":
        base_p = EBMParams().to_dict()
        base_p.update(params)
        return ExplainableBoostingClassifier(**base_p)

    else:
        raise ValueError(f"Unknown model name '{model_name}'. Allowed: {MODEL_NAMES}")


def build_candidate_pipeline(
    model_name: str,
    custom_params: Optional[Dict[str, Any]] = None,
    spec: FeatureSpec = DEFAULT_SPEC,
) -> Pipeline:
    """
    Constructs a complete scikit-learn Pipeline with strict preprocessing and model estimator.
    """
    preprocessor = build_preprocessor(spec)
    classifier = create_model_instance(model_name, custom_params)
    return Pipeline(steps=[
        ("preprocessor", preprocessor),
        ("classifier", classifier),
    ])


def measure_inference_latency(
    pipeline: Pipeline,
    sample_df: pd.DataFrame,
    n_runs: int = 50,
) -> Dict[str, float]:
    """
    Measures single-sample and batch inference latency in milliseconds.
    """
    if sample_df.empty:
        return {"single_latency_ms": 0.0, "batch_latency_ms": 0.0}

    single_row = sample_df.iloc[[0]]

    # Warmup
    _ = pipeline.predict_proba(single_row)
    _ = pipeline.predict_proba(sample_df)

    # Single-sample latency
    single_times = []
    for _ in range(n_runs):
        t0 = time.perf_counter()
        _ = pipeline.predict_proba(single_row)
        single_times.append((time.perf_counter() - t0) * 1000.0)

    # Batch latency (entire sample_df)
    batch_times = []
    for _ in range(max(10, n_runs // 2)):
        t0 = time.perf_counter()
        _ = pipeline.predict_proba(sample_df)
        batch_times.append((time.perf_counter() - t0) * 1000.0)

    return {
        "single_latency_ms": float(np.median(single_times)),
        "batch_latency_ms": float(np.median(batch_times)),
        "single_latency_p95_ms": float(np.percentile(single_times, 95)),
    }


def measure_model_size_kb(pipeline: Pipeline) -> float:
    """Measures serialized size of the pipeline artifact in KB."""
    buf = io.BytesIO()
    joblib.dump(pipeline, buf, compress=3)
    return float(len(buf.getvalue()) / 1024.0)

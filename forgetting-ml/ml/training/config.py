"""
config.py

Centralized hyperparameter and training configuration.
Keeping tunables here (rather than inline) makes the pipeline reproducible
and easy to audit - a recruiter reading this file can immediately see what
knobs were turned and why.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any


SEED: int = 42

MODEL_VERSION: str = "1.1.0"

DATASET_VERSION: str = "1.0.0"

SPLIT_CONFIG: Dict[str, float] = {
    "train_frac": 0.70,
    "val_frac": 0.15,
}

DATASET_CONFIG: Dict[str, Any] = {
    "n_users": 100,
    "n_days": 95,
    "min_observations": 10000,
    "seed": SEED,
}


@dataclass
class LogisticRegressionParams:
    max_iter: int = 1000
    class_weight: str = "balanced"
    C: float = 1.0
    solver: str = "lbfgs"
    random_state: int = SEED

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RandomForestParams:
    n_estimators: int = 400
    max_depth: int = 12
    min_samples_leaf: int = 15
    min_samples_split: int = 40
    class_weight: str = "balanced_subsample"
    max_features: str = "sqrt"
    bootstrap: bool = True
    oob_score: bool = False
    random_state: int = SEED
    n_jobs: int = -1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class XGBoostParams:
    n_estimators: int = 500
    max_depth: int = 5
    learning_rate: float = 0.05
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    colsample_bylevel: float = 0.9
    min_child_weight: int = 5
    reg_alpha: float = 0.1
    reg_lambda: float = 1.0
    gamma: float = 0.0
    eval_metric: str = "logloss"
    objective: str = "binary:logistic"
    tree_method: str = "hist"
    random_state: int = SEED
    n_jobs: int = -1

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


THRESHOLD_TUNING = {
    "metric": "f1",
    "min_threshold": 0.05,
    "max_threshold": 0.95,
    "n_thresholds": 181,
}

CALIBRATION_CONFIG = {
    "methods": ["isotonic", "sigmoid"],
    "cv": "prefit",
}

CROSS_VALIDATION_CONFIG = {
    "n_splits": 5,
    "strategy": "time_series",
    "gap": 0,
}

SHAP_CONFIG = {
    "n_background_samples": 200,
    "n_summary_samples": 500,
    "top_k_features": 20,
}


@dataclass
class LightGBMParams:
    n_estimators: int = 300
    max_depth: int = 6
    num_leaves: int = 31
    learning_rate: float = 0.05
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    class_weight: str = "balanced"
    random_state: int = SEED
    n_jobs: int = -1
    verbose: int = -1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CatBoostParams:
    iterations: int = 400
    depth: int = 6
    learning_rate: float = 0.05
    l2_leaf_reg: float = 3.0
    auto_class_weights: str = "Balanced"
    random_seed: int = SEED
    verbose: int = 0
    thread_count: int = -1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HistGBMParams:
    max_iter: int = 300
    max_depth: int = 6
    learning_rate: float = 0.05
    min_samples_leaf: int = 20
    class_weight: str = "balanced"
    random_state: int = SEED

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EBMParams:
    max_bins: int = 256
    interactions: int = 5
    learning_rate: float = 0.05
    outer_bags: int = 8
    inner_bags: int = 0
    random_state: int = SEED
    n_jobs: int = -1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


BENCHMARK_HPO_GRIDS: Dict[str, Dict[str, list]] = {
    "logistic_regression": {
        "C": [0.01, 0.1, 1.0, 5.0, 10.0],
        "class_weight": ["balanced", None],
    },
    "random_forest": {
        "n_estimators": [100, 250, 400],
        "max_depth": [6, 10, 14],
        "min_samples_leaf": [10, 20, 40],
        "class_weight": ["balanced", "balanced_subsample"],
    },
    "xgboost": {
        "n_estimators": [150, 300, 500],
        "max_depth": [3, 5, 7],
        "learning_rate": [0.02, 0.05, 0.1],
        "subsample": [0.7, 0.8, 1.0],
    },
    "lightgbm": {
        "n_estimators": [150, 300, 500],
        "max_depth": [4, 6, 8],
        "learning_rate": [0.02, 0.05, 0.1],
        "num_leaves": [15, 31, 63],
        "subsample": [0.7, 0.8, 1.0],
    },
    "catboost": {
        "iterations": [200, 400, 600],
        "depth": [4, 6, 8],
        "learning_rate": [0.02, 0.05, 0.1],
        "l2_leaf_reg": [1.0, 3.0, 5.0],
    },
    "hist_gbm": {
        "max_iter": [150, 300, 450],
        "max_depth": [4, 6, 8],
        "learning_rate": [0.02, 0.05, 0.1],
        "min_samples_leaf": [10, 20, 50],
    },
    "ebm": {
        "learning_rate": [0.02, 0.05, 0.1],
        "interactions": [0, 5, 10],
        "outer_bags": [4, 8],
    },
}


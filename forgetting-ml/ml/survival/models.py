"""
models.py

ContextIQ Survival Modeling Pipeline
Phase 2.3 Specification Implementation

Trains and persists survival analysis baselines:
1. Kaplan-Meier Estimator (Non-parametric population & stratified survival)
2. Cox Proportional Hazards Model (Semi-parametric covariate modeling)
3. Weibull Accelerated Failure Time (Parametric hazard modeling)
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import joblib
import numpy as np
import pandas as pd
from lifelines import KaplanMeierFitter, CoxPHFitter, WeibullAFTFitter
from lifelines.utils import concordance_index

# Covariates used in multivariate survival modeling
SURVIVAL_COVARIATES = [
    "deadline_distance_hours",
    "interruptions_today",
    "recent_context_switches",
    "historical_forgetting_rate",
    "avg_resumption_lag_seconds",
    "avg_interruption_duration",
    "priority",
    "task_category",
]


class SurvivalModelPipeline:
    def __init__(self, penalizer: float = 0.05):
        self.penalizer = penalizer
        self.kmf: Optional[KaplanMeierFitter] = None
        self.cph: Optional[CoxPHFitter] = None
        self.aft: Optional[WeibullAFTFitter] = None
        self.stratified_km: Dict[str, Dict[str, KaplanMeierFitter]] = {}
        self.feature_columns: List[str] = []
        self.fitted: bool = False

    def _prepare_survival_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepares dataframe with encoded dummy variables for Cox and AFT fitting."""
        cols = ["duration", "event_observed"]
        for c in SURVIVAL_COVARIATES:
            if c in df.columns:
                cols.append(c)

        sub_df = df[cols].copy()
        # Guarantee minimum duration
        sub_df["duration"] = sub_df["duration"].clip(lower=0.01)

        # One-hot encode categoricals with drop_first to prevent perfect collinearity
        encoded_df = pd.get_dummies(sub_df, columns=["priority", "task_category"], drop_first=True, dtype=float)
        return encoded_df

    def fit(self, train_df: pd.DataFrame) -> "SurvivalModelPipeline":
        """Fits Kaplan-Meier, Cox PH, and Weibull AFT models."""
        durations = train_df["duration"].clip(lower=0.01)
        events = train_df["event_observed"].astype(int)

        # 1. Fit Kaplan-Meier
        self.kmf = KaplanMeierFitter()
        self.kmf.fit(durations=durations, event_observed=events, label="Population Survival")

        # Stratified Kaplan-Meier by Priority
        self.stratified_km["priority"] = {}
        if "priority" in train_df.columns:
            for p_val, grp in train_df.groupby("priority"):
                km = KaplanMeierFitter()
                km.fit(grp["duration"].clip(lower=0.01), grp["event_observed"].astype(int), label=f"Priority_{p_val}")
                self.stratified_km["priority"][str(p_val)] = km

        # 2. Fit Cox Proportional Hazards
        encoded_train = self._prepare_survival_df(train_df)
        self.feature_columns = [c for c in encoded_train.columns if c not in ("duration", "event_observed")]

        self.cph = CoxPHFitter(penalizer=self.penalizer)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.cph.fit(
                encoded_train,
                duration_col="duration",
                event_col="event_observed",
                show_progress=False,
            )

        # 3. Fit Weibull Accelerated Failure Time (AFT) Model
        self.aft = WeibullAFTFitter(penalizer=self.penalizer)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                self.aft.fit(
                    encoded_train,
                    duration_col="duration",
                    event_col="event_observed",
                    show_progress=False,
                )
            except Exception:
                self.aft = None

        self.fitted = True
        return self

    def predict_survival_at_times(
        self,
        X_df: pd.DataFrame,
        times: List[float],
        model_name: str = "cox",
    ) -> np.ndarray:
        """
        Predicts S(t) = P(T > t) for given times across rows in X_df.
        Returns array of shape (n_samples, len(times)).
        """
        if not self.fitted:
            raise RuntimeError("SurvivalModelPipeline must be fitted before predict.")

        if model_name == "km" or self.cph is None:
            # Population Kaplan-Meier survival probabilities
            surv_series = self.kmf.survival_function_at_times(times).values.ravel()
            return np.tile(surv_series, (len(X_df), 1))

        # Cox model individualized survival
        # Align features
        encoded_X = pd.get_dummies(X_df, columns=["priority", "task_category"], drop_first=True, dtype=float)
        # Ensure all training columns exist
        for col in self.feature_columns:
            if col not in encoded_X.columns:
                encoded_X[col] = 0.0
        aligned_X = encoded_X[self.feature_columns]

        # Predict survival matrix (index=times, columns=samples)
        surv_curves = self.cph.predict_survival_function(aligned_X, times=times)
        # Transpose to (n_samples, len(times))
        return surv_curves.values.T

    def get_hazard_ratios(self) -> Dict[str, float]:
        """Returns exp(beta) for each covariate in the Cox model."""
        if not self.fitted or self.cph is None:
            return {}
        summary = self.cph.summary
        return {str(idx): round(float(row["exp(coef)"]), 4) for idx, row in summary.iterrows()}

    def save(self, filepath: Path):
        """Serializes the fitted survival bundle."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        bundle = {
            "pipeline": self,
            "hazard_ratios": self.get_hazard_ratios(),
            "feature_columns": self.feature_columns,
            "model_version": "2.3.0",
        }
        joblib.dump(bundle, filepath)

    @classmethod
    def load(cls, filepath: Path) -> "SurvivalModelPipeline":
        if not filepath.exists():
            raise FileNotFoundError(f"Survival bundle not found at {filepath}")
        data = joblib.load(filepath)
        if isinstance(data, dict) and "pipeline" in data:
            return data["pipeline"]
        return data

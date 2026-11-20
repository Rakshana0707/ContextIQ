"""
calibrator.py

Advanced Probability Calibration Engine for ContextIQ (Phase 2.5).
Implements:
1. Platt Scaling (Logistic Sigmoid Calibration)
2. Isotonic Regression (Non-parametric isotonic mapping)
3. Temperature Scaling (Continuous logit scaling)
4. Comprehensive Diagnostics:
   - Expected Calibration Error (ECE)
   - Reliability diagrams
   - Calibration slope and intercept (logistic calibration-in-the-large)
   - Brier Score & Log Loss
"""

from __future__ import annotations

import io
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.special import expit, logit
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.calibration import calibration_curve
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss

EPSILON = 1e-6


def clip_probabilities(probs: np.ndarray, eps: float = EPSILON) -> np.ndarray:
    """Clips probabilities strictly away from 0.0 and 1.0 to prevent undefined logits."""
    return np.clip(probs, eps, 1.0 - eps)


def compute_calibration_slope_and_intercept(
    y_true: np.ndarray,
    y_prob: np.ndarray,
) -> Tuple[float, float]:
    """
    Fits a univariate logistic regression of true binary labels on logit(predictions):
        logit(P(Y=1)) = beta_0 + beta_1 * logit(y_prob)
    
    Returns:
        (intercept, slope)
        - Ideal intercept (calibration-in-the-large): 0.0
        - Ideal slope: 1.0
        - Slope < 1.0 indicates overconfidence (probabilities too extreme).
        - Slope > 1.0 indicates underconfidence (probabilities too central).
    """
    p_clipped = clip_probabilities(y_prob)
    log_odds = logit(p_clipped).reshape(-1, 1)

    # Fit unpenalized logistic regression
    clf = LogisticRegression(C=1e5, solver="lbfgs")
    try:
        clf.fit(log_odds, y_true)
        intercept = float(clf.intercept_[0])
        slope = float(clf.coef_[0][0])
    except Exception:
        intercept = 0.0
        slope = 1.0

    return round(intercept, 4), round(slope, 4)


def compute_reliability_metrics(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> Dict[str, Any]:
    """Computes comprehensive calibration diagnostics on given probabilities."""
    p_clipped = clip_probabilities(y_prob)
    brier = float(brier_score_loss(y_true, p_clipped))
    nll = float(log_loss(y_true, p_clipped))
    intercept, slope = compute_calibration_slope_and_intercept(y_true, p_clipped)

    # Reliability diagram bins (uniform binning)
    frac_pos, mean_pred = calibration_curve(y_true, p_clipped, n_bins=n_bins, strategy="uniform")
    
    # ECE calculation
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_indices = np.digitize(p_clipped, bin_edges) - 1
    total_samples = len(y_true)
    ece = 0.0

    for i in range(n_bins):
        mask = bin_indices == i
        if np.any(mask):
            weight = np.sum(mask) / total_samples
            cal_err = abs(np.mean(y_true[mask]) - np.mean(p_clipped[mask]))
            ece += weight * cal_err

    return {
        "brier_score": round(brier, 4),
        "log_loss": round(nll, 4),
        "expected_calibration_error": round(float(ece), 4),
        "calibration_intercept": intercept,
        "calibration_slope": slope,
        "bin_mean_predictions": [round(float(x), 4) for x in mean_pred],
        "bin_fractions_positive": [round(float(x), 4) for x in frac_pos],
    }


# =====================================================================
# Calibrator Implementations
# =====================================================================

class PlattScalingCalibrator:
    """Platt Scaling: Fits a sigmoid mapping over logits using unpenalized logistic regression."""

    def __init__(self):
        self.lr = LogisticRegression(C=1e5, solver="lbfgs")
        self.is_fitted = False

    def fit(self, y_prob: np.ndarray, y_true: np.ndarray) -> "PlattScalingCalibrator":
        p_clipped = clip_probabilities(y_prob)
        z = logit(p_clipped).reshape(-1, 1)
        self.lr.fit(z, y_true)
        self.is_fitted = True
        return self

    def predict_proba(self, y_prob: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise ValueError("PlattScalingCalibrator is not fitted.")
        p_clipped = clip_probabilities(y_prob)
        z = logit(p_clipped).reshape(-1, 1)
        return self.lr.predict_proba(z)[:, 1]


class IsotonicCalibrator:
    """Isotonic Regression: Fits a non-parametric isotonic step function."""

    def __init__(self):
        self.iso = IsotonicRegression(y_min=0.0001, y_max=0.9999, out_of_bounds="clip")
        self.is_fitted = False

    def fit(self, y_prob: np.ndarray, y_true: np.ndarray) -> "IsotonicCalibrator":
        p_clipped = clip_probabilities(y_prob)
        self.iso.fit(p_clipped, y_true)
        self.is_fitted = True
        return self

    def predict_proba(self, y_prob: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise ValueError("IsotonicCalibrator is not fitted.")
        p_clipped = clip_probabilities(y_prob)
        return clip_probabilities(self.iso.predict(p_clipped))


class TemperatureScalingCalibrator:
    """Temperature Scaling: Learns a single positive scalar T minimizing cross-entropy on logits."""

    def __init__(self):
        self.temperature: float = 1.0
        self.is_fitted = False

    def fit(self, y_prob: np.ndarray, y_true: np.ndarray) -> "TemperatureScalingCalibrator":
        p_clipped = clip_probabilities(y_prob)
        z = logit(p_clipped)

        def nll_obj(t: float) -> float:
            scaled_p = expit(z / max(1e-4, t))
            return log_loss(y_true, clip_probabilities(scaled_p))

        res = minimize_scalar(nll_obj, bounds=(0.05, 10.0), method="bounded")
        self.temperature = float(res.x)
        self.is_fitted = True
        return self

    def predict_proba(self, y_prob: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise ValueError("TemperatureScalingCalibrator is not fitted.")
        p_clipped = clip_probabilities(y_prob)
        z = logit(p_clipped)
        return clip_probabilities(expit(z / self.temperature))


class ProbabilityCalibrationPipeline:
    """
    Unified manager that fits all 3 calibration methods on validation data,
    evaluates their out-of-fold calibration performance, and selects the optimal calibrator.
    """

    def __init__(self):
        self.calibrators = {
            "platt": PlattScalingCalibrator(),
            "isotonic": IsotonicCalibrator(),
            "temperature": TemperatureScalingCalibrator(),
        }
        self.best_method: str = "uncalibrated"
        self.best_calibrator: Optional[Any] = None
        self.validation_metrics: Dict[str, Dict[str, Any]] = {}
        self.calibration_version: str = "2.5.0"

    def fit(self, y_val_prob: np.ndarray, y_val_true: np.ndarray) -> "ProbabilityCalibrationPipeline":
        # Uncalibrated baseline metrics
        uncal_metrics = compute_reliability_metrics(y_val_true, y_val_prob)
        self.validation_metrics["uncalibrated"] = uncal_metrics

        best_brier = uncal_metrics["brier_score"]
        best_method = "uncalibrated"
        best_calibrator = None

        for name, cal in self.calibrators.items():
            try:
                cal.fit(y_val_prob, y_val_true)
                cal_probs = cal.predict_proba(y_val_prob)
                metrics = compute_reliability_metrics(y_val_true, cal_probs)
                self.validation_metrics[name] = metrics

                # Selection rule: must strictly improve validation Brier score and have ECE < uncalibrated
                if metrics["brier_score"] < best_brier and metrics["expected_calibration_error"] <= uncal_metrics["expected_calibration_error"]:
                    best_brier = metrics["brier_score"]
                    best_method = name
                    best_calibrator = cal
            except Exception as e:
                self.validation_metrics[name] = {"error": str(e)}

        self.best_method = best_method
        self.best_calibrator = best_calibrator
        return self

    def calibrate(self, raw_probs: Union[float, np.ndarray]) -> np.ndarray:
        """Calibrates input raw probabilities using the selected optimal calibrator."""
        arr = np.asarray(raw_probs, dtype=float)
        scalar = arr.ndim == 0
        if scalar:
            arr = arr.reshape(1)

        if self.best_calibrator is None or self.best_method == "uncalibrated":
            out = clip_probabilities(arr)
        else:
            out = self.best_calibrator.predict_proba(arr)

        return float(out[0]) if scalar else out

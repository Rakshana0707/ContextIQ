"""
Causal Evaluator for ContextIQ Intervention Effectiveness Engine (Phase 4.7).
Implements:
- Propensity Score Estimation e(X)
- Inverse Propensity Weighting (IPW)
- Doubly Robust (DR) Average Treatment Effect (ATE) Estimation
- Conditional Average Treatment Effect (CATE) under high cognitive friction
- Welch's t-test p-values & 95% Confidence Intervals
- Statistical Power Guardrails (N >= 20 threshold)
- Habituation / Intervention Fatigue Detection
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple


def _normal_cdf(x: float) -> float:
    """Computes the standard normal cumulative distribution function Phi(x)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _two_tailed_p_value(t_stat: float) -> float:
    """Calculates asymptotic two-tailed p-value for a given test statistic."""
    if math.isnan(t_stat) or math.isinf(t_stat):
        return 1.0
    abs_t = abs(t_stat)
    p = 2.0 * (1.0 - _normal_cdf(abs_t))
    return max(0.0, min(1.0, p))


class CausalEvaluator:
    """
    Evaluates causal treatment effects of behavioral interventions using
    randomized holdouts and doubly robust observational corrections.
    """

    MIN_TOTAL_SAMPLE_SIZE: int = 20
    MIN_TREATED_SAMPLE_SIZE: int = 10
    MIN_CONTROL_SAMPLE_SIZE: int = 5
    FATIGUE_SLOPE_THRESHOLD: float = -0.05
    PROPENSITY_CLIP_EPS: float = 0.05

    @classmethod
    def estimate_propensity_score(
        cls,
        context_features: Dict[str, float],
        weights: Optional[Dict[str, float]] = None,
        bias: float = 0.0,
    ) -> float:
        """
        Estimates the propensity score e(X) = P(Treatment = 1 | X) using a logistic model.
        Features typically include: baseline_bfi, urgency, hour_of_day, priority.
        """
        if weights is None:
            # Default weights prioritizing high friction and high urgency
            weights = {
                "baseline_bfi": 0.02,
                "urgency_score": 0.3,
                "forgetting_risk": 0.4,
                "hourly_interruption_rate": 0.1,
            }

        linear_predictor = bias
        for feature_name, weight in weights.items():
            val = float(context_features.get(feature_name, 0.0))
            linear_predictor += weight * val

        # Logistic sigmoid
        # Clip linear predictor to prevent overflow
        linear_predictor = max(-15.0, min(15.0, linear_predictor))
        raw_propensity = 1.0 / (1.0 + math.exp(-linear_predictor))

        # Positivity / overlap clipping [eps, 1 - eps]
        return max(cls.PROPENSITY_CLIP_EPS, min(1.0 - cls.PROPENSITY_CLIP_EPS, raw_propensity))

    @classmethod
    def compute_observational_difference(
        cls,
        treated_outcomes: List[float],
        control_outcomes: List[float],
    ) -> Tuple[float, float, float]:
        """
        Computes the raw observational difference: mean(Y_T) - mean(Y_C).
        Returns: (difference, mean_treated, mean_control)
        """
        n_t = len(treated_outcomes)
        n_c = len(control_outcomes)

        mean_t = (sum(treated_outcomes) / n_t) if n_t > 0 else 0.0
        mean_c = (sum(control_outcomes) / n_c) if n_c > 0 else 0.0

        return round(mean_t - mean_c, 4), round(mean_t, 4), round(mean_c, 4)

    @classmethod
    def estimate_ipw_ate(
        cls,
        samples: List[Dict[str, Any]],
        clip_weights: float = 10.0,
    ) -> Dict[str, Any]:
        """
        Inverse Propensity Weighting (IPW) estimator for Average Treatment Effect:
        ATE_IPW = (1/N) * sum_i [ (T_i * Y_i / e_i) - ((1 - T_i) * Y_i / (1 - e_i)) ]
        Each sample dict must contain:
        - "treatment": int (1 or 0)
        - "outcome": float (e.g. composite score or BFI delta)
        - "propensity": Optional[float] (if absent, will be estimated or default to 0.5)
        """
        n = len(samples)
        if n == 0:
            return {"ate": 0.0, "sample_size": 0, "standard_error": 0.0}

        treated_weighted = 0.0
        control_weighted = 0.0
        treated_sum_w = 0.0
        control_sum_w = 0.0

        for s in samples:
            t = int(s["treatment"])
            y = float(s["outcome"])
            e = max(cls.PROPENSITY_CLIP_EPS, min(1.0 - cls.PROPENSITY_CLIP_EPS, float(s.get("propensity", 0.5))))

            if t == 1:
                w = min(clip_weights, 1.0 / e)
                treated_weighted += w * y
                treated_sum_w += w
            else:
                w = min(clip_weights, 1.0 / (1.0 - e))
                control_weighted += w * y
                control_sum_w += w

        # Hajek normalized IPW estimator for reduced variance
        mu_1 = (treated_weighted / treated_sum_w) if treated_sum_w > 0 else 0.0
        mu_0 = (control_weighted / control_sum_w) if control_sum_w > 0 else 0.0
        ate = mu_1 - mu_0

        return {
            "ate": round(ate, 4),
            "sample_size": n,
            "mu_treated_weighted": round(mu_1, 4),
            "mu_control_weighted": round(mu_0, 4),
        }

    @classmethod
    def estimate_doubly_robust_ate(
        cls,
        samples: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Doubly Robust (DR) Estimator combining outcome regression models mu_1(x), mu_0(x)
        with propensity score weighting e(x):
        ATE_DR = (1/N) * sum_{i=1}^N [
            mu_1(X_i) - mu_0(X_i)
            + T_i * (Y_i - mu_1(X_i)) / e(X_i)
            - (1 - T_i) * (Y_i - mu_0(X_i)) / (1 - e(X_i))
        ]
        Guaranteed to be unbiased if EITHER outcome model OR propensity model is correct.
        """
        n = len(samples)
        if n == 0:
            return {
                "ate": 0.0,
                "confidence_interval_95": [0.0, 0.0],
                "p_value": 1.0,
                "standard_error": 0.0,
                "is_statistically_valid": False,
                "validation_note": "No samples available.",
            }

        treated_samples = [s for s in samples if int(s["treatment"]) == 1]
        control_samples = [s for s in samples if int(s["treatment"]) == 0]
        n_t = len(treated_samples)
        n_c = len(control_samples)

        # Baseline outcome regressions (sample means as constant baseline models)
        y_t_mean = sum(float(s["outcome"]) for s in treated_samples) / n_t if n_t > 0 else 0.0
        y_c_mean = sum(float(s["outcome"]) for s in control_samples) / n_c if n_c > 0 else 0.0

        dr_terms: List[float] = []

        for s in samples:
            t = int(s["treatment"])
            y = float(s["outcome"])
            e = max(cls.PROPENSITY_CLIP_EPS, min(1.0 - cls.PROPENSITY_CLIP_EPS, float(s.get("propensity", 0.5))))

            mu_1 = float(s.get("predicted_outcome_treated", y_t_mean))
            mu_0 = float(s.get("predicted_outcome_control", y_c_mean))

            term = (mu_1 - mu_0) + (t * (y - mu_1) / e) - ((1 - t) * (y - mu_0) / (1 - e))
            dr_terms.append(term)

        ate_dr = sum(dr_terms) / n

        # Influence function variance and standard error
        variance = sum((term - ate_dr) ** 2 for term in dr_terms) / max(1, (n - 1))
        se = math.sqrt(variance / n) if n > 0 else 0.0

        # Confidence interval (95%)
        ci_lower = round(ate_dr - 1.96 * se, 4)
        ci_upper = round(ate_dr + 1.96 * se, 4)

        # Hypothesis test: H0: ATE = 0
        t_stat = (ate_dr / se) if se > 1e-6 else 0.0
        p_val = _two_tailed_p_value(t_stat)

        # Statistical power validation check
        is_valid = (
            n >= cls.MIN_TOTAL_SAMPLE_SIZE
            and n_t >= cls.MIN_TREATED_SAMPLE_SIZE
            and n_c >= cls.MIN_CONTROL_SAMPLE_SIZE
        )

        validation_note = None
        if not is_valid:
            validation_note = (
                f"Sample size underpowered (Total={n}, Treated={n_t}, Control={n_c}). "
                f"Requires at least {cls.MIN_TOTAL_SAMPLE_SIZE} total (with {cls.MIN_TREATED_SAMPLE_SIZE} treated and {cls.MIN_CONTROL_SAMPLE_SIZE} control) "
                "for verified causal significance."
            )

        return {
            "ate": round(ate_dr, 4),
            "confidence_interval_95": [ci_lower, ci_upper],
            "p_value": round(p_val, 4),
            "standard_error": round(se, 4),
            "sample_size_total": n,
            "sample_size_treated": n_t,
            "sample_size_control": n_c,
            "is_statistically_valid": is_valid,
            "validation_note": validation_note,
        }

    @classmethod
    def estimate_cate(
        cls,
        samples: List[Dict[str, Any]],
        stratum_key: str = "high_friction",
    ) -> Dict[str, Any]:
        """
        Estimates Conditional Average Treatment Effect (CATE) across specific subgroups:
        e.g. during high friction (BFI >= 60) vs. low friction (BFI < 60).
        """
        subgroup_a = [s for s in samples if s.get(stratum_key, False)]
        subgroup_b = [s for s in samples if not s.get(stratum_key, False)]

        res_a = cls.estimate_doubly_robust_ate(subgroup_a)
        res_b = cls.estimate_doubly_robust_ate(subgroup_b)

        return {
            "stratum": stratum_key,
            "subgroup_active": res_a,
            "subgroup_inactive": res_b,
            "heterogeneity_difference": round(res_a["ate"] - res_b["ate"], 4),
        }

    @classmethod
    def detect_habituation_fatigue(
        cls,
        acceptance_history: List[Tuple[float, int]],  # (timestamp_or_day_index, accepted_flag_0_or_1)
    ) -> Tuple[bool, Optional[float]]:
        """
        Detects habituation fatigue over time.
        Calculates linear trend slope dR/dt of acceptance rate.
        If slope < -0.05, flags habituation fatigue.
        """
        if len(acceptance_history) < 8:
            return False, None

        # Sort by day/time
        sorted_history = sorted(acceptance_history, key=lambda x: x[0])
        n = len(sorted_history)

        x_vals = [float(item[0]) for item in sorted_history]
        y_vals = [float(item[1]) for item in sorted_history]

        x_mean = sum(x_vals) / n
        y_mean = sum(y_vals) / n

        denom = sum((x - x_mean) ** 2 for x in x_vals)
        if denom < 1e-6:
            return False, None

        slope = sum((x_vals[i] - x_mean) * (y_vals[i] - y_mean) for i in range(n)) / denom

        is_fatigued = slope < cls.FATIGUE_SLOPE_THRESHOLD
        return is_fatigued, round(slope, 4)

    @classmethod
    def apply_benjamini_hochberg_correction(
        cls,
        comparison_results: List[Dict[str, Any]],
        fdr_alpha: float = 0.05,
    ) -> List[Dict[str, Any]]:
        """
        Applies Benjamini-Hochberg False Discovery Rate (FDR) control for multiple hypothesis testing.
        Adjusts p-values across all intervention types evaluated concurrently.
        """
        m = len(comparison_results)
        if m == 0:
            return []

        # Sort comparisons by raw p-value
        sorted_indices = sorted(
            range(m),
            key=lambda i: comparison_results[i].get("p_value", 1.0)
            if comparison_results[i].get("p_value") is not None
            else 1.0,
        )

        adjusted_results = [dict(c) for c in comparison_results]

        for rank, idx in enumerate(sorted_indices, start=1):
            raw_p = adjusted_results[idx].get("p_value")
            if raw_p is None:
                continue
            bh_critical_value = (rank / m) * fdr_alpha
            adjusted_results[idx]["bh_critical_value"] = round(bh_critical_value, 4)
            adjusted_results[idx]["fdr_significant"] = bool(
                raw_p <= bh_critical_value and adjusted_results[idx].get("is_statistically_valid", False)
            )

        return adjusted_results

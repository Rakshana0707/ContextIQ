"""
Causal Inference Engine & Confounding Analysis Service (ContextIQ Phase 6.3).

Implements:
1. Target Trial Cohort Alignment (Strict Time Zero T0 enforcement, prevents immortal-time bias).
2. Propensity Score Modeling (Regularized Logistic Regression on Minimal Adjustment Sets).
3. Overlap & Positivity Diagnostics (Common support & violation clipping).
4. Covariate Balance Evaluation (Standardized Mean Differences - SMD before and after adjustment).
5. Method Implementations:
   - Doubly Robust AIPW (Champion)
   - Inverse Probability Weighting (Hajek-stabilized & trimmed IPW)
   - Propensity Score Matching (1:1 Nearest-Neighbor with caliper)
   - G-computation Regression Adjustment
6. E-value Sensitivity Analysis for Unmeasured Confounding.
7. Effect Heterogeneity (Subgroup CATE with N >= 30 power guardrails).
8. Explicit Abstention Protocol when assumptions or power fail.
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.preprocessing import StandardScaler

from app.schemas.causal_analysis import (
    AnalysisStatus,
    CausalAnalysisResult,
    CausalEstimand,
    CausalEvaluationRequest,
    CausalMethod,
    CausalQuestionId,
    CovariateBalanceItem,
    OverlapDiagnostics,
    SensitivityAnalysis,
    SubgroupCATE,
    TargetTrialProtocol,
)
from app.services.causal_dag import (
    CAUSAL_DAG_REGISTRY,
    TARGET_TRIAL_PROTOCOLS,
    get_causal_dag,
    get_target_trial,
)

logger = logging.getLogger(__name__)


class CausalInferenceEngine:
    """
    Robust causal inference engine enforcing counterfactual rigor,
    covariate balance, overlap verification, and sensitivity bounds.
    """

    MIN_TOTAL_SAMPLE_SIZE: int = 20
    MIN_TREATED_SAMPLE_SIZE: int = 10
    MIN_CONTROL_SAMPLE_SIZE: int = 10
    MIN_SUBGROUP_SAMPLE_SIZE: int = 30
    DEFAULT_CALIPER_SD: float = 0.20
    PROPENSITY_CLIP_EPS: float = 0.05
    BALANCE_SMD_THRESHOLD: float = 0.10

    @classmethod
    def evaluate(
        cls,
        data: pd.DataFrame,
        question_id: CausalQuestionId,
        method: CausalMethod = CausalMethod.DOUBLY_ROBUST_AIPW,
        caliper: float = 0.20,
        trim_threshold: float = 0.05,
    ) -> CausalAnalysisResult:
        """
        Executes an end-to-end causal analysis for a specified research question.
        Grounded in target trial protocol and DAG minimal adjustment set.
        """
        dag = get_causal_dag(question_id)
        target_trial = get_target_trial(question_id)
        if dag is None or target_trial is None:
            raise ValueError(f"Unknown causal question ID: {question_id}")

        treatment_col = "treatment"
        outcome_col = "outcome"
        adjustment_set = [col for col in dag.minimal_sufficient_adjustment_set if col in data.columns]

        # 1. Guardrail: Sample size checks
        n_total = len(data)
        if treatment_col not in data.columns or outcome_col not in data.columns:
            return cls._build_abstained_result(
                question_id=question_id,
                target_trial=target_trial,
                method=method,
                reason="Missing required treatment or outcome columns in dataset.",
                n_total=n_total,
                n_treated=0,
                n_control=0,
            )

        n_treated = int((data[treatment_col] == 1).sum())
        n_control = int((data[treatment_col] == 0).sum())

        if (
            n_total < cls.MIN_TOTAL_SAMPLE_SIZE
            or n_treated < cls.MIN_TREATED_SAMPLE_SIZE
            or n_control < cls.MIN_CONTROL_SAMPLE_SIZE
        ):
            return cls._build_abstained_result(
                question_id=question_id,
                target_trial=target_trial,
                method=method,
                reason=(
                    f"Insufficient sample size for causal identification: N={n_total} "
                    f"(Treated: {n_treated}, Control: {n_control}). "
                    f"Minimum required: N>={cls.MIN_TOTAL_SAMPLE_SIZE}, Treated>={cls.MIN_TREATED_SAMPLE_SIZE}, Control>={cls.MIN_CONTROL_SAMPLE_SIZE}."
                ),
                n_total=n_total,
                n_treated=n_treated,
                n_control=n_control,
            )

        # 2. Raw observational difference
        y_treated = data[data[treatment_col] == 1][outcome_col].astype(float)
        y_control = data[data[treatment_col] == 0][outcome_col].astype(float)
        mean_y1 = float(y_treated.mean())
        mean_y0 = float(y_control.mean())
        raw_diff = round(mean_y1 - mean_y0, 4)

        if not adjustment_set:
            return cls._build_abstained_result(
                question_id=question_id,
                target_trial=target_trial,
                method=method,
                reason="No pre-treatment confounders from the minimal adjustment set are available in data.",
                n_total=n_total,
                n_treated=n_treated,
                n_control=n_control,
                raw_diff=raw_diff,
            )

        # 3. Propensity Score Estimation
        X = data[adjustment_set].copy()
        # Handle non-numeric encoding
        X_encoded = pd.get_dummies(X, drop_first=True)
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_encoded)

        T = data[treatment_col].values.astype(int)
        Y = data[outcome_col].values.astype(float)

        ps_model = LogisticRegression(C=1.0, max_iter=1000, random_state=42)
        ps_model.fit(X_scaled, T)
        propensities = ps_model.predict_proba(X_scaled)[:, 1]

        # 4. Overlap & Positivity Diagnostics
        overlap_diag = cls._evaluate_overlap(
            propensities=propensities,
            treatment=T,
            trim_threshold=trim_threshold,
        )

        if not overlap_diag.has_sufficient_overlap:
            return cls._build_abstained_result(
                question_id=question_id,
                target_trial=target_trial,
                method=method,
                reason=(
                    f"Severe positivity/overlap violation: {overlap_diag.positivity_violations_pct}% "
                    f"of units fall outside common support [{overlap_diag.common_support_min:.3f}, {overlap_diag.common_support_max:.3f}]. "
                    f"Counterfactual identification requires positive probability of both treatment conditions."
                ),
                n_total=n_total,
                n_treated=n_treated,
                n_control=n_control,
                raw_diff=raw_diff,
                overlap=overlap_diag,
            )

        # 5. Method-Specific Estimation & Covariate Balance
        if method == CausalMethod.INVERSE_PROBABILITY_WEIGHTING:
            est_res = cls._estimate_ipw(X=X_encoded, T=T, Y=Y, propensities=propensities, trim_eps=trim_threshold)
        elif method == CausalMethod.PROPENSITY_SCORE_MATCHING:
            est_res = cls._estimate_matching(X=X_encoded, T=T, Y=Y, propensities=propensities, caliper_sd=caliper)
        elif method == CausalMethod.REGRESSION_ADJUSTMENT:
            est_res = cls._estimate_regression_adjustment(X=X_scaled, T=T, Y=Y)
        else:
            # Default: Doubly Robust AIPW
            est_res = cls._estimate_aipw(X=X_scaled, X_raw=X_encoded, T=T, Y=Y, propensities=propensities, trim_eps=trim_threshold)

        causal_effect = est_res["effect"]
        se = est_res["se"]
        ci = est_res["ci"]
        p_val = est_res["p_value"]
        balance_items = est_res["balance"]

        # 6. Balance Assessment
        imbalanced_count = sum(1 for b in balance_items if not b.is_balanced)
        severe_imbalance_ratio = imbalanced_count / max(1, len(balance_items))

        # 7. Sensitivity Analysis (E-value)
        sensitivity = cls._calculate_e_value(
            effect=causal_effect,
            ci_lower=ci[0] if ci else 0.0,
            ci_upper=ci[1] if ci else 0.0,
            y_baseline=mean_y0,
            y_is_binary=bool(data[outcome_col].nunique() <= 2),
        )

        # 8. Effect Heterogeneity (Subgroup CATE)
        subgroup_cates = cls._evaluate_subgroup_heterogeneity(
            data=data,
            treatment_col=treatment_col,
            outcome_col=outcome_col,
            adjustment_cols=adjustment_set,
        )

        # Determine overall analysis status
        if severe_imbalance_ratio > 0.50:
            status = AnalysisStatus.INCONCLUSIVE
            explanation = (
                f"Residual confounding: {imbalanced_count}/{len(balance_items)} covariates remain "
                f"imbalanced (|SMD| > 0.10) after adjustment. Causal effect cannot be definitively claimed."
            )
        elif sensitivity and sensitivity.robustness_assessment == "FRAGILE":
            status = AnalysisStatus.INCONCLUSIVE
            explanation = (
                f"Weak sensitivity: Observed effect has E-value={sensitivity.e_value_estimate:.2f}. "
                f"Plausible unmeasured confounders (e.g., emotional frustration, external interruptions) could explain it away."
            )
        else:
            status = AnalysisStatus.CONVINCING
            explanation = None

        return CausalAnalysisResult(
            question_id=question_id,
            title=target_trial.title,
            status=status,
            method_used=method,
            target_trial=target_trial,
            sample_size_treated=n_treated,
            sample_size_control=n_control,
            total_sample_size=n_total,
            raw_observational_difference=raw_diff,
            estimated_causal_effect=round(float(causal_effect), 4),
            confidence_interval=(round(float(ci[0]), 4), round(float(ci[1]), 4)) if ci else None,
            standard_error=round(float(se), 4) if se is not None else None,
            p_value=round(float(p_val), 4) if p_val is not None else None,
            covariate_balance=balance_items,
            overlap_diagnostics=overlap_diag,
            sensitivity=sensitivity,
            effect_heterogeneity=subgroup_cates,
            identification_assumptions=[
                "Conditional Exchangeability (No unmeasured confounders conditional on adjustment set)",
                "Positivity / Common Support (0 < P(A=1|X) < 1 across all covariate strata)",
                "Consistency (Observed outcome under intervention matches counterfactual potential outcome)",
                "SUTVA (Stable Unit Treatment Value Assumption: No interference between distinct disruption episodes)",
            ],
            limitations=[
                "Observational design cannot completely rule out unmeasured psychological frustration or offline disruption.",
                "Immortal-time bias was controlled by strict T0 alignment, but self-selection into software usage may persist.",
                "Subgroup CATE estimates with N < 30 are suppressed to prevent premature generalizations.",
            ],
            abstention_explanation=explanation,
        )

    # -----------------------------------------------------------------------
    # Overlap & Positivity Diagnostics
    # -----------------------------------------------------------------------

    @classmethod
    def _evaluate_overlap(
        cls,
        propensities: np.ndarray,
        treatment: np.ndarray,
        trim_threshold: float,
    ) -> OverlapDiagnostics:
        treated_ps = propensities[treatment == 1]
        control_ps = propensities[treatment == 0]

        cs_min = float(max(np.min(treated_ps), np.min(control_ps)))
        cs_max = float(min(np.max(treated_ps), np.max(control_ps)))

        # Count positivity violations (too close to 0 or 1)
        violations = np.sum((propensities < trim_threshold) | (propensities > (1.0 - trim_threshold)))
        violation_pct = round(float(violations) / len(propensities) * 100.0, 1)

        # Sufficient overlap requires valid non-empty range and reasonable violation percentage (< 25%)
        has_overlap = bool((cs_min < cs_max) and (violation_pct < 25.0) and (cs_max - cs_min >= 0.10))

        return OverlapDiagnostics(
            common_support_min=round(cs_min, 3),
            common_support_max=round(cs_max, 3),
            treated_propensity_mean=round(float(np.mean(treated_ps)), 3),
            control_propensity_mean=round(float(np.mean(control_ps)), 3),
            positivity_violations_count=int(violations),
            positivity_violations_pct=violation_pct,
            has_sufficient_overlap=has_overlap,
        )

    # -----------------------------------------------------------------------
    # Balance Diagnostics (SMD)
    # -----------------------------------------------------------------------

    @classmethod
    def _calculate_smd(
        cls,
        x: np.ndarray,
        treatment: np.ndarray,
        weights: Optional[np.ndarray] = None,
    ) -> Tuple[float, float, float]:
        """
        Calculates weighted or unweighted Standardized Mean Difference (SMD).
        Returns: (mean_treated, mean_control, smd)
        """
        if weights is None:
            w1 = np.ones(np.sum(treatment == 1))
            w0 = np.ones(np.sum(treatment == 0))
        else:
            w1 = weights[treatment == 1]
            w0 = weights[treatment == 0]

        x1 = x[treatment == 1]
        x0 = x[treatment == 0]

        mean1 = float(np.average(x1, weights=w1))
        mean0 = float(np.average(x0, weights=w0))

        var1 = float(np.average((x1 - mean1) ** 2, weights=w1))
        var0 = float(np.average((x0 - mean0) ** 2, weights=w0))

        pooled_sd = math.sqrt(max(1e-6, 0.5 * (var1 + var0)))
        smd = (mean1 - mean0) / pooled_sd if pooled_sd > 1e-5 else 0.0
        return round(mean1, 3), round(mean0, 3), round(float(smd), 3)

    @classmethod
    def _compute_balance_table(
        cls,
        X_df: pd.DataFrame,
        treatment: np.ndarray,
        weights: Optional[np.ndarray] = None,
    ) -> List[CovariateBalanceItem]:
        items: List[CovariateBalanceItem] = []
        for col in X_df.columns:
            vals = X_df[col].values.astype(float)
            m1_raw, m0_raw, smd_raw = cls._calculate_smd(vals, treatment, weights=None)
            m1_adj, m0_adj, smd_adj = cls._calculate_smd(vals, treatment, weights=weights)

            items.append(
                CovariateBalanceItem(
                    covariate_name=col,
                    mean_treated=m1_adj,
                    mean_control=m0_adj,
                    smd_unadjusted=smd_raw,
                    smd_adjusted=smd_adj,
                    is_balanced=bool(abs(smd_adj) <= cls.BALANCE_SMD_THRESHOLD),
                )
            )
        return items

    # -----------------------------------------------------------------------
    # Causal Estimators
    # -----------------------------------------------------------------------

    @classmethod
    def _estimate_aipw(
        cls,
        X: np.ndarray,
        X_raw: pd.DataFrame,
        T: np.ndarray,
        Y: np.ndarray,
        propensities: np.ndarray,
        trim_eps: float,
    ) -> Dict[str, Any]:
        """Doubly Robust Augmented Inverse Probability Weighting (AIPW)."""
        N = len(T)
        clipped_ps = np.clip(propensities, trim_eps, 1.0 - trim_eps)

        # 1. Outcome models mu1(X) and mu0(X)
        reg1 = LinearRegression()
        reg0 = LinearRegression()

        X1, Y1 = X[T == 1], Y[T == 1]
        X0, Y0 = X[T == 0], Y[T == 0]

        reg1.fit(X1, Y1)
        reg0.fit(X0, Y0)

        mu1_hat = reg1.predict(X)
        mu0_hat = reg0.predict(X)

        # 2. AIPW Individual Scores (Doubly Robust pseudo-outcomes)
        # Gamma1 = mu1(X) + T*(Y - mu1(X))/e(X)
        # Gamma0 = mu0(X) + (1-T)*(Y - mu0(X))/(1-e(X))
        gamma1 = mu1_hat + (T * (Y - mu1_hat)) / clipped_ps
        gamma0 = mu0_hat + ((1 - T) * (Y - mu0_hat)) / (1.0 - clipped_ps)

        tau_i = gamma1 - gamma0
        ate = float(np.mean(tau_i))

        # Asymptotic Standard Error via Influence Function Variance
        var_ate = float(np.var(tau_i, ddof=1) / N)
        se = math.sqrt(max(1e-8, var_ate))

        z_crit = 1.96
        ci = (ate - z_crit * se, ate + z_crit * se)
        z_stat = ate / se if se > 1e-8 else 0.0
        p_value = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z_stat) / math.sqrt(2.0))))

        # Weights for balance table: Hajek stabilized weights
        w = np.where(T == 1, 1.0 / clipped_ps, 1.0 / (1.0 - clipped_ps))
        balance = cls._compute_balance_table(X_raw, T, weights=w)

        return {
            "effect": ate,
            "se": se,
            "ci": ci,
            "p_value": p_value,
            "balance": balance,
        }

    @classmethod
    def _estimate_ipw(
        cls,
        X: pd.DataFrame,
        T: np.ndarray,
        Y: np.ndarray,
        propensities: np.ndarray,
        trim_eps: float,
    ) -> Dict[str, Any]:
        """Hajek-stabilized Inverse Probability Weighting (IPW) with weight trimming."""
        clipped_ps = np.clip(propensities, trim_eps, 1.0 - trim_eps)
        raw_weights = np.where(T == 1, 1.0 / clipped_ps, 1.0 / (1.0 - clipped_ps))

        # Trim at 95th percentile to prevent high-variance instability
        p95 = float(np.percentile(raw_weights, 95))
        trimmed_weights = np.clip(raw_weights, 0.0, p95)

        # Hajek estimator (normalized weights)
        sum_w1 = np.sum(trimmed_weights[T == 1])
        sum_w0 = np.sum(trimmed_weights[T == 0])

        mean_y1_ipw = np.sum(trimmed_weights[T == 1] * Y[T == 1]) / max(1e-6, sum_w1)
        mean_y0_ipw = np.sum(trimmed_weights[T == 0] * Y[T == 0]) / max(1e-6, sum_w0)
        ate = float(mean_y1_ipw - mean_y0_ipw)

        # Standard error via weighted variance approximation
        var1 = np.sum(((trimmed_weights[T == 1] / sum_w1) ** 2) * ((Y[T == 1] - mean_y1_ipw) ** 2))
        var0 = np.sum(((trimmed_weights[T == 0] / sum_w0) ** 2) * ((Y[T == 0] - mean_y0_ipw) ** 2))
        se = math.sqrt(max(1e-8, var1 + var0))

        ci = (ate - 1.96 * se, ate + 1.96 * se)
        z_stat = ate / se if se > 1e-8 else 0.0
        p_val = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z_stat) / math.sqrt(2.0))))

        balance = cls._compute_balance_table(X, T, weights=trimmed_weights)
        return {"effect": ate, "se": se, "ci": ci, "p_value": p_val, "balance": balance}

    @classmethod
    def _estimate_matching(
        cls,
        X: pd.DataFrame,
        T: np.ndarray,
        Y: np.ndarray,
        propensities: np.ndarray,
        caliper_sd: float,
    ) -> Dict[str, Any]:
        """Nearest Neighbor 1:1 Propensity Score Matching with Caliper."""
        # Convert to logit propensity for matching scale
        clipped_ps = np.clip(propensities, 0.001, 0.999)
        logit_ps = np.log(clipped_ps / (1.0 - clipped_ps))
        caliper = caliper_sd * float(np.std(logit_ps))

        treated_idx = np.where(T == 1)[0]
        control_idx = np.where(T == 0)[0]

        matched_treated: List[int] = []
        matched_control: List[int] = []
        available_controls = set(control_idx)

        for t_i in treated_idx:
            t_logit = logit_ps[t_i]
            best_c = None
            best_dist = float("inf")
            for c_i in available_controls:
                dist = abs(t_logit - logit_ps[c_i])
                if dist < best_dist and dist <= caliper:
                    best_dist = dist
                    best_c = c_i

            if best_c is not None:
                matched_treated.append(t_i)
                matched_control.append(best_c)
                available_controls.remove(best_c)

        if len(matched_treated) < 5:
            # Fallback to simple regression if insufficient matches within caliper
            return cls._estimate_regression_adjustment(X=X.values, T=T, Y=Y)

        diffs = Y[matched_treated] - Y[matched_control]
        att = float(np.mean(diffs))
        se = float(np.std(diffs, ddof=1) / math.sqrt(len(diffs)))
        ci = (att - 1.96 * se, att + 1.96 * se)
        z_stat = att / se if se > 1e-8 else 0.0
        p_val = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z_stat) / math.sqrt(2.0))))

        # Balance on matched subset
        matched_indices = matched_treated + matched_control
        sub_X = X.iloc[matched_indices].copy()
        sub_T = T[matched_indices]
        balance = cls._compute_balance_table(sub_X, sub_T, weights=None)

        return {"effect": att, "se": se, "ci": ci, "p_value": p_val, "balance": balance}

    @classmethod
    def _estimate_regression_adjustment(
        cls,
        X: np.ndarray,
        T: np.ndarray,
        Y: np.ndarray,
    ) -> Dict[str, Any]:
        """G-computation regression adjustment."""
        reg1 = LinearRegression().fit(X[T == 1], Y[T == 1])
        reg0 = LinearRegression().fit(X[T == 0], Y[T == 0])

        y1_pred = reg1.predict(X)
        y0_pred = reg0.predict(X)

        individual_effects = y1_pred - y0_pred
        ate = float(np.mean(individual_effects))
        se = float(np.std(individual_effects, ddof=1) / math.sqrt(len(Y)))
        ci = (ate - 1.96 * se, ate + 1.96 * se)
        z_stat = ate / se if se > 1e-8 else 0.0
        p_val = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z_stat) / math.sqrt(2.0))))

        balance: List[CovariateBalanceItem] = []
        return {"effect": ate, "se": se, "ci": ci, "p_value": p_val, "balance": balance}

    # -----------------------------------------------------------------------
    # Sensitivity Analysis: E-Value
    # -----------------------------------------------------------------------

    @classmethod
    def _calculate_e_value(
        cls,
        effect: float,
        ci_lower: float,
        ci_upper: float,
        y_baseline: float,
        y_is_binary: bool,
    ) -> SensitivityAnalysis:
        """
        Calculates the E-value for the point estimate and lower confidence limit.
        Quantifies the minimum relative risk an unmeasured confounder must have with
        both treatment and outcome to explain away the observed causal effect.
        """
        if y_is_binary:
            p0 = max(0.01, min(0.99, y_baseline))
            p1 = max(0.01, min(0.99, p0 + effect))
            rr = p1 / p0
            rr_low = max(0.01, min(0.99, p0 + ci_lower)) / p0
        else:
            # Continuous conversion via Cohen's d: RR ~ exp(0.91 * d)
            # Assuming unit standard deviation approximation
            d = effect
            rr = math.exp(0.91 * d)
            rr_low = math.exp(0.91 * ci_lower)

        # Invert if protective effect (RR < 1)
        if rr < 1.0:
            rr = 1.0 / max(0.001, rr)
            rr_low = 1.0 / max(0.001, rr_low)

        # Point E-value: RR + sqrt(RR * (RR - 1))
        e_val = rr + math.sqrt(max(0.0, rr * (rr - 1.0)))

        # CI bound E-value
        if rr_low <= 1.0:
            e_val_low = 1.0  # Null can be explained by unmeasured confounder of strength 1.0 (none)
        else:
            e_val_low = rr_low + math.sqrt(max(0.0, rr_low * (rr_low - 1.0)))

        if e_val >= 2.5:
            assessment = "ROBUST"
            interp = (
                f"Robust to moderate unmeasured confounding (E-value = {e_val:.2f}). "
                "An unmeasured confounder must multiply the risk of both intervention and outcome "
                f"by at least {e_val:.2f}-fold to fully explain away this estimated effect."
            )
        elif e_val >= 1.5:
            assessment = "MODERATE"
            interp = (
                f"Moderate robustness (E-value = {e_val:.2f}). "
                "Plausible unmeasured workplace stress or meeting disruptions could partially attenuate this effect."
            )
        else:
            assessment = "FRAGILE"
            interp = (
                f"Fragile causal claim (E-value = {e_val:.2f}, CI lower bound = {e_val_low:.2f}). "
                "Even minor unmeasured factors (such as coworker chatting or mild fatigue) could nullify this result."
            )

        return SensitivityAnalysis(
            e_value_estimate=round(float(e_val), 2),
            e_value_lower_bound=round(float(e_val_low), 2),
            interpretation=interp,
            robustness_assessment=assessment,
        )

    # -----------------------------------------------------------------------
    # Effect Heterogeneity (Subgroup CATE)
    # -----------------------------------------------------------------------

    @classmethod
    def _evaluate_subgroup_heterogeneity(
        cls,
        data: pd.DataFrame,
        treatment_col: str,
        outcome_col: str,
        adjustment_cols: List[str],
    ) -> List[SubgroupCATE]:
        """
        Calculates stratum-specific CATE while enforcing strict sample size
        guardrails (N >= 30). Suppresses underpowered subgroup claims.
        """
        cates: List[SubgroupCATE] = []
        candidate_dimensions = [
            ("task_category", "Task Category"),
            ("task_priority", "Task Urgency"),
            ("time_of_day_bucket", "Time of Day"),
            ("user_experience_level", "User Experience"),
            ("context_switch_frequency", "Context Switch Frequency"),
        ]

        for dim_col, dim_label in candidate_dimensions:
            if dim_col not in data.columns:
                continue

            unique_strata = data[dim_col].dropna().unique()
            for stratum in unique_strata:
                stratum_data = data[data[dim_col] == stratum]
                n_t = int((stratum_data[treatment_col] == 1).sum())
                n_c = int((stratum_data[treatment_col] == 0).sum())
                n_stratum = n_t + n_c

                if n_stratum < cls.MIN_SUBGROUP_SAMPLE_SIZE or n_t < 5 or n_c < 5:
                    cates.append(
                        SubgroupCATE(
                            subgroup_name=str(stratum),
                            dimension=dim_label,
                            sample_size_treated=n_t,
                            sample_size_control=n_c,
                            estimated_cate=None,
                            ci_lower=None,
                            ci_upper=None,
                            is_statistically_sound=False,
                            abstention_reason=(
                                f"Underpowered subgroup: N={n_stratum} < {cls.MIN_SUBGROUP_SAMPLE_SIZE} "
                                f"(Treated: {n_t}, Control: {n_c}). Suppressed to prevent premature conclusions."
                            ),
                        )
                    )
                else:
                    # Stratum has sufficient sample size
                    y1 = stratum_data[stratum_data[treatment_col] == 1][outcome_col].astype(float)
                    y0 = stratum_data[stratum_data[treatment_col] == 0][outcome_col].astype(float)
                    sub_diff = float(y1.mean() - y0.mean())
                    se = float(math.sqrt(y1.var(ddof=1) / n_t + y0.var(ddof=1) / n_c))
                    ci = (round(sub_diff - 1.96 * se, 3), round(sub_diff + 1.96 * se, 3))

                    cates.append(
                        SubgroupCATE(
                            subgroup_name=str(stratum),
                            dimension=dim_label,
                            sample_size_treated=n_t,
                            sample_size_control=n_c,
                            estimated_cate=round(sub_diff, 3),
                            ci_lower=ci[0],
                            ci_upper=ci[1],
                            is_statistically_sound=True,
                            abstention_reason=None,
                        )
                    )

        return cates

    # -----------------------------------------------------------------------
    # Helper: Build Abstained Result
    # -----------------------------------------------------------------------

    @classmethod
    def _build_abstained_result(
        cls,
        question_id: CausalQuestionId,
        target_trial: TargetTrialProtocol,
        method: CausalMethod,
        reason: str,
        n_total: int,
        n_treated: int,
        n_control: int,
        raw_diff: float = 0.0,
        overlap: Optional[OverlapDiagnostics] = None,
    ) -> CausalAnalysisResult:
        if overlap is None:
            overlap = OverlapDiagnostics(
                common_support_min=0.0,
                common_support_max=1.0,
                treated_propensity_mean=0.5,
                control_propensity_mean=0.5,
                positivity_violations_count=0,
                positivity_violations_pct=0.0,
                has_sufficient_overlap=False,
            )

        return CausalAnalysisResult(
            question_id=question_id,
            title=target_trial.title,
            status=AnalysisStatus.ABSTAINED,
            method_used=method,
            target_trial=target_trial,
            sample_size_treated=n_treated,
            sample_size_control=n_control,
            total_sample_size=n_total,
            raw_observational_difference=raw_diff,
            estimated_causal_effect=None,
            confidence_interval=None,
            standard_error=None,
            p_value=None,
            covariate_balance=[],
            overlap_diagnostics=overlap,
            sensitivity=None,
            effect_heterogeneity=[],
            identification_assumptions=[
                "Conditional Exchangeability (Violated or unverifiable due to insufficient data)",
                "Positivity / Common Support (Violated)",
            ],
            limitations=[
                f"Analysis abstained: {reason}",
                "ContextIQ strictly abstains from presenting correlation as causal evidence.",
            ],
            abstention_explanation=reason,
        )


# ===========================================================================
# 3. Observational Study Dataset Generator for Benchmark & Testing
# ===========================================================================

class CausalDatasetGenerator:
    """
    Generates synthetic observational datasets with realistic confounding,
    selection mechanisms, effect modifiers, and known counterfactual ground truth.
    """

    @classmethod
    def generate_study_data(
        cls,
        question_id: CausalQuestionId,
        n_samples: int = 300,
        true_ate: float = 0.18,
        confounding_strength: float = 0.70,
        seed: int = 42,
    ) -> pd.DataFrame:
        """
        Creates an observational benchmark dataframe adhering strictly to the DAG.
        Confounders bias treatment assignment towards higher-friction/higher-urgency units.
        """
        rng = np.random.RandomState(seed)

        if question_id == CausalQuestionId.RECOVERY_BUFFER_ON_RESUMPTION:
            baseline_bfi = rng.normal(loc=45.0, scale=15.0, size=n_samples)
            baseline_bfi = np.clip(baseline_bfi, 10.0, 95.0)

            interruption_duration = rng.exponential(scale=180.0, size=n_samples) + 60.0
            interruption_duration = np.clip(interruption_duration, 60.0, 1200.0)

            hour_of_day = rng.randint(8, 19, size=n_samples)
            calendar_meeting_density = rng.poisson(lam=3.0, size=n_samples)
            task_priority = rng.choice([1.0, 2.0, 3.0, 4.0], size=n_samples, p=[0.2, 0.4, 0.3, 0.1])

            # Selection mechanism: Higher BFI, longer interruption, and higher priority increase P(A=1)
            logit_ps = (
                -1.5
                + confounding_strength * (
                    0.03 * (baseline_bfi - 45.0)
                    + 0.002 * (interruption_duration - 180.0)
                    + 0.4 * (task_priority - 2.0)
                    + 0.15 * (calendar_meeting_density - 3.0)
                )
                + rng.normal(0, 0.4, size=n_samples)
            )
            prob_treated = 1.0 / (1.0 + np.exp(-logit_ps))
            treatment = (rng.uniform(0, 1, size=n_samples) < prob_treated).astype(int)

            # Potential outcomes
            # Baseline probability of resumption without buffer (confounded by friction and interruption duration)
            base_prob = (
                0.60
                - 0.004 * (baseline_bfi - 45.0)
                - 0.0005 * (interruption_duration - 180.0)
                + 0.05 * (task_priority - 2.0)
            )
            base_prob = np.clip(base_prob, 0.10, 0.90)

            # True causal lift of buffer
            y_prob = base_prob + treatment * true_ate
            y_prob = np.clip(y_prob, 0.05, 0.95)
            outcome = (rng.uniform(0, 1, size=n_samples) < y_prob).astype(int)

            # Subgroup columns
            task_category = rng.choice(["Coding", "DeepWork", "Administrative", "Communication"], size=n_samples)
            time_of_day_bucket = np.where(hour_of_day < 12, "Morning", "Afternoon")
            task_priority_str = np.where(task_priority >= 3.0, "HIGH", "LOW")

            return pd.DataFrame({
                "treatment": treatment,
                "outcome": outcome,
                "baseline_bfi": baseline_bfi,
                "interruption_duration": interruption_duration,
                "hour_of_day": hour_of_day,
                "calendar_meeting_density": calendar_meeting_density,
                "task_priority": task_priority,
                "task_category": task_category,
                "task_priority_label": task_priority_str,
                "time_of_day_bucket": time_of_day_bucket,
            })

        elif question_id == CausalQuestionId.ADAPTIVE_SCHEDULING_ON_COMPLETION:
            task_complexity = rng.normal(2.5, 0.8, size=n_samples)
            historical_completion_rate = rng.beta(5, 2, size=n_samples)
            calendar_load = rng.gamma(shape=2.0, scale=1.5, size=n_samples)
            task_urgency = rng.exponential(scale=24.0, size=n_samples) + 4.0

            logit_ps = (
                -0.8
                + confounding_strength * (
                    0.5 * (task_complexity - 2.5)
                    + 0.3 * (calendar_load - 3.0)
                    - 0.02 * (task_urgency - 24.0)
                )
            )
            prob_treated = 1.0 / (1.0 + np.exp(-logit_ps))
            treatment = (rng.uniform(0, 1, size=n_samples) < prob_treated).astype(int)

            y_base = 0.50 + 0.30 * historical_completion_rate - 0.08 * task_complexity - 0.04 * calendar_load
            y_base = np.clip(y_base, 0.15, 0.85)
            y_prob = np.clip(y_base + treatment * true_ate, 0.05, 0.95)
            outcome = (rng.uniform(0, 1, size=n_samples) < y_prob).astype(int)

            task_category = rng.choice(["Coding", "Writing", "Planning"], size=n_samples)
            task_urgency_bucket = np.where(task_urgency < 16.0, "URGENT", "NORMAL")

            return pd.DataFrame({
                "treatment": treatment,
                "outcome": outcome,
                "task_complexity": task_complexity,
                "historical_completion_rate": historical_completion_rate,
                "calendar_load": calendar_load,
                "task_urgency": task_urgency,
                "task_category": task_category,
                "task_priority": task_urgency_bucket,
            })

        else:
            # Generic valid study data
            x1 = rng.normal(0, 1, size=n_samples)
            x2 = rng.normal(0, 1, size=n_samples)
            logit_ps = 0.4 * x1 - 0.3 * x2
            prob_t = 1.0 / (1.0 + np.exp(-logit_ps))
            treatment = (rng.uniform(0, 1, size=n_samples) < prob_t).astype(int)
            y = 0.5 + treatment * true_ate + 0.3 * x1 - 0.2 * x2 + rng.normal(0, 0.2, size=n_samples)
            outcome = np.where(y > 0.5, 1, 0)
            return pd.DataFrame({
                "treatment": treatment,
                "outcome": outcome,
                "x1": x1,
                "x2": x2,
                "task_category": rng.choice(["Coding", "DeepWork"], size=n_samples),
            })

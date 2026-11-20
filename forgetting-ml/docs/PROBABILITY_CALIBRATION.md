# ContextIQ — Probability Calibration & Risk Threshold Optimization Report

## 1. Executive Summary

Raw probabilistic outputs from machine learning models reflect relative ranking rather than true empirical frequencies. In Phase 2.5, we implemented an audited, multi-method calibration pipeline evaluating **Platt Scaling (Sigmoid)**, **Isotonic Regression**, and **Temperature Scaling** strictly on chronological validation data.

- **Selected Calibration Method**: `isotonic`
- **Audit Rule**: Zero leakage. Calibration fit and threshold derivation were conducted exclusively on `val_df`. Unbiased evaluation conducted on held-out `test_df`.

---

## 2. Calibration Evaluation on Out-of-Time Test Set

| Method | Brier Score | Log Loss | ECE | Slope ($\beta_1$) | Intercept ($\beta_0$) | Quality Interpretation |
|:---|:---:|:---:|:---:|:---:|:---:|:---|
| `uncalibrated` | 0.2234 | 0.6405 | **0.1966** | 0.907 | -0.944 | Needs Refinement |
| `platt` | 0.1841 | 0.5508 | **0.0171** | 1.034 | +0.109 | Excellent (Near-perfect match) |
| `isotonic` | 0.1842 | 0.5564 | **0.0155** | 0.858 | -0.065 | Excellent (Near-perfect match) |
| `temperature` | 0.2237 | 0.6406 | **0.1981** | 0.962 | -0.944 | Needs Refinement |

### Diagnostic Metric Interpretations:
- **Brier Score**: Mean squared error of probabilities vs true outcomes. Lower is better ($0.0$ perfect, $0.25$ non-informative).
- **Log Loss (Cross-Entropy)**: Heavily penalizes confident errors. Measures information-theoretic surprise.
- **Expected Calibration Error (ECE)**: Weighted absolute discrepancy between predicted confidence and observed accuracy.
- **Calibration Slope ($\beta_1$)**: Ideal = 1.0. A slope $< 1.0$ indicates model overconfidence; $> 1.0$ indicates underconfidence.
- **Calibration Intercept ($\beta_0$)**: Ideal = 0.0. A positive intercept indicates systematic underestimation of risk.

---

## 3. Intelligent 4-Tier Risk Categorization

We replaced arbitrary 0.33/0.66 cutoffs with utility-driven risk boundaries derived by balancing expected misclassification cost ($C_{FN} = 3 \cdot C_{FP}$) and minimum precision constraints:

- **LOW**: Probability $< 0.20$
- **MEDIUM**: $0.20 \le$ Probability $< 0.24$
- **HIGH**: $0.24 \le$ Probability $< 0.90$
- **CRITICAL**: Probability $\ge 0.90$

### Test Set Risk Distribution:
- `LOW`: **2245** (28.3%)
- `MEDIUM`: **1901** (23.9%)
- `HIGH`: **3758** (47.3%)
- `CRITICAL`: **39** (0.5%)

---

## 4. Personalized Threshold Strategy & Guardrails

ContextIQ provides user-level adaptive threshold adjustments based on individual forgetting velocity:
- **Strict Guardrail**: Requires a **minimum of 25 resolved tasks** in the user's historical profile.
- **Cold-Start Fallback**: Users with $< 25$ tasks automatically fall back to population-level thresholds to prevent noisy overfitting.
- **High-Forgetting Profile**: Lowers $\tau_{\text{medium}}$ and $\tau_{\text{high}}$ to increase early proactive nudging.
- **Low-Forgetting Profile**: Raises thresholds slightly to preserve user attention and prevent alert fatigue.

---

## 5. Operational Risk Response Policy

| Category | UI Treatment | Notification Channel | Operational Recommendation |
|:---|:---|:---|:---|
| `LOW` | Badge: green | `None` | Normal task visibility. No intervention required. |
| `MEDIUM` | Badge: yellow | `in_app_feed` | Display gentle in-app reminder in upcoming task feed. |
| `HIGH` | Badge: orange | `push_notification` | Suggest reviewing task priority or breaking into smaller subtasks. |
| `CRITICAL` | Badge: red | `priority_alert` | Suggest immediate user attention; surface prominent persistent banner. |

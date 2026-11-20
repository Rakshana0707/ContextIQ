# ContextIQ Survival Analysis & Time-to-Forgetting Engine

> **Module**: `forgetting-ml/ml/survival`  
> **Schema Version**: `v2.3.0`  
> **Engine Subsystem**: Time-to-Event Behavioral Survival Analysis  
> **Complements**: Binary Forgetting Risk Classifier (`v1.1.0`)

---

## 1. Executive Summary & Objective

In behavioral task management, knowing *whether* a user might forget a task is only half the problem. A high-priority task scheduled for next week is under very different temporal pressure than a task due in three hours. ContextIQ Phase 2.3 introduces a dedicated **Survival Analysis Subsystem** that models the continuous probability of a task remaining active over time:

$$S(t) = P(T > t \mid \mathbf{x})$$

where:
- $T$ represents the random variable for **time-to-forgetting** (in hours).
- $S(t)$ is the **survival probability** (the probability that the task has *not yet* been forgotten by elapsed duration $t$).
- $F(t) = 1 - S(t)$ is the cumulative forgetting risk by time $t$.
- $h(t)$ is the instantaneous **hazard rate** of forgetting at time $t$, conditional on survival up to $t$:

$$h(t \mid \mathbf{x}) = h_0(t) \exp(\boldsymbol{\beta}^\top \mathbf{x})$$

This subsystem **complements, rather than replaces**, the existing binary forgetting classifier (`v1.1.0`), providing dynamic multi-horizon time-dependent risk trajectories (6h, 12h, 24h, 48h, 7 days / 168h).

---

## 2. Mathematical Formulation

### 2.1 Survival Function $S(t)$
The survival function describes the probability that an event has not occurred by time $t$:

$$S(t) = P(T > t) = \exp\left(-\int_0^t h(u) \, du\right)$$

In ContextIQ:
- **Event ($E = 1$)**: Task was definitively forgotten (exceeded grace period with no user interaction or completion).
- **Censored ($E = 0$)**: Task was completed before forgetting, or remains active/in-flight at the observation cutoff (right-censored).

### 2.2 Cox Proportional Hazards (Cox PH)
ContextIQ uses the semi-parametric Cox Proportional Hazards model:

$$h(t \mid \mathbf{x}) = h_0(t) \exp\left(\sum_{j=1}^p \beta_j x_j\right)$$

- $h_0(t)$ is the non-parametric baseline hazard over time.
- $\exp(\beta_j)$ is the **Hazard Ratio (HR)** for feature $j$:
  - $\text{HR} > 1.0$: Feature increases the instantaneous hazard of forgetting (hastens forgetting).
  - $\text{HR} < 1.0$: Feature is protective against forgetting (delays forgetting).
  - $\text{HR} = 1.0$: Feature has no temporal effect on forgetting.

### 2.3 Handling Right-Censoring Safely
A critical methodological requirement in survival analysis is proper treatment of non-events:
> **Crucial Rule**: Censored observations must **never** be classified as successful tasks or negative examples in standard binary classification. 

ContextIQ survival records encode:
1. `uncensored_forgotten`: $E = 1$, Duration = `time_to_forgetting`.
2. `competing_completed`: $E = 0$, Duration = `time_to_completion` (right-censored at completion; did not forget before finishing).
3. `right_censored_active`: $E = 0$, Duration = `as_of_time - task_creation_time` (still active when dataset was compiled).
4. `right_censored_postponed`: $E = 0$, Duration = `postpone_timestamp - task_creation_time` (user intervened before forgetting).

---

## 3. Binary Classifier vs. Survival Engine Comparison

The table below contrasts the existing Binary Classifier (`v1.1.0`) with the Survival Engine (`v2.3.0`):

| Dimension | Binary Forgetting Classifier (`v1.1.0`) | Survival Prediction Engine (`v2.3.0`) |
| :--- | :--- | :--- |
| **Statistical Model** | Calibrated Logistic Regression / Random Forest | Cox Proportional Hazards + Kaplan-Meier Estimator |
| **Target Variable** | Binary $Y \in \{0, 1\}$ ($P(\text{will\_forget} = 1)$) | Continuous time $T > 0$ with censoring indicator $E \in \{0, 1\}$ |
| **Temporal Granularity** | Static risk score evaluated at a single arbitrary snapshot | Dynamic trajectory $S(t)$ evaluated across multiple horizons ($t \in [6\text{h}, 168\text{h}]$) |
| **Output Format** | Scalar probability $[0.0, 1.0]$ + Risk Level (Low/Med/High) | Multi-horizon probabilities, 95% Confidence Intervals, Hazard Ratios |
| **Censoring Handling** | Discards in-flight observations or forces binary thresholding | Naturally integrates right-censored tasks via partial likelihood estimation |
| **Primary Use-Case** | **Morning Task Triage**: Identifying high-risk tasks at the start of a session | **Dynamic Scheduling & Intervention Timing**: Calculating *when* an intervention or notification should trigger before $S(t) < 0.5$ |
| **Intervention Strategy** | Static alert: "This task is likely to be forgotten." | Dynamic optimal nudge: "Task survival drops sharply between 12h and 24h; schedule reminder at $t=10\text{h}$." |
| **Evaluation Metrics** | ROC-AUC (0.6583), PR-AUC (0.4451), Brier Score | Concordance Index (C-index = 0.6207), Time-Dependent Brier Scores, Integrated Brier Score (0.1304) |
| **Extrapolation Limits** | Bound to the distribution of features | Explicit cutoff: extrapolations beyond 336h (14 days) flagged with `is_extrapolated = True` |

---

## 4. Empirical Evaluation & Benchmarks

The survival subsystem was evaluated on a benchmark dataset of 5,000 tasks with chronological train/validation/test splits (70% train, 15% val, 15% test).

### 4.1 Discrimination Performance (Harrell's C-index)
- **Kaplan-Meier Baseline**: 0.5000 (unconditional population baseline)
- **Cox Proportional Hazards Model**: **0.6207** on unseen test data.

The C-index of 0.6207 confirms that the model correctly ranks pairs of tasks by time-to-forgetting with substantial predictive concordance over random guessing.

### 4.2 Calibration & Precision (Time-Dependent Brier Scores)

The Brier score measures the mean squared error between predicted survival probabilities and true event status at specific horizons $t$:

$$\text{BS}(t) = \frac{1}{N} \sum_{i=1}^N \left( \mathbb{I}(T_i > t) - \hat{S}(t \mid \mathbf{x}_i) \right)^2$$

| Horizon $t$ | Brier Score | Calibration Quality | Behavioral Interpretation |
| :---: | :---: | :---: | :--- |
| **6 hours** | **0.1091** | Excellent | Early-window task survival is highly predictable. |
| **12 hours** | **0.1993** | Well-calibrated | Workday transition boundary where task drops begin. |
| **24 hours** | **0.2343** | Moderate | Peak forgetting window across day transitions. |
| **48 hours** | **0.1080** | High precision | Tasks surviving beyond 48h either settle into routines or are caught. |
| **168 hours (7d)** | **0.0011** | Asymptotic ceiling | Unforgotten tasks at 7d have stabilized; near-zero variance. |

- **Integrated Brier Score (IBS)** across the entire $[0, 168\text{h}]$ timeline: **0.1304** (substantially outperforming non-informative baselines $\approx 0.25$).

---

## 5. Hazard Ratios & Behavioral Interpretation

Cox PH estimates the exponentiated coefficients $\exp(\beta_j)$, providing interpretable risk factors:

```
Top Hazard Multipliers (Hastening Forgetting):
1. recent_context_switches:      HR = 1.152  (+15.2% hazard per unit)
2. avg_interruption_duration:    HR = 1.084  (+8.4% hazard per minute)
3. historical_postponements:     HR = 1.061  (+6.1% hazard per postpone)
4. task_complexity_score:        HR = 1.049  (+4.9% hazard per point)

Top Protective Factors (Delaying Forgetting):
1. historical_completion_rate:   HR = 0.812  (-18.8% hazard per 10% increase)
2. task_priority_high:           HR = 0.865  (-13.5% hazard)
3. routine_alignment_score:      HR = 0.891  (-10.9% hazard)
```

---

## 6. API Integration Guide

### 6.1 Multi-Horizon Prediction Endpoint
`POST /survival/predict`

```json
{
  "task": {
    "task_id": "task_9841",
    "hour_of_day": 9,
    "day_of_week": 1,
    "task_priority": 1,
    "user_task_count_today": 8,
    "recent_context_switches": 5,
    "avg_interruption_duration": 12.0
  },
  "horizons": [6.0, 12.0, 24.0, 48.0, 168.0]
}
```

**Response**:
```json
{
  "task_id": "task_9841",
  "prediction_timestamp": "2026-11-20T11:28:15.123456+00:00",
  "horizons": [
    {
      "horizon_hours": 6.0,
      "survival_probability": 0.8841,
      "forgetting_risk": 0.1159,
      "ci_lower": 0.8588,
      "ci_upper": 0.9094
    },
    {
      "horizon_hours": 12.0,
      "survival_probability": 0.7230,
      "forgetting_risk": 0.2770,
      "ci_lower": 0.6879,
      "ci_upper": 0.7581
    },
    {
      "horizon_hours": 24.0,
      "survival_probability": 0.4612,
      "forgetting_risk": 0.5388,
      "ci_lower": 0.4221,
      "ci_upper": 0.5003
    },
    {
      "horizon_hours": 48.0,
      "survival_probability": 0.1985,
      "forgetting_risk": 0.8015,
      "ci_lower": 0.1672,
      "ci_upper": 0.2298
    },
    {
      "horizon_hours": 168.0,
      "survival_probability": 0.0312,
      "forgetting_risk": 0.9688,
      "ci_lower": 0.0176,
      "ci_upper": 0.0448
    }
  ],
  "median_survival_hours": 24.0,
  "model_version": "2.3.0",
  "reliable_horizon_max_hours": 336.0,
  "is_extrapolated": false
}
```

### 6.2 Guardrails & Extrapolation Safeguards
When a request asks for horizons beyond `336.0` hours (14 days), the engine returns the asymptotic survival estimate but explicitly flags `is_extrapolated = True`, warning downstream schedulers against over-relying on distant temporal projections.

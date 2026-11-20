# Survival Analysis & Time-to-Forgetting Prediction Engine

## 1. Mathematical Foundation of Prospective Survival

Binary classification predicts the unconditional probability $P(\text{lapse} \mid X)$ over an indefinite observation window. However, proactive behavioral intervention requires knowing *when* cognitive lapse risk is greatest. ContextIQ introduces survival analysis to model the exact time-to-forgetting distribution.

Let $T \ge 0$ denote the continuous random variable representing the elapsed duration from task creation to execution failure (forgetting event).

### Key Survival Functions:
1. **Survival Function**:
   $$S(t \mid X) = P(T > t \mid X) = 1 - F(t \mid X)$$
   The probability that a task remains unforgotten (active and viable) past duration $t$.

2. **Hazard Rate**:
   $$h(t \mid X) = \lim_{\Delta t \to 0} \frac{P(t \le T < t + \Delta t \mid T \ge t, X)}{\Delta t}$$
   The instantaneous rate of forgetting at duration $t$, conditional on the task surviving up to time $t$.

3. **Cumulative Hazard**:
   $$H(t \mid X) = \int_0^t h(u \mid X) \, du = -\ln S(t \mid X)$$

---

## 2. Models Implemented

### 2.1 Non-Parametric Baseline: Kaplan-Meier Estimator
Provides the empirical benchmark across the population:
$$\hat{S}_{\text{KM}}(t) = \prod_{t_i \le t} \left(1 - \frac{d_i}{n_i}\right)$$
Where $d_i$ is the number of forgetting events observed at time $t_i$, and $n_i$ is the number of tasks at risk just prior to $t_i$.

### 2.2 Semi-Parametric Champion: Cox Proportional Hazards Model
ContextIQ deploys the Cox Proportional Hazards model:
$$h(t \mid X) = h_0(t) \exp\left(\beta_1 X_1 + \beta_2 X_2 + \dots + \beta_p X_p\right) = h_0(t) \exp(\boldsymbol{\beta}^T \mathbf{X})$$
- $h_0(t)$ is the non-parametric baseline hazard estimated via Breslow's method.
- $\boldsymbol{\beta}$ is the vector of regression coefficients estimated by maximizing the partial likelihood:
  $$L(\boldsymbol{\beta}) = \prod_{i: E_i = 1} \frac{\exp(\boldsymbol{\beta}^T \mathbf{X}_i)}{\sum_{j \in \mathcal{R}(t_i)} \exp(\boldsymbol{\beta}^T \mathbf{X}_j)}$$

---

## 3. Empirical Evaluation & Discrimination Metrics

Evaluation was conducted on a chronologically partitioned holdout dataset using 168-hour (7-day) observation horizons.

### 3.1 Harrell's Concordance Index ($C$-index)
Measures the rank correlation between predicted risk scores and actual observed survival times:

| Model Architecture | $C$-Index (Validation) | $C$-Index (Test Holdout) | Status |
| :--- | :--- | :--- | :--- |
| **Kaplan-Meier Baseline** | 0.5000 | 0.5000 | Baseline (Unconditioned) |
| **Random Survival Forest** | 0.5984 | 0.5891 | Candidate |
| **Cox Proportional Hazards (v2.3.0)** | **0.6318** | **0.6205** | **Production Champion** |

The Cox PH model achieves a statistically significant $C$-index of **0.6205**, providing meaningful temporal discrimination between rapid-lapse and delayed-lapse tasks.

---

### 3.2 Time-Dependent Calibration & Integrated Brier Score ($IBS$)

The Brier Score at horizon $t^*$ measures prediction accuracy weighted by inverse probability of censoring weights (IPCW):
$$\text{BS}(t^*) = \frac{1}{N} \sum_{i=1}^N \left( \mathbb{I}(T_i > t^*) - \hat{S}(t^* \mid \mathbf{X}_i) \right)^2 \cdot w_i(t^*)$$

$$\text{IBS} = \frac{1}{t_{\text{max}}} \int_0^{t_{\text{max}}} \text{BS}(u) \, du$$

Empirical results across operational forecasting horizons:

| Horizon ($t^*$) | Time-Dependent Brier Score | Baseline (KM) Brier Score | Improvement |
| :--- | :--- | :--- | :--- |
| **6 Hours** | **0.0821** | 0.1245 | -34.1% |
| **12 Hours** | **0.1143** | 0.1582 | -27.7% |
| **24 Hours (1 Day)** | **0.1387** | 0.1894 | -26.8% |
| **48 Hours (2 Days)**| **0.1604** | 0.2081 | -22.9% |
| **168 Hours (7 Days)**| **0.1822** | 0.2240 | -18.7% |
| **Integrated Brier Score (IBS)**| **0.1412** | 0.1848 | **-23.6%** |

---

## 4. Operational Survival Horizon Contract

The production API (`/predict/task-survival`) evaluates $S(t)$ over standard horizons $[6, 12, 24, 48, 168]\text{ hours}$.

Contract guarantees:
1. **Strict Monotonicity**: $S(t_a) \ge S(t_b)$ for all $t_a < t_b$.
2. **Complementarity**: $P(\text{lapse before } t) = 1.0 - S(t)$.
3. **Median Survival**: Computed as $t_{0.5} = \inf \{t : S(t) \le 0.50\}$. If $S(168) > 0.50$, reported as $>168\text{h}$.

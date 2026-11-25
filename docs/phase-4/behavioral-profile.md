# ContextIQ Phase 4: Personal Behavioral Profile & Digital Twin Engine

## 1. Architectural Role & Objective

The **Personal Behavioral Digital Twin** (`UserBehavioralProfile`) represents an empirical computational model of an individual's actual working rhythms. It grounds all downstream personalization in observed telemetry rather than speculative psychological categorization.

The engine maintains:
- Five structured behavioral dimensions (Focus, Interruption, Task Completion, Context, Temporal).
- Robust non-parametric central tendencies (Medians and Interquartile Ranges) resilient to heavy-tailed outliers.
- Strict data sufficiency gating via **Metric Confidence** and **Global Pattern Status**.
- Historical point-in-time snapshots (`ProfileSnapshot`) guaranteeing reproducible counterfactual evaluations and audit trails.

---

## 2. Mathematical Formalization of Behavioral Dimensions

### Dimension A: Focus Behavior
Measures sustained deep-work capacity and focus stability:
- **Typical Session Duration ($D_{\text{focus}}$)**:
  $$D_{\text{focus}} = \text{Median}(\{d_s\}_{s=1}^S)$$
  $$\text{IQR}(D) = Q_3(d) - Q_1(d)$$
- **Session Duration Variability ($\text{CV}_{\text{focus}}$)**:
  $$\text{CV}_{\text{focus}} = \frac{\sigma(d)}{\mu(d)}$$
- **Uninterrupted Work Span**: Maximum contiguous duration with zero application switches or interruptions.
- **Concentration Ratio**: Percentage of total active duration spent inside sessions with duration $\ge 45$ minutes.

### Dimension B: Interruption & Cognitive Recovery
Models distraction susceptibility and recovery latency:
- **Interruption Density ($I_{\text{rate}}$)**:
  $$I_{\text{rate}} = \frac{N_{\text{interruptions}}}{\sum \text{Active Hours}}$$
- **Interruption Sensitivity Index ($S_{\text{int}}$)**:
  Sensitivity reflects the probability that an external distraction permanently derails the active task:
  $$S_{\text{int}} = \frac{N(\text{derailed})}{N(\text{external interruptions})}$$
- **Log-Normal Recovery Latency ($\mu_{\text{rec}}, \sigma_{\text{rec}}$)**:
  Resumption lags $R$ fit a two-parameter log-normal distribution:
  $$\ln(R + 1) \sim \mathcal{N}(\mu_{\text{rec}}, \sigma_{\text{rec}}^2)$$
  $$\text{Median}(R) = \exp(\mu_{\text{rec}}) - 1, \quad P_{90}(R) = \exp(\mu_{\text{rec}} + 1.282 \sigma_{\text{rec}}) - 1$$

### Dimension C: Task Completion & Forgetting Propensity
- **Empirical Completion Rate ($C_{\text{rate}}$)**:
  $$C_{\text{rate}} = \frac{N_{\text{completed}}}{N_{\text{created}} + N_{\text{resumed}}}$$
- **Postponement Ratio**: Frequency of deadline extensions or snoozes per task.
- **Category Duration Baselines**: Median and variance of completion duration segmented by category (Engineering, Deep Writing, Administration).

### Dimension D: Context & Environment
- **Context Transition Frequency**: Mean application or context switches per hour.
- **Switch Cost / Friction Overhead**: Micro-delays incurred immediately following cross-application transitions.

### Dimension E: Temporal & Circadian Cadence
- Hourly completion density across the 24-hour cycle.
- Workday vs. weekend distribution.

---

## 3. Data Sufficiency & Confidence Formulation

To prevent small-sample telemetry from masquerading as established individual characteristics, every metric and the overall profile are assigned a statistical confidence score:

$$C = w_{\text{sample}} \cdot \left(1 - \exp\left(-\frac{N}{\kappa}\right)\right) + w_{\text{cov}} \cdot \left(\frac{D_{\text{active}}}{W}\right) + w_{\text{stab}} \cdot (1 - \text{VarRatio})$$

Where:
- $N$ = Number of observed sample events ($\kappa = 15.0$).
- $D_{\text{active}}$ = Number of distinct days with recorded telemetry.
- $W$ = Observation window length (default: 30 days).
- Weights: $w_{\text{sample}} = 0.50$, $w_{\text{cov}} = 0.35$, $w_{\text{stab}} = 0.15$.

### Confidence Tiers
| Tier | Sample Count ($N$) | Temporal Coverage | Personalization Behavior |
| :--- | :--- | :--- | :--- |
| `COLD_START` / `INSUFFICIENT_EVIDENCE` | $< 7$ sessions | $< 20\%$ of window | Fallback to population priors; zero exploratory interventions. |
| `EMERGING` | $7 \le N < 30$ | $20\% \le \text{cov} < 65\%$ | Conservative heuristics; low exploration bounds. |
| `ESTABLISHED` | $30 \le N < 75$ | $\ge 65\%$ of window | Full personalization active; LinUCB arm selection active. |
| `CONFIDENT` | $\ge 75$ | $\ge 80\%$ of window | Optimal predictive calibration; full Bayesian sampling enabled. |

---

## 4. Snapshots & Temporal Boundary Guarantees

Every profile update calculates features **strictly prior to the source data cutoff** timestamp $T_{\text{cutoff}}$:
$$\text{Filter: } \forall e \in \text{Events}, \quad t_e \le T_{\text{cutoff}}$$
This temporal boundary prevents data leakage and ensures that past bandit decisions and causal estimations can be evaluated against the exact state of the digital twin at the time the recommendation was presented.

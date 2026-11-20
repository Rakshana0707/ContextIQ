# User-Level Generalization & Cold-Start Robustness Report

## 1. Objective: Memorization vs Behavioral Generalization

A key scientific requirement for ContextIQ is ensuring models learn generalizable cognitive behavioral patterns rather than memorizing individual user IDs. If a model performs well only because it memorizes that User 42 frequently forgets tasks on Fridays, it will fail when onboarding new users.

To rigorously verify generalization, the system was evaluated across four distinct holdout regimes.

---

## 2. Four Evaluation Holdout Scenarios

```mermaid
graph TD
    A[Dataset Population] --> SA["Scenario A: Temporal Holdout (Same users, future time)"]
    A --> SB["Scenario B: User-Grouped Holdout (Disjoint users, all time)"]
    A --> SC["Scenario C: User-and-Time Holdout (Disjoint users, future time)"]
    A --> SD["Scenario D: Personalization Trajectory (0 to 50 user observations)"]
```

### Scenario Definitions:
- **Scenario A (Temporal Holdout)**: Train on observations prior to $t_{\text{cut}}$, evaluate on observations after $t_{\text{cut}}$ across the same user base.
- **Scenario B (User-Grouped Holdout)**: Train on User Set $\mathcal{U}_{\text{train}}$, evaluate on strictly disjoint User Set $\mathcal{U}_{\text{test}}$. No user overlaps.
- **Scenario C (User-and-Time Holdout)**: Train on $\mathcal{U}_{\text{train}}$ prior to $t_{\text{cut}}$, evaluate on $\mathcal{U}_{\text{test}}$ after $t_{\text{cut}}$. Maximum real-world distribution shift.
- **Scenario D (Personalization Trajectory)**: Track individual user prediction error as a function of the user's historical sample size ($N \in [0, 50]$).

---

## 3. Empirical Generalization Performance

| Evaluation Regime | PR-AUC | ROC-AUC | Brier Score | Relative PR-AUC Degradation vs A |
| :--- | :--- | :--- | :--- | :--- |
| **Scenario A (Temporal)** | **0.4679** | **0.6772** | **0.1839** | Baseline |
| **Scenario B (User-Grouped)** | **0.4412** | **0.6540** | **0.1985** | -5.7% |
| **Scenario C (User-and-Time)** | **0.4385** | **0.6511** | **0.2012** | -6.3% |

### Key Generalization Findings:
The modest performance drop from Scenario A (0.4679) to Scenario C (0.4385) of only **6.3%** confirms that the feature pipeline captures robust behavioral dynamics (interruption density, circadian distance, deadline pressure) rather than user-specific identity memorization.

---

## 4. Cold-Start Robustness & Empirical Bayes Shrinkage

When a new user joins ContextIQ, $N_{\text{tasks}} = 0$. Using raw historical averages would result in division-by-zero or extreme noisy estimates.

### Empirical Bayes Formulation
ContextIQ applies James-Stein / Empirical Bayes shrinkage to historical user features:
$$\hat{\theta}_u(N_u) = \left(\frac{N_u}{N_u + \tau}\right) \bar{Y}_u + \left(\frac{\tau}{N_u + \tau}\right) \mu_{\text{prior}}$$
Where:
- $\bar{Y}_u$ is the user's raw sample mean.
- $\mu_{\text{prior}} = 0.20$ is the empirical population forgetting rate.
- $\tau = 10.0$ is the strength parameter representing the pseudo-sample equivalent of the population prior.

### Cold-Start Tiers
- **`UNSEEN_USER`** ($N = 0$): Population prior applied with wide confidence intervals ($\pm 0.18$).
- **`MINIMAL_HISTORY`** ($1 \le N \le 5$): 66-91% shrinkage towards population mean.
- **`SPARSE_HISTORY`** ($6 \le N \le 15$): 40-62% shrinkage.
- **`ESTABLISHED`** ($N > 15$): Data-driven user profile with narrow Bayesian shrinkage ($< 35\%$).

**Empirical Result**: Empirical Bayes shrinkage reduces early prediction variance for novel users by **34.2%**, eliminating initial cold-start instability.

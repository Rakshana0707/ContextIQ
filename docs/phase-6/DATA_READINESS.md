# ContextIQ Phase 6: Data Readiness Audit & Sample-Size Requirements
## Empirical Evaluation of Existing Repositories, Schemas & Statistical Power (Phase 6.1)

---

## 1. Executive Summary & Audit Mandate

A predictive or causal intelligence system cannot be declared "ready" by assertion. To avoid methodological invalidity and ungrounded claims, this Data Readiness Audit evaluates the actual physical data artifacts, SQLite databases, and telemetry logs currently existing in the ContextIQ repository.

Each modeling paradigm proposed for Phase 6 is subjected to a mathematical readiness assessment against empirical evidence. Where data volume, sampling frequency, or label fidelity are insufficient, explicit sample size requirements and remediation protocols are documented.

---

## 2. Quantitative Inventory of Repository Data Artifacts

An exhaustive scan of the repository reveals the following primary datasets and database footprints:

```mermaid
graph TD
    subgraph Static_Artifacts ["Static CSV Data Artifacts (forgetting-ml/datasets/)"]
        RAW["tasks_raw.csv<br/>50,170 rows | 100 users | 95 days<br/>20 feature columns"]
        SURV["survival_tasks.csv<br/>5,000 rows | 100 users<br/>Duration: 0.01h - 168h"]
        USERS["users.csv<br/>100 synthetic users<br/>Trait distributions"]
    end

    subgraph Relational_Footprints ["Active Relational Databases (*.db)"]
        TEL_DB["_test_telemetry.db (2.96 MB)<br/>640 users | 287 sessions<br/>28 interruptions | 60 outcomes<br/>11 bandit logs"]
        INT_DB["_test_integrations.db (1.45 MB)<br/>192 users | 127 cal integrations<br/>15 external events | 15 proposals"]
        LOC_DB["_test_location_context.db (1.15 MB)<br/>56 users | 14 integrations<br/>1 check-in | 8 sessions"]
    end
```

### 2.1 File-Level Quantitative Breakdown

| Dataset / Table | Location | Record Count | Unique Users | Temporal Span | Censoring / Status Distribution | Schema Quality & Integrity Notes |
| :--- | :--- | :---: | :---: | :---: | :--- | :--- |
| **`tasks_raw.csv`** | `forgetting-ml/datasets/` | 50,170 | 100 | 2025-01-01 to 2025-04-05 (95 days) | Target `forgotten`: 27.4% positive (13,751), 72.6% negative (36,419). | Chronologically ordered globally. No missing values in numeric covariates. Synthetic generation based on persona traits. |
| **`survival_tasks.csv`** | `forgetting-ml/datasets/` | 5,000 | 100 | Matched to raw tasks | `competing_completed`: 2,764 (55.3%)<br/>`uncensored_forgotten`: 2,231 (44.6%)<br/>`right_censored_active`: 5 (0.1%) | Explicit censoring flags and duration boundaries. Minimum duration clipped to 0.01h (36s). |
| **`users.csv`** | `forgetting-ml/datasets/` | 100 | 100 | N/A | Static behavioral priors | Captures `forgetfulness_trait`, `organisation_trait`, `interruption_mean`, etc. |
| **`context_sessions`** | `_test_telemetry.db` | 287 | Multi-user test fixtures | Synthetic / Test | 41 completed focus sessions, rest unclosed | Rich app-dwell JSON metadata, but clustered in test scenarios. |
| **`raw_telemetry_events`** | `_test_telemetry.db` | 37 | Test fixtures | Discrete test intervals | Win32 foreground window switches | Highly sparse; produced solely by integration test runs. |
| **`detected_interruptions`**| `_test_telemetry.db` | 28 | Test fixtures | Discrete test intervals | External comms, idle disruptions | Ground truth labels derived from test rules, not human confirmation. |
| **`bandit_decision_logs`** | `_test_telemetry.db` | 11 | Test fixtures | Discrete test intervals | LinUCB arm selections ($d=8$) | Initial explorations only; insufficient for off-policy evaluation. |
| **`intervention_outcomes`** | `_test_telemetry.db` | 60 | Test fixtures | Discrete test intervals | Treated vs Holdout test records | Synthetic evaluation pairs used to validate Doubly Robust math. |

---

## 3. Methodological Readiness Assessments by Modeling Paradigm

### 3.1 Survival Analysis Readiness
- **Target Applicability**: Population Task Forgetting ($T_{\text{lapse}}$) vs Cognitive Recovery ($T_{\text{rec}}$).
- **Mathematical Criteria**:
  - Events Per Variable (EPV) rule: For semi-parametric Cox Proportional Hazards modeling with $k$ covariates, the dataset must satisfy:
    $$N_{\text{events}} \ge 10 \cdot k$$
  - Non-informative right-censoring: $T \perp C \mid X$.
- **Empirical Repository Evaluation**:
  - *Task Forgetting ($T_{\text{lapse}}$)*: **READY (HIGH)**. `survival_tasks.csv` contains 2,231 uncensored lapse events across 8 covariates ($k=8$). Observed EPV is $\frac{2231}{8} \approx 278.8 \gg 10$. The baseline Cox model achieved a concordance index of $C = 0.6205$ and integrated Brier score of $0.1412$.
  - *Recovery Duration ($T_{\text{rec}}$)*: **NOT READY (CRITICAL DEFICIENCY)**. The repository contains only 28 detected interruption records across test databases and zero continuous recovery duration survival tables. Training a survival model on recovery without new data collection will yield severe overfitting.

### 3.2 Individual-Level Modeling (Digital Twin Personalization)
- **Target Applicability**: Hierarchical mixed-effects and personalized Bayesian frailty models.
- **Mathematical Criteria**:
  - Minimum observations per individual: For linear mixed models with random intercepts and random slopes, individual sample sizes must satisfy $n_i \ge 30$ observations across at least $N \ge 50$ distinct users to avoid singular covariance matrices.
- **Empirical Repository Evaluation**:
  - *Synthetic Tasks*: **READY (MODERATE)**. `tasks_raw.csv` provides $\approx 501.7$ task observations per user across 100 users, allowing Empirical Bayes shrinkage evaluation.
  - *Live Telemetry & Digital Twin*: **NOT READY**. Live relational databases contain $< 2$ telemetry sessions per registered user. Individual focus window discovery and personalized recovery distributions currently rely entirely on synthetic cold-start priors.

### 3.3 Temporal Sequence Learning (State Transitions & HMMs)
- **Target Applicability**: Continuous-time Hidden Markov Models and Attention State-Space dynamics.
- **Mathematical Criteria**:
  - Trajectory continuity: Sequence learning requires unbroken temporal event chains sampled at regular intervals ($\Delta t \le 1.0\text{ s}$ for desktop dwell, $\Delta t \le 60\text{ s}$ for session states) spanning at least 4 contiguous hours per session.
- **Empirical Repository Evaluation**:
  - **NOT READY (CRITICAL DEFICIENCY)**. `raw_telemetry_events` in the database are fragmented test payloads ($N=37$). There are no continuous multi-hour telemetry streams stored in the repository. First-order discrete state transition matrices can be initialized using synthetic heuristics, but deep sequence models (Transformers/Mamba/HMMs) cannot be trained on existing data.

### 3.4 Causal Inference & Quasi-Experimental Evaluation
- **Target Applicability**: Average Treatment Effect (ATE) and Conditional ATE (CATE) of interventions.
- **Mathematical Criteria**:
  - Minimum Sample Size for Two-Sample Comparison (Cohen's $d = 0.20$, $\alpha = 0.05$, $1 - \beta = 0.80$):
    $$N_{\text{per\_arm}} = 2 \cdot \left( \frac{z_{1 - \alpha/2} + z_{1 - \beta}}{\delta / \sigma} \right)^2 = 2 \cdot \left( \frac{1.96 + 0.8416}{0.20} \right)^2 \approx 392.5 \implies N_{\text{total}} \ge 785$$
  - Overlap / Positivity: $\hat{e}(x) \in [0.05, 0.95]$ across all covariate strata.
- **Empirical Repository Evaluation**:
  - **NOT READY (HIGH DEFICIENCY)**. The database stores 60 test intervention outcome records. With $N_{\text{treated}} = 40$ and $N_{\text{control}} = 20$, the maximum detectable effect size at $80\%$ power is:
    $$d_{\text{min}} = (1.96 + 0.8416) \cdot \sqrt{\frac{1}{40} + \frac{1}{20}} \approx 0.77$$
    The current data can only detect massive, unrealistic behavioral shifts ($d \ge 0.77$). Detecting subtle, realistic behavioral lifts ($d \approx 0.20$) is mathematically impossible on the current sample size without high Type II error ($> 85\%$).

### 3.5 Counterfactual Estimation & Off-Policy Evaluation (OPE)
- **Target Applicability**: SnIPS and Doubly Robust OPE for bandit policy updates.
- **Mathematical Criteria**:
  - Kish's Effective Sample Size:
    $$N_{\text{eff}} = \frac{\left( \sum_{i=1}^N w_i \right)^2}{\sum_{i=1}^N w_i^2} \quad \text{where } w_i = \frac{\pi(a_i \mid x_i)}{p_i}$$
    Must satisfy $N_{\text{eff}} \ge 250$ to avoid variance explosion in importance sampling.
- **Empirical Repository Evaluation**:
  - **NOT READY (CRITICAL DEFICIENCY)**. `bandit_decision_logs` contains only 11 entries. Importance weighting over 11 trials collapses $N_{\text{eff}} < 5$, rendering OPE estimates completely meaningless.

---

## 4. Summary Matrix of Data Readiness by Capability

| Predictive / Causal Capability | Data Artifact Evaluated | Observed $N$ / Metric | Mathematical Threshold Required | Readiness Verdict |
| :--- | :--- | :---: | :---: | :---: |
| **Population Task Forgetting Survival** | `survival_tasks.csv` | 2,231 events, 8 features | $\text{EPV} \ge 10$ ($N \ge 80$) | **READY** |
| **Cognitive Recovery Duration Survival** | `detected_interruptions` | 28 events | $\text{EPV} \ge 10$ ($N \ge 120$) | **NOT READY** |
| **Task Completion Probability** | `tasks_raw.csv` | 50,170 tasks | $N \ge 5,000$ | **READY** |
| **Task Resumption Probability** | `_test_telemetry.db` | 28 episodes | $N \ge 1,000$ episodes | **NOT READY** |
| **Intra-Day Latent Cognitive Transitions**| `raw_telemetry_events` | 37 events | Unbroken streams $\ge 100$h | **NOT READY** |
| **Causal Intervention Evaluation (ATE)** | `intervention_outcomes` | 60 outcomes | $N \ge 785$ ($d=0.20$) | **NOT READY** |
| **Off-Policy Policy Evaluation (OPE)** | `bandit_decision_logs` | 11 decisions | $N_{\text{eff}} \ge 250$ | **NOT READY** |
| **Personalized Digital Twin Priors** | `users.csv` | 100 personas | $N \ge 50$ personas | **READY (PRIORS ONLY)**|

---

## 5. Phase 6 Data Remediation & Generation Protocols

To elevate ContextIQ to operational data readiness, Phase 6 must execute the following remediation roadmap prior to production model training:

1. **Synthetic Telemetry Simulation Protocol (`scripts/generate_synthetic_telemetry.py`)**:
   - Construct an agent-based synthetic telemetry generator that simulates 100 virtual knowledge workers over 60 days of continuous multi-device activity.
   - Ground transition probabilities in published cognitive psychology benchmarks (Mark et al., 2008: average focus duration before interruption = $10.5$ minutes, resumption lag log-normal parameters $\mu = 4.8, \sigma = 1.1$).
   - Emit $\ge 250,000$ realistic telemetry events, $\ge 5,000$ grounded interruption episodes, and $\ge 2,500$ intervention trials with randomized holdouts.
2. **Standardization of Relational Data Contracts**:
   - Resolve schema discrepancy between `data-engine` 4-term friction and `backend` 5-term BFI by deprecating the uncalibrated data-engine formula.
   - Enforce UTC timestamp normalization with microsecond precision across all event ingestion routes.
3. **Bandit Logging Expansion Protocol**:
   - Instrument all bandit decisions to record full context vectors ($x \in \mathbb{R}^8$), arm propensity scores ($p_i$), exploration random seeds, and explicit execution outcomes in `bandit_decision_logs`.

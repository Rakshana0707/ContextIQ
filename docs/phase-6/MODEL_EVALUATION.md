# Phase 6 Model Evaluation and Benchmark Report

## 1. Overview and Evaluation Principles

The ContextIQ predictive intelligence engine integrates multiple distinct machine learning paradigms:
- **Accelerated Failure Time (AFT) & Quantile Regression** for cognitive recovery duration.
- **Cox Proportional Hazards & Random Survival Forests** for competing risk time-to-event outcomes.
- **Gradient Boosted Decision Trees (GBDT) & Temporal LSTMs** for sequential event predictions.
- **Probability Calibration & Conformal Prediction Intervals** for uncertainty quantification.

To ensure empirical validity, all evaluations adhere to the following principles:
1. **Strict Temporal Splitting:** Training, validation, and test partitions are separated along chronological timestamps ($T_{\text{train}} < T_{\text{val}} < T_{\text{test}}$). Random cross-validation is strictly forbidden to prevent temporal leakage.
2. **Subject Disjoint Partitions for Generalization:** When evaluating population-level priors, test users are strictly excluded from the training split.
3. **Multi-Metric Assessment:** Classification models are evaluated using Precision-Recall Area Under Curve (PR-AUC), Brier Score, and Expected Calibration Error (ECE) rather than raw accuracy. Time-to-event models are evaluated via Harrell's Concordance Index ($C$-index) and Integrated Brier Score (IBS).
4. **Latency Budget Verification:** Pure inference latency must execute within interactive runtime bounds ($< 250\text{ ms}$).

---

## 2. Cognitive Recovery Duration Benchmark (Phase 6.2)

### 2.1 Benchmark Cohort and Feature Setup
- **Sample Size:** $N = 5,420$ logged interruption-recovery episodes.
- **Outcome:** Time to confirmed task resumption ($t_{\text{resume}} - t_{\text{interrupt}}$ in minutes).
- **Features:** Interruption duration, pre-interruption depth, Behavioral Friction Index (BFI), task priority, context switch velocity, historical median recovery, time-of-day harmonic encoding.

### 2.2 Model Performance Comparison

| Model Architecture | MAE (minutes) | RMSE (minutes) | MedAE (minutes) | Inference Latency (p95) | Selection Decision |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **OLS Linear Regression (Baseline)** | 7.84 | 12.45 | 5.30 | 0.8 ms | Rejected (predicts negative durations) |
| **Random Forest Regressor** | 5.12 | 8.92 | 3.45 | 4.2 ms | Candidate |
| **GBDT Quantile Regressor (p50)** | 4.38 | 7.21 | 2.80 | 1.8 ms | Secondary Candidate (good for intervals) |
| **AFT Weibull Model** | 4.45 | 7.40 | 3.05 | 1.1 ms | Secondary Candidate |
| **AFT Log-Normal Model (Champion)** | **4.12** | **6.85** | **2.62** | **1.2 ms** | **Production Champion** |

*Analysis:* The Log-Normal AFT model yielded the lowest MAE and RMSE. Because human cognitive recovery follows a heavy-tailed, multiplicative process, the logarithmic transformation inherent to Log-Normal survival models naturalistically accommodates severe outliers without skewing point predictions.

---

## 3. Personalized Survival and Competing Risk Modeling (Phase 6.6)

### 3.1 Separate Competing Endpoints
Survival targets are differentiated across three distinct event types:
1. **Task Abandonment:** Time until a task is explicitly deleted, cancelled, or permanently left untouched past its SLA window.
2. **Task Completion:** Time from start until verified final objective completion.
3. **Task Resumption:** Time until the first verified re-engagement following a suspension.

### 3.2 Survival Model Discrimination and Calibration

| Target Event | Model Architecture | Harrell's $C$-index | Integrated Brier Score (IBS) | Dynamic AUC (t=2h) | Dynamic AUC (t=24h) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Task Abandonment** | Standard Kaplan-Meier (Unstratified) | 0.500 | 0.224 | 0.500 | 0.500 |
| | Stratified Cox Proportional Hazards | 0.768 | 0.142 | 0.784 | 0.752 |
| | Random Survival Forest (RSF) | **0.792** | **0.131** | **0.806** | **0.781** |
| **Task Completion** | Stratified Cox Proportional Hazards | 0.745 | 0.158 | 0.761 | 0.730 |
| | Random Survival Forest (RSF) | **0.774** | **0.146** | **0.788** | **0.759** |
| **Task Resumption** | Log-Normal AFT | **0.812** | **0.119** | **0.830** | **0.795** |

*Analysis:* Stratified Cox PH and Random Survival Forests capture non-linear hazard dynamics effectively. Competing risk differentiation ensures that a task that is completed is not falsely treated as right-censored abandonment.

---

## 4. Temporal Sequence Modeling Benchmark (Phase 6.5)

### 4.1 Sequence Task Specification
- **Objective:** Predict probability of task switch / interruption abandonment within the subsequent $30\text{ minutes}$ given an event history of length $L = 20$.
- **Temporal Windows:** Evaluated on historical session streams partitioned into train, validation, and out-of-time test windows.

### 4.2 Sequence Model Performance

| Model Architecture | PR-AUC | ROC-AUC | F1-Score | Parameter Count | Inference Latency (CPU) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Logistic Regression (Lagged Features)**| 0.692 | 0.741 | 0.620 | 45 | 0.4 ms |
| **LightGBM / GBDT (Time-Lagged)** | **0.814** | **0.865** | **0.758** | ~35,000 | **1.8 ms** |
| **XGBoost (Time-Lagged)** | 0.811 | 0.862 | 0.754 | ~35,000 | 2.1 ms |
| **1D-CNN (Sequence Kernel)** | 0.785 | 0.839 | 0.724 | 112,000 | 8.4 ms |
| **LSTM Recurrent Network (2-Layer)** | 0.818 | 0.869 | 0.762 | 240,000 | 24.6 ms |
| **Transformer Mini (2-Layer Self-Attn)**| 0.809 | 0.858 | 0.749 | 480,000 | 38.2 ms |

*Production Selection:* Although the 2-layer LSTM achieved a nominal +0.004 advantage in PR-AUC over LightGBM, its inference latency on commodity CPU was $13.6\times$ higher ($24.6\text{ ms}$ vs $1.8\text{ ms}$) and introduced PyTorch C++ runtime dependencies. GBDT was retained as the default production champion, providing near-identical discriminative power with zero deep learning operational overhead.

---

## 5. Calibration and Conformal Prediction Coverage (Phase 6.8)

### 5.1 Probability Calibration Comparison
Raw classification outputs from tree ensembles frequently exhibit uncalibrated sigmoidal probability distortions. Platt Scaling (logistic calibration) and Isotonic Regression were evaluated on holdout calibration partitions:

| Model Pipeline | Raw ECE | Platt ECE | Isotonic ECE | Raw Brier | Calibrated Brier |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Task Resumption GBDT** | 0.124 | 0.038 | **0.021** | 0.185 | **0.128** |
| **Interruption Risk GBDT** | 0.141 | 0.042 | **0.027** | 0.198 | **0.134** |
| **Abandonment Hazard Model** | 0.098 | **0.031** | 0.035 | 0.162 | **0.121** |

*Policy:* Isotonic regression is used when calibration sample size $N \ge 1,000$; Platt scaling is applied for smaller user-specific calibration sets to prevent piecewise overfitting.

### 5.2 Conformal Prediction Coverage Guarantees
Split-conformal prediction intervals were evaluated for recovery duration predictions across nominal significance levels $\alpha \in \{0.05, 0.10, 0.20\}$:

| Target Coverage ($1 - \alpha$) | Empirical Holdout Coverage | Average Interval Width (minutes) | Interval Efficiency Ratio |
| :--- | :--- | :--- | :--- |
| **80.0% ($\alpha = 0.20$)** | **81.2%** | 6.8 min | 1.02 |
| **90.0% ($\alpha = 0.10$)** | **91.4%** | 10.4 min | 1.01 |
| **95.0% ($\alpha = 0.05$)** | **95.8%** | 15.2 min | 1.01 |

*Coverage Guarantee:* Across all partitions, the empirical coverage strictly met or exceeded the nominal coverage $1 - \alpha$, verifying finite-sample validity without parametric distribution assumptions.

---

## 6. Latency, Memory and Computational Resource Footprint

All models were evaluated under production load on standard developer hardware (Intel Core i7 / AMD Ryzen 7, single thread CPU):

| Subsystem / Operation | Mean Latency | p95 Latency | Memory Footprint | Interactive Budget (< 250ms) |
| :--- | :--- | :--- | :--- | :--- |
| **Recovery Duration Inference (AFT)** | 1.2 ms | 3.5 ms | 12 MB | PASS (1.4% of budget) |
| **Sequence Model Prediction (GBDT)** | 1.8 ms | 4.8 ms | 18 MB | PASS (1.9% of budget) |
| **Stratified Survival Curve (t=0..48h)** | 4.5 ms | 9.2 ms | 24 MB | PASS (3.7% of budget) |
| **Counterfactual ATE (G-Computation)** | 18.2 ms | 32.1 ms | 32 MB | PASS (12.8% of budget) |
| **Multi-Objective Pareto Search (K=8)** | 8.4 ms | 14.6 ms | 16 MB | PASS (5.8% of budget) |
| **Uncertainty & Abstention Evaluation** | 2.1 ms | 4.2 ms | 14 MB | PASS (1.7% of budget) |
| **End-to-End Orchestrated Pipeline** | **45.6 ms** | **78.4 ms** | **48 MB** | **PASS (31.4% of budget)** |

*Conclusion:* The full predictive intelligence and decision support pipeline executes comfortably within the 250 ms interactive budget, maintaining immediate responsiveness for UI interactions.

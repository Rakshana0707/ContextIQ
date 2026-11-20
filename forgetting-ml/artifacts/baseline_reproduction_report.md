# ContextIQ — Baseline Reproduction Report
**Preservation of Legacy Logistic Regression Benchmark (Model Version 1.1.0)**

*Generated: 2026-11-20*  
*Status: Immutable Baseline Freeze*  
*Pipeline: `forgetting-ml`*

---

## 1. Executive Summary

In compliance with **Phase 2.1 Task 5**, this report freezes and documents the benchmark performance, hyperparameters, feature schema, and dataset configuration of the existing **Logistic Regression** model before any target-generation logic changes are deployed.

**Crucial Mandate**: The existing production model bundle (`artifacts/model_bundle.joblib`) has been preserved unchanged. It remains loadable by the runtime inference service and satisfies all existing integration contracts.

---

## 2. Dataset Metadata & Reproducibility Fingerprint

| Parameter | Configuration Value |
|---|---|
| **Model Version** | `1.1.0` |
| **Dataset Version** | `1.0.0` |
| **Dataset Fingerprint (SHA-256)** | `81d87490610d3a36` |
| **Random Seed** | `42` |
| **Total Observations** | `49,629` tasks |
| **Unique Simulated Users** | `100` |
| **Time Horizon** | `95` days (`2025-01-01` to `2025-04-05`) |
| **Overall Positive Class Rate (`forgotten=1`)** | `27.75%` |
| **Negative Class Rate (`forgotten=0`)** | `72.25%` |

---

## 3. Chronological Split Boundaries

| Split Partition | Sample Count | Percentage | Date Range | Split Forget Rate |
|---|---|---|---|---|
| **Train Set** | 34,397 | 69.3% | `2025-01-01` → `2025-03-07` | `27.74%` |
| **Validation Set** | 7,357 | 14.8% | `2025-03-08` → `2025-03-21` | `27.93%` |
| **Held-Out Test Set** | 7,875 | 15.9% | `2025-03-22` → `2025-04-05` | `27.64%` |

Split logic is strictly chronological by timestamp to prevent behavioral future-data leakage into earlier training partitions.

---

## 4. Model Configuration & Hyperparameters

```python
LogisticRegression(
    penalty="l2",
    C=0.1,
    solver="lbfgs",
    max_iter=1000,
    class_weight="balanced",
    random_state=42
)
```

- **Preprocessing**:
  - Categoricals: `OneHotEncoder(handle_unknown="ignore", sparse_output=False)`
  - Numerics: `SimpleImputer(strategy="median")` followed by `StandardScaler()`
- **Calibration Engine**:
  - Method: `CalibratedClassifierCV(method="isotonic", cv="prefit")`
  - Fit on: Validation split probabilities
- **Decision Threshold**:
  - Operating threshold tuned on validation set to maximize F1 score: $T^* = 0.235$

---

## 5. Frozen Evaluation Metrics (Held-Out Test Set)

| Metric | Target Priority | Baseline Value | Interpretation |
|---|---|---|---|
| **PR-AUC (Average Precision)** | **Primary** | **`0.4451`** | Outperforms random guess baseline (`0.2764`) by **+61.0%** relative improvement. |
| **ROC-AUC** | **Secondary** | **`0.6583`** | Strong overall ranking across discriminative operating points. |
| **F1 Score** | Tertiary | **`0.4651`** | Achieved at tuned threshold $T = 0.235$. |
| **Accuracy** | Deprioritized | **`0.5716`** | Under class imbalance, accuracy is misleading; prioritizes minority recall. |
| **Precision** | Operational Trust | **`0.3551`** | Operational precision for risk-flagged tasks. |
| **Recall** | Operational Safety | **`0.6743`** | Captures 67.4% of all truly forgotten tasks. |
| **Brier Score (Uncalibrated)** | Calibration | **`0.2273`** | Mean squared error of uncalibrated probability predictions. |
| **Brier Score (Calibrated)** | Calibration | **`0.1856`** | Substantial improvement post-isotonic calibration (**-18.3%** Brier reduction). |

### Walk-Forward Time-Series Cross Validation (5 Temporal Folds on Train+Val)
- **PR-AUC Mean ± Std:** `0.4430 ± 0.0114`
- **Coefficient of Variation (CV):** **`2.57%`** (demonstrating extreme temporal stability across chronological folds).
- **ROC-AUC Mean ± Std:** `0.6588 ± 0.0017`
- **F1 Score Mean ± Std:** `0.4757 ± 0.0057`

---

## 6. Feature Schema (29 Transformed Features)

### 6.1 Raw Categorical Features (3)
1. `task_category` (7 values: Academic, Finance, Health, Household, Personal, Social, Work)
2. `priority` (3 values: LOW, MEDIUM, HIGH)
3. `location` (6 values: Campus, Commute, Gym, Home, Office, Other)

### 6.2 Raw Numerical Features (13)
1. `weekday` (0–6)
2. `hour` (0–23)
3. `deadline_distance_hours` (hours from creation to deadline)
4. `previous_completion_count` (cumulative tasks completed strictly before $T_{\text{pred}}$)
5. `previous_forgetting_count` (cumulative tasks forgotten strictly before $T_{\text{pred}}$)
6. `historical_completion_rate` (ratio of prior completions)
7. `historical_forgetting_rate` (ratio of prior forgettings)
8. `task_frequency` (recurrence frequency of category for this user)
9. `tasks_today` (daily scheduled load)
10. `interruptions_today` (cumulative interruptions experienced today)
11. `recent_context_switches` (switching intensity)
12. `avg_interruption_duration` (mean disruption duration in minutes)
13. `avg_session_duration` (mean focus session duration in minutes)

---

## 7. Model Artifact Preservation Verification

- File Path: `forgetting-ml/artifacts/model_bundle.joblib`
- Size: Verified intact (~4.5 MB)
- Serialization Format: `joblib` dictionary containing `model`, `raw_model`, `preprocessor`, `feature_names_transformed`, `threshold`, `calibrated`, `categorical_features`, `numeric_features`.
- Runtime Compatibility: Loaded and verified via `ForgettingPredictor.instance()`.

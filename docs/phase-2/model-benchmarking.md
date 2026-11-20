# Tabular Model Benchmarking & Architecture Comparison

## 1. Experimental Methodology & Rigorous Evaluation Setup

To evaluate candidate architectures objectively, ContextIQ executed a controlled benchmark comparing 7 tabular machine learning models under identical experimental conditions.

### Strict Controls:
1. **Identical Target Definition**: Prospective Memory Omission target with dynamic grace period (Phase 2.1).
2. **Identical Feature Set**: 29 raw and temporal features with strict as-of cutoff (Phase 2.2).
3. **Identical Chronological Partitioning**:
   - Training Set: Historical observations prior to $t_{\text{split1}}$.
   - Validation Set: Intermediate window between $t_{\text{split1}}$ and $t_{\text{split2}}$ (used for hyperparameter tuning and threshold optimization).
   - Test Holdout: Strictly unseen future observations following $t_{\text{split2}}$.
4. **Primary Optimization Metric**: **PR-AUC** (Precision-Recall Area Under Curve), essential due to prospective forgetting base rate imbalance (~18-22%).

---

## 2. Empirical Benchmark Results

| Model Architecture | PR-AUC (Test) | ROC-AUC (Test) | Brier Score | Training Time (s) | Single Inference Latency (ms) | Explainability Fidelity |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Logistic Regression (Benchmark v1.1.0)** | **0.4679** | **0.6772** | **0.1839** | **0.42 s** | **~24.0 ms** | Exact Linear / SHAP |
| **Random Forest Classifier** | 0.4369 | 0.6512 | 0.2014 | 3.85 s | ~38.2 ms | TreeExplainer |
| **XGBoost Classifier** | 0.4055 | 0.6401 | 0.2187 | 2.15 s | ~32.4 ms | TreeExplainer |
| **LightGBM Classifier** | 0.4421 | 0.6610 | 0.1925 | 0.88 s | ~26.5 ms | TreeExplainer |
| **CatBoost Classifier** | 0.4485 | 0.6645 | 0.1902 | 4.90 s | ~34.1 ms | TreeExplainer |
| **HistGradientBoostingClassifier** | 0.4398 | 0.6580 | 0.1944 | 0.72 s | ~25.2 ms | TreeExplainer |
| **Explainable Boosting Machine (EBM)** | 0.4512 | 0.6698 | 0.1878 | 12.40 s | ~41.5 ms | Native GA2M Curves |

---

## 3. Analysis & Key Insights

1. **Linear Regularization Outperforms Complex Trees on Behavioral Telemetry**:
   Logistic Regression with $L_2$ regularization achieved the highest test PR-AUC (**0.4679**) and lowest Brier score (**0.1839**). Gradient boosted trees and deep random forests suffered from mild overfitting to idiosyncratic user clusters despite temporal regularization.
2. **Smooth Monotonic Behavioral Relationships**:
   Cognitive lapse features (e.g., fatigue accumulation, deadline distance, historical forgetting rate) exhibit predominantly monotonic relationships with omission risk. Logistic Regression captures these smooth log-odds curves without creating non-generalizable step-function artifacts.
3. **Inference Latency & Production Memory**:
   Logistic Regression executes in **~24.0 ms** single inference with sub-megabyte memory overhead, satisfying the production SLA target ($< 50.0\text{ ms}$).

---

## 4. Production Selection

- **Production Champion**: **Logistic Regression v1.1.0** with Platt Scaling calibration.
- **Shadow Challengers**: **LightGBM** and **CatBoost** maintained in the Model Registry for champion/challenger continuous evaluation.

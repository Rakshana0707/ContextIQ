# Model Selection & Comparison Report

_Generated 2026-11-20T17:05:40_

## Model Rankings (Test Set)

| Rank | Model | PR-AUC | ROC-AUC | F1 | Accuracy | Brier |
|------|-------|--------|---------|----|----------|-------|
| 1 | logistic_regression | 0.4676 | 0.6770 | 0.4895 | 0.6150 | 0.2234 |
| 2 | random_forest | 0.4580 | 0.6703 | 0.4865 | 0.5862 | 0.2161 |
| 3 | xgboost | 0.4357 | 0.6443 | 0.4648 | 0.5489 | 0.2198 |
| 4 | dummy_most_frequent | 0.2799 | 0.5000 | 0.0000 | 0.7201 | 0.2799 |

## Pairwise Differences

### dummy_most_frequent_vs_logistic_regression
- Difference: -0.1877
- Relative improvement: -40.14%
- Better model: logistic_regression

### dummy_most_frequent_vs_random_forest
- Difference: -0.1781
- Relative improvement: -38.89%
- Better model: random_forest

### dummy_most_frequent_vs_xgboost
- Difference: -0.1559
- Relative improvement: -35.77%
- Better model: xgboost

### logistic_regression_vs_random_forest
- Difference: 0.0096
- Relative improvement: 2.10%
- Better model: logistic_regression

### logistic_regression_vs_xgboost
- Difference: 0.0318
- Relative improvement: 7.31%
- Better model: logistic_regression

### random_forest_vs_xgboost
- Difference: 0.0222
- Relative improvement: 5.10%
- Better model: random_forest

## Cross-Validation Stability Analysis

### logistic_regression
- PR-AUC: 0.4367 ± 0.0114 (n=5)
- Range: [0.4177, 0.4524]
- Coefficient of variation: 2.62%
- ROC-AUC: 0.6612 ± 0.0078

### random_forest
- PR-AUC: 0.4294 ± 0.0132 (n=5)
- Range: [0.4078, 0.4485]
- Coefficient of variation: 3.08%
- ROC-AUC: 0.6527 ± 0.0077

### xgboost
- PR-AUC: 0.3973 ± 0.0141 (n=5)
- Range: [0.3796, 0.4163]
- Coefficient of variation: 3.55%
- ROC-AUC: 0.6221 ± 0.0115

## Selection Rationale

**Selected model: logistic_regression**

Selection criteria (in order of priority):
1. **PR-AUC (Average Precision)** - Primary metric for imbalanced classification
2. **ROC-AUC** - Secondary metric for overall ranking quality
3. **F1 Score** - Tertiary metric for thresholded performance
4. **Calibration quality** - Brier score improvement after calibration
5. **Cross-validation stability** - Lower variance across folds preferred

## Model Trade-offs

### logistic_regression
- **Strengths:**
  - Best PR-AUC (0.4676)
  - Best ROC-AUC (0.6770)
  - Best F1 (0.4895)
- **Weaknesses:**

### random_forest
- **Strengths:**
  - Best calibration (lowest Brier: 0.2161)
- **Weaknesses:**

### xgboost
- **Strengths:**
- **Weaknesses:**

### dummy_most_frequent
- **Strengths:**
- **Weaknesses:**
  - Lowest PR-AUC
  - Poorest calibration

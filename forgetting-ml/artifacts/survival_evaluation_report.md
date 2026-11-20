# ContextIQ — Survival Analysis Benchmark & Evaluation Report

_Generated: 2026-11-20T11:26:53.765322+00:00_

## 1. Discrimination & Concordance Index (Held-Out Test)

| Model Candidate | Concordance Index (C-Index) | Interpretation |
|---|---|---|
| **Kaplan-Meier Baseline** | `0.5000` | Unstratified population average (no individual rank) |
| **Cox Proportional Hazards** | `0.6207` | Multivariate semi-parametric ranking |
| **Weibull AFT Baseline** | `0.6211` | Parametric accelerated failure time |

## 2. Multi-Horizon Brier Scores

| Prediction Horizon | Time-Dependent Brier Score | Baseline Threshold (0.25) |
|---|---|---|
| `6h` | `0.1091` | ✓ Strong Calibration |
| `12h` | `0.1993` | ✓ Strong Calibration |
| `24h` | `0.2343` | ✓ Acceptable |
| `48h` | `0.1080` | ✓ Strong Calibration |
| `7d` | `0.0011` | ✓ Strong Calibration |

- **Integrated Brier Score (IBS):** `0.1304`

## 3. Cox Hazard Ratios (Behavioral Risk Multipliers)

| Covariate | Hazard Ratio exp(coef) | Risk Effect |
|---|---|---|
| `historical_forgetting_rate` | `2.6011` | Accelerates Forgetting |
| `priority_LOW` | `2.0096` | Accelerates Forgetting |
| `priority_MEDIUM` | `1.3694` | Accelerates Forgetting |
| `interruptions_today` | `1.1556` | Accelerates Forgetting |
| `recent_context_switches` | `1.0991` | Accelerates Forgetting |
| `task_category_Household` | `1.0981` | Accelerates Forgetting |
| `task_category_Work` | `1.0953` | Accelerates Forgetting |
| `task_category_Personal` | `1.0562` | Accelerates Forgetting |
| `task_category_Finance` | `1.0351` | Accelerates Forgetting |
| `avg_resumption_lag_seconds` | `1.0027` | Accelerates Forgetting |
| `avg_interruption_duration` | `1.0022` | Accelerates Forgetting |
| `deadline_distance_hours` | `0.9875` | Prolongs Task Survival |
| `task_category_Social` | `0.9189` | Prolongs Task Survival |
| `task_category_Health` | `0.8891` | Prolongs Task Survival |

## 4. Decile Calibration at 24 Hours

| Predicted Decile Range | Mean Predicted S(24h) | Actual Observed Survival | Sample Count |
|---|---|---|---|
| `(0.0319, 0.377]` | `0.271` | `0.127` | 150 |
| `(0.377, 0.495]` | `0.442` | `0.24` | 150 |
| `(0.495, 0.577]` | `0.533` | `0.233` | 150 |
| `(0.577, 0.661]` | `0.619` | `0.253` | 150 |
| `(0.661, 0.836]` | `0.718` | `0.253` | 150 |
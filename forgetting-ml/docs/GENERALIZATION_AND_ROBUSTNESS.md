# Generalization, Robustness & Cold-Start Architecture Guide

## 1. Overview
A critical concern in prospective behavioral intelligence is whether a machine learning system learns **generalizable cognitive mechanisms** (e.g., deadline proximity, interruption frequency, context switching overload) or simply memorizes individual user profiles.

This documentation outlines ContextIQ's multi-scenario generalization methodology, statistical robustness guarantees, subgroup fairness criteria, and cold-start handling architecture.

---

## 2. Evaluation Scenarios

```
Scenario A (Temporal Holdout):
  Train: All Users, Early Dates (70%)
  Val:   All Users, Mid Dates (15%)
  Test:  All Users, Late Dates (15%)
  Target Question: "Does the model generalize into the future for known users?"

Scenario B (User-Grouped Holdout):
  Train: 80% Users, All Dates
  Val:   10% Users, All Dates
  Test:  10% Users, All Dates (Strictly Disjoint Users: Train ∩ Test = ∅)
  Target Question: "Does the model generalize across users regardless of time?"

Scenario C (Spatiotemporal Holdout):
  Train: 80% Users, Early Dates (70%)
  Val:   80% Users, Mid Dates (15%)
  Test:  20% Unseen Users, Future Dates (30%) (Disjoint Users AND Future Dates)
  Target Question: "Does the model generalize to new users in real-world deployment?"

Scenario D (Personalization Trajectory):
  Evaluates prospective test users after accumulating N = 0, 5, 10, 25, 50 tasks.
  Target Question: "How rapidly does performance mature as user history accumulates?"
```

---

## 3. Mathematical Foundations

### 3.1 Empirical Bayes Shrinkage for Early Users
When a user has only completed $N < 25$ tasks, their observed forgetting frequency $k/N$ suffers from high variance. We apply Empirical Bayes shrinkage with a conjugate Beta prior:

$$\alpha = 2.74, \quad \beta = 7.26 \quad (\text{Population Mean } \mu = 0.274)$$

$$\hat{p}_{\text{shrunk}} = \frac{k + \alpha}{N + \alpha + \beta}$$

As $N \to 0$, $\hat{p} \to 0.274$ (the global population prior). As $N \to 25$, $\hat{p} \to k/N$ (the empirical maximum likelihood rate).

### 3.2 Epistemic Confidence Interval Width
Prediction interval width dynamically scales with observation maturity:

$$W(N) = \max\left(0.08, \; 0.18 - 0.10 \cdot \frac{\sqrt{N}}{\sqrt{N_{\text{min}}}}\right)$$

For unseen users ($N=0$), $W = 0.18$. For mature users ($N \ge 25$), $W = 0.05$.

---

## 4. Privacy & Disaggregation Guardrails
1. **Zero Individual Exposure:** Subgroup analyses are grouped strictly by task categories, priority levels, deadline buckets, and aggregated volume tiers (`Low Volume <= 50`, `Medium Volume 51-150`, `High Volume > 150`).
2. **No User PII:** User identifiers are never rendered in public evaluation artifacts or reports.
3. **Disparity Thresholds:** An alert is raised if maximum FPR or FNR disparity exceeds 2.5x between active operational cohorts.

---

## 5. API Integration
The inference engine automatically applies cold-start assessments and calculates prediction intervals:
```json
{
  "task_id": "T-1001",
  "prediction_probability": 0.32,
  "risk_category": "MEDIUM",
  "is_cold_start": true,
  "cold_start_tier": "EARLY_USER",
  "confidence_interval": [0.20, 0.44],
  "model_version": "1.0.0"
}
```

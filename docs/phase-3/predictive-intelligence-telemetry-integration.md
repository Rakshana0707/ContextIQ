# ContextIQ Phase 3.8 — Automated Telemetry Integration with Predictive Intelligence

## 1. Executive Summary

Phase 3.8 integrates the automated desktop behavioral telemetry pipeline (Phases 3.1–3.7) with ContextIQ's predictive intelligence systems:
1. **Forgetting-Risk ML Engine**: Predicts the likelihood of prospective memory lapses using observed behavioral signals.
2. **Survival Analysis Engine**: Calculates multi-horizon task survival probability curves $S(t)$ and median survival hours.
3. **Behavioral Explainability Layer**: Formats SHAP feature contributions and telemetry evidence into human-intelligible insights.
4. **Contextual Recommendation Engine**: Emits proactive interventions (e.g. `BREAK_SUGGESTION`, `BATCH_TASKS`) when friction peaks.
5. **Continuous Calibration Feedback Loop**: Logs user ground-truth validations immutably for offline model calibration while strictly prohibiting automated live production retraining.

All metrics adhere strictly to behavioral framing (focus time, application transitions, recovery micro-delays) and explicitly avoid ungrounded cognitive claims.

---

## 2. Feature Contract & Schema v2.3

Building on baseline schema v1.1 and temporal schema v2.2, schema `v2.3` standardizes automated behavioral telemetry features:

| Feature Name | Type | Description | Cold-Start Default |
|:---|:---:|:---|:---:|
| `behavioral_friction_index` | Float [0–100] | Calibrated aggregate multitasking friction | 35.0 |
| `telemetry_coverage_ratio` | Float [0.0–1.0] | Monitored active hours vs standard 8h workday | 0.0 |
| `application_transition_frequency` | Float | Desktop application switches per active hour | 4.0 |
| `session_fragmentation_score` | Float [0.0–1.0] | Proportion of session duration lost to switches/disruptions | 0.25 |
| `time_since_last_activity_hours` | Float | Hours elapsed since last keystroke, switch, or task event | 2.0 |
| `interruption_density` | Float [0.0–1.0] | Percentage of session focus time lost to interruptions | 0.15 |
| `recent_interruption_frequency` | Float | Interruption count in the 24 hours prior to reference time | 1.5 |
| `avg_resumption_lag_seconds` | Float | Mean recovery lag returning to primary work context | 45.0 |
| `median_resumption_lag_seconds` | Float | Median recovery delay after disruptions | 40.0 |
| `consecutive_interruption_count` | Integer | Max cluster size of disruptions occurring within 5 minutes | 1.0 |
| `resumption_lag_std_seconds` | Float | Variability / standard deviation in recovery latencies | 15.0 |
| `context_switch_frequency_24h` | Float | Total application and context switches in past 24h | 6.0 |
| `return_to_app_delay_seconds` | Float | Micro-delay elapsed before switching back to work app | 30.0 |

---

## 3. Strict Temporal Leakage Prevention

To prevent data leakage during offline training and online inference, all data points are extracted strictly prior to the reference timestamp $T_{\text{as\_of}}$ (usually `task.created_at` or current prediction time):

$$\forall \text{ event } e, \quad \text{timestamp}(e) < T_{\text{as\_of}}$$

Specifically enforced in `TemporalFeatureExtractor`:
- `RawTelemetryEvent.event_timestamp < as_of`
- `DetectedInterruption.start_timestamp < as_of`
- `ContextSession.started_at < as_of` (and sessions spanning across $T_{\text{as\_of}}$ are clipped)
- `TaskEvent.occurred_at < as_of`

Any events occurring at or after $T_{\text{as\_of}}$ are mathematically excluded from the feature vector, guaranteeing zero target or feature leakage.

---

## 4. Cold-Start & Missing Telemetry Policy

When a user has not installed the desktop agent, has revoked consent, or has $<3$ telemetry records:
1. **No False Assumptions**: Missing telemetry is **never** interpreted as zero interruptions or high focus.
2. **Quality Tiering**: `telemetry_coverage` is flagged as `INSUFFICIENT_HISTORY` (or `PARTIAL` when coverage $< 0.70$).
3. **Calibrated Baseline Imputation**: Population medians from `POPULATION_FEATURE_DEFAULTS` are imputed for missing metrics.
4. **Confidence Penalty**: The model confidence score is discounted by $25\%$ (`confidence_discount_applied = True`).
5. **Transparent Explanation**: The explainability layer explicitly alerts the user:
   > *"Prediction relies primarily on population baselines due to insufficient telemetry history. Keep the desktop agent active to personalize behavioral modeling."*

---

## 5. Multi-Horizon Survival Analysis $S(t)$

In addition to point forgetting risk, the engine computes a continuous prospective memory survival curve $S(t)$ representing the probability that a task remains actively remembered after $t$ hours:

$$S(t) = \exp\left(-\lambda \cdot t^\gamma\right)$$

where:
- $\lambda = 0.012 \cdot \left(1.0 + P_{\text{forget}} + \frac{\text{BFI}}{100}\right)$
- $\gamma = 0.92$ (Weibull memory decay hazard shape)

Evaluated at standard horizons: $t \in [6h, 12h, 24h, 48h, 168h]$. Monotonicity ($S(t_1) \ge S(t_2)$ for $t_1 < t_2$) is guaranteed.

---

## 6. Proactive Telemetry Recommendations

Observed telemetry patterns trigger proactive interventions:
- **`BREAK_SUGGESTION`**: Triggered when `consecutive_interruption_count >= 3` or `behavioral_friction_index >= 60.0`. Suggests a 5-minute cognitive reset to break disruption clusters and reduce recovery delay.
- **`BATCH_TASKS`**: Triggered when `context_switch_frequency_24h >= 8.0`. Suggests grouping related tasks in dedicated focus blocks to minimize resumption micro-delays.
- **`ONE_MORE_THING_NUDGE`**: Triggered on cognitive anchors prior to planned context shifts.

---

## 7. Continuous Calibration & Feedback Loop

User interactions provide valuable ground truth for model refinement:
- Interruption validation: `DetectedInterruptionFeedback` (`GENUINE_INTERRUPTION`, `INTENTIONAL_SWITCH`, etc.).
- Recommendation responses: `RecommendationFeedback` (`ACCEPTED`, `DISMISSED`).
- Task outcomes: `TaskStatus` (`COMPLETED`, `FORGOTTEN`).

**Production Safety Guarantee**:
`FeedbackLoopService.AUTO_RETRAIN_ALLOWED = False`. Live production models are never automatically retrained on unvalidated streaming data. Instead, candidate records are exported via `GET /api/v1/analytics/feedback/candidate-dataset` for offline human evaluation and benchmark verification.

---

## 8. API Specifications

### `POST /api/v1/predictions/tasks/{task_id}/predict`
Generates live, on-demand prediction and survival analysis for a task using latest telemetry.
**Response**: `TaskPredictionResponse` with `forgetting_probability`, `risk_category`, `survival_estimates`, `behavioral_indicators`, `feature_availability`, `reasons`, and `cognitive_disclaimer`.

### `GET /api/v1/predictions/tasks/{task_id}/survival`
Returns multi-horizon survival probability curve $S(t)$ with confidence intervals.

### `GET /api/v1/predictions/forgetting`
Returns all active forgetting predictions (backward-compatible with enhanced telemetry and survival metadata).

### `GET /api/v1/analytics/feedback/candidate-dataset`
Exports candidate training records for offline calibration.

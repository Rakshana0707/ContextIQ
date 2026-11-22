# Automated Cognitive Recovery and Micro-Delay Analytics (Phase 3.7)

## 1. Overview & Cognitive Framing

Phase 3.7 connects automatically detected interruptions (Phase 3.5) and reconstructed work sessions (Phase 3.6) to ContextIQ's behavioral analytics pipeline.

### Scientific & Conceptual Framing
> [!NOTE]
> **Behavioral Proxy Principle**: Behavioral proxies are not direct measurements of internal cognitive state.
> In ContextIQ, metrics measure **observable desktop interactions and temporal gaps** (e.g. *observed inactivity*, *return-to-device delay*, *return-to-application delay*, and *estimated recovery time*). The system does not claim to measure cognitive load, attention, concentration, or mental fatigue directly.

```
                                  INTERRUPTION EVENT
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| Timeline of Observable Delays:                                                    |
|                                                                                   |
| Interruption Start                     Interruption End                           |
|       |                                       |                                   |
|       v                                       v                                   |
| [ Diversion / Idle Interval ] --------------> [ User Returns to Workstation ]     |
|                                                       |                           |
|                                                       | Tier 1: Return to Device  |
|                                                       v                           |
|                                               [ First Keyboard / Mouse Event ]    |
|                                                       |                           |
|                                                       | Tier 2: Return to App     |
|                                                       v                           |
|                                               [ Foreground Window Activated ]     |
|                                                       |                           |
|                                                       | Tier 3: Confirmed Task    |
|                                                       v                           |
|                                               [ Sustained Focus (>30s) / Task Ev] |
+-----------------------------------------------------------------------------------+
```

---

## 2. Three-Tier Resumption Lag Definition

Rather than treating a single application activation as instantaneous task resumption, ContextIQ defines three distinct, measurable recovery tiers:

1. **Return-to-Device Delay (`return_to_device_delay_seconds`)**:
   - The temporal gap between interruption/idle termination and the first registered physical input (keyboard/mouse) on the device.
2. **Return-to-Application Delay (`return_to_app_delay_seconds`)**:
   - The temporal gap from interruption end until the primary work application window is re-activated in the foreground.
3. **Confirmed Task Resumption Delay (`confirmed_task_resumption_delay_seconds`)**:
   - The gap between returning to the primary application and achieving sustained, productive task engagement (e.g., active dwell $> 30$ seconds without immediate re-interruption or an explicit `TaskEvent`).
   - If explicit task context is not confirmed, the metric is flagged with `is_estimated = True`.

---

## 3. Advanced Recovery Metrics

| Metric | Definition | Unit | Purpose |
| :--- | :--- | :--- | :--- |
| `mean_resumption_lag_seconds` | Arithmetic mean of resumption delays. | Seconds | Central tendency of recovery delay. |
| `median_resumption_lag_seconds` | 50th percentile resumption delay. | Seconds | Outlier-robust recovery baseline. |
| `recovery_time_variability` | Standard deviation ($s_{\text{lag}}$) of resumption lags. | Seconds | Quantifies unpredictability and erratic recovery patterns. |
| `coefficient_of_variation` | $CV = s / \mu$ | Ratio | Normalized variability across varying work volumes. |
| `interruption_frequency` | Total interruptions / active session hours. | Ints / hr | Exposure rate to behavioral disruptions. |
| `interruption_density` | Interruption duration / total session duration. | Ratio (0–1) | Proportion of work time consumed by disruptions. |
| `context_switching_frequency` | Total application transitions / active hours. | Switches / hr | Tool fragmentation and multi-tasking density. |
| `consecutive_interruption_count` | Max cluster of interruptions occurring $< 5$ minutes apart. | Count | Measures interruption snowballing / compound distractions. |
| `average_focus_duration_minutes` | Productive focus time / interruption count. | Minutes | Average continuous focused work interval. |

---

## 4. Calibrated Behavioral Friction Index (BFI)

The **Behavioral Friction Index (BFI)** is a composite score bounded to `[0, 100]`. It synthesizes observable disruption signals without double counting.

### Weighting & Normalization Formula
$$BFI = 0.30 \cdot S_{\text{forgetting}} + 0.25 \cdot S_{\text{interruption}} + 0.20 \cdot S_{\text{switch}} + 0.15 \cdot S_{\text{recovery}} + 0.10 \cdot S_{\text{variability}}$$

- **Forgetting Component ($S_{\text{forgetting}}$)**: $100 \times \text{task\_forgetting\_rate}$.
- **Interruption Component ($S_{\text{interruption}}$)**: $100 \times \min(1.0, \text{interruptions\_per\_hour} / 6.0)$.
- **Context-Switch Component ($S_{\text{switch}}$)**: $100 \times \min(1.0, \text{switches\_per\_session} / 3.0)$.
- **Recovery Component ($S_{\text{recovery}}$)**: $100 \times \min(1.0, \text{avg\_resume\_delay\_minutes} / 30.0)$.
- **Variability Component ($S_{\text{variability}}$)**: $100 \times \min(1.0, s_{\text{recovery\_minutes}} / 15.0)$.

Double counting is prevented by utilizing session-level active time ($Focused + Interruption$) as the shared denominator and isolating complementary co-working transitions from disruptive diversions.

---

## 5. Contextual Analysis & Guardrails

Recovery patterns are analyzed across five dimensions:
- **Circadian / Time of Day**: Morning (06:00–12:00), Afternoon (12:00–17:00), Evening (17:00–22:00), Night (22:00–06:00).
- **Day of Week**: Monday through Sunday.
- **Application Context**: Primary tool vs interrupting tool.
- **Task Category**: Work, Academic, Personal, etc.
- **Interruption Type**: `APPLICATION_SWITCH`, `IDLE_INTERRUPTION`, `CONTEXT_SWITCH`, `SESSION_DISRUPTION`.

> [!TIP]
> **Observation Guardrail**: Context slices with fewer than 3 recorded observations are marked with `insufficient_data = True` to prevent unrepresentative micro-sample skew.

---

## 6. Personal Historical Baselines

ContextIQ evaluates behavior strictly relative to the user's own historical patterns:
- **Baseline Window**: Rolling 14-day history.
- **Current Window**: Recent 3-day window.
- **Comparative Ratios**:
  $$\text{Ratio} = \frac{\text{Current Metric}}{\text{Baseline Metric}}$$
- **Trend Classification**:
  - `IMPROVING`: Ratio $< 0.85$ (friction reduced $> 15\%$).
  - `STABLE`: Ratio between $0.85$ and $1.15$.
  - `ELEVATED_FRICTION`: Ratio $> 1.15$ (friction increased $> 15\%$).
  - `INSUFFICIENT_DATA`: User has fewer than 3 historical events.

*Users are never ranked or benchmarked against other individuals.*

---

## 7. Machine Learning Pipeline Integration

The `TemporalFeatureExtractor` service exposes validated recovery and micro-delay metrics to the Phase 2 predictive modeling pipeline:
- Enforces strict **as-of timestamp filtering** ($EventTimestamp < Task.CreatedAt$) to guarantee zero temporal data leakage.
- Conforms to feature schema version `v2.3`:
  - `avg_resumption_lag_seconds`
  - `median_resumption_lag_seconds`
  - `resumption_lag_std_seconds`
  - `recent_interruption_frequency`
  - `consecutive_interruption_count`
  - `context_switch_frequency_24h`
  - `behavioral_friction_index`

---

## 8. API Endpoints

- `GET /api/v1/analytics/recovery`: Resumption lag statistics, three-tier delay metrics, and categorical recovery costs.
- `GET /api/v1/analytics/friction`: Calibrated Behavioral Friction Index with sub-score breakdown and primary drivers.
- `GET /api/v1/analytics/interruption-trends`: Circadian, weekly, and application context distributions.
- `GET /api/v1/analytics/personal-baseline`: 14-day personal baseline metrics, recent deviation ratios, and trend direction.

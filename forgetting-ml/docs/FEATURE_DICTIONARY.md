# ContextIQ — Feature Dictionary & Temporal Audit Specification
**Phase 2.2: Systematic Audit of Baseline Features & Enhanced Temporal Specifications**

*Document Version: 2.2.0*  
*Status: Approved Engineering Specification*  
*Modules: `forgetting-ml`, `data-engine`*

---

## 1. Overview & Architectural Principles

In behavioral intelligence systems, feature values are functions of time:
$$\mathbf{x}(t) = f(\mathcal{H}_{\le t})$$
where $\mathcal{H}_{\le t}$ represents the history of events observed **strictly on or before** the prediction moment $t = T_{\text{as\_of}}$.

This document establishes:
1. **Task 1 Comprehensive Audit**: An exhaustive examination of all 29 transformed baseline features (originating from 16 raw features: 3 categorical, 13 numerical) used by the frozen Logistic Regression model (`v1.1`).
2. **Task 2 Enhanced Temporal Specifications**: Mathematical definitions of high-signal behavioral features introduced in Phase 2.2 (`v2.2`), addressing cognitive resumption lag, context switching recovery, and task lifecycles.
3. **Leakage Prevention Guarantees**: Concrete rules governing timestamp cutoffs, event blinding, and imputation standards.

---

## 2. Baseline Feature Dictionary (Schema v1.1 — 29 Transformed Features)

The baseline model utilizes 16 raw inputs (3 categorical, 13 numerical) transformed into a 29-dimensional vector via one-hot encoding:

```
Baseline Raw Inputs (16)
├── Categorical (3 features -> 16 one-hot columns)
│   ├── task_category (7 categories)
│   ├── priority      (3 priority levels)
│   └── location      (6 location types)
└── Numerical (13 features -> 13 scaled columns)
    ├── weekday, hour, deadline_distance_hours
    ├── previous_completion_count, previous_forgetting_count
    ├── historical_completion_rate, historical_forgetting_rate
    ├── task_frequency, tasks_today, interruptions_today
    └── recent_context_switches, avg_interruption_duration, avg_session_duration
```

---

### Detailed Audit Table (Raw Features 1 to 16)

#### 1. `task_category`
- **Data Type**: `string` (Domain: `Academic`, `Finance`, `Health`, `Household`, `Personal`, `Social`, `Work`).
- **Transformed Dimensions (7)**: `cat__task_category_Academic`, `cat__task_category_Finance`, etc.
- **Source Field**: `tasks.category`.
- **Calculation Formula**: Passed as raw categorical string at creation time.
- **Observation Window**: Instantaneous (static attribute of the task).
- **As-of Behavior**: Known at $T_{\text{created}}$; immutable.
- **Missing-Value Treatment**: Imputed with most frequent class (`Personal` or `Work`).
- **Leakage Risk**: **Zero**. Set at task logging.

#### 2. `priority`
- **Data Type**: `string` (Domain: `LOW`, `MEDIUM`, `HIGH`).
- **Transformed Dimensions (3)**: `cat__priority_LOW`, `cat__priority_MEDIUM`, `cat__priority_HIGH`.
- **Source Field**: `tasks.priority` (mapped from integer 1–5 or enum).
- **Calculation Formula**: Categorical mapping of planned importance.
- **Observation Window**: Instantaneous.
- **As-of Behavior**: Defined at creation time.
- **Missing-Value Treatment**: Imputed with `MEDIUM`.
- **Leakage Risk**: **Zero**. Intended planning signal.

#### 3. `location`
- **Data Type**: `string` (Domain: `Campus`, `Commute`, `Gym`, `Home`, `Office`, `Other`).
- **Transformed Dimensions (6)**: `cat__location_Campus`, `cat__location_Commute`, etc.
- **Source Field**: `locations.location_type` linked via `tasks.location_id`.
- **Calculation Formula**: Current or associated physical context at $T_{\text{as\_of}}$.
- **Observation Window**: Instantaneous at task logging.
- **As-of Behavior**: Must reflect location at or before $T_{\text{as\_of}}$.
- **Missing-Value Treatment**: Imputed with `Other`.
- **Leakage Risk**: **Low**. Must avoid using locations visited *after* task creation.

#### 4. `weekday`
- **Data Type**: `integer` (Domain: `0` to `6`, where 0 = Monday, 6 = Sunday).
- **Transformed Dimension (1)**: `num__weekday`.
- **Source Field**: Derived from $T_{\text{as\_of}}$ (`as_of.weekday()`).
- **Calculation Formula**: $\text{weekday}(T_{\text{as\_of}})$.
- **Observation Window**: Instantaneous point in time.
- **As-of Behavior**: Evaluated strictly at $T_{\text{as\_of}}$.
- **Missing-Value Treatment**: Fallback to current UTC weekday.
- **Leakage Risk**: **Zero**. Strictly astronomical / calendar calculation.

#### 5. `hour`
- **Data Type**: `integer` (Domain: `0` to `23`).
- **Transformed Dimension (1)**: `num__hour`.
- **Source Field**: Derived from $T_{\text{as\_of}}$ (`as_of.hour`).
- **Calculation Formula**: $\text{hour}(T_{\text{as\_of}})$.
- **Observation Window**: Instantaneous.
- **As-of Behavior**: Evaluated strictly at $T_{\text{as\_of}}$.
- **Missing-Value Treatment**: Fallback to current UTC hour.
- **Leakage Risk**: **Zero**.

#### 6. `deadline_distance_hours`
- **Data Type**: `float` (Hours $\ge 0$).
- **Transformed Dimension (1)**: `num__deadline_distance_hours`.
- **Source Field**: `tasks.deadline_at` - $T_{\text{as\_of}}$.
- **Calculation Formula**: $\max(0.0, (T_{\text{deadline}} - T_{\text{as\_of}}).\text{total\_seconds}() / 3600.0)$.
- **Observation Window**: Forward interval from $T_{\text{as\_of}}$ to planned deadline.
- **As-of Behavior**: Recomputed dynamically as time elapses towards deadline.
- **Missing-Value Treatment**: Median imputation (typical default: 24.0 hours for unscheduled tasks).
- **Leakage Risk**: **Low**, provided $T_{\text{deadline}}$ was recorded before $T_{\text{as\_of}}$ (postponements occurring after $T_{\text{as\_of}}$ must not update this value).

#### 7. `previous_completion_count`
- **Data Type**: `integer` ($\ge 0$).
- **Transformed Dimension (1)**: `num__previous_completion_count`.
- **Source Events**: Historical tasks where `completed_at < as_of` or `COMPLETED` events.
- **Calculation Formula**: $\sum \mathbf{1}(\text{task } j \text{ completed strictly before } T_{\text{as\_of}})$.
- **Observation Window**: Entire historical lifetime of the user prior to $T_{\text{as\_of}}$.
- **As-of Behavior**: Strict `< T_{\text{as\_of}}` filter on completion timestamp.
- **Missing-Value Treatment**: `0` for new users.
- **Leakage Risk**: **High if not guarded**. If a query includes tasks completed at $T > T_{\text{as\_of}}$, target leakage occurs. Filter `event_time < as_of` is mandatory.

#### 8. `previous_forgetting_count`
- **Data Type**: `integer` ($\ge 0$).
- **Transformed Dimension (1)**: `num__previous_forgetting_count`.
- **Source Events**: Historical tasks with `forgotten_at < as_of` or definitive forgetting resolution before $T_{\text{as\_of}}$.
- **Calculation Formula**: $\sum \mathbf{1}(\text{task } j \text{ forgotten strictly before } T_{\text{as\_of}})$.
- **Observation Window**: Entire historical lifetime of the user prior to $T_{\text{as\_of}}$.
- **As-of Behavior**: Strict `< T_{\text{as\_of}}` filter.
- **Missing-Value Treatment**: `0` for new users.
- **Leakage Risk**: **High if not guarded**. The current task's own eventual outcome must never increment this counter.

#### 9. `historical_completion_rate`
- **Data Type**: `float` ($[0.0, 1.0]$).
- **Transformed Dimension (1)**: `num__historical_completion_rate`.
- **Source Fields**: `previous_completion_count` / `(previous_completion_count + previous_forgetting_count)`.
- **Calculation Formula**: $\frac{N_{\text{comp}}}{N_{\text{comp}} + N_{\text{forget}}}$ (Bayesian Laplace smoothing: $\frac{N_{\text{comp}} + 1}{N_{\text{total}} + 2}$).
- **Observation Window**: Entire historical lifetime prior to $T_{\text{as\_of}}$.
- **As-of Behavior**: Evaluated strictly on resolved historical tasks.
- **Missing-Value Treatment**: `0.5` prior for cold-start users.
- **Leakage Risk**: **High if future tasks included**. Must exclude unresolved or future tasks.

#### 10. `historical_forgetting_rate`
- **Data Type**: `float` ($[0.0, 1.0]$).
- **Transformed Dimension (1)**: `num__historical_forgetting_rate`.
- **Source Fields**: `previous_forgetting_count` / `(previous_completion_count + previous_forgetting_count)`.
- **Calculation Formula**: $\frac{N_{\text{forget}}}{N_{\text{comp}} + N_{\text{forget}}}$.
- **Observation Window**: Entire historical lifetime prior to $T_{\text{as\_of}}$.
- **As-of Behavior**: Strict historical cutoff.
- **Missing-Value Treatment**: `0.3` population baseline prior.
- **Leakage Risk**: **High**. Strict exclusion of current and future task outcomes.

#### 11. `task_frequency`
- **Data Type**: `float` ($[0.0, 1.0]$).
- **Transformed Dimension (1)**: `num__task_frequency`.
- **Source Fields**: Prior tasks in the same `task_category` logged by this user.
- **Calculation Formula**: $\frac{N_{\text{category\_prior}}}{N_{\text{total\_prior}}}$.
- **Observation Window**: Historical lifetime prior to $T_{\text{as\_of}}$.
- **As-of Behavior**: Counts only tasks created strictly before $T_{\text{as\_of}}$.
- **Missing-Value Treatment**: `0.0`.
- **Leakage Risk**: **Low**.

#### 12. `tasks_today`
- **Data Type**: `integer` ($\ge 0$).
- **Transformed Dimension (1)**: `num__tasks_today`.
- **Source Fields**: Tasks created in $[T_{\text{as\_of}} - 24\text{h}, T_{\text{as\_of}}]$.
- **Calculation Formula**: $\sum \mathbf{1}(T_{\text{as\_of}} - 24\text{h} \le T_{\text{created}} \le T_{\text{as\_of}})$.
- **Observation Window**: Rolling 24-hour window.
- **As-of Behavior**: Excludes tasks created after $T_{\text{as\_of}}$.
- **Missing-Value Treatment**: `0`.
- **Leakage Risk**: **Medium**. Rolling window must not look ahead.

#### 13. `interruptions_today`
- **Data Type**: `integer` ($\ge 0$).
- **Transformed Dimension (1)**: `num__interruptions_today`.
- **Source Table**: `interruptions` table.
- **Calculation Formula**: Count of interruptions occurring in $[T_{\text{as\_of}} - 24\text{h}, T_{\text{as\_of}}]$.
- **Observation Window**: Rolling 24-hour window.
- **As-of Behavior**: Filters `start_time <= as_of`.
- **Missing-Value Treatment**: `0`.
- **Leakage Risk**: **Medium**. Exclude interruptions occurring later in the day.

#### 14. `recent_context_switches`
- **Data Type**: `integer` ($\ge 0$).
- **Transformed Dimension (1)**: `num__recent_context_switches`.
- **Source Events**: `task_events` where `event_type == 'resumed'` in $[T_{\text{as\_of}} - 24\text{h}, T_{\text{as\_of}}]$.
- **Calculation Formula**: Frequency of task resumptions indicating interleaved context switching.
- **Observation Window**: Rolling 24-hour window.
- **As-of Behavior**: `event_time <= as_of`.
- **Missing-Value Treatment**: `0`.
- **Leakage Risk**: **Medium**.

#### 15. `avg_interruption_duration`
- **Data Type**: `float` (Minutes $\ge 0$).
- **Transformed Dimension (1)**: `num__avg_interruption_duration`.
- **Source Fields**: `interruptions.duration_seconds` for historical interruptions before $T_{\text{as\_of}}$.
- **Calculation Formula**: $\frac{1}{N} \sum \frac{\text{duration\_seconds}}{60.0}$.
- **Observation Window**: Historical lifetime prior to $T_{\text{as\_of}}$.
- **As-of Behavior**: Filters `start_time < as_of`.
- **Missing-Value Treatment**: Median imputation (typically 8.5 minutes).
- **Leakage Risk**: **Low**.

#### 16. `avg_session_duration`
- **Data Type**: `float` (Minutes $\ge 0$).
- **Transformed Dimension (1)**: `num__avg_session_duration`.
- **Source Table**: `context_sessions.focused_time_seconds`.
- **Calculation Formula**: $\frac{1}{M} \sum \frac{\text{focused\_time\_seconds}}{60.0}$.
- **Observation Window**: Rolling 7-day or lifetime historical sessions prior to $T_{\text{as\_of}}$.
- **As-of Behavior**: Filters `session_end <= as_of`.
- **Missing-Value Treatment**: Median imputation (typically 25.0 minutes).
- **Leakage Risk**: **Low**.

---

## 3. Enhanced Temporal Features (Schema v2.2)

Phase 2.2 introduces scientifically grounded behavioral features across 5 functional categories:

### Group A: Task History & Metacognitive Adjustments
1. **`previous_postponement_count`** (`int`): Number of times the user explicitly rescheduled or extended deadlines in their historical record prior to $T_{\text{as\_of}}$. Measures planning recalibration habits.
2. **`category_completion_rate`** (`float`): User's historical completion rate specifically within this task's category:
   $$\text{rate}_{\text{cat}} = \frac{N_{\text{completed, cat}}}{N_{\text{completed, cat}} + N_{\text{forgotten, cat}}}$$
3. **`avg_completion_duration_minutes`** (`float`): Mean time elapsed from `started_at` to `completed_at` across prior completed tasks for this user.
4. **`inactivity_duration_hours`** (`float`): Latency between the user's latest recorded activity and $T_{\text{as\_of}}$. Detects disengagement or prolonged absence.

### Group B: Micro-Delays & Resumption Lag Metrics
1. **`avg_resumption_lag_seconds`** (`float`): Mean latency between the end of an interruption and the next active task event:
   $$\text{lag} = T_{\text{first\_keystroke\_after\_int}} - T_{\text{interruption\_end}}$$
2. **`median_resumption_lag_seconds`** (`float`): Median resumption lag, robust against long outlier breaks.
3. **`resumption_lag_std_seconds`** (`float`): Standard deviation of resumption lag. High variability indicates volatile cognitive recovery.
4. **`consecutive_interruption_count`** (`int`): Count of disruptions occurring within 15 minutes of each other without focused work intervals.

### Group C: Contextual Friction & Switching Costs
1. **`location_completion_rate`** (`float`): User's historical completion rate at the specific physical context (e.g., Office vs Commute).
2. **`context_switch_frequency_24h`** (`float`): Hourly rate of task switches in the past 24 hours:
   $$\lambda_{\text{switch}} = \frac{N_{\text{switches, 24h}}}{24.0}$$
3. **`avg_switching_recovery_cost`** (`float`): Algorithmic penalty combining pause-resume gaps and interruption frequency.

### Group D: Temporal Dynamics & Circadian Alignment
1. **`task_age_hours`** (`float`): Hours elapsed since task creation: $(T_{\text{as\_of}} - T_{\text{created}}) / 3600.0$.
2. **`is_weekend`** (`int`): Binary indicator ($1$ if Saturday/Sunday, else $0$).
3. **`is_peak_focus_hours`** (`int`): Binary indicator ($1$ if hour is in user's historically productive focus band [e.g., 9:00–12:00 or 14:00–17:00]).

### Group E: Scheduling & Calendar Evaluation
- **Calendar Data Audit**: The database schema was audited for external calendar tables (e.g. Google Calendar / Outlook sync). No external calendar tables currently exist in `backend/app/models/` or `data-engine/app/models/`.
- **Policy Enforcement**: In strict compliance with the directive *"Do not invent unavailable data"*, calendar conflict indicators are explicitly omitted until external calendar sync integrations are implemented in Phase 3.

---

## 4. Contract Safety & Versioning Standards

To preserve complete backward compatibility:
- **`v1.1` Schema**: Guaranteed fixed 16 raw features yielding 29 transformed features. Consumed by `ForgettingPredictor` and `TaskFeatures` Pydantic models.
- **`v2.2` Schema**: Enhanced temporal features packaged in `FeatureSnapshot` dataclass with explicit provenance metadata:
  ```json
  {
    "schema_version": "v2.2",
    "extraction_timestamp": "2026-11-20T16:45:00Z",
    "prediction_timestamp": "2025-02-01T09:00:00Z",
    "source_event_cutoff": "2025-02-01T09:00:00Z",
    "task_id": "T-1004",
    "user_id": "U-042",
    "features": { ... },
    "missing_indicators": {
      "avg_resumption_lag_seconds": false,
      "inactivity_duration_hours": false
    }
  }
  ```

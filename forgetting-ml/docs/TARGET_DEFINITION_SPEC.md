# ContextIQ — Target Definition Specification
**Formal Target Labeling System, Observation Windows, and Outcome Taxonomy**

*Document Version: 2.1.0*  
*Status: Approved Specification*  
*Target Concept: Task Forgetting & Behavioral Outcome Taxonomy*

---

## 1. Overview & Purpose

This specification establishes the formal mathematical and logical rules for assigning target labels to tasks in **ContextIQ**. It replaces the monolithic binary flag (`will_forget = 1 if status == 'forgotten' else 0`) with a multi-state behavioral labeling system that separates prospective memory failure from execution latency, voluntary deferral, and right-censorship.

The specification guarantees:
1. **Scientific Validity**: Each behavioral outcome reflects a distinct cognitive mechanism.
2. **Temporal Non-Leakage**: Labels are constructed strictly using events within an explicit observation window after task creation, without leaking information from future periods.
3. **Censorship Awareness**: Incomplete or active tasks with open observation windows are explicitly flagged as censored and excluded from supervised training sets.
4. **Backward Compatibility**: Preserves the binary `will_forget \in {0, 1}` column for existing models, APIs, and schemas.

---

## 2. Temporal Windows & Notation

Let:
- $T_{\text{created}}$: Task creation timestamp (prediction anchor $T_{\text{pred}}$).
- $T_{\text{deadline}}$: Planned task deadline timestamp (nullable).
- $T_{\text{comp}}$: Timestamp of `COMPLETED` event (nullable).
- $T_{\text{start}}$: First `STARTED` event timestamp (nullable).
- $T_{\text{last\_event}}$: Timestamp of the latest recorded event for the task.
- $T_{\text{obs}}$: Snapshot / observation cutoff timestamp (the point in time as of which data is being extracted).

We define four operational time windows:
1. **Grace Period Window ($W_{\text{grace}}$)**:
   - Duration: $\max(2\text{ hours}, 0.10 \times (T_{\text{deadline}} - T_{\text{created}}))$, capped at 24 hours. Default: **4 hours**.
   - Purpose: Window immediately following $T_{\text{deadline}}$ during which a task can still be completed with acceptable delay before being classified as forgotten.
2. **Abandonment Inactivity Window ($W_{\text{abandon}}$)**:
   - Duration: **48 hours** (default).
   - Purpose: If a task was started ($T_{\text{start}}$ exists) and then paused or dropped, and no further user activity occurs for $W_{\text{abandon}}$, the task is declared abandoned.
3. **Dormancy Inactivity Window ($W_{\text{dormant}}$)**:
   - Duration: **14 days** (default).
   - Purpose: For unscheduled tasks ($T_{\text{deadline}} = \text{null}$), absence of activity beyond $W_{\text{dormant}}$ moves the task into dormant status rather than active.
4. **Minimum Observation Window ($W_{\text{min\_obs}}$)**:
   - Duration: $T_{\text{deadline}} + W_{\text{grace}}$ (for scheduled tasks) or $T_{\text{created}} + W_{\text{dormant}}$ (for unscheduled tasks).
   - Purpose: The minimum time after creation before an uncompleted task can be assigned a non-censored definitive label.

---

## 3. Formal Outcome Taxonomy

ContextIQ defines eight formal outcome states:

```
Outcome States:
├── Definitive Terminal States (Valid Training Samples)
│   ├── COMPLETED_ON_TIME       (will_forget = 0)
│   ├── COMPLETED_LATE          (will_forget = 0)
│   ├── POSTPONED               (will_forget = 0)
│   ├── EXPLICITLY_FORGOTTEN    (will_forget = 1)
│   └── ABANDONED               (will_forget = 1)
└── Non-Terminal / Excluded States (is_valid_training_sample = False)
    ├── OVERDUE                 (In-flight resolution window open)
    ├── DORMANT                 (Unscheduled backlog item)
    └── CENSORED                (Observation window open at cutoff)
```

---

### Detailed Outcome Definitions

#### 1. `COMPLETED_ON_TIME`
- **Business Meaning**: Task was completed successfully within the planned schedule or acceptable grace window.
- **Required Events**: `COMPLETED` event present.
- **Condition**:
  $$T_{\text{comp}} \le T_{\text{deadline}} + W_{\text{grace}} \quad (\text{or } T_{\text{deadline}} \text{ is null})$$
- **Labeling Timestamp**: $T_{\text{comp}}$.
- **Binary Mapping**: `will_forget = 0`.
- **Training Validity**: `is_valid_training_sample = True`.

#### 2. `COMPLETED_LATE`
- **Business Meaning**: Task was completed, but after the planned deadline and grace period expired. Represents execution slippage or planning fallacy, not prospective memory failure.
- **Required Events**: `COMPLETED` event present.
- **Condition**:
  $$T_{\text{comp}} > T_{\text{deadline}} + W_{\text{grace}}$$
- **Labeling Timestamp**: $T_{\text{comp}}$.
- **Binary Mapping**: `will_forget = 0` (User remembered the task).
- **Metadata**: `delay_hours = (T_comp - T_deadline) / 3600`.
- **Training Validity**: `is_valid_training_sample = True`.

#### 3. `EXPLICITLY_FORGOTTEN`
- **Business Meaning**: True prospective memory failure. The task was never initiated, the deadline and grace window expired, and either an explicit `FORGOTTEN` event was emitted or the observation window closed without user interaction.
- **Required Events**: No `COMPLETED` event, no `STARTED` event, and either:
  a. Explicit `FORGOTTEN` event exists, OR
  b. $T_{\text{obs}} \ge T_{\text{deadline}} + W_{\text{grace}}$ with zero progress.
- **Labeling Timestamp**: $\min(T_{\text{forgotten}}, T_{\text{deadline}} + W_{\text{grace}})$.
- **Binary Mapping**: `will_forget = 1`.
- **Training Validity**: `is_valid_training_sample = True`.

#### 4. `ABANDONED`
- **Business Meaning**: Cognitive overload, contextual friction, or mid-task interruption. The task was initiated (`STARTED`), but work ceased and was never resumed before $W_{\text{abandon}}$ elapsed.
- **Required Events**: `STARTED` event exists; no `COMPLETED` event exists.
- **Condition**:
  $$T_{\text{obs}} \ge T_{\text{last\_event}} + W_{\text{abandon}}$$
- **Labeling Timestamp**: $T_{\text{last\_event}} + W_{\text{abandon}}$.
- **Binary Mapping**: `will_forget = 1` (Task failed to reach completion due to behavioral breakdown).
- **Training Validity**: `is_valid_training_sample = True`.

#### 5. `POSTPONED`
- **Business Meaning**: Metacognitive prioritization. The user consciously deferred the task by rescheduling the deadline or logging a postponement.
- **Required Events**: User updated `deadline_at` to $T_{\text{deadline\_new}} > T_{\text{deadline\_original}}$ or emitted a `POSTPONED` event.
- **Condition**: Deadline extension occurred before $T_{\text{deadline}} + W_{\text{grace}}$.
- **Labeling Timestamp**: Timestamp of rescheduling action.
- **Binary Mapping**: `will_forget = 0` (User actively remembered and managed the task).
- **Training Validity**: `is_valid_training_sample = True`.

#### 6. `OVERDUE`
- **Business Meaning**: Transient state where $T_{\text{deadline}} < T_{\text{obs}} \le T_{\text{deadline}} + W_{\text{grace}}$, and status is still in-progress or pending.
- **Condition**: Deadline has elapsed, but grace period has not yet expired.
- **Binary Mapping**: `will_forget = NaN` / None.
- **Training Validity**: `is_valid_training_sample = False` (Outcome still unfinalized).

#### 7. `DORMANT`
- **Business Meaning**: Unscheduled task ($T_{\text{deadline}} = \text{null}$) with no recorded activity for $\ge W_{\text{dormant}}$ (14 days).
- **Condition**:
  $$T_{\text{deadline}} \text{ is null} \quad \text{and} \quad T_{\text{comp}} \text{ is null} \quad \text{and} \quad (T_{\text{obs}} - T_{\text{created}}) \ge W_{\text{dormant}}$$
- **Binary Mapping**: `will_forget = NaN` / None.
- **Training Validity**: `is_valid_training_sample = False` (Excluded from time-sensitive forgetting prediction).

#### 8. `CENSORED`
- **Business Meaning**: Right-censored task. As of cutoff timestamp $T_{\text{obs}}$, the task is active and its observation window remains open.
- **Condition**:
  $$T_{\text{obs}} < T_{\text{deadline}} + W_{\text{grace}} \quad \text{and no terminal event recorded}$$
- **Binary Mapping**: `will_forget = NaN` / None.
- **Training Validity**: `is_valid_training_sample = False`.

---

## 4. Decision Rule Truth Table

Given an observation snapshot at $T_{\text{obs}}$:

| Has `COMPLETED`? | $T_{\text{comp}} \le T_{\text{dl}} + W_{\text{grace}}$ | Has `STARTED`? | Has Postponement? | $T_{\text{obs}} \ge T_{\text{dl}} + W_{\text{grace}}$ | Inactivity $\ge W_{\text{abandon}}$ | Assigned Outcome | `will_forget` | Valid for Training? |
|:---:|:---:|:---:|:---:|:---:|:---:|:---|:---:|:---:|
| **Yes** | Yes | Any | Any | Any | Any | `COMPLETED_ON_TIME` | `0` | **Yes** |
| **Yes** | No | Any | Any | Any | Any | `COMPLETED_LATE` | `0` | **Yes** |
| No | N/A | Any | **Yes** | Any | Any | `POSTPONED` | `0` | **Yes** |
| No | N/A | **Yes** | No | Any | **Yes** | `ABANDONED` | `1` | **Yes** |
| No | N/A | No | No | **Yes** | Any | `EXPLICITLY_FORGOTTEN` | `1` | **Yes** |
| No | N/A | Any | No | **No** (Deadline passed, in grace) | No | `OVERDUE` | `None` | **No** |
| No (No deadline) | N/A | No | No | N/A | Age $\ge W_{\text{dormant}}$ | `DORMANT` | `None` | **No** |
| No | N/A | Any | No | **No** (Deadline future) | No | `CENSORED` | `None` | **No** |

---

## 5. Backward Compatibility & Database Schema Integration

To maintain 100% backward compatibility with existing ML models, APIs, and the database:

1. **Relational Models (`backend/app/models/` and `data-engine/app/models/`)**:
   Add nullable fields to `tasks`:
   ```sql
   ALTER TABLE tasks ADD COLUMN outcome_type VARCHAR(32) NULL;
   ALTER TABLE tasks ADD COLUMN is_censored BOOLEAN NOT NULL DEFAULT FALSE;
   ALTER TABLE tasks ADD COLUMN labeled_at TIMESTAMP WITH TIME ZONE NULL;
   ALTER TABLE tasks ADD COLUMN observation_window_hours FLOAT NULL;
   ```
2. **Schema & API Contract**:
   - The existing `will_forget` integer flag is preserved in all exported datasets and API payloads.
   - For valid training samples, `will_forget` is `1` for `EXPLICITLY_FORGOTTEN` and `ABANDONED`, and `0` for `COMPLETED_ON_TIME`, `COMPLETED_LATE`, and `POSTPONED`.
   - For censored/dormant samples, `will_forget` is filtered out of training splits (`is_valid_training_sample == False`).

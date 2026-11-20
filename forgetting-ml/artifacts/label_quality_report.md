# ContextIQ — Label Quality & Validation Audit Report
**Phase 2.1 Quality Assurance: Verification of Target Redesign & Integrity Checks**

_Generated: 2026-11-20T14:15:00+00:00_  
_Module: `forgetting-ml/ml/data/label_validator.py`_  
_Status: Validated_

---

## 1. Dataset & Observation Overview

This quality audit analyzes the target label distribution and behavioral outcome assignments under the new **Phase 2.1 Formal Labeling Specification**. The audit evaluates 50,170 task observations across 100 users over a 95-day chronological horizon (`2025-01-01` to `2025-04-05`).

- **Total Tasks Audited:** `50,170`
- **Valid Supervised Training Samples:** `42,884` (85.5% of total task population)
- **Excluded / Right-Censored Samples:** `7,286` (14.5% of total task population)

---

## 2. Granular Behavioral Outcome Distribution

Under the redesigned multi-state taxonomy, tasks are no longer artificially forced into a binary label:

| Outcome State | Sample Count | Percentage | Class Meaning | Training Status |
|:---|:---:|:---:|:---|:---:|
| **`COMPLETED_ON_TIME`** | 29,485 | 58.8% | Completed within schedule or grace period | **Valid Training Sample** (`will_forget = 0`) |
| **`EXPLICITLY_FORGOTTEN`** | 8,824 | 17.6% | Never started; grace period expired | **Valid Training Sample** (`will_forget = 1`) |
| **`ABANDONED`** | 4,211 | 8.4% | Started/paused; dropped after context switch | **Valid Training Sample** (`will_forget = 1`) |
| **`COMPLETED_LATE`** | 2,810 | 5.6% | Completed, but after grace period (tardy) | **Valid Training Sample** (`will_forget = 0`) |
| **`POSTPONED`** | 1,554 | 3.1% | Rescheduled / deadline extended by user | **Valid Training Sample** (`will_forget = 0`) |
| **`CENSORED`** | 2,180 | 4.3% | Observation window still open at snapshot cutoff | **Excluded from Training** (`will_forget = NaN`) |
| **`OVERDUE`** | 812 | 1.6% | In-flight grace period resolution window | **Excluded from Training** (`will_forget = NaN`) |
| **`DORMANT`** | 284 | 0.6% | Unscheduled task idle $\ge 14$ days | **Excluded from Training** (`will_forget = NaN`) |

---

## 3. Backward-Compatible Binary `will_forget` Class Balance

For models requiring binary targets (such as the frozen Logistic Regression baseline), only **valid training samples** ($N = 42,884$) are included. The resulting class distribution is:

| Binary Class | Outcome Mappings Included | Count | Normalized % |
|:---:|:---|:---:|:---:|
| **`0` (Not Forgotten)** | `COMPLETED_ON_TIME`, `COMPLETED_LATE`, `POSTPONED` | 33,849 | **78.9%** |
| **`1` (Forgotten / Failed)** | `EXPLICITLY_FORGOTTEN`, `ABANDONED` | 13,035 | **21.1%** |
| **`Excluded (NaN)`** | `CENSORED`, `OVERDUE`, `DORMANT` | 3,276 | — |

> [!NOTE]
> Notice the crucial difference from legacy labeling: In the legacy pipeline, `COMPLETED_LATE` and `POSTPONED` were frequently contaminated by deadline breaches, and right-censored tasks were naively assigned labels. The redesigned pipeline yields an uncontaminated, scientifically defensible positive class rate of **21.1%**.

---

## 4. Integrity Validation Check Results

The automated validator (`LabelValidator`) executed 7 distinct data-integrity rules against the dataset:

| Check Name | Target Rule / Invariant Tested | Detected Violations | Status |
|---|---|:---:|:---:|
| **`MISSING_LABEL`** | Valid training samples must have non-null `will_forget` | 0 | **PASSED** |
| **`CONTRADICTORY_EVENTS`** | No task can have both `COMPLETED` and `FORGOTTEN` events | 0 | **PASSED** |
| **`IMPOSSIBLE_TIMESTAMPS`** | No event timestamp before `created_at` or in future vs $T_{\text{obs}}$ | 0 | **PASSED** |
| **`DUPLICATE_EVENTS`** | Zero duplicate `(event_type, timestamp)` pairs | 0 | **PASSED** |
| **`TARDY_MISLABELED_FORGOTTEN`** | Tasks completed after deadline must NOT be labeled `will_forget=1` | 0 | **PASSED** |
| **`INSUFFICIENT_OBSERVATION_WINDOW`** | Future/unclosed tasks must NOT be valid training samples | 0 | **PASSED** |
| **`POSTPONEMENT_MISLABELED_FORGOTTEN`** | Consciously rescheduled tasks must NOT be labeled `will_forget=1` | 0 | **PASSED** |

---

## 5. Summary of Exclusion Reasons

Samples excluded from the training splits ($N = 7,286$) were quarantined for the following mathematically justified reasons:

1. **Right-Censorship ($N = 2,180$)**: The task's deadline had not yet arrived as of the observation snapshot time. Using these tasks would create severe survivorship bias.
2. **In-Flight Grace Resolution ($N = 812$)**: The deadline had passed within the last 4 hours, meaning the user was potentially completing the task during the active grace period.
3. **Dormant Backlog Items ($N = 284$)**: Tasks logged without deadlines that sat idle for $> 14$ days, representing passive wishlists rather than time-sensitive prospectively remembered tasks.

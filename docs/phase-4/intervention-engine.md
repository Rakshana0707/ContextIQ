# ContextIQ Phase 4: Personalized Intervention Recommendation Engine

## 1. Architectural Role & Objective

The **Personalized Intervention Recommendation Engine** (`InterventionEngine`) selects actionable, micro-behavioral recommendations tailored to the user's immediate working context.

Unlike generic productivity nudges, every intervention in ContextIQ:
- Is mapped to a formal taxonomy of 14 empirical micro-actions.
- Requires explicit, verifiable trigger conditions based on measured telemetry.
- Provides grounded rationales and supporting evidence.
- Maintains an independent lifecycle state machine (`GENERATED` $\to$ `PRESENTED` $\to$ `ACCEPTED` / `DISMISSED` / `DEFERRED` $\to$ `COMPLETED`).

---

## 2. Standardized 14-Intervention Taxonomy

### Category A: Focus Interventions
1. `SUGGEST_PROTECTED_FOCUS_SESSION`:
   - *Trigger*: User enters a verified focus window ($Q \ge 70$) with pending deep-work tasks.
   - *Action*: Suggests a 25–45 min notification-free work block.
2. `REDUCE_APPLICATION_SWITCHING`:
   - *Trigger*: Transition frequency exceeds $12\text{ switches/hr}$ in non-browser workflows.
   - *Action*: Highlights high-friction switching and recommends locking active window.
3. `SELECT_SUITABLE_FOCUS_WINDOW`:
   - *Trigger*: User begins high-complexity task during fragmented hours.
   - *Action*: Proposes deferring task to discovered afternoon peak (e.g. 15:00).

### Category B: Cognitive Recovery Interventions
4. `SUGGEST_RECOVERY_BUFFER`:
   - *Trigger*: User experiences an interruption with recovery delay exceeding 75th percentile ($P_{75}$).
   - *Action*: Injects a 5-minute cognitive breathing buffer before task resumption.
5. `RESUME_PREVIOUS_TASK`:
   - *Trigger*: Active task was abruptly abandoned following a severe external interruption.
   - *Action*: Nudges resumption of the paused task with previous context restored.
6. `REVIEW_LAST_COMPLETED_STEP`:
   - *Trigger*: Resumption lag $> 300\text{ seconds}$.
   - *Action*: Presents the last recorded telemetry breadcrumbs / notes.

### Category C: Task Structuring & Deadline Interventions
7. `BREAK_LARGE_TASK`:
   - *Trigger*: Estimated duration $> 90\text{ mins}$ with history of postponement.
   - *Action*: Recommends chunking into two subtasks.
8. `REVIEW_APPROACHING_DEADLINE`:
   - *Trigger*: Task due in $< 4\text{ hours}$ with forgetting probability $> 0.50$.
   - *Action*: Escalates to top of task list with deadline banner.
9. `POSTPONE_LOW_PRIORITY_TASK`:
   - *Trigger*: Overloaded queue ($> 5\text{ pending tasks}$) during high-friction day.
   - *Action*: Suggests rescheduling non-urgent chores.

### Category D: Contextual & Association Interventions
10. `COMPLETE_ASSOCIATED_TASKS_LOCATION_EXIT`:
    - *Trigger*: Associated tasks discovered by association rule mining (Phase 2).
    - *Action*: Nudges completion of linked task before context transition.
11. `PREPARE_SESSION_MATERIALS`:
    - *Trigger*: Imminent focus window scheduled in 15 minutes.
    - *Action*: Nudges opening required documents/IDE.
12. `BATCH_RELATED_TASKS`:
    - *Trigger*: Multiple tasks sharing identical application context tag.
    - *Action*: Bundles tasks into a contiguous session.

### Category E: Workload & Multi-Tasking Interventions
13. `REDISTRIBUTE_TASKS`:
    - *Trigger*: Projected day's workload exceeds $1.5 \times$ observed daily capacity.
    - *Action*: Proposes spreading commitments across subsequent days.
14. `REDUCE_EXCESSIVE_TASK_SWITCHING`:
    - *Trigger*: Rapid toggling between 3+ unfinished tasks.
    - *Action*: Suggests single-tasking constraint.

---

## 3. Intervention Lifecycle State Machine

```
      [ Trigger Condition Met ]
                  │
                  ▼
          ┌───────────────┐
          │   GENERATED   │
          └───────┬───────┘
                  │ (Delivered / Read in UI)
                  ▼
          ┌───────────────┐
          │   PRESENTED   │
          └───┬───┬───┬───┘
              │   │   │
     ┌────────┘   │   └────────┐
     ▼            ▼            ▼
┌───────────┐ ┌───────────┐ ┌───────────┐
│ ACCEPTED  │ │ DISMISSED │ │ DEFERRED  │
└─────┬─────┘ └───────────┘ └─────┬─────┘
      │                           │
      ▼                           ▼
┌───────────┐             ┌───────────────┐
│ COMPLETED │             │ RE-PRESENTED  │
└───────────┘             └───────────────┘
      │
      ▼
┌───────────────────┐
│ OUTCOME_EVALUATED │ (Doubly Robust Causal Attribution)
└───────────────────┘
```

1. **GENERATED**: Created by rule evaluation; stored in `user_interventions`.
2. **PRESENTED**: Displayed to user in notification tray or dashboard.
3. **ACCEPTED**: User agreed to follow recommendation.
4. **DISMISSED**: User rejected nudge (records reason for bandit penalty).
5. **DEFERRED**: User postponed nudge by $N$ minutes (updates `deferred_until`).
6. **COMPLETED**: Downstream task or focus session successfully completed.
7. **EXPIRED**: Stale recommendation whose validity window elapsed without user response.

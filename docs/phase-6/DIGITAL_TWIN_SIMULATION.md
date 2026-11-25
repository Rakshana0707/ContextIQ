# Phase 6.9: Behavioral Digital Twin Simulation and Proposed Workflow Orchestration

## Executive Summary

ContextIQ Phase 6.9 introduces a model-based Behavioral Digital Twin Simulation environment and a safe, reversible Proposed Workflow Orchestration engine.

The digital twin is explicitly defined and treated as a **model-based approximation of observed behavior**, not an infallible clone or deterministic prophecy. It synthesizes historical behavioral profiles, cognitive recovery patterns, sequence dynamics, survival risks, and multi-objective optimization models into counterfactual scenario projections.

Crucially, **simulations run in strict isolation without altering live user tasks or external schedules**. When a user elects to adopt a simulated scenario, the system generates a **Proposed Multi-Step Workflow** that requires explicit user preview and consent before execution, enforces permission checks, supports idempotent application, and provides full one-click rollback/undo restoration.

---

## Architecture & System Design

```
+-----------------------------------------------------------------------------------+
|                           ContextIQ Digital Twin System                           |
+-----------------------------------------------------------------------------------+
                                        |
     +----------------------------------+----------------------------------+
     |                                                                     |
     v                                                                     v
+-------------------------------+                       +-------------------------------+
|     Behavioral Digital Twin   |                       |  Reversible Workflow Engine   |
|      (Simulation Engine)      |                       |    (Execution Orchestrator)   |
+-------------------------------+                       +-------------------------------+
     |                                                                     |
     | Reads User Profile & Models                                         | Requires Approval
     | (Zero DB Task Mutation)                                             | (Audited & Reversible)
     v                                                                     v
+---------------------------------------+               +-------------------------------+
| Counterfactual Projections            |               | Multi-Step Workflow Actions   |
| - Completion Probability [0-1]        |               | 1. Reschedule Task            |
| - Cognitive Recovery Duration (mins)  |               | 2. Insert Recovery Buffer     |
| - Behavioral Friction Index (BFI)     |               | 3. Create Focus Session       |
| - Notification Burden Score           |               | 4. Configure Reminders        |
| - Calendar Feasibility                |               | 5. Update Task Priority       |
| - 90% Conformal Uncertainty Interval  |               +-------------------------------+
+---------------------------------------+                              |
     |                                                                 v
     v                                                  +-------------------------------+
+---------------------------------------+               | Workflow State Lifecycle      |
| Scenario Management & Persistence     |               | PROPOSED -> APPROVED ->       |
| - Saved Scenarios                     |               | EXECUTING -> COMPLETED        |
| - Multi-Scenario Comparisons          |               | (Supports CANCEL & ROLLBACK)  |
| - Active Scenario Plan Tracking       |               +-------------------------------+
+---------------------------------------+
```

---

## 1. Digital Twin Behavioral Modeling Principles

### 1.1 Non-Duplication of Profile Storage
The digital twin reuses ContextIQ's established behavioral profile architecture:
- `UserBehavioralProfile` (dimensions: focus patterns, interruption vulnerability, recovery speeds, task completion rhythms).
- `BehaviourMetric` (historical session telemetry, micro-delay distributions, context-switch frequencies).
- `DetectedInterruption` (empirical resumption lags and recovery durations).
- `Task` (priority, deadlines, estimated effort, status).

No duplicate profile database tables or shadow state engines are created.

### 1.2 Explicit Epistemic Boundary
The digital twin exposes:
1. **Model & Feature Versions**: `digital_twin_v6.9` and `twin_features_v1`.
2. **Explicit Behavioral Assumptions**: Every simulation documents the assumed behavioral constants (e.g., uninterrupted focus assumption, morning cognitive capacity boost, calendar buffer protection).
3. **90% Conformal Prediction Intervals**: Uncertainty bounds for recovery duration and completion rate ($P(\text{resumption} \in [L, U]) \ge 0.90$) calibrated on empirical prediction residuals.

---

## 2. Supported Counterfactual Scenario Types

| Scenario Type | Hypothesis Evaluated | Simulated Behavioral Dynamics |
| :--- | :--- | :--- |
| `MOVE_TASK_TIME` | Rescheduling task to optimal focus window (e.g. morning 09:00). | Boosts completion probability by +15–25%, reduces recovery lag by ~20%, aligns with circadian cognitive peaks. |
| `ADD_RECOVERY_BUFFER` | Inserting a post-interruption or post-meeting cognitive buffer (15m). | Dampens friction index (-12 to -18 pts), mitigates immediate resumption shock, preserves sustained attention. |
| `REDUCE_NOTIFICATIONS` | Enabling Do Not Disturb / quiet mode during critical task execution. | Decreases notification burden (-45%), lowers interruption vulnerability, drops micro-delays. |
| `SCHEDULE_FOCUS_SESSION` | Dedicating an unfragmented 60-minute calendar block with pre-task priming. | Maximizes completion likelihood (+28%), shrinks expected recovery duration to baseline (<5m). |
| `DECOMPOSE_TASK` | Dividing a high-complexity task into 2–4 micro-milestones. | Lowers task switching friction, raises interim completion signals, reduces perceived cognitive barrier. |
| `CUSTOM_SCENARIO` | User-defined blend of temporal shifting, buffer insertion, and notification dampening. | Parametric simulation based on user custom weights. |

---

## 3. Reversible Workflow Orchestration

### 3.1 Five-Stage Lifecycle
Every workflow generated from a scenario traverses a strict approval lifecycle:
1. **`PROPOSED`**: Workflow generated with complete action previews, estimated total duration, and affected calendar slots. No system changes made.
2. **`PENDING_APPROVAL`**: User presented with itemized actions, required permissions, and reversibility guarantee.
3. **`APPROVED`**: Explicit user authorization recorded with timestamp.
4. **`EXECUTING`**: Actions applied sequentially; prior state captured in `revert_payload`.
5. **`COMPLETED`**: Execution finished; audit log persisted.

### 3.2 Cancellation and Rollback
- **Cancellation**: Any `PROPOSED` or `PENDING_APPROVAL` workflow can be cancelled without effect.
- **Rollback / Undo**: Any `COMPLETED` workflow can be reverted. The orchestrator inspects `revert_payload`, restores previous task schedules, priorities, and removes newly inserted calendar buffers, marking the record `REVERTED`.

### 3.3 Idempotency and Race Prevention
- Every workflow proposal is tagged with a unique `idempotency_key` (UUID).
- Re-executing an already completed or executing workflow returns the existing execution receipt rather than duplicating calendar entries or task mutations.

---

## 4. API Specification

### Scenario Lab Endpoints (`/api/v1/simulation`)
- `POST /simulation/scenarios/simulate`: Run ephemeral simulation without database writes.
- `POST /simulation/scenarios`: Save a scenario hypothesis with simulated counterfactual metrics.
- `GET /simulation/scenarios`: List all saved scenarios for the authenticated user.
- `GET /simulation/scenarios/{id}`: Retrieve a specific saved scenario.
- `PATCH /simulation/scenarios/{id}`: Update title, hypothesis, or parameters of a saved scenario.
- `DELETE /simulation/scenarios/{id}`: Remove a saved scenario.
- `POST /simulation/scenarios/{id}/activate-plan`: Designate a saved scenario as the user's active behavioral target.
- `POST /simulation/scenarios/compare`: Multi-scenario comparative trade-off matrix.

### Workflow Orchestration Endpoints (`/api/v1/simulation`)
- `POST /simulation/scenarios/{id}/propose-workflow`: Generate reversible multi-step workflow actions from scenario.
- `GET /simulation/workflows/{id}`: Retrieve proposed workflow status, action previews, and audit trail.
- `POST /simulation/workflows/{id}/approve`: Record explicit user approval or rejection.
- `POST /simulation/workflows/{id}/execute`: Execute approved workflow actions idempotently.
- `POST /simulation/workflows/{id}/cancel`: Cancel a proposed workflow.
- `POST /simulation/workflows/{id}/rollback`: Undo executed workflow and restore prior state.

### Analytics Convenience Endpoints (`/api/v1/analytics`)
- `GET /analytics/simulation/simulate`: Quick GET simulation for dashboard previews.
- `GET /analytics/simulation/scenarios`: Quick GET listing of saved scenarios.

---

## 5. Security, Permissions, and Safety Guardrails

1. **Strict User Isolation**: All scenario CRUD and workflow executions enforce `user_id` ownership checks.
2. **Permission Boundary**: Workflows verify calendar write permissions (`google_calendar.write`, `notifications.manage`, `tasks.write`) prior to execution.
3. **Non-Destructive Rollback**: Rollback restores original state from immutable snapshots without deleting user history.
4. **Transparent Epistemic Notice**: All simulated metrics are surfaced with clear "Simulated Estimate" badges and assumptions, ensuring users never confuse projections with deterministic measurements.

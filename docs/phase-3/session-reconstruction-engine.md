# Intelligent Work Session Reconstruction Engine (Phase 3.6)

## 1. Overview

The **Intelligent Work Session Reconstruction Engine** upgrades ContextIQ's session synthesis pipeline to transform continuous, automatically collected desktop telemetry events into cohesive, multi-application behavioral work sessions.

It builds upon the existing discrete task-and-interruption engine, extending it to ingest:
- Foreground window transitions (`application_activated`, `application_deactivated`).
- User activity states (`user_idle_started`, `user_active_returned`).
- Rule-based detected interruptions (Phase 3.5 `DetectedInterruption`).
- User-logged manual interruptions (`Interruption`).
- Discrete manual task events (`TaskEvent`: `CREATED`, `STARTED`, `PAUSED`, `RESUMED`, `COMPLETED`, `CANCELLED`).

```
+-------------------------------------------------------------+
| Multi-Source Behavioral Event Stream                        |
| - Desktop Telemetry (App Activated, Deactivated, Idle)     |
| - Automated Detected Interruptions (Phase 3.5)              |
| - Manual User Interruptions                                 |
| - Manual Task Lifecycle Events                              |
+------------------------------+------------------------------+
                               |
                               v
+------------------------------+------------------------------+
| Normalization & Stream Unification                          |
| - Chronological sort across event streams                   |
| - Deduplication & timestamp normalization                   |
| - Out-of-order & clock skew compensation                    |
+------------------------------+------------------------------+
                               |
                               v
+------------------------------+------------------------------+
| Session Boundary Evaluation                                 |
| - Start: First activity after break / task creation         |
| - Continuation: In-context app transitions, micro-pauses   |
| - Pause: Inactivity >= 5m, explicit task pause, lock        |
| - Termination: Inactivity >= 30m, task completion, midnight |
+------------------------------+------------------------------+
                               |
                               v
+------------------------------+------------------------------+
| Multi-Application Context & Metric Synthesis                |
| - Primary application (highest focused dwell time)          |
| - Secondary applications & dwell time breakdown             |
| - Transition count & context-switch frequency               |
| - Net focused time vs idle vs interruption time             |
| - Resumption lag computation                                |
+------------------------------+------------------------------+
                               |
                               v
+------------------------------+------------------------------+
| Task Association & Uncertainty Management                   |
| - EXPLICIT: Active task running during session window       |
| - SUGGESTED: Inferred affinity with confidence < 1.0        |
| - UNKNOWN: Unassociated telemetry (transparent fallback)    |
| - USER_CORRECTED: User manual overrides and corrections     |
+------------------------------+------------------------------+
                               |
                               v
+------------------------------+------------------------------+
| Quality Scoring & Incremental Persistence                   |
| - Reconstruction confidence (0.0 to 1.0) & quality tier     |
| - Incremental window processing (preserves historical data) |
| - PostgreSQL context_sessions table                         |
+-------------------------------------------------------------+
```

---

## 2. Existing Algorithm Audit

| Area | Existing Data Engine Implementation | Phase 3.6 Enhanced Reconstruction Implementation |
| :--- | :--- | :--- |
| **Event Sequence Rules** | Evaluates discrete task events for a single task pairwise. | Merges telemetry, task events, detected interruptions, and manual interruptions into a unified timeline. |
| **Session Boundary Conditions** | Opened by `STARTED`/`RESUMED`, closed by `PAUSED`/`COMPLETED` or idle timeout. | Dynamic session boundaries: 30-min idle timeout, 5-min pause threshold, task completion, and midnight day boundaries. Unrelated sessions on the same day are never arbitrarily merged. |
| **Task Association Logic** | Strictly partitioned by `task_id`. Assumes all events already belong to a task. | Strict separation between desktop activity and task assignment: supports `EXPLICIT`, `SUGGESTED` (with confidence score), `UNKNOWN` (unassigned telemetry), and `USER_CORRECTED`. |
| **Interruption Handling** | Queries manual interruptions overlapping task window and deducts duration. | Integrates both Phase 3.5 `DetectedInterruption` and manual `Interruption`, classifying interruption types and resumption delays. |
| **Resume Event Handling** | Computes gap between prior `PAUSED` and `RESUMED` events. | Tracks resumption lag for both task resumes and `user_active_returned` from idle intervals. |
| **Duplicate Event Handling** | Overwrites open events defensively. | Idempotent deduplication using unique event IDs and timestamps. |
| **Missing Event Handling** | Closes dangling sessions at `last_event + idle_timeout`. | Implied completion using configurable timeout (`min(last_event + 30m, now)`), with quality confidence deductions. |

---

## 3. Session Boundaries & Multi-Application Context

### Session Boundaries
- **Session Start**: Initiated by an explicit task start/resume or the first significant work application activation after an inactivity gap $\ge 30$ minutes.
- **Session Continuation**: Co-working transitions (e.g. IDE to Terminal), micro-glances ($< 3$s), and cognitive thinking pauses ($< 180$s).
- **Session Pause**: Marked when user idle exceeds 5 minutes or workstation locks.
- **Session Termination**: Marked when idle exceeds 30 minutes, explicit task completes, or midnight is crossed. Unrelated sessions are preserved separately.

### Multi-Application Representation
- `primary_application`: The application with the highest cumulative focused dwell time.
- `secondary_applications`: List of all other tools used during the session.
- `application_breakdown`: Key-value map (`app_name: active_seconds`).
- `transition_count`: Total number of application switches.
- `context_switch_frequency`: Normalized switches per hour of session duration.
- `focused_time_seconds`: Net productive focus time ($Duration - Idle - Interruptions$).

---

## 4. Task Association & Uncertainty

Activity is **not automatically assumed** to represent a particular task:
1. `EXPLICIT`: An active task was in progress during the session window ($Confidence \approx 0.95$).
2. `SUGGESTED`: Historical user affinity suggests a task mapping ($Confidence \approx 0.70$), with `suggested_task_id` populated.
3. `UNKNOWN`: No active task was found. The session is preserved with `task_id = None`.
4. `USER_CORRECTED`: User manually assigned or corrected task context via `POST /api/v1/context/sessions/{session_id}/correct` ($Confidence = 1.0$).

---

## 5. Session Quality & Confidence Scoring

Reconstruction quality is quantified via a 0.0–1.0 score and categorized into tiers:
- **`HIGH`** ($\ge 0.85$): Complete transitions, explicit task linkage, clean boundary closures.
- **`MEDIUM`** ($0.65 - 0.85$): Session closed by idle timeout or task association suggested with uncertainty.
- **`LOW`** ($< 0.65$): Sparse events ($< 3$ events), unknown task association, and timeout boundaries.

---

## 6. Incremental Processing Architecture

To prevent $O(N^2)$ full history re-computation:
- `reconstruct_sessions_for_user(db, user_id, lookback_hours=24, force_full_rebuild=False)`:
  - Re-evaluates only sessions and events falling within the configurable lookback window (default: 24h).
  - Finalized historical sessions outside the window remain locked and untouched.
  - Manual user corrections (`user_corrected = True`) are preserved and protected from overwrite.

---

## 7. API Endpoints

- `GET /api/v1/context/sessions`: Paginated list with filtering by `task_id`, `status`, `quality_tier`, and time ranges.
- `GET /api/v1/context/sessions/{session_id}`: Full session details including application breakdown and quality metrics.
- `GET /api/v1/context/sessions/{session_id}/timeline`: Chronological list of granular segments (`FOCUS`, `APPLICATION_SWITCH`, `IDLE`, `INTERRUPTION`, `RESUME`).
- `POST /api/v1/context/sessions/{session_id}/correct`: Allows user to re-associate task context and record correction notes.
- `POST /api/v1/context/sessions/reconstruct`: Trigger on-demand incremental or full reconstruction.

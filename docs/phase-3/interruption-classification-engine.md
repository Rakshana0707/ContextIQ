# Automated Interruption Detection and Classification Engine (Phase 3.5)

## 1. Overview

The **Automated Interruption Detection and Classification Engine** transforms raw desktop behavioral telemetry events (from `raw_telemetry_events` table and client agents) into classified, privacy-preserving behavioral interruption events.

A critical principle of ContextIQ is that **an application switch is not automatically an interruption**. Modern knowledge work requires regular transitions between tools (e.g., an IDE and a terminal, or a design tool and local documentation). The engine applies an evidence-based rule hierarchy and false-positive suppression controls before classifying any transition as an interruption.

```
+------------------------------------+
| Raw Desktop Telemetry Events       |
| (Activated, Deactivated, Idle...)  |
+-----------------+------------------+
                  |
                  v
+-----------------+------------------+
| Normalization & Preprocessing     |
| - Timestamp UTC sort               |
| - Idempotency & deduplication      |
| - Application ID normalization     |
+-----------------+------------------+
                  |
                  v
+-----------------+------------------------------------------+
| False-Positive Suppression Filters                         |
| - Micro-switches (< 3.0s dwell e.g. alt-tab glances)       |
| - Complementary co-working tool pairs (IDE <-> Terminal)   |
| - Micro-inactivity (< 180s thinking / reading time)        |
+-----------------+------------------------------------------+
                  |
                  v
+-----------------+------------------------------------------+
| Interruption Classification & Metric Extraction            |
| - APPLICATION_SWITCH (Diversion to distraction apps)       |
| - IDLE_INTERRUPTION (Inactivity >= 180s with resume)       |
| - CONTEXT_SWITCH (Attention thrashing >= 4 switches / 20s) |
| - SESSION_DISRUPTION (System lock / sleep / pause)         |
| - Resumption lag measurement & evidence explanation        |
+-----------------+------------------------------------------+
                  |
                  v
+-----------------+------------------+
| Storage & User Feedback Validation |
| - detected_interruptions           |
| - detected_interruption_feedback   |
+------------------------------------+
```

---

## 2. Classification Hierarchy

| Interruption Type | Trigger Conditions | Severity Grading | Example Explanation |
| :--- | :--- | :--- | :--- |
| `APPLICATION_SWITCH` | User transitions from sustained primary work app ($\ge 45$s) to an external distraction app ($\ge 15$s) and resumes. | `LOW` (15-60s), `MEDIUM` (1-5m), `HIGH` (5-15m), `CRITICAL` ($>15$m). | *"User transitioned from primary task (code.exe) to slack.exe for 45.2 seconds before returning to code.exe (Estimated resumption lag: 6.8s)."* |
| `IDLE_INTERRUPTION` | Sustained lack of user input/activity $\ge 180$ seconds during an active work session. | `LOW` (3-10m), `MEDIUM` (10-15m), `HIGH` (15-30m), `CRITICAL` ($>30$m). | *"An interruption was detected because the user was inactive for 12.0 minutes while working in code.exe before activity resumed."* |
| `CONTEXT_SWITCH` | Rapid attention thrashing / pinballing: $\ge 4$ switches across $\ge 2$ unique apps within 20 seconds. | `HIGH` | *"Rapid attention thrashing detected: 5 context switches across 3 applications (code.exe -> spotify.exe -> discord.exe -> code.exe -> spotify.exe) in 12.0 seconds."* |
| `SESSION_DISRUPTION` | Workstation lock, screensaver, system sleep, or agent pause. | `MEDIUM` (3-15m), `HIGH` ($>15$m). | *"Work session was disrupted by system_pause for 25.0 minutes."* |

---

## 3. False-Positive Suppression Controls

1. **Complementary Co-working Tool Pairs**:
   - `code.exe` $\leftrightarrow$ `cmd.exe`, `powershell.exe`, `windowsterminal.exe`, `wt.exe`, `git.exe`, `bash.exe`, `chrome.exe` (localhost/dev)
   - `pycharm64.exe` / `idea64.exe` $\leftrightarrow$ terminals and browsers
   - `figma.exe` $\leftrightarrow$ browsers
   These pairings are recognized as standard integrated workflows and are never classified as distractions.

2. **Micro-switch Suppression**:
   - Transitions with dwell time $< 3.0$ seconds (e.g. transient alt-tab passing, clock checks) are ignored unless they form part of a rapid context-switching cluster.

3. **Thinking & Reading Buffers**:
   - Inactivity $< 180$ seconds is considered normal reflection, reading, or note-taking rather than an idle interruption.

4. **Session Boundaries**:
   - Exits occurring when a task is completed or intentionally stopped do not trigger disruption events.

---

## 4. Database Models & Schema

### `detected_interruptions`
- `id` (UUID, PK)
- `user_id` (UUID, FK `users.id`, indexed)
- `source_event_ids` (JSONB list of UUIDs/strings)
- `interruption_type` (Enum: `APPLICATION_SWITCH`, `IDLE_INTERRUPTION`, `SESSION_DISRUPTION`, `CONTEXT_SWITCH`, `UNKNOWN_INTERRUPTION`)
- `severity` (Enum: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`)
- `start_timestamp` (DateTime UTC, indexed)
- `end_timestamp` (DateTime UTC, nullable)
- `duration_seconds` (Float, nullable)
- `confidence` (Float, 0.0 - 1.0)
- `detection_method` (String, default `"RULE_BASED_HEURISTIC"`)
- `detection_version` (String, default `"1.0.0"`)
- `explanation` (Text)
- `primary_app` (String, nullable)
- `interrupting_app` (String, nullable)
- `resumption_lag_seconds` (Float, nullable)
- `metadata_payload` (JSONB)
- `created_at` (DateTime UTC)

### `detected_interruption_feedback`
- `id` (UUID, PK)
- `interruption_id` (UUID, FK `detected_interruptions.id`, cascade delete, indexed)
- `user_id` (UUID, FK `users.id`, indexed)
- `feedback_classification` (Enum: `GENUINE_INTERRUPTION`, `INTENTIONAL_SWITCH`, `IGNORE`, `INCORRECT_DETECTION`)
- `notes` (Text, nullable)
- `created_at` (DateTime UTC)

---

## 5. API Endpoints

- `GET /api/v1/interruptions/detected`: Paginated and filtered query (`interruption_type`, `severity`, `start_time`, `end_time`, `min_confidence`).
- `GET /api/v1/interruptions/detected/{id}`: Full detail with user feedback history.
- `POST /api/v1/interruptions/detected/{id}/feedback`: User feedback submission.
- `GET /api/v1/interruptions/metrics`: Behavioral interruption breakdown, average duration, resumption lag, accuracy rate, and false-positive rate.
- `POST /api/v1/interruptions/detect`: On-demand batch execution against recent telemetry events.
- `POST /api/v1/interruptions`, `GET /api/v1/interruptions`: Backward-compatible manual interruption logging endpoints preserved without regression.

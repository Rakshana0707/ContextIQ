# Long-Term Behavioral Memory & Pattern Evolution Guide

## 1. Overview

ContextIQ's **Long-Term Behavioral Memory** system maintains an evolving, longitudinal understanding of the user's cognitive and productivity tendencies over months and years. It extends the immediate Phase 1–7 behavioral profiles into structured, durable knowledge while supporting user inspection, correction, and decay.

---

## 2. Memory Categories

Behavioral memories are structured into 10 explicit categories:
1. `BEHAVIORAL_PREFERENCES`: Individual working styles and self-reported inclinations.
2. `PRODUCTIVITY_PATTERNS`: Recurrent output rhythms and scheduling tendencies.
3. `FOCUS_PATTERNS`: Discovered optimal focus windows and deep work capacity.
4. `RECOVERY_PATTERNS`: Post-interruption recovery lag and fatigue indicators.
5. `TASK_MANAGEMENT_PREFERENCES`: Estimation accuracy, batching tendencies, and completion styles.
6. `CONTEXT_ASSOCIATIONS`: Relationships between environmental contexts (e.g., location, apps) and focus.
7. `SUCCESSFUL_INTERVENTIONS`: Nudges, schedule shifts, or break recommendations that succeeded.
8. `UNSUCCESSFUL_INTERVENTIONS`: Interventions dismissed or leading to increased behavioral friction.
9. `LONG_TERM_GOALS`: Strategic milestones and overarching personal objectives.
10. `EXPLICIT_USER_INSTRUCTIONS`: Direct, immutable operational constraints provided by the user.

---

## 3. Confidence Modeling & Temporal Decay

Inferred memories evolve over time based on supporting observations and recency:

$$\text{Confidence}(t) = \text{BaseConfidence} \cdot e^{-\lambda \cdot \Delta t} + \text{EvidenceReinforcement}$$

- $\Delta t$: Days elapsed since the last supporting observation.
- $\lambda$: Half-life decay parameter (defaults to $0.015$, corresponding to a $\approx 45$-day half-life).
- Direct user instructions and user-corrected memories do not experience temporal decay.

---

## 4. User Inspection & Correction Workflow

Users maintain full sovereign control over their behavioral profile:
1. **View Memories**: In the Behavioral Memory UI or via API, users inspect inferred memories and their underlying evidence.
2. **Correct Memory**: A user can modify the memory title, description, or mark the inference inaccurate.
3. **Audit Trail**: Every update writes an immutable entry to `MemoryAuditLog` capturing:
   - `previous_state` & `new_state`.
   - `user_correction_notes`.
   - `evolution_type` (e.g. `USER_OVERRIDE`, `PATTERN_EVOLUTION`, `DECAY_REMOVAL`).
   - Timestamp and actor ID.

---

## 5. API Endpoints

- `GET /api/v1/behavioral-memory`: List memories with category, validity status, and minimum confidence filters.
- `POST /api/v1/behavioral-memory/{id}/correct`: Submit a user correction or override.
- `GET /api/v1/behavioral-memory/{id}/history`: Retrieve complete audit log history for a memory item.
- `POST /api/v1/behavioral-memory/consolidate`: Run the background pattern consolidation engine.

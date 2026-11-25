# ContextIQ Phase 4: Frontend Integration & Explainable Personalization

## 1. Architectural Role & Objective

The frontend integration connects the complete Phase 4 Adaptive Behavioral Intelligence stack to ContextIQ's Next.js 16 user interface.

The design adheres to three core tenets:
1. **Explainable Personalization**: Every recommendation, ranking score, and focus window displays its underlying evidence, trigger conditions, and confidence level.
2. **User Sovereignty**: Users retain absolute authority to inspect their digital twin, adjust weighting presets, reset their profile, toggle personalization off, configure quiet hours, or pause notifications.
3. **Non-Speculative Grounding**: Cold-start states and insufficient telemetry are rendered honestly using data sufficiency indicators rather than fabricated trait descriptions.

---

## 2. Navigation & Layout Hierarchy

The application layout ([`sidebar.tsx`](file:///e:/Downloads%20%F0%9F%94%83/ContextIQ-main/ContextIQ-main/frontend/components/layout/sidebar.tsx)) organizes navigation into two clear sections:

### I. Core Platform
- **Dashboard** (`/`)
- **Tasks** (`/tasks`) — *Enhanced with Adaptive Task Ranking*
- **Context & Micro-Delays** (`/context`)
- **Telemetry** (`/telemetry`)
- **Predictions** (`/predictions`)
- **Recommendations** (`/recommendations`)
- **Behaviour Insights** (`/insights`)
- **ML Monitoring** (`/monitoring`)
- **Privacy** (`/privacy`)

### II. Adaptive Intelligence
- **Digital Twin Profile** (`/adaptive/profile`)
- **Focus Windows** (`/adaptive/focus`)
- **Intervention Center** (`/adaptive/interventions`)
- **Contextual Learning** (`/adaptive/learning`)
- **Causal Effectiveness** (`/adaptive/effectiveness`)
- **Notification Controls** (`/adaptive/notifications`)

---

## 3. Dedicated Adaptive Route Architecture

### 1. Personal Behavioral Profile (`/adaptive/profile`)
- **Visualizes**:
  - Focus session duration (median and standard deviation variability).
  - Uninterrupted work span.
  - Interruption frequency per hour and recovery latency distribution.
  - Task completion rates and category duration baselines.
  - Context-switching transition overhead and friction index.
  - Global Confidence Badge (`COLD_START`, `EMERGING`, `ESTABLISHED`, `CONFIDENT`).
- **Interactive Controls**:
  - `Rebuild Profile`: Triggers immediate re-aggregation from raw telemetry.
  - `Reset Profile`: Restores cold-start baseline while retaining raw telemetry.
  - `Toggle Personalization`: Opts in/out of algorithmic task ranking and bandit nudges.

### 2. Focus-Window Explorer (`/adaptive/focus`)
- **Visualizes**:
  - 24-hour Circadian Focus Timeline with quality scores ($Q \in [0, 100]$).
  - Peak morning and afternoon discovered windows with stability scores.
  - Task category recommendations (Coding, Deep Writing, Strategy).
- **Controls**: "Run Focus Window Discovery" on-demand trigger.

### 3. Personalized Intervention Center (`/adaptive/interventions`)
- **Visualizes**: Priority-ranked candidate recommendations with priority tags (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
- **Explainability**: Cards render the exact trigger condition, telemetry evidence payload, and estimated effort level (LOW: 1–2m, MEDIUM: 5–10m, HIGH: >15m).
- **Actions**: Direct interactive buttons for `Accept`, `Complete`, `Snooze`, and `Dismiss`.

### 4. Contextual Bandit Learning Dashboard (`/adaptive/learning`)
- **Visualizes**:
  - Active policy (LinUCB with Sherman-Morrison rank-1 updates or Thompson Sampling).
  - Arm pull counts, cumulative rewards, and exploitation payoff vs exploration bonus.
  - Circuit Breaker Quarantine status indicators.
- **Transparency Notice**: Explains contextual machine learning in accessible terms without clinical claims.

### 5. Causal Evaluation & Effectiveness Dashboard (`/adaptive/effectiveness`)
- **Demarcation Banner**: Methodological alert explicitly separating unadjusted observational correlation from counterfactual Doubly Robust ATE.
- **Metrics Table**:
  - Sample sizes ($N_T, N_C$).
  - Observational difference ($\Delta Y_{\text{obs}}$).
  - Doubly Robust ATE with 95% Confidence Intervals.
  - Asymptotic $p$-values and Benjamini-Hochberg critical values.
  - Habituation / fatigue alerts ($\frac{dR}{dt} < -0.05$).

### 6. Intelligent Notification Controls (`/adaptive/notifications`)
- **Controls**:
  - Category toggles (Critical Deadlines, Forgetting Alerts, Recovery, Focus, Contextual, Summaries).
  - Timezone-aware quiet hours range slider (e.g. 22:00–08:00).
  - Hourly cap (1–10/hr) and daily ceiling (5–50/day).
  - 1-Hour Pause button with live countdown.
  - Real-time Cognitive Interaction Fatigue gauge.

---

## 4. Task Manager Integration (`adaptive-task-ranking.tsx`)

Integrated directly into `/tasks` via a tabbed switcher:
- Allows toggling between **Adaptive Priority & Schedule** and the **Standard Task List**.
- Provides preset selection (`Balanced`, `Deep Work`, `Deadline Crunch`, `Recovery Mode`).
- Renders composite priority score (0–100) alongside individual component bars (Urgency, Forgetting Risk, Focus Fit, Context Match, Scheduling Feasibility).
- Features quick actions: `Start Now`, `Snooze`, `Pin`.

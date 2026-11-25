# ContextIQ Phase 4: Adaptive Task Prioritization & Personalized Scheduling

## 1. Architectural Role & Objective

The **Adaptive Task Prioritization Engine** (`PrioritizationEngine`) produces an explainable, multi-objective ranking of pending tasks.

Unlike traditional static priority schemes (High/Medium/Low), ContextIQ computes a dynamic composite score $S(t) \in [0, 100]$ that balances:
1. Impending deadline urgency.
2. Predictive forgetting-risk probabilities from the CatBoost model.
3. Time-varying survival analysis hazard rates.
4. Alignment with the user's active focus windows.
5. Contextual switching friction and application compatibility.
6. Execution feasibility and recovery overhead buffers.

---

## 2. Multi-Objective Scoring Formulation

The composite priority score for task $t$ at reference time $\tau$ is:

$$S(t, \tau) = 100 \cdot \Big[ w_U \cdot U(t, \tau) + w_F \cdot F(t) + w_P \cdot P(t, \tau) + w_C \cdot C(t, \text{ctx}) + w_S \cdot \Phi(t, \tau) \Big]$$

Where:

### 1. Deadline Urgency $U(t, \tau) \in [0, 1]$
- Calculated from remaining time $\Delta T = T_{\text{due}} - \tau$:
  $$U(t, \tau) = \begin{cases}
  1.0 & \text{if overdue or } \Delta T \le 2\text{ hours} \\
  \exp\left(-\frac{\Delta T}{24.0}\right) & \text{if } 2 < \Delta T \le 168\text{ hours (7 days)} \\
  0.10 \cdot \text{PriorityWeight} & \text{if no due date}
  \end{cases}$$

### 2. Forgetting Risk $F(t) \in [0, 1]$
- Combines predicted forgetting probability $\hat{p}_{\text{forget}}$ and Cox hazard rate $\lambda(t)$:
  $$F(t) = 0.70 \cdot \hat{p}_{\text{forget}} + 0.30 \cdot \min(1.0, \lambda(t))$$

### 3. Personal Focus Suitability $P(t, \tau) \in [0, 1]$
- If the current hour $\tau$ matches an active focus window ($Q \ge 58.0$):
  - High-concentration tasks receive $P(t, \tau) = 0.85 + 0.15 \cdot \frac{Q}{100}$.
  - Short chores receive $P(t, \tau) = 0.35$ (preventing degradation of prime focus windows).
- If $\tau$ is inside a fragmented / high-interruption period:
  - Short administrative chores receive $P(t, \tau) = 0.90$.
  - Deep-work tasks receive $P(t, \tau) = 0.25$.

### 4. Context Compatibility $C(t, \text{ctx}) \in [0, 1]$
- Measures transition friction between the active foreground application and the task's required tools:
  $$C(t, \text{ctx}) = 1.0 - \text{SwitchCostPenalty}$$

### 5. Scheduling Feasibility $\Phi(t, \tau) \in [0, 1]$
- Evaluates whether estimated duration + recovery buffer fits within the remaining window:
  $$\Phi(t, \tau) = \max\left(0.1, 1.0 - \frac{|\text{EstimatedMins} + \text{Buffer} - \text{WindowRemaining}|}{\text{EstimatedMins}}\right)$$

---

## 3. Presets & Dynamic Weight Profiles

Users can select ranking presets depending on their immediate operational mode:

| Preset | Urgency ($w_U$) | Forgetting ($w_F$) | Focus Fit ($w_P$) | Context ($w_C$) | Feasibility ($w_S$) | Target Use Case |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `BALANCED` | 0.30 | 0.25 | 0.20 | 0.15 | 0.10 | Standard daily operations |
| `DEADLINE_CRUNCH` | 0.60 | 0.10 | 0.10 | 0.10 | 0.10 | Imminent delivery pressure |
| `DEEP_WORK` | 0.15 | 0.15 | 0.45 | 0.15 | 0.10 | High-quality focus protection |
| `RECOVERY_MODE` | 0.10 | 0.15 | 0.15 | 0.30 | 0.30 | Clearing small tasks post-fatigue |

---

## 4. Primary Driver Badges & Grounded Explanations

Each ranked task card renders a deterministic reason badge:
- `CRITICAL_DEADLINE`: Deadline within 4 hours.
- `FOCUS_WINDOW_MATCH`: Aligns with verified circadian peak.
- `FORGETTING_RISK_SHIELD`: Model predicts $\hat{p}_{\text{forget}} > 0.65$.
- `QUICK_WIN_ADMIN`: Low-effort task scheduled during fragmented hours.
- `CONTEXT_MATCH`: Application currently open on desktop.

User actions (`Start Now`, `Snooze`, `Pin`, `Dismiss`) are fed directly into `task_ranking_feedback` to adapt future weight distributions.

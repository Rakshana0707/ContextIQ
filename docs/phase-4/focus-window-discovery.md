# ContextIQ Phase 4: Personalized Focus-Window Discovery

## 1. Objective & Non-Prescriptive Philosophy

Conventional productivity tools impose static, prescriptive schedules (e.g. 9:00 AM to 5:00 PM or rigid 25-minute Pomodoro timers). In contrast, ContextIQ's **Focus-Window Discovery Engine** discovers when an individual actually achieves sustained focus, lower distraction rates, and higher task throughput.

The engine:
- Evaluates 24-hour circadian cycles using historical context sessions and completion timestamps.
- Computes an empirical **Focus Window Quality Score ($Q$)**.
- Groups contiguous high-quality intervals into candidate focus windows.
- Maps specific task categories (e.g. deep writing, code refactoring, admin chores) to optimal personal temporal windows.

---

## 2. Mathematical Formulation of Window Quality ($Q$)

For any candidate temporal bucket $b \in [0, 23]$:

$$Q(b) = 100 \cdot \Big[ w_C \cdot C(b) + w_F \cdot F(b) + w_I \cdot (1 - \tilde{I}(b)) + w_R \cdot (1 - \tilde{R}(b)) + w_S \cdot S(b) \Big]$$

Where:
- $C(b) \in [0, 1]$: **Task Completion Rate** during hour $b$.
- $F(b) \in [0, 1]$: **Focus Session Duration Factor** ($\min(1.0, \bar{D}_b / 60)$).
- $\tilde{I}(b) \in [0, 1]$: **Normalized Interruption Density** ($\min(1.0, \text{Rate}_b / 4.0)$).
- $\tilde{R}(b) \in [0, 1]$: **Normalized Recovery Delay** ($\min(1.0, \text{Lag}_b / 300.0)$).
- $S(b) \in [0, 1]$: **Historical Consistency / Stability** across observed weeks.
- Weights: $w_C = 0.30$, $w_F = 0.25$, $w_I = 0.20$, $w_R = 0.15$, $w_S = 0.10$.

### Thresholding & Boundary Clustering
An interval is classified as a valid Focus Window if:
$$Q(b) \ge Q_{\text{threshold}} \quad (Q_{\text{threshold}} = 58.0)$$
Contiguous hours exceeding $Q_{\text{threshold}}$ are merged into unified windows (e.g. 09:00–11:30 or 15:00–17:00). Windows with duration $< 45$ minutes are filtered unless tagged for quick administrative batching.

---

## 3. Category-Conditioned Focus Windows

Not all productive hours support the same cognitive load. ContextIQ conditions window discovery on task categories:

1. **High-Concentration / Deep Work (Coding, Architecture, Writing)**:
   - Requires $Q \ge 70.0$, low interruption rate ($I < 1.0/\text{hr}$), and duration $\ge 90$ minutes.
2. **Collaborative / Intermittent Tasks**:
   - Tolerates moderate interruptions ($I \le 3.0/\text{hr}$) with medium session stability.
3. **Low-Cognitive Administrative / Chores**:
   - Best scheduled in fragmented hours ($I \ge 3.0/\text{hr}$ or $Q < 50.0$) where brief 10–15 minute tasks can be cleared without wasting high-focus cognitive bandwidth.

---

## 4. Verification & Reproducibility Results

From automated integration testing:
- Bimodal circadian distributions (morning peak 09:00–11:30 and afternoon peak 15:00–17:00) were successfully recovered from synthetic and historical telemetry.
- Cold-start users receive transparent placeholder recommendations flagged with `INSUFFICIENT_EVIDENCE` rather than speculative productivity assertions.

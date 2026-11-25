# ContextIQ Phase 4: Bandit Reward Design & Attribution

## 1. Multi-Objective Reward Objective

The reward function $r \in [-1.0, 1.0]$ provides the primary learning feedback to the contextual bandit engine.

A naive reward based solely on clicks or immediate acceptance would incentivize clickbait or nagging alerts. ContextIQ employs a **dual-loop reward design**:
1. **Loop 1: Immediate Interaction Feedback** (Fast, explicit, observed within seconds/minutes).
2. **Loop 2: Downstream Behavioral Lift** (Delayed, implicit, observed over a 120-minute attribution window).

---

## 2. Formal Reward Function

The total reward $r$ attributed to intervention $a$ delivered at time $t_0$ is:

$$r = w_{\text{interact}} \cdot r_{\text{interact}} + w_{\text{task}} \cdot r_{\text{task}} + w_{\text{friction}} \cdot r_{\text{friction}} + w_{\text{rec}} \cdot r_{\text{rec}} - r_{\text{penalty}}$$

Where:

### 1. Interaction Reward $r_{\text{interact}} \in \{-1.0, 0.0, 0.5, 1.0\}$
- `ACCEPTED`: $+0.50$
- `COMPLETED`: $+1.00$
- `DEFERRED`: $0.00$ (neutral delay)
- `DISMISSED`: $-0.50$
- `IGNORED / EXPIRED`: $-0.20$

### 2. Downstream Task Completion Reward $r_{\text{task}} \in [0.0, 1.0]$
Evaluated over observation window $W = 120\text{ minutes}$:
- If the associated task was completed before its deadline: $+1.00$.
- If completed within $W$ but after initial deadline: $+0.50$.
- If uncompleted: $0.00$.

### 3. Friction Reduction Reward $r_{\text{friction}} \in [-0.5, 0.5]$
Measures delta in Behavioral Friction Index (BFI) relative to the user's pre-intervention baseline:
$$r_{\text{friction}} = \min\left(0.5, \max\left(-0.5, \frac{\text{BFI}_{\text{pre}} - \text{BFI}_{\text{post}}}{40.0}\right)\right)$$

### 4. Recovery Speedup Reward $r_{\text{rec}} \in [-0.3, 0.3]$
For recovery interventions (`SUGGEST_RECOVERY_BUFFER`, `RESUME_PREVIOUS_TASK`):
$$r_{\text{rec}} = \min\left(0.3, \max\left(-0.3, \frac{\text{Lag}_{\text{median}} - \text{Lag}_{\text{observed}}}{120.0}\right)\right)$$

### 5. Annoyance & Negative Feedback Penalties $r_{\text{penalty}}$
- User selected "Not relevant": $-0.30$.
- User selected "Interrupted my focus": $-0.60$.
- User reported "Repeated too often": $-0.50$ (and triggers 24h quarantine).

---

## 3. Delayed Attribution Windows & Outcome Settlement

Because downstream task completion and cognitive recovery take time to manifest, rewards are processed asynchronously via `RewardAttributionEngine`:

```
Delivered (t=0) ────► Immediate Feedback Recorded (t < 5m)
                           │
                           ▼
                      Observation Window Active (t in [0, 120m])
                           │
                           ▼
                      Telemetry Ingest & Task Settlement (t = 120m)
                           │
                           ▼
                      Bandit Arm Update: A_inv & b
```

If the user logs off or the observation window elapses without task activity, the reward settles using available explicit feedback with a conservative missing-outcome assumption.

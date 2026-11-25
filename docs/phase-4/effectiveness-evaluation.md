# Intervention Effectiveness Evaluation Engine Design

## 1. Overview & Purpose

The **Intervention Evaluation Engine** measures whether delivered interventions actually improve behavioral outcomes for each user.

A common pitfall in algorithmic recommendation systems is relying purely on click-through or acceptance metrics. A user might accept a break suggestion out of habit but immediately return to frantic context-switching, or dismiss a task nudge but complete the task 10 minutes later. 

ContextIQ implements a **Dual-Loop Effectiveness Evaluation** architecture:
1. **Loop 1: Immediate Explicit Feedback** (Accept, Dismiss, Snooze, Response Latency, Qualitative Thumbs).
2. **Loop 2: Downstream Behavioral Impact** (Reduction in micro-delay resumption lag, subsequent task completion, stabilization of Behavioral Friction Index).

This composite reward directly drives the online updates of the **Contextual Bandit Engine** and the continuous recalibration of the **Behavioral Profile Engine**.

```mermaid
graph TB
    subgraph Intervention_Delivery [Intervention Delivery Event]
        INT[Intervention Delivered: Arm a* at Time t_0]
    end

    subgraph Loop_1 [Loop 1: Immediate Explicit Response (0 - 5 min)]
        ACT{User Action}
        ACT -->|Accepted| R_ACC["R_explicit = +1.0"]
        ACT -->|Snoozed| R_SNO["R_explicit = +0.2"]
        ACT -->|Dismissed| R_DIS["R_explicit = -0.5"]
        ACT -->|Explicit Negative| R_NEG["R_explicit = -1.0"]
        ACT -->|Ignored / Expired| R_IGN["R_explicit = -0.2"]
    end

    subgraph Loop_2 [Loop 2: Downstream Behavioral Tracking (15 min - 2 hr)]
        TEL[Stream Subsequent Desktop Telemetry]
        TEL --> LAG[Resumption Lag Delta: ΔLag = Lag_before - Lag_after]
        TEL --> COMP[Target Task Completed: Flag in {0, 1}]
        TEL --> BFI[Behavioral Friction Index Delta: ΔBFI]
        LAG --> R_BEH[Compute Composite Behavioral Reward R_beh]
        COMP --> R_BEH
        BFI --> R_BEH
    end

    subgraph Synthesis [Reward Synthesis & Learning]
        R_ACC --> TOTAL["Total Composite Reward:<br/>R = w_1 R_explicit + w_2 R_beh in [-1.0, +1.0]"]
        R_SNO --> TOTAL
        R_DIS --> TOTAL
        R_NEG --> TOTAL
        R_IGN --> TOTAL
        R_BEH --> TOTAL
        TOTAL --> BANDIT_UPDATE[Bandit State Matrix Update]
        TOTAL --> RECEPTIVITY[Update User Profile Arm Receptivity]
    end

    INT --> Loop_1
    INT --> Loop_2
```

---

## 2. Mathematical Dual-Loop Reward Formulation

### 2.1 Loop 1: Explicit Interaction Reward ($R_{\text{explicit}} \in [-1.0, +1.0]$)
Captures immediate user receptivity and engagement:

$$R_{\text{explicit}} = \begin{cases}
+1.0 & \text{if Action == ACCEPTED (and task initiated)} \\
+0.6 & \text{if Action == ACCEPTED (added to queue)} \\
+0.2 & \text{if Action == SNOOZED} \\
-0.2 & \text{if Action == EXPIRED (unanswered after 30 min)} \\
-0.5 & \text{if Action == DISMISSED} \\
-1.0 & \text{if Action == EXPLICIT_NEGATIVE ("Don't show this again")}
\end{cases}$$

Additionally, if the user accepted with rapid reaction time ($t_{\text{response}} < 5\text{ seconds}$), an engagement bonus $+0.1$ is applied.

### 2.2 Loop 2: Downstream Behavioral Reward ($R_{\text{behavioral}} \in [-1.0, +1.0]$)
Evaluates measurable cognitive improvement over the 30-minute evaluation window post-intervention:

$$R_{\text{behavioral}} = \beta_1 \cdot \Delta_{\text{Lag}} + \beta_2 \cdot \Delta_{\text{BFI}} + \beta_3 \cdot \mathbb{I}(\text{TaskCompleted}) - \beta_4 \cdot \text{DisruptionChurn}$$

Where $\sum \beta_i = 1.0$ (default configuration: $\beta_1 = 0.35, \beta_2 = 0.30, \beta_3 = 0.25, \beta_4 = 0.10$):
- $\Delta_{\text{Lag}} = \frac{\text{BaselineLag} - \text{ObservedLag}_{30m}}{\max(\text{BaselineLag}, 30)} \in [-1, 1]$ (measures cognitive recovery speedup).
- $\Delta_{\text{BFI}} = \frac{BFI_{t_0} - BFI_{t_0 + 30m}}{100} \in [-1, 1]$ (measures friction reduction).
- $\mathbb{I}(\text{TaskCompleted}) \in \{0, 1\}$ (equals 1 if the target task or associated task was marked completed within 2 hours).
- $\text{DisruptionChurn} = \min(1.0, \text{InterruptionCount}_{30m} / 5)$ (penalizes interventions that fail to stop disruption cascades).

### 2.3 Composite Multi-Horizon Reward ($R_t$)
The total reward synthesized for bandit optimization is:

$$R_t = w_{\text{exp}} \cdot R_{\text{explicit}} + w_{\text{beh}} \cdot R_{\text{behavioral}}$$

Where default weights are $w_{\text{exp}} = 0.40$ and $w_{\text{beh}} = 0.60$. This formulation ensures that even if an intervention is dismissed ($R_{\text{explicit}} = -0.5$), if the user subsequently calmed their context-switching and completed their core work ($R_{\text{behavioral}} = +0.8$), the net reward remains mildly positive ($R_t = +0.28$), recognizing behavioral efficacy over superficial click friction.

---

## 3. Evaluation Horizons & Tracking Pipeline

Because cognitive effects unfold over time, outcomes are evaluated in three distinct temporal stages:

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              EVALUATION HORIZONS                                        │
├──────────────────┬──────────────────────┬───────────────────────────────────────────────┤
│ Horizon          │ Duration Window      │ Metrics Collected                             │
├──────────────────┼──────────────────────┼───────────────────────────────────────────────┤
│ 1. Immediate     │ 0 to 5 minutes       │ User click (Accept / Dismiss / Snooze),       │
│                  │                      │ reaction latency, initial window switch.      │
├──────────────────┼──────────────────────┼───────────────────────────────────────────────┤
│ 2. Short-Term    │ 5 to 30 minutes      │ Resumption lag, app transitions, BFI delta,   │
│                  │                      │ break duration adherence.                     │
├──────────────────┼──────────────────────┼───────────────────────────────────────────────┤
│ 3. Medium-Term   │ 30 min to 2 hours    │ Task completion status, context stability,    │
│                  │                      │ sustained focus span without disruption.      │
└──────────────────┴──────────────────────┴───────────────────────────────────────────────┘
```

---

## 4. Database Schema: `intervention_outcomes`

```python
"""Database model for tracking dual-loop intervention outcomes."""
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import UUIDPKMixin, utcnow


class InterventionOutcome(Base, UUIDPKMixin):
    """
    Measurable dual-loop outcome of a delivered intervention.
    Connects explicit user feedback and subsequent behavioral telemetry
    into a ground-truth reward for bandit updates.
    """

    __tablename__ = "intervention_outcomes"
    __table_args__ = (
        Index("ix_intervention_outcomes_user_created", "user_id", "created_at"),
        Index("ix_intervention_outcomes_intervention", "intervention_id", unique=True),
        Index("ix_intervention_outcomes_arm", "bandit_arm_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    intervention_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interventions.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    bandit_arm_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Loop 1: Explicit Outcomes
    explicit_action: Mapped[str] = mapped_column(String(32), nullable=False)  # ACCEPTED, DISMISSED, SNOOZED, EXPIRED, NEGATIVE
    response_latency_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    feedback_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    explicit_reward_score: Mapped[float] = mapped_column(Float, nullable=False)  # -1.0 to +1.0

    # Loop 2: Downstream Behavioral Outcomes
    evaluation_window_minutes: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=30)
    baseline_bfi_at_delivery: Mapped[float] = mapped_column(Float, nullable=False)
    observed_bfi_post_window: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bfi_delta: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    baseline_resumption_lag_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    observed_resumption_lag_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    resumption_lag_delta_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    target_task_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    task_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    behavioral_reward_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # -1.0 to +1.0

    # Composite Bandit Payoff
    composite_reward: Mapped[float] = mapped_column(Float, nullable=False)  # -1.0 to +1.0
    bandit_updated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    evaluation_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship("User")
    intervention = relationship("Intervention")
```

---

## 5. Counterfactual & Off-Policy Evaluation

To guard against algorithmic degeneration and ensure new policies outperform baselines before deployment, the engine supports **Off-Policy Evaluation (OPE)** using **Doubly Robust (DR)** estimation over logged intervention histories:

$$\hat{V}_{\text{DR}}(\pi_{\text{new}}) = \frac{1}{N} \sum_{i=1}^N \left( \hat{Q}(x_i, \pi_{\text{new}}(x_i)) + \frac{\mathbb{I}(a_i = \pi_{\text{new}}(x_i))}{p(a_i \mid x_i)} \left( r_i - \hat{Q}(x_i, a_i) \right) \right)$$

Where $p(a_i \mid x_i)$ is the logging policy probability, and $\hat{Q}$ is a baseline outcome regression model.

### 5.1 Habituation & Intervention Fatigue Detection
If an arm exhibits a statistically significant downward slope in acceptance rate ($\frac{d R}{d t} < -0.05$ over 14 days), the engine flags **Intervention Fatigue**, automatically suppressing that specific framing for 7 days to allow user habituation to decay.

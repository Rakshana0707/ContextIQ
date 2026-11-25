# ContextIQ Phase 4: Contextual Bandit Learning for Personalized Interventions

## 1. Problem Formulation & Objective

The **Contextual Bandit Engine** learns which eligible intervention arm $a \in \mathcal{A}$ produces the highest expected reward given the user's current behavioral state vector $\mathbf{x} \in \mathbb{R}^d$.

Unlike standard multi-armed bandits, contextual bandits personalize selections according to the immediate context $\mathbf{x}$. Unlike full reinforcement learning, contextual bandits optimize one-step decisions without needing unstable long-horizon value iteration.

### Definitions
- **Context ($\mathbf{x}$)**: $d=12$ dimensional feature vector describing the current behavioral state.
- **Action ($a$)**: An eligible intervention arm selected from the intervention catalog or `NO_ACTION`.
- **Reward ($r$)**: Scalar payoff $r \in [-1.0, 1.0]$ derived from user response and downstream task completion.

---

## 2. 12-Dimensional Behavioral Context State Vector ($\mathbf{x}$)

Every decision query constructs $\mathbf{x} = [x_1, \dots, x_{12}]^T$ strictly from information available at decision time:

1. $x_1$: Normalized hour of day ($\tau / 24.0$).
2. $x_2$: Weekend indicator ($1.0$ if Saturday/Sunday else $0.0$).
3. $x_3$: Active focus window suitability score ($Q / 100.0$).
4. $x_4$: Baseline Behavioral Friction Index (BFI / 100.0).
5. $x_5$: Recent interruption rate (hourly rate / 4.0).
6. $x_6$: Median resumption lag ($\min(1.0, \text{lag} / 300.0)$).
7. $x_7$: Session fragmentation ratio (switches per active hour).
8. $x_8$: Mean pending task urgency score $U \in [0, 1]$.
9. $x_9$: Mean forgetting risk prediction $\hat{p}_{\text{forget}} \in [0, 1]$.
10. $x_{10}$: Rolling 7-day acceptance rate for candidate arm.
11. $x_{11}$: Cumulative deliveries in last 24 hours (volume saturation).
12. $x_{12}$: Cognitive interaction fatigue score $F \in [0, 1]$.

---

## 3. Disjoint LinUCB Policy Formulation

For each arm $a$, ContextIQ maintains a ridge regression model parameterized by:
- Inverse covariance matrix $\mathbf{A}_a^{-1} \in \mathbb{R}^{d \times d}$ (initialized to $\mathbf{I}_d$).
- Payoff accumulator vector $\mathbf{b}_a \in \mathbb{R}^d$ (initialized to $\mathbf{0}$).
- Parameter estimate $\hat{\boldsymbol{\theta}}_a = \mathbf{A}_a^{-1} \mathbf{b}_a$.

### Action Selection
For all eligible arms $a \in \mathcal{A}_{\text{eligible}}$:
$$p_t(a) = \mathbf{x}^T \hat{\boldsymbol{\theta}}_a + \alpha \sqrt{\mathbf{x}^T \mathbf{A}_a^{-1} \mathbf{x}}$$
$$a^* = \arg\max_{a \in \mathcal{A}_{\text{eligible}}} p_t(a)$$

Where $\alpha > 0$ controls exploration. In ContextIQ, $\alpha = 0.85$ under `ESTABLISHED` confidence and decays to $0.40$ as sample count increases.

### Sherman-Morrison Online Update
Upon observing reward $r$ for chosen arm $a^*$ and context $\mathbf{x}$, the inverse covariance matrix is updated in $O(d^2)$ time:
$$\mathbf{v} = \mathbf{A}_{a^*}^{-1} \mathbf{x}$$
$$\mathbf{A}_{a^*}^{-1} \leftarrow \mathbf{A}_{a^*}^{-1} - \frac{\mathbf{v} \mathbf{v}^T}{1 + \mathbf{x}^T \mathbf{v}}$$
$$\mathbf{b}_{a^*} \leftarrow \mathbf{b}_{a^*} + r \cdot \mathbf{x}$$
$$\hat{\boldsymbol{\theta}}_{a^*} \leftarrow \mathbf{A}_{a^*}^{-1} \mathbf{b}_{a^*}$$

---

## 4. Linear Thompson Sampling (Bayesian Alternative)

For users with `CONFIDENT` profile tiers, Bayesian sampling provides smooth posterior exploration:
$$\tilde{\boldsymbol{\theta}}_a \sim \mathcal{N}\left(\hat{\boldsymbol{\theta}}_a, v^2 \mathbf{A}_a^{-1}\right)$$
$$a^* = \arg\max_{a \in \mathcal{A}_{\text{eligible}}} \mathbf{x}^T \tilde{\boldsymbol{\theta}}_a$$
Where $v = 0.5$ scales posterior sampling variance.

---

## 5. Safety Guardrails & Circuit Breakers

1. **NO_ACTION Guarantee**: `NO_ACTION` is always eligible and carries a baseline zero cost. If all candidate interventions have negative expected payoffs, the engine stays silent.
2. **Rate Limiting**: Minimum 45-minute cooldown between non-critical interventions.
3. **Quarantine Circuit Breaker (`BanditCircuitBreaker`)**:
   - If any arm incurs **3 consecutive negative rewards** ($r \le -0.5$) or its 7-day dismissal rate exceeds 75%, it is quarantined for 24 hours.
   - During quarantine, the arm is excluded from LinUCB selection, protecting the user from toxic or annoying nudges.

---

## 6. Offline Evaluation Framework (IPS & Replay)

To evaluate new policies without risking user disruption, ContextIQ implements Inverse Propensity Scoring (IPS):
$$\hat{R}_{\text{IPS}}(\pi) = \frac{1}{N} \sum_{i=1}^N \frac{\mathbb{I}(\pi(\mathbf{x}_i) = a_i)}{p_i} \cdot r_i$$
Where $p_i$ is the logged propensity with clipping $w_i = \min(20.0, 1/p_i)$ to prevent high-variance instability.

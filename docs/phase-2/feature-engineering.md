# Temporal Feature Engineering & Behavioral Feature Dictionary

## 1. Feature Engineering Principles

The ContextIQ feature pipeline extracts 29 numerical and one-hot categorical behavioral features strictly parameterized by an as-of query timestamp $t_{\text{as\_of}}$. All calculations enforce three non-negotiable guarantees:
1. **Zero Future Contamination**: Events with timestamp $t_e > t_{\text{as\_of}}$ are dropped prior to feature aggregation.
2. **Missingness Preservation**: Missing values are not filled with unconditional zeros; missingness indicators are tracked and imputed using group priors or neutral Bayesian medians.
3. **Temporal Lineage**: Every feature record carries a `FeatureSnapshot` metadata header with cutoff timestamps.

---

## 2. Comprehensive 29-Feature Dictionary

### Group A: Baseline Task Attributes & Demographics

| Feature Name | Type | Mathematical Formula / Definition | Source Fields | As-Of Behavior | Missing Value Treatment |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `task_category` | Categorical | Categorical domain: `Work`, `Personal`, `Health`, `Finance`, `Other` | `tasks.category` | Point-in-time creation | Mode: `Other` |
| `priority` | Categorical | Domain: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` | `tasks.priority` | Point-in-time creation | Default: `MEDIUM` |
| `location` | Categorical | Domain: `Home`, `Office`, `Transit`, `Other` | `tasks.location` | Point-in-time creation | Default: `Other` |
| `weekday` | Int (0-6) | $\text{DayOfWeek}(t_{\text{as\_of}})$ | System clock | Computed at $t_{\text{as\_of}}$ | Deterministic |
| `hour` | Int (0-23) | $\text{HourOfDay}(t_{\text{as\_of}})$ | System clock | Computed at $t_{\text{as\_of}}$ | Deterministic |
| `deadline_distance_hours` | Float | $\max\left(0.0, \, \frac{t_{\text{dead}} - t_{\text{as\_of}}}{3600}\right)$ | `tasks.deadline_at` | Computed at $t_{\text{as\_of}}$ | Median: 24.0h |
| `task_frequency` | Float | $\frac{\text{Count of user tasks in category in 30d}}{30}$ | `tasks.created_at` | Events $\le t_{\text{as\_of}}$ | Bayesian Prior: 0.20 |
| `tasks_today` | Int | $\sum \mathbb{I}(t_{\text{create}} \ge \text{Midnight}(t_{\text{as\_of}}) \land t_{\text{create}} \le t_{\text{as\_of}})$ | `tasks.created_at` | Window $\le t_{\text{as\_of}}$ | 0 |

---

### Group B: Historical Task Completion & Execution Dynamics

| Feature Name | Type | Mathematical Formula / Definition | Source Fields | As-Of Behavior | Missing Value Treatment |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `previous_completion_count` | Int | $\sum_{j \in \text{Tasks}(u)} \mathbb{I}(t_{\text{comp}}^{(j)} \le t_{\text{as\_of}})$ | Task ledger | Strict cutoff | 0 |
| `previous_forgetting_count` | Int | $\sum_{j \in \text{Tasks}(u)} \mathbb{I}(\text{Outcome}(j) = \text{Lapse} \land t_{\text{eval}}^{(j)} \le t_{\text{as\_of}})$ | Label ledger | Strict cutoff | 0 |
| `historical_completion_rate`| Float | $\frac{N_{\text{comp}} + \alpha_{\text{prior}}}{N_{\text{total}} + \alpha_{\text{prior}} + \beta_{\text{prior}}}$ | Task ledger | Empirical Bayes | Prior: 0.80 |
| `historical_forgetting_rate`| Float | $1.0 - \text{historical\_completion\_rate}$ | Task ledger | Empirical Bayes | Prior: 0.20 |
| `historical_postponements` | Int | Total postponement requests across prior tasks | Event stream | Events $\le t_{\text{as\_of}}$ | 0 |
| `avg_completion_duration_minutes` | Float | $\frac{1}{N}\sum (t_{\text{comp}} - t_{\text{create}})$ (in minutes) | Completed tasks | Historical window | Population median: 35.0m |
| `task_inactivity_duration_hours` | Float | $\frac{t_{\text{as\_of}} - \max(t_{\text{last\_activity}})}{3600}$ | Event stream | Strict cutoff | 0.0 |
| `deadline_extensions_count` | Int | Number of extensions applied specifically to target task | Target task ledger | Strict cutoff | 0 |

---

### Group C: Interruption Behavior & Cognitive Load

| Feature Name | Type | Mathematical Formula / Definition | Source Fields | As-Of Behavior | Missing Value Treatment |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `interruptions_today` | Int | Total interruptions recorded since midnight | `events.interruptions` | Events $\le t_{\text{as\_of}}$ | 0 |
| `recent_context_switches`| Int | App / window switches in trailing 60 minutes | `events.app_switch` | Trailing 60m window | 0 |
| `avg_interruption_duration`| Float | Mean duration of interruptions today (minutes) | `events.interruptions` | Midnight to $t_{\text{as\_of}}$ | Population median: 3.5m |
| `avg_session_duration` | Float | Mean active work session duration (minutes) | `data_engine.sessions` | Midnight to $t_{\text{as\_of}}$ | Population median: 25.0m |
| `interruption_latency_mean`| Float | Average time from notification to interruption | `events.notifications` | Trailing 24h window | Population median: 2.0m |
| `interruption_frequency_1h`| Int | Interruption count in trailing 60 minutes | `events.interruptions` | Trailing 60m window | 0 |
| `context_switch_burstiness`| Float | Normalized Fano factor: $B = \frac{\sigma_{\Delta t} - \mu_{\Delta t}}{\sigma_{\Delta t} + \mu_{\Delta t}}$ | Inter-switch intervals | Trailing 4h window | 0.0 (regular) |
| `post_interruption_delay_mean` | Float | Mean delay before resuming task after interruption | Context switch log | Trailing 24h window | Population median: 3.0m |

---

### Group D: Fatigue, Fragmentation & Circadian Rhythms

| Feature Name | Type | Mathematical Formula / Definition | Source Fields | As-Of Behavior | Missing Value Treatment |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `cumulative_fatigue_index` | Float | $\text{CFI} = \sum_{k} w_k \cdot \text{duration}_k \cdot e^{-\lambda(t_{\text{as\_of}} - t_k)}$ | Session stream | Trailing 12h window | 0.10 (low fatigue) |
| `daily_schedule_fragmentation` | Float | Entropy of active vs idle intervals across day: $H = -\sum p_i \log_2 p_i$ | Schedule timeline | Trailing 24h window | Population mean: 0.35 |
| `circadian_rhythm_peak_distance` | Float | $| \text{Hour}(t_{\text{as\_of}}) - \text{PeakHour}(u) | \pmod{24}$ | Historical profile | Population peak: 10:00 AM |
| `days_since_prior_forgetting` | Float | $\frac{t_{\text{as\_of}} - \max(t_{\text{prior\_lapse}})}{86400}$ | Outcome ledger | Strict cutoff | Cap: 30.0 days |
| `urgency_decay_rate` | Float | Exponential decay: $e^{-\kappa \cdot \Delta t_{\text{deadline}}}$ | Task attributes | Point-in-time | Neutral: 0.10 |
| `context_similarity_prior_lapse` | Float | Cosine similarity between current context vector and context vector at last recorded forgetting event | Context state | Point-in-time vs historic | Prior: 0.05 |

---

## 3. Mathematical Details of Key Engineered Features

### 3.1 Context Switch Burstiness ($B$)
Burstiness captures whether context switches occur in rapid-fire bursts (high cognitive overload) or steady intervals:
$$B = \frac{\sigma_{\tau} - \mu_{\tau}}{\sigma_{\tau} + \mu_{\tau}} \in [-1, 1]$$
Where $\tau$ denotes the inter-arrival intervals between successive context switches. $B \to 1$ indicates highly bursty interruptions, strongly correlating with prospective intention decay.

### 3.2 Cumulative Fatigue Index ($\text{CFI}$)
Fatigue is modeled as an accumulating decaying exponential:
$$\text{CFI}(t) = \min\left(1.0, \, \sum_{k=1}^{M} \frac{D_k}{60} \cdot \exp\left(-\frac{t - t_k}{\tau_{\text{recovery}}}\right)\right)$$
Where $D_k$ is the duration of focus session or meeting $k$ in minutes, and $\tau_{\text{recovery}} = 4.0\text{ hours}$.

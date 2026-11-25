# ContextIQ Governed Automation & Proactive Intelligence
## User Guide and Operational Handbook

Welcome to ContextIQ Governed Automation. This guide explains how ContextIQ acts as an intelligent executive assistant for your working memory, how to configure rules, review proactive proposals, manage approvals, and exercise full emergency control.

---

## 1. Core Principles of Governed Automation

ContextIQ is built on the principle of **governed autonomy**:
- **You are always in control**: ContextIQ never takes high-impact actions on your behalf without explicit approval or policy pre-authorization.
- **Explainable reasoning**: Every suggestion comes with an explanation ("Why it matters"), empirical evidence, and conformal confidence bounds (e.g., `Conformal [75%-92%]`).
- **Reversibility**: Reversible actions can be rolled back with a single click.
- **Zero Surveillance**: ContextIQ never captures keystrokes, screenshots, or document contents. Only app transitions and session metadata are processed.

---

## 2. Managing Your Proactive Intelligence Feed

When ContextIQ detects meaningful behavioral patterns, it publishes actionable insight cards to your **Proactive Feed**:

### Types of Insights
1. **Forgetting-Risk Spikes**: Triggered when an unfinished task has been inactive beyond your retention threshold and statistical lapse probability exceeds 70%.
2. **Context Thrashing**: Detected when you switch between applications 6+ times in a minute, indicating fragmentation of attention.
3. **Calendar Saturation**: Triggered when back-to-back meetings lack sufficient transition buffers.
4. **Prolonged Recovery Lag**: Detected when resuming deep work after an interruption takes significantly longer than your personalized baseline.

### How to Respond to an Insight Card
Every proactive card offers three immediate options:
- **Review Proposal (Action)**: Opens the multi-step execution proposal synthesized to address the issue.
- **Snooze**: Postpones reminders on this topic for a configurable interval (1 hour, 4 hours, or until tomorrow).
- **Dismiss**: Clears the card and suppresses similar non-critical alerts for 4 hours.

---

## 3. Reviewing & Approving Multi-Step Workflow Proposals

When you review a proposal, ContextIQ presents a structured plan breakdown:

```
[Proposal: Protect Deep Work & Address Q4 RFC Forgetting Risk]
Strategy: BALANCED (Score: 0.88) | Estimated Duration: 55m | Reversibility: Fully Reversible

Step 1: Elevate Priority for 'Q4 RFC' -> HIGH
Step 2: Reschedule 'Sync Meeting' to tomorrow at 14:00 (Requires External Approval)
Step 3: Insert 50-minute Protected Focus Window on Google Calendar
Step 4: Attach Context Recovery Notes to IDE workspace
Step 5: Schedule 10-minute Post-Session Decompression Buffer

[  APPROVE WORKFLOW  ]    [  REVISE STEPS  ]    [  REJECT  ]
```

### Plan Lifecycle
- **Awaiting Approval**: The plan is pending your review. Unapproved plans expire after 24 hours.
- **Approved**: You have authorized execution. The plan is handed off to the execution engine.
- **Executing**: Steps are being executed in topological dependency order.
- **Completed**: All steps were successfully executed. Receipts are visible in your history.
- **Rolled Back**: A step encountered an error and all previous steps were reverted.
- **Cancelled**: You or an emergency stop cancelled the plan before execution.

---

## 4. Configuring Personalized Automation Rules

Navigate to **Settings > Automation Rules** to customize automated triggers:

### Rule Parameters
- **Triggers**: Choose when the rule activates (e.g., `FORGETTING_RISK_SPIKE`, `THRASHING_DETECTED`, `CALENDAR_OVERLOAD`).
- **Conditions**: Add deterministic filters (e.g., `current_risk >= 0.75 AND task.priority == "HIGH"`). No coding or scripting is required.
- **Cooldown**: Minimum minutes between activations (prevents alert spam; default: 60 minutes).
- **Daily Execution Limit**: Maximum number of times the rule can execute per day (default: 3).
- **Quiet Hours**: Define hours during which non-critical automations are suppressed (e.g., `22:00` to `08:00`).

---

## 5. Emergency Stop (Operational Kill Switch)

If you notice unexpected calendar movements or wish to immediately halt all background automations:

### How to Engage
1. Click the red **Emergency Stop** button in the top navigation bar, or run:
   ```bash
   POST /api/v1/automations/emergency-stop
   {
     "reason": "Pause all automations while traveling"
   }
   ```
2. **Immediate Effects**:
   - All pending and scheduled workflows are immediately cancelled.
   - Any currently running execution step is halted.
   - All automated rules are paused.
   - No background worker will take action on your behalf.

### How to Resume
1. Review your **Audit Log** to inspect the state of all past executions.
2. Click **Lift Emergency Stop**. ContextIQ will prompt you to confirm before resuming standard governed operations.

---

## 6. Rolling Back Actions

If an automation took an action you wish to undo:
1. Open **Activity & Audit History**.
2. Locate the executed workflow proposal.
3. Click **Rollback Workflow**. ContextIQ executes compensating actions in reverse order (e.g., restores previous task priority, removes calendar block).

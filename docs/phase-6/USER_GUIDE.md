# ContextIQ Phase 6 User Guide: Predictive Intelligence & Decision Support

Welcome to **ContextIQ Phase 6**. This guide introduces the advanced predictive intelligence, scenario simulation lab, and decision support features designed to help you navigate interruptions, optimize focus, and protect your cognitive well-being without losing control over your day.

---

## 1. Core Principles: You Are in Complete Control

Before exploring the new tools, here are three essential principles of how ContextIQ respects your agency:
1. **ContextIQ Never Changes Your Schedule Without Your Permission:** The system will never silently reschedule your meetings, move tasks, or create calendar holds without your explicit review and one-click approval.
2. **Predictions Are Forecasts, Not Inevitabilities:** Human work is creative, fluid, and unpredictable. When ContextIQ shows a recovery forecast or risk score, it provides a probabilistic estimate with clear confidence intervals—not a judgment.
3. **Simulation is a Sandbox:** The Digital Twin Simulation Lab lets you test "What-If" scenarios safely. Every simulation is clearly watermarked so you always know what is real and what is hypothetical.

---

## 2. Cognitive Recovery Duration Forecasts

When you step away from a complex task—whether due to an urgent phone call, an unexpected meeting, or an app notification—getting back into the flow takes time. This is your **Cognitive Recovery Duration**.

### 2.1 The 6 Stages of Recovery
ContextIQ tracks recovery through six distinct, scientifically grounded phases:
1. **Interruption Detected:** An interruption occurred (e.g., active task backgrounded).
2. **Revisited:** You opened the task or window again.
3. **Context Restored:** Contextual notes, documents, or browser tabs are reloaded.
4. **Resumption Confirmed:** You resumed active typing, editing, or substantive input on the task.
5. **Task Completed:** You successfully finished the task.
6. **Recovery Not Observed:** The task was abandoned or postponed indefinitely.

### 2.2 Reading the Recovery Forecast Card
Following an interruption, ContextIQ displays an estimate of how long it typically takes to regain deep focus:
- **Expected Duration:** E.g., *"12 minutes to regain deep focus"*.
- **90% Confidence Interval:** E.g., *"[8 min – 18 min]"*. This conformal prediction band shows the realistic range based on your past habits and current task complexity.
- **Recommended Action:** E.g., *"Take a 5-minute breather before diving back in"*, or *"Review your last 3 saved code changes"*.

---

## 3. The Digital Twin "What-If" Simulation Lab

Have you ever wondered: *"What if I push this heavy writing task to tomorrow morning?"* or *"What if I block 90 minutes for deep focus this afternoon?"*

The **Behavioral Digital Twin** allows you to simulate your workday in an isolated sandbox.

### 3.1 Running a Scenario
1. Open the **Simulation Lab** in your dashboard.
2. Select or create a scenario:
   - **Move Task to Morning:** Forecasts focus quality if scheduled during your peak alertness window.
   - **Add Recovery Buffer:** Simulates the effect of adding 15-minute buffers between back-to-back meetings.
   - **Notification Throttling:** Simulates reducing desktop alerts during high-friction tasks.
   - **Deconstruct Task:** Simulates breaking a 4-hour epic task into three 45-minute focused sprints.
3. Click **Run Simulation**.

### 3.2 Interpreting Simulation Results
Every simulation displays:
- **Estimated Completion Probability:** E.g., *78% (vs. 54% baseline)*.
- **Expected Friction Reduction:** E.g., *-14 points on Behavioral Friction Index*.
- **Trade-Off Summary:** E.g., *"+30 min total focus time, but requires rescheduling 1 low-priority review"*.
- **Simulation Watermark:** Clearly labeled `[SIMULATION ONLY]` to avoid confusion with your real calendar.

---

## 4. Multi-Objective Intervention Optimization

ContextIQ understands that productivity should never come at the expense of your mental health, family time, or cognitive fatigue. 

When the system suggests an intervention, it balances four competing objectives:
1. **Task Resumption & Completion:** Maximizing the likelihood of reaching your goals.
2. **Cognitive Recovery:** Minimizing the stress and friction of task resumption.
3. **Notification Burden:** Keeping interruptions to an absolute minimum.
4. **Schedule Feasibility:** Respecting your calendar and energy levels.

### 4.1 Strict Hard Constraints
The optimization engine strictly respects your personal rules:
- **Quiet Hours:** No non-critical reminders between your configured evening and morning hours (e.g., 10 PM – 8 AM).
- **Daily Caps:** Strict limits on automated nudges (default: max 6 per day).
- **Focus Shielding:** Zero interruptions allowed when you are in a calendar-blocked focus window.

---

## 5. Workflow Orchestration: Approval, Execution & Undo

When you find a simulated scenario or recommendation you like, you can convert it into an executable **Workflow Proposal**.

### 5.1 The Two-Phase Approval Flow
1. **Proposal Review:** ContextIQ presents a clear step-by-step diff:
   - *Step 1: Move Task "Quarterly Report" from 3:00 PM to Tomorrow 9:30 AM.*
   - *Step 2: Reserve a 15-minute recovery buffer at 11:00 AM.*
   - *Step 3: Enable notification throttling during tomorrow's morning block.*
2. **Explicit Approval:** You click **Approve Workflow**. Nothing happens until you click this button.
3. **Instant Execution:** ContextIQ applies the approved changes to your task list and calendar.

### 5.2 One-Click Undo & Rollback
Changed your mind? Every approved workflow can be rolled back with a single click:
- Navigate to **Recent Workflows** in your settings.
- Click **Rollback Proposal**.
- All tasks and calendar events are instantly restored to their exact prior positions.

---

## 6. Understanding Uncertainty Badges & Intelligent Abstention

Unlike typical AI tools that generate confident answers even when they are guessing, ContextIQ is programmed to know what it does not know.

When data is scarce or your workday is unusually volatile, you will see an **Intelligent Abstention** badge:
- **`INSUFFICIENT_EVIDENCE`:** You haven't performed enough tasks in this category yet. ContextIQ steps aside and lets you work without unproven suggestions.
- **`SHIFT_DETECTED`:** Your recent work patterns differ substantially from your historical baseline (e.g., traveling, attending an all-day conference, or switching roles).
- **`UNSUPPORTED_INPUT`:** The task constraints or environment are outside the verified safety envelope.

When ContextIQ abstains, it protects you from bad advice and relies on standard, non-intrusive default workflows.

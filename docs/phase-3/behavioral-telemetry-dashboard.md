# ContextIQ — Behavioral Telemetry Dashboard & Desktop Agent Controls

## 1. Overview & Purpose

ContextIQ Phase 3.9 delivers the dedicated frontend interface for automated behavioral monitoring and desktop agent operations. Built with Next.js 16, React 19, Tailwind CSS v4, and Recharts, the `/telemetry` dashboard bridges low-level desktop activity ingestion (Phases 3.1–3.4) and advanced behavioral analytics (Phases 3.5–3.8) with human agency, transparency, and calibrated user feedback.

---

## 2. Core UI Modules & Capabilities

```
frontend/
  app/
    telemetry/
      page.tsx                           # Master dashboard container
  components/
    telemetry/
      desktop-agent-status.tsx           # Heartbeat, daemon controls & command launcher
      telemetry-overview-card.tsx        # Daily KPI counters (events, active/idle ratio, sync)
      activity-timeline-chart.tsx        # Recharts chronological stream & hourly stacked view
      interruption-explorer.tsx          # Evidence inspector & feedback calibration controls
      recovery-analytics-panel.tsx       # 3-tier resumption lags, BFI gauge, circadian pattern
      telemetry-privacy-controls.tsx     # Quick pause, exclusions summary, zero-keystroke notice
  types/
    telemetry.ts                         # Complete TypeScript contracts mirroring backend APIs
  lib/api/services/
    telemetry.ts                         # Resilient service client with offline & mock fallback
```

### Module 1: Desktop Agent Status (`desktop-agent-status.tsx`)
- **Live Connection Dot**: Real-time heartbeat tracking with relative age (`12s ago`).
- **Connection Tiers**: `Active Monitoring` (Emerald), `Monitoring Paused` (Amber), `Agent Offline` (Rose).
- **Daemon Telemetry**: Local queue backlog counter, daemon version (`v0.2.0-win`), device identifier.
- **Developer Launcher**: 1-click clipboard copy of `python -m desktop_agent.app.main`.

### Module 2: Daily Behavioral Overview (`telemetry-overview-card.tsx`)
- **Observed Events**: Daily count of validated v1 schema events.
- **Observed Active Time**: Focused application dwelling vs idle time percentage bar.
- **Detected Interruptions**: Filtered switches categorized by rule baseline and pattern matching.
- **Server Sync Status**: Batch HTTPS transmission health and last sync timestamp.

### Module 3: Chronological Activity Timeline (`activity-timeline-chart.tsx`)
- **Dual Visual Modes**:
  1. *Hourly Blocks*: Stacked Recharts visualization showing Focused Active Time, Inactivity Dwell, and Recovery Latency across the workday.
  2. *Chronological Stream*: Granular event-by-event timeline marking duration, observed resumption lag, and confidence scores.
- **Confirmed vs Estimated Visual Distinction**: Unconfirmed or rule-inferred intervals carry distinct dashed borders and `ESTIMATED` badges to preserve epistemic modesty.

### Module 4: Interruption Explorer & Calibration (`interruption-explorer.tsx`)
- **Multidimensional Evidence**: Inspects specific behavioral triggers (e.g., sudden application switches away from primary task, idle gaps followed by rapid multi-app transitions).
- **Three-Tier Delay Inspection**: Displays Return-to-Device ($\tau_1$), Return-to-App ($\tau_2$), and Confirmed Task Resumption ($\tau_3$).
- **One-Click Ground-Truth Feedback**:
  - `GENUINE_INTERRUPTION`: Confirms an external or unexpected disruption occurred.
  - `INTENTIONAL_SWITCH`: Marks intentional multi-app reference workflow (e.g. copying tokens between browser and IDE).
  - `INCORRECT_DETECTION`: Dismisses erroneous heuristic trigger.
  - `Feedback Notes`: Optional contextual user annotations.
- Logged immutably to backend candidate datasets for offline model calibration.

### Module 5: Recovery Analytics & Friction Index (`recovery-analytics-panel.tsx`)
- **Behavioral Friction Index (BFI 0–100)**: Composite index with four tiers (`LOW`, `MODERATE`, `HIGH`, `SEVERE`), progress bar, and primary driver identification.
- **Three-Tier Lag Breakdown**:
  - *Tier 1 (Return-to-Device)*: Physical input resumption.
  - *Tier 2 (Return-to-App)*: Primary workspace refocus.
  - *Tier 3 (Confirmed Resumption)*: Explicit task re-engagement.
- **Circadian Trend**: Area chart mapping peak disruption windows across workday hours.
- **14-Day Rolling Baseline**: Self-relative comparison displaying percentage improvement or elevation against personal historical performance.

### Module 6: Privacy & Agency Quick Controls (`telemetry-privacy-controls.tsx`)
- **Instant Pause**: Quick buttons for 15-minute, 1-hour, or 4-hour monitoring pauses.
- **Transparency Safeguards**: Highlights active title sanitization, process exclusions, and zero-keystroke architecture.
- **Direct Navigation**: Deep link to the comprehensive Privacy Cockpit (`/privacy`).

---

## 3. Behavioral Framing Standards

In accordance with ContextIQ's core behavioral tenets:
1. **Observable Phenomena**: Metrics are strictly labeled with physical terminology (e.g., *Observed Application Dwell*, *Return-to-Device Latency*).
2. **Cognitive Humility**: The UI never claims to directly read "mental fatigue", "brain exhaustion", or "cognitive overload".
3. **Explicit Estimation**: Any metric derived from heuristic association without explicit user confirmation is badged as `ESTIMATED`.

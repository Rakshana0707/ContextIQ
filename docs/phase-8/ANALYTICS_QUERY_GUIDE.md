# Natural-Language Productivity Analytics & Query Planning Guide

## 1. Overview

ContextIQ allows users to explore their productivity metrics through natural-language questions (e.g., *"Which project consumed most of my productive time?"*, *"Which goal has the greatest number of blocked tasks?"*).

To prevent SQL injection vulnerabilities and LLM hallucinations, ContextIQ does **not** generate dynamic raw SQL. Instead, natural-language queries are translated into validated **Abstract Syntax Trees (AST)** and executed strictly through parameterized SQLAlchemy ORM aggregation pipelines.

---

## 2. Architecture & AST Pipeline

```mermaid
graph LR
    NLQ[Natural Language Query] --> AQP[Analytics Query Planner]
    AQP --> AST[Validated Analytics AST]
    AST --> AQE[Safe Query Executor]
    AQE --> ORM[Parameterized ORM Aggregation]
    ORM --> RES[Structured Analytics Result]
    RES --> VAG[Visual Analytics Generator]
    VAG --> VIZ[ECharts / Recharts Visual Spec]
```

---

## 3. Supported Query Domains

The [AnalyticsQueryPlanner](file:///e:/Downloads 🔃/ContextIQ-main/ContextIQ-main/backend/app/services/analytics_query_planner.py) maps user intents into explicit target domains:

| Domain | Canonical Example | Aggregation Strategy |
| :--- | :--- | :--- |
| `PROJECT_TIME_CONSUMPTION` | *"Which project consumed most of my productive time?"* | Sum completed task durations grouped by project. |
| `GOAL_BLOCKED_TASKS` | *"Which goal has the greatest number of blocked tasks?"* | Count tasks linked to goals having unresolved blocker dependencies. |
| `PROJECT_DELAY_RISK` | *"Which project has the highest delay risk?"* | Order projects by latest forecast `delay_risk_score`. |
| `POSTPONED_TASKS_ANALYSIS` | *"What types of tasks do I postpone most often?"* | Group task postpone/reschedule events by task category. |
| `RECOVERY_DURATION_TRENDS` | *"How has my recovery duration changed?"* | Time-series aggregation of daily recovery lag. |
| `INTERVENTION_EFFECTIVENESS` | *"Which interventions have the strongest historical evidence?"* | Rank recommendation types by positive user feedback ratio. |
| `DEADLINE_CONFLICT_ANALYSIS` | *"Which upcoming deadlines conflict with current priorities?"* | Detect overlapping high-priority task due dates. |

---

## 4. Visual Analytics Generation

The [VisualAnalyticsGenerator](file:///e:/Downloads 🔃/ContextIQ-main/ContextIQ-main/backend/app/services/visual_analytics_generator.py) transforms structured query results into chart visualization specifications:
- **Bar Charts**: Categorical comparisons (e.g., hours per project, blocked tasks per goal).
- **Line Charts**: Longitudinal trends (e.g., recovery duration over time, friction drift).
- **Scatter / Risk Charts**: Delay risk vs. remaining workload.
- **Epistemic Disclaimers**: Appends data insufficiency warnings when sample sizes are inadequate.

---

## 5. API Endpoints

- `POST /api/v1/analytics/query`: Submit natural-language analytics question; returns query plan, data rows, and visual chart specifications.
- `GET /api/v1/analytics/saved-queries`: Retrieve saved and pinned analytics queries.
- `POST /api/v1/analytics/saved-queries`: Save a customized analytics query with dashboard pin options.

"""
Structured Analytics Query Planner (ContextIQ Phase 8.9).

Translates natural language analytical questions into safe, deterministic,
strictly typed AnalyticsQueryPlan specifications.
Never executes arbitrary or LLM-generated raw SQL.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.analytics_workspace import (
    AnalyticsDomain,
    AnalyticsQueryPlan,
    AnalyticsTimeRange,
)

MALICIOUS_SQL_PATTERNS = [
    r"\bSELECT\b",
    r"\bDROP\s+TABLE\b",
    r"\bDELETE\s+FROM\b",
    r"\bINSERT\s+INTO\b",
    r"\bUPDATE\s+\w+\s+SET\b",
    r"\bUNION\s+SELECT\b",
    r"\bTRUNCATE\s+TABLE\b",
    r"\bALTER\s+TABLE\b",
    r"\bEXEC(?:\s+|\()",
    r";\s*--",
    r";\s*DROP",
    r";\s*DELETE",
]


class AnalyticsQueryPlanner:
    """
    Parses and plans safe analytical queries from user natural language input.
    """

    @classmethod
    def plan_query(
        cls,
        query: str,
        lookback_days: int = 30,
        explicit_filters: Optional[Dict[str, Any]] = None,
    ) -> AnalyticsQueryPlan:
        """
        Parses user query, checks safety guards, infers domain, and returns an AnalyticsQueryPlan.
        """
        q_clean = query.strip()
        q_upper = q_clean.upper()

        # 1. Malicious input detection
        for pat in MALICIOUS_SQL_PATTERNS:
            if re.search(pat, q_upper, re.IGNORECASE):
                raise ValueError(
                    f"Security Policy Violation: Query contains forbidden SQL token matching {pat}."
                )

        # 2. Extract time range mentions
        window_days, time_label = cls._extract_time_window(q_clean, default_days=lookback_days)
        now = datetime.now(timezone.utc)
        start_date = (now - timedelta(days=window_days)).strftime("%Y-%m-%d")
        end_date = now.strftime("%Y-%m-%d")

        time_range = AnalyticsTimeRange(
            lookback_days=window_days,
            start_date=start_date,
            end_date=end_date,
            label=time_label,
        )

        q_lower = q_clean.lower()
        filters: Dict[str, Any] = explicit_filters.copy() if explicit_filters else {}

        # 3. Classify Domain & Structure Plan
        if "time" in q_lower or "consumed" in q_lower or "hours" in q_lower or "spent" in q_lower or "allocation" in q_lower:
            return AnalyticsQueryPlan(
                plan_id=str(uuid.uuid4()),
                target_domain=AnalyticsDomain.PROJECT_TIME_ALLOCATION,
                entity="projects",
                time_range=time_range,
                filters=filters,
                group_by="project",
                aggregation="SUM",
                sort_by="productive_hours",
                sort_order="DESC",
                limit=10,
                comparison_mode="CROSS_PROJECT",
                is_valid=True,
                planning_rationale="Evaluates tracked and estimated focus minutes grouped by project to compute productive time share.",
            )

        elif "blocked" in q_lower or "blocker" in q_lower or ("goal" in q_lower and "block" in q_lower):
            return AnalyticsQueryPlan(
                plan_id=str(uuid.uuid4()),
                target_domain=AnalyticsDomain.GOAL_BLOCKED_TASKS,
                entity="goals",
                time_range=time_range,
                filters=filters,
                group_by="goal",
                aggregation="COUNT",
                sort_by="blocked_tasks_count",
                sort_order="DESC",
                limit=10,
                comparison_mode="CROSS_GOAL",
                is_valid=True,
                planning_rationale="Counts unfinished tasks associated with each goal that are actively blocked by upstream dependencies.",
            )

        elif "delay" in q_lower or "risk" in q_lower or "falling behind" in q_lower or "behind" in q_lower:
            return AnalyticsQueryPlan(
                plan_id=str(uuid.uuid4()),
                target_domain=AnalyticsDomain.PROJECT_DELAY_RISK,
                entity="projects",
                time_range=time_range,
                filters=filters,
                group_by="project",
                aggregation="MAX",
                sort_by="delay_risk_score",
                sort_order="DESC",
                limit=10,
                comparison_mode="CROSS_PROJECT",
                is_valid=True,
                planning_rationale="Ranks projects by calibrated delay risk scores and forecast completion probabilities.",
            )

        elif "postpone" in q_lower or "procrastinat" in q_lower or "delaying" in q_lower or "defer" in q_lower:
            return AnalyticsQueryPlan(
                plan_id=str(uuid.uuid4()),
                target_domain=AnalyticsDomain.TASK_POSTPONEMENT_TYPES,
                entity="tasks",
                time_range=time_range,
                filters=filters,
                group_by="context_tag_or_priority",
                aggregation="COUNT",
                sort_by="postponement_count",
                sort_order="DESC",
                limit=10,
                comparison_mode="BY_CATEGORY",
                is_valid=True,
                planning_rationale="Aggregates task postponement event frequencies categorized by task priority and context tag.",
            )

        elif "recovery" in q_lower or "resumption" in q_lower or "interruption" in q_lower:
            return AnalyticsQueryPlan(
                plan_id=str(uuid.uuid4()),
                target_domain=AnalyticsDomain.RECOVERY_DURATION_TREND,
                entity="behavioral_daily_metrics",
                time_range=time_range,
                filters=filters,
                group_by="metric_date",
                aggregation="AVG",
                sort_by="metric_date",
                sort_order="ASC",
                limit=window_days,
                comparison_mode="CHRONOLOGICAL_TREND",
                is_valid=True,
                planning_rationale="Calculates rolling average and trend trajectory for resumption lag and recovery efficiency scores.",
            )

        elif "intervention" in q_lower or "recommendation" in q_lower or "worked well" in q_lower or "evidence" in q_lower:
            return AnalyticsQueryPlan(
                plan_id=str(uuid.uuid4()),
                target_domain=AnalyticsDomain.INTERVENTION_HISTORICAL_EVIDENCE,
                entity="recommendation_feedback",
                time_range=time_range,
                filters=filters,
                group_by="recommendation_type",
                aggregation="COUNT",
                sort_by="acceptance_rate",
                sort_order="DESC",
                limit=10,
                comparison_mode="BY_TYPE",
                is_valid=True,
                planning_rationale="Analyzes historical recommendation feedback acceptance rates and post-intervention metric shifts.",
            )

        elif "deadline" in q_lower or "conflict" in q_lower or "upcoming" in q_lower:
            return AnalyticsQueryPlan(
                plan_id=str(uuid.uuid4()),
                target_domain=AnalyticsDomain.DEADLINE_PRIORITY_CONFLICTS,
                entity="tasks",
                time_range=time_range,
                filters=filters,
                group_by="task",
                aggregation="RANK",
                sort_by="due_at",
                sort_order="ASC",
                limit=15,
                comparison_mode="TIMELINE_CONFLICTS",
                is_valid=True,
                planning_rationale="Detects upcoming deadlines where high urgency or estimated duration conflicts with lower priority tasks.",
            )

        elif "cross" in q_lower or "progress" in q_lower or "all projects" in q_lower:
            return AnalyticsQueryPlan(
                plan_id=str(uuid.uuid4()),
                target_domain=AnalyticsDomain.CROSS_PROJECT_PROGRESS,
                entity="projects",
                time_range=time_range,
                filters=filters,
                group_by="project",
                aggregation="AVG",
                sort_by="completion_pct",
                sort_order="DESC",
                limit=10,
                comparison_mode="CROSS_PROJECT",
                is_valid=True,
                planning_rationale="Generates multi-project progress and health comparison overview.",
            )

        else:
            # Fallback general productivity aggregation
            return AnalyticsQueryPlan(
                plan_id=str(uuid.uuid4()),
                target_domain=AnalyticsDomain.CUSTOM_PRODUCTIVITY_QUERY,
                entity="tasks",
                time_range=time_range,
                filters=filters,
                group_by="priority",
                aggregation="COUNT",
                sort_by="priority",
                sort_order="DESC",
                limit=10,
                comparison_mode="GENERAL_BREAKDOWN",
                is_valid=True,
                planning_rationale="General query plan aggregating task volume by priority for broad workspace exploration.",
            )

    @classmethod
    def _extract_time_window(cls, text: str, default_days: int) -> Tuple[int, str]:
        t_low = text.lower()
        if "7 day" in t_low or "last week" in t_low or "past week" in t_low:
            return 7, "Last 7 Days"
        elif "14 day" in t_low or "two week" in t_low:
            return 14, "Last 14 Days"
        elif "90 day" in t_low or "quarter" in t_low or "three month" in t_low:
            return 90, "Last 90 Days"
        elif "30 day" in t_low or "month" in t_low:
            return 30, "Last 30 Days"
        elif "year" in t_low or "365 day" in t_low:
            return 365, "Last 365 Days"
        return default_days, f"Last {default_days} Days"

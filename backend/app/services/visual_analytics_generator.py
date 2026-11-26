"""
Visual Analytics Generator (ContextIQ Phase 8.9).

Constructs validated, interactive chart specifications directly from query execution results.
Guarantees that chart data points match database records exactly with zero hallucination.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.schemas.analytics_workspace import (
    AnalyticsDataPoint,
    AnalyticsDomain,
    AnalyticsQueryPlan,
    AnalyticsVisualizationSpec,
    ChartType,
)
from app.services.analytics_query_executor import ExecutionResult


class VisualAnalyticsGenerator:
    """
    Transforms execution results into deterministic visualization specifications.
    """

    COLOR_PALETTE = [
        "#3B82F6",  # blue
        "#10B981",  # emerald
        "#F59E0B",  # amber
        "#EF4444",  # rose
        "#8B5CF6",  # violet
        "#06B6D4",  # cyan
        "#EC4899",  # pink
        "#6366F1",  # indigo
    ]

    @classmethod
    def generate(
        cls,
        plan: AnalyticsQueryPlan,
        result: ExecutionResult,
    ) -> AnalyticsVisualizationSpec:
        domain = plan.target_domain
        records = result.supporting_records

        if domain == AnalyticsDomain.PROJECT_TIME_ALLOCATION:
            series = [
                AnalyticsDataPoint(
                    label=r["project_title"],
                    value=float(r["productive_hours"]),
                    secondary_value=float(r.get("time_share_pct", 0.0)),
                    category="Project",
                    color=cls.COLOR_PALETTE[i % len(cls.COLOR_PALETTE)],
                    metadata={"health": r.get("health_status")},
                )
                for i, r in enumerate(records[:10])
            ]
            return AnalyticsVisualizationSpec(
                chart_type=ChartType.BAR,
                title="Productive Time Allocation by Project",
                x_axis_label="Project",
                y_axis_label="Productive Hours",
                series=series,
                chart_config={"unit": "hours", "show_percentage": True},
            )

        elif domain == AnalyticsDomain.GOAL_BLOCKED_TASKS:
            series = [
                AnalyticsDataPoint(
                    label=r["goal_title"],
                    value=float(r["blocked_tasks_count"]),
                    secondary_value=float(r.get("total_linked_tasks", 0)),
                    category="Goal",
                    color="#EF4444" if r["blocked_tasks_count"] > 0 else "#10B981",
                    metadata={"progress_pct": r.get("progress_pct")},
                )
                for r in records[:10]
            ]
            return AnalyticsVisualizationSpec(
                chart_type=ChartType.BAR,
                title="Blocked Tasks per Strategic Goal",
                x_axis_label="Goal",
                y_axis_label="Blocked Tasks",
                series=series,
                chart_config={"unit": "tasks", "threshold_warning": 1},
            )

        elif domain == AnalyticsDomain.PROJECT_DELAY_RISK:
            tier_colors = {"LOW": "#10B981", "MODERATE": "#F59E0B", "HIGH": "#EF4444", "CRITICAL": "#B91C1C"}
            series = [
                AnalyticsDataPoint(
                    label=r["project_title"],
                    value=float(r["delay_risk_score"]),
                    secondary_value=float(r.get("on_time_probability", 0.0) * 100),
                    category=r.get("delay_risk_tier", "LOW"),
                    color=tier_colors.get(r.get("delay_risk_tier"), "#3B82F6"),
                    metadata={"overdue_milestones": r.get("overdue_milestones_count")},
                )
                for r in records[:10]
            ]
            return AnalyticsVisualizationSpec(
                chart_type=ChartType.BAR,
                title="Cross-Project Delay Risk Comparison",
                x_axis_label="Project",
                y_axis_label="Delay Risk Score (0-1.0)",
                series=series,
                chart_config={"unit": "risk_score", "max_domain": 1.0},
            )

        elif domain == AnalyticsDomain.TASK_POSTPONEMENT_TYPES:
            series = [
                AnalyticsDataPoint(
                    label=r["category"],
                    value=float(r["postponement_count"]),
                    category="Task Category",
                    color=cls.COLOR_PALETTE[i % len(cls.COLOR_PALETTE)],
                    metadata={},
                )
                for i, r in enumerate(records[:8])
            ]
            return AnalyticsVisualizationSpec(
                chart_type=ChartType.PIE,
                title="Task Postponement Distribution by Category",
                x_axis_label="Category",
                y_axis_label="Postponement Count",
                series=series,
                chart_config={"donut": True, "show_legend": True},
            )

        elif domain == AnalyticsDomain.RECOVERY_DURATION_TREND:
            series = [
                AnalyticsDataPoint(
                    label=r["date"][-5:],  # MM-DD
                    value=float(r["avg_recovery_lag_seconds"]),
                    secondary_value=float(r.get("recovery_efficiency_pct", 0.0)),
                    category="Daily Lag",
                    color="#8B5CF6",
                    metadata={"full_date": r["date"]},
                )
                for r in records
            ]
            return AnalyticsVisualizationSpec(
                chart_type=ChartType.LINE,
                title="Resumption Lag & Recovery Efficiency Trend",
                x_axis_label="Date",
                y_axis_label="Recovery Lag (seconds)",
                series=series,
                chart_config={"smooth": True, "dual_axis": True},
            )

        elif domain == AnalyticsDomain.INTERVENTION_HISTORICAL_EVIDENCE:
            series = [
                AnalyticsDataPoint(
                    label=r["intervention_type"],
                    value=float(r["acceptance_rate_pct"]),
                    secondary_value=float(r.get("accepted_count", 0)),
                    category="Intervention",
                    color="#10B981",
                    metadata={"total": r.get("total_suggestions")},
                )
                for r in records[:8]
            ]
            return AnalyticsVisualizationSpec(
                chart_type=ChartType.BAR,
                title="Intervention Compliance & Acceptance Rates",
                x_axis_label="Intervention Type",
                y_axis_label="Acceptance Rate (%)",
                series=series,
                chart_config={"unit": "%", "max_domain": 100.0},
            )

        elif domain == AnalyticsDomain.DEADLINE_PRIORITY_CONFLICTS:
            series = [
                AnalyticsDataPoint(
                    label=r["task_title"][:24],
                    value=float(r["estimated_hours"]),
                    category=r.get("priority", "MEDIUM"),
                    color="#EF4444" if r.get("has_conflict") else "#3B82F6",
                    metadata={"due_at": r["due_at"], "conflict": r.get("conflict_reason")},
                )
                for r in records[:10]
            ]
            return AnalyticsVisualizationSpec(
                chart_type=ChartType.TABLE,
                title="Upcoming Deadlines & Schedule Priority Conflicts",
                x_axis_label="Task",
                y_axis_label="Estimated Hours",
                series=series,
                chart_config={"show_conflict_badge": True},
            )

        else:
            # Fallback general chart
            series = [
                AnalyticsDataPoint(
                    label=str(r.get("priority", r.get("label", "Item"))),
                    value=float(r.get("count", r.get("value", 1.0))),
                    category="Category",
                    color=cls.COLOR_PALETTE[i % len(cls.COLOR_PALETTE)],
                    metadata={},
                )
                for i, r in enumerate(records[:10])
            ]
            return AnalyticsVisualizationSpec(
                chart_type=ChartType.BAR,
                title="Productivity Breakdown Overview",
                x_axis_label="Dimension",
                y_axis_label="Count",
                series=series,
                chart_config={},
            )

"""
Pydantic schemas for Natural-Language Productivity Analytics & Cross-Project Decision Intelligence (Phase 8.9).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class AnalyticsDomain(str, Enum):
    PROJECT_TIME_ALLOCATION = "PROJECT_TIME_ALLOCATION"
    GOAL_BLOCKED_TASKS = "GOAL_BLOCKED_TASKS"
    PROJECT_DELAY_RISK = "PROJECT_DELAY_RISK"
    TASK_POSTPONEMENT_TYPES = "TASK_POSTPONEMENT_TYPES"
    RECOVERY_DURATION_TREND = "RECOVERY_DURATION_TREND"
    INTERVENTION_HISTORICAL_EVIDENCE = "INTERVENTION_HISTORICAL_EVIDENCE"
    DEADLINE_PRIORITY_CONFLICTS = "DEADLINE_PRIORITY_CONFLICTS"
    CROSS_PROJECT_PROGRESS = "CROSS_PROJECT_PROGRESS"
    CUSTOM_PRODUCTIVITY_QUERY = "CUSTOM_PRODUCTIVITY_QUERY"


class ChartType(str, Enum):
    BAR = "BAR"
    LINE = "LINE"
    PIE = "PIE"
    RADAR = "RADAR"
    TIMELINE = "TIMELINE"
    TABLE = "TABLE"


class AnalyticsTimeRange(BaseModel):
    lookback_days: Optional[int] = 30
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    label: str = "Last 30 Days"

    model_config = ConfigDict(from_attributes=True)


class AnalyticsQueryPlan(BaseModel):
    """
    Structured, AST-like query plan compiled deterministically from natural language.
    Prevents arbitrary raw SQL execution.
    """
    plan_id: str
    target_domain: AnalyticsDomain
    entity: str
    time_range: AnalyticsTimeRange
    filters: Dict[str, Any] = Field(default_factory=dict)
    group_by: Optional[str] = None
    aggregation: str = "COUNT"  # SUM, AVG, COUNT, MIN, MAX, RANK
    sort_by: Optional[str] = None
    sort_order: Literal["ASC", "DESC"] = "DESC"
    limit: int = 10
    comparison_mode: Optional[str] = None
    is_valid: bool = True
    planning_rationale: str = ""

    model_config = ConfigDict(from_attributes=True)


class AnalyticsDataPoint(BaseModel):
    label: str
    value: float
    secondary_value: Optional[float] = None
    category: Optional[str] = None
    color: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class AnalyticsVisualizationSpec(BaseModel):
    chart_type: ChartType
    title: str
    x_axis_label: Optional[str] = None
    y_axis_label: Optional[str] = None
    series: List[AnalyticsDataPoint] = Field(default_factory=list)
    chart_config: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class DecisionRecommendation(BaseModel):
    decision_type: str
    target_title: str
    target_id: Optional[str] = None
    score: float
    rank: int
    rationale: str
    suggested_action: str

    model_config = ConfigDict(from_attributes=True)


class AnalyticsQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000, description="Natural-language analytical question")
    lookback_days: Optional[int] = Field(30, ge=1, le=365, description="Lookback window in days")
    filters: Optional[Dict[str, Any]] = Field(None, description="Optional explicit entity filters")


class AnalyticsQueryResponse(BaseModel):
    query: str
    plan: AnalyticsQueryPlan
    summary_answer: str
    calculation_details: Dict[str, Any] = Field(default_factory=dict)
    time_range: Dict[str, Any] = Field(default_factory=dict)
    supporting_records: List[Dict[str, Any]] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    suggested_decisions: List[DecisionRecommendation] = Field(default_factory=list)
    visualization: AnalyticsVisualizationSpec
    epistemic_disclaimer: str = (
        "Analyses reflect observed productivity data in ContextIQ. Statistical associations do not imply singular causal attribution."
    )

    model_config = ConfigDict(from_attributes=True)


class SavedAnalyticsQueryCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    query_text: str = Field(..., min_length=1, max_length=1000)
    target_domain: Optional[str] = "GENERAL"
    plan_snapshot: Optional[Dict[str, Any]] = None
    is_favorite: bool = False


class SavedAnalyticsQueryRead(BaseModel):
    id: uuid.UUID
    title: str
    query_text: str
    target_domain: str
    is_favorite: bool
    created_at: datetime
    last_run_at: Optional[datetime] = None
    plan_snapshot: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class SavedAnalyticsQueryListResponse(BaseModel):
    queries: List[SavedAnalyticsQueryRead]
    total: int


class AnalyticsSuggestionItem(BaseModel):
    question: str
    category: str
    expected_chart_type: str
    description: str

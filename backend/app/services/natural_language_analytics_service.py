"""
Natural-Language Productivity Analytics & Cross-Project Decision Intelligence Service (Phase 8.9).

Coordinates:
1. Query planning and AST validation (preventing arbitrary SQL).
2. Safe ORM execution with user data isolation.
3. Cross-project decision intelligence and ranked recommendations.
4. Visual analytics generation (matching DB records).
5. User-saved queries CRUD.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.analytics_workspace import SavedAnalyticsQuery
from app.schemas.analytics_workspace import (
    AnalyticsDomain,
    AnalyticsQueryPlan,
    AnalyticsQueryRequest,
    AnalyticsQueryResponse,
    AnalyticsSuggestionItem,
    DecisionRecommendation,
    SavedAnalyticsQueryCreate,
    SavedAnalyticsQueryRead,
)
from app.services.analytics_query_executor import AnalyticsQueryExecutor, ExecutionResult
from app.services.analytics_query_planner import AnalyticsQueryPlanner
from app.services.visual_analytics_generator import VisualAnalyticsGenerator

SUGGESTED_ANALYTICS_QUESTIONS: List[AnalyticsSuggestionItem] = [
    AnalyticsSuggestionItem(
        question="Which project consumed most of my productive time?",
        category="Time Allocation",
        expected_chart_type="BAR",
        description="Analyzes productive time share and tracked hours across all active projects.",
    ),
    AnalyticsSuggestionItem(
        question="Which goal has the greatest number of blocked tasks?",
        category="Dependencies",
        expected_chart_type="BAR",
        description="Counts active dependency blockers that obstruct strategic goal progress.",
    ),
    AnalyticsSuggestionItem(
        question="Which project has the highest delay risk?",
        category="Forecasting",
        expected_chart_type="BAR",
        description="Ranks projects by survival delay hazard scores and completion probabilities.",
    ),
    AnalyticsSuggestionItem(
        question="What types of tasks do I postpone most often?",
        category="Behavioral Patterns",
        expected_chart_type="PIE",
        description="Categorizes task deferral events across priorities and tags.",
    ),
    AnalyticsSuggestionItem(
        question="How has my recovery duration changed?",
        category="Recovery Analytics",
        expected_chart_type="LINE",
        description="Traces resumption lag and recovery efficiency trajectories over time.",
    ),
    AnalyticsSuggestionItem(
        question="Which interventions have the strongest historical evidence?",
        category="Interventions",
        expected_chart_type="BAR",
        description="Measures empirical acceptance rates across recommendation types.",
    ),
    AnalyticsSuggestionItem(
        question="Which upcoming deadlines conflict with my current priorities?",
        category="Schedule Optimization",
        expected_chart_type="TABLE",
        description="Detects temporal overlaps and priority inversions among upcoming tasks.",
    ),
]


class NaturalLanguageAnalyticsService:
    """
    Main orchestration service for natural language productivity analytics.
    """

    @classmethod
    def execute_query(
        cls,
        db: Session,
        user_id: uuid.UUID,
        request: AnalyticsQueryRequest,
    ) -> AnalyticsQueryResponse:
        """
        Interprets natural language query, validates plan, executes safely via ORM,
        synthesizes decision recommendations, and generates matching visualization spec.
        """
        # 1. Compile structured plan
        plan = AnalyticsQueryPlanner.plan_query(
            query=request.query,
            lookback_days=request.lookback_days or 30,
            explicit_filters=request.filters,
        )

        # 2. Execute safely via ORM with user scoping
        result = AnalyticsQueryExecutor.execute(db=db, user_id=user_id, plan=plan)

        # 3. Generate visualization specification
        viz_spec = VisualAnalyticsGenerator.generate(plan=plan, result=result)

        # 4. Synthesize structured decision recommendations
        decisions = cls._generate_decision_recommendations(plan=plan, result=result)

        return AnalyticsQueryResponse(
            query=request.query,
            plan=plan,
            summary_answer=result.summary_answer,
            calculation_details=result.calculation_details,
            time_range=plan.time_range.model_dump(),
            supporting_records=result.supporting_records,
            limitations=result.limitations,
            suggested_decisions=decisions,
            visualization=viz_spec,
            epistemic_disclaimer=(
                "ContextIQ natural-language analytics are computed deterministically from verified user records. "
                "Observational correlations do not constitute singular causal proof."
            ),
        )

    @classmethod
    def get_suggestions(cls) -> List[AnalyticsSuggestionItem]:
        """Returns the canonical list of suggested analytical questions."""
        return SUGGESTED_ANALYTICS_QUESTIONS

    @classmethod
    def save_query(
        cls,
        db: Session,
        user_id: uuid.UUID,
        payload: SavedAnalyticsQueryCreate,
    ) -> SavedAnalyticsQueryRead:
        """Saves a query for repeated execution."""
        now = datetime.now(timezone.utc)
        record = SavedAnalyticsQuery(
            user_id=user_id,
            title=payload.title,
            query_text=payload.query_text,
            target_domain=payload.target_domain or "GENERAL",
            is_favorite=payload.is_favorite,
            plan_snapshot=payload.plan_snapshot or {},
            created_at=now,
            updated_at=now,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return SavedAnalyticsQueryRead.model_validate(record)

    @classmethod
    def list_saved_queries(
        cls,
        db: Session,
        user_id: uuid.UUID,
    ) -> List[SavedAnalyticsQueryRead]:
        """Lists user-saved queries."""
        records = (
            db.query(SavedAnalyticsQuery)
            .filter(SavedAnalyticsQuery.user_id == user_id)
            .order_by(SavedAnalyticsQuery.is_favorite.desc(), SavedAnalyticsQuery.created_at.desc())
            .all()
        )
        return [SavedAnalyticsQueryRead.model_validate(r) for r in records]

    @classmethod
    def get_saved_query(
        cls,
        db: Session,
        user_id: uuid.UUID,
        query_id: uuid.UUID,
    ) -> Optional[SavedAnalyticsQueryRead]:
        """Gets a single saved query strictly owned by user_id."""
        record = (
            db.query(SavedAnalyticsQuery)
            .filter(
                SavedAnalyticsQuery.id == query_id,
                SavedAnalyticsQuery.user_id == user_id,
            )
            .first()
        )
        if not record:
            return None
        return SavedAnalyticsQueryRead.model_validate(record)

    @classmethod
    def delete_saved_query(
        cls,
        db: Session,
        user_id: uuid.UUID,
        query_id: uuid.UUID,
    ) -> bool:
        """Deletes a saved query strictly owned by user_id."""
        record = (
            db.query(SavedAnalyticsQuery)
            .filter(
                SavedAnalyticsQuery.id == query_id,
                SavedAnalyticsQuery.user_id == user_id,
            )
            .first()
        )
        if not record:
            return False
        db.delete(record)
        db.commit()
        return True

    @classmethod
    def _generate_decision_recommendations(
        cls,
        plan: AnalyticsQueryPlan,
        result: ExecutionResult,
    ) -> List[DecisionRecommendation]:
        """Synthesizes actionable, ranked decision recommendations from analytical findings."""
        recs: List[DecisionRecommendation] = []
        domain = plan.target_domain
        records = result.supporting_records

        if domain == AnalyticsDomain.PROJECT_TIME_ALLOCATION and records:
            top_p = records[0]
            recs.append(
                DecisionRecommendation(
                    decision_type="RESOURCE_ALLOCATION",
                    target_title=top_p["project_title"],
                    target_id=top_p.get("project_id"),
                    score=0.88,
                    rank=1,
                    rationale=f"Project '{top_p['project_title']}' absorbs {top_p.get('time_share_pct', 0)}% of focus time.",
                    suggested_action="Review milestone deliverables to prevent neglect of secondary projects.",
                )
            )

        elif domain == AnalyticsDomain.GOAL_BLOCKED_TASKS and records:
            top_g = records[0]
            if top_g.get("blocked_tasks_count", 0) > 0:
                recs.append(
                    DecisionRecommendation(
                        decision_type="BLOCKER_RESOLUTION",
                        target_title=top_g["goal_title"],
                        target_id=top_g.get("goal_id"),
                        score=0.95,
                        rank=1,
                        rationale=f"Goal '{top_g['goal_title']}' has {top_g['blocked_tasks_count']} blocked task(s) impeding progress.",
                        suggested_action="Prioritize unblocking upstream dependencies in tomorrow's primary focus slot.",
                    )
                )

        elif domain == AnalyticsDomain.PROJECT_DELAY_RISK and records:
            top_risk = records[0]
            recs.append(
                DecisionRecommendation(
                    decision_type="SCHEDULE_INTERVENTION",
                    target_title=top_risk["project_title"],
                    target_id=top_risk.get("project_id"),
                    score=float(top_risk.get("delay_risk_score", 0.8)),
                    rank=1,
                    rationale=f"Delay hazard tier is {top_risk.get('delay_risk_tier')} with only {round(top_risk.get('on_time_probability', 0) * 100)}% on-time likelihood.",
                    suggested_action="Propose governed schedule adjustment or scope compression via workflow governance.",
                )
            )

        elif domain == AnalyticsDomain.TASK_POSTPONEMENT_TYPES and records:
            top_cat = records[0]
            recs.append(
                DecisionRecommendation(
                    decision_type="BEHAVIORAL_NUDGE",
                    target_title=f"{top_cat['category']} Tasks",
                    score=0.82,
                    rank=1,
                    rationale=f"Highest postponement volume concentrated in '{top_cat['category']}' tasks ({top_cat['postponement_count']} events).",
                    suggested_action="Decompose large items in this category into 15-minute subtasks with clear acceptance criteria.",
                )
            )

        elif domain == AnalyticsDomain.DEADLINE_PRIORITY_CONFLICTS and records:
            conflicts = [r for r in records if r.get("has_conflict")]
            if conflicts:
                top_c = conflicts[0]
                recs.append(
                    DecisionRecommendation(
                        decision_type="TASK_PRIORITIZATION",
                        target_title=top_c["task_title"],
                        target_id=top_c.get("task_id"),
                        score=0.91,
                        rank=1,
                        rationale=f"Task '{top_c['task_title']}' has deadline conflict: {top_c.get('conflict_reason')}.",
                        suggested_action="Reorder execution priority to ensure high-impact deliverable is protected.",
                    )
                )

        if not recs:
            recs.append(
                DecisionRecommendation(
                    decision_type="EXECUTION_ALIGNMENT",
                    target_title="Workspace Execution",
                    score=0.75,
                    rank=1,
                    rationale="Metrics reflect stable execution without immediate critical friction bottlenecks.",
                    suggested_action="Maintain scheduled focus rhythms and monitor active project milestones.",
                )
            )

        return recs

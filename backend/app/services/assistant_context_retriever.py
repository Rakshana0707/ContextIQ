"""
Assistant Context Retrieval Layer (ContextIQ Phase 8.8).

Enforces:
1. Strict user-scoped isolation: every SQL query filters strictly by user_id.
2. Comprehensive multi-domain retrieval across:
   - Tasks & TaskEvents (open, overdue, priorities, postponements).
   - Projects & Milestones (health status, target dates, completion rates).
   - Goals & Associations (hierarchy, progress, linked tasks).
   - Task Dependencies & Knowledge Graph (blockers, dependencies, relationships).
   - Behavioral Memory (habits, focus patterns, preferences).
   - Historical Metrics & Trends (friction, focus consistency, 7d/30d rolling stats, milestones).
   - Recommendations & Feedback (accepted recommendations, historical effectiveness).
   - Project Forecasts (completion probability, delay risk tier).
3. Data freshness tracking (timestamps of evaluated sources).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from app.models.assistant import AssistantConversation, AssistantMessage
from app.models.behavioral_memory import BehavioralMemory, MemoryValidityStatus
from app.models.behavioral_trend import (
    BehavioralChangePoint,
    BehavioralDailyMetric,
    BehavioralMilestoneRecord,
)
from app.models.enums import (
    RecommendationFeedbackAction,
    TaskEventType,
    TaskPriority,
    TaskStatus,
)
from app.models.goal_project import GoalTaskAssociation, ProjectMilestone
from app.models.knowledge_graph import Goal, KnowledgeNode, KnowledgeRelationship, Project
from app.models.project_forecast import ProjectForecast
from app.models.recommendation import Recommendation
from app.models.recommendation_feedback import RecommendationFeedback
from app.models.task import Task
from app.models.task_dependency import TaskDependency
from app.models.task_event import TaskEvent
from app.models.workflow_models import WorkflowExecutionPlan


@dataclass
class TaskSummary:
    id: str
    title: str
    status: str
    priority: str
    due_at: Optional[datetime]
    is_overdue: bool
    estimated_minutes: Optional[int]
    completed_at: Optional[datetime]
    postponement_count: int
    context_tag: Optional[str]


@dataclass
class ProjectSummary:
    id: str
    title: str
    status: str
    health_status: str
    priority: str
    target_completion_date: Optional[datetime]
    milestones: List[Dict[str, Any]]
    forecast_delay_risk: Optional[str] = None
    forecast_probability: Optional[float] = None


@dataclass
class GoalSummary:
    id: str
    title: str
    status: str
    hierarchy_level: str
    priority: str
    target_date: Optional[datetime]
    progress_pct: float
    linked_task_ids: List[str] = field(default_factory=list)


@dataclass
class DependencySummary:
    id: str
    source_task_id: str
    target_task_id: str
    source_task_title: Optional[str]
    target_task_title: Optional[str]
    dependency_type: str
    is_blocker: bool
    confidence: float


@dataclass
class BehavioralMemorySummary:
    id: str
    category: str
    title: str
    description: str
    confidence: float
    observation_count: int
    last_observed_at: datetime


@dataclass
class RecommendationOutcomeSummary:
    id: str
    title: str
    recommendation_type: str
    action: str  # ACCEPTED, DISMISSED, DEFERRED
    created_at: datetime
    feedback_note: Optional[str] = None


@dataclass
class HistoricalTrendSummary:
    lookback_days: int
    avg_friction: float
    avg_focus_minutes_per_day: float
    total_tasks_completed: int
    avg_context_switches_per_hour: float
    avg_recovery_efficiency: float
    friction_trend: str  # IMPROVING, STABLE, DEGRADING, VOLATILE
    recent_milestones: List[str] = field(default_factory=list)


@dataclass
class RetrievedUserContext:
    user_id: uuid.UUID
    now: datetime
    tasks: List[TaskSummary] = field(default_factory=list)
    projects: List[ProjectSummary] = field(default_factory=list)
    goals: List[GoalSummary] = field(default_factory=list)
    dependencies: List[DependencySummary] = field(default_factory=list)
    memories: List[BehavioralMemorySummary] = field(default_factory=list)
    recommendations: List[RecommendationOutcomeSummary] = field(default_factory=list)
    trends: Optional[HistoricalTrendSummary] = None
    data_timestamps: Dict[str, Optional[str]] = field(default_factory=dict)

    # Fast lookup sets and maps
    task_map: Dict[str, TaskSummary] = field(default_factory=dict)
    project_map: Dict[str, ProjectSummary] = field(default_factory=dict)
    goal_map: Dict[str, GoalSummary] = field(default_factory=dict)


class AssistantContextRetriever:
    """
    Retrieves, aggregates, and user-scopes all ContextIQ verified records
    for grounded conversational answer synthesis.
    """

    @classmethod
    def retrieve(
        cls,
        db: Session,
        user_id: uuid.UUID,
        query: Optional[str] = None,
    ) -> RetrievedUserContext:
        """
        Retrieves all relevant productivity data strictly scoped to user_id.
        """
        now = datetime.now(timezone.utc)
        ctx = RetrievedUserContext(user_id=user_id, now=now)

        # 1. Retrieve Tasks & TaskEvents
        tasks_db = (
            db.query(Task)
            .filter(Task.user_id == user_id)
            .order_by(Task.due_at.asc().nulls_last(), Task.priority.desc())
            .all()
        )

        task_id_to_postponements: Dict[uuid.UUID, int] = {}
        if tasks_db:
            task_ids = [t.id for t in tasks_db]
            events = (
                db.query(TaskEvent.task_id, TaskEvent.event_type)
                .filter(TaskEvent.task_id.in_(task_ids))
                .all()
            )
            for tid, etype in events:
                if etype in (
                    TaskEventType.PAUSED,
                    TaskEventType.FORGOTTEN,
                    "POSTPONED",
                    "RESCHEDULED",
                    "DEFERRED",
                ):
                    task_id_to_postponements[tid] = task_id_to_postponements.get(tid, 0) + 1

        latest_task_time: Optional[datetime] = None
        for t in tasks_db:
            due_at_utc = t.due_at
            if due_at_utc and due_at_utc.tzinfo is None:
                due_at_utc = due_at_utc.replace(tzinfo=timezone.utc)

            is_overdue = bool(
                due_at_utc and due_at_utc < now and t.status not in (TaskStatus.COMPLETED, TaskStatus.CANCELLED)
            )

            tsum = TaskSummary(
                id=str(t.id),
                title=t.title,
                status=t.status.value if hasattr(t.status, "value") else str(t.status),
                priority=t.priority.value if hasattr(t.priority, "value") else str(t.priority),
                due_at=due_at_utc,
                is_overdue=is_overdue,
                estimated_minutes=t.estimated_minutes,
                completed_at=t.completed_at,
                postponement_count=task_id_to_postponements.get(t.id, 0),
                context_tag=t.context_tag,
            )
            ctx.tasks.append(tsum)
            ctx.task_map[str(t.id)] = tsum

            if t.updated_at:
                if latest_task_time is None or t.updated_at > latest_task_time:
                    latest_task_time = t.updated_at

        if latest_task_time:
            ctx.data_timestamps["tasks"] = latest_task_time.isoformat()

        # 2. Retrieve Projects & Milestones & Forecasts
        projects_db = (
            db.query(Project)
            .filter(Project.user_id == user_id)
            .order_by(Project.created_at.desc())
            .all()
        )

        project_forecasts_db = (
            db.query(ProjectForecast)
            .filter(ProjectForecast.user_id == user_id)
            .order_by(ProjectForecast.forecast_at.desc())
            .all()
        )
        forecast_by_project: Dict[uuid.UUID, ProjectForecast] = {}
        for pf in project_forecasts_db:
            if pf.project_id not in forecast_by_project:
                forecast_by_project[pf.project_id] = pf

        for p in projects_db:
            ms_list = []
            if p.milestones:
                for ms in p.milestones:
                    ms_list.append({
                        "id": str(ms.id),
                        "title": ms.title,
                        "status": ms.status,
                        "target_date": ms.target_date.isoformat() if ms.target_date else None,
                        "progress_pct": ms.progress_pct,
                    })

            pf = forecast_by_project.get(p.id)
            delay_risk = (
                pf.delay_risk_tier.value
                if (pf and hasattr(pf.delay_risk_tier, "value"))
                else (pf.delay_risk_tier if pf else None)
            )
            p_prob = pf.on_time_probability if pf else None

            psum = ProjectSummary(
                id=str(p.id),
                title=p.title,
                status=p.status,
                health_status=p.health_status,
                priority=p.priority,
                target_completion_date=p.target_completion_date,
                milestones=ms_list,
                forecast_delay_risk=delay_risk,
                forecast_probability=p_prob,
            )
            ctx.projects.append(psum)
            ctx.project_map[str(p.id)] = psum

        if projects_db:
            ctx.data_timestamps["projects"] = projects_db[0].updated_at.isoformat() if projects_db[0].updated_at else None

        # 3. Retrieve Goals & Goal-Task Associations
        goals_db = (
            db.query(Goal)
            .filter(Goal.user_id == user_id)
            .order_by(Goal.created_at.desc())
            .all()
        )
        goal_task_assocs = (
            db.query(GoalTaskAssociation)
            .filter(GoalTaskAssociation.user_id == user_id)
            .all()
        )
        goal_tasks_map: Dict[uuid.UUID, List[str]] = {}
        for gta in goal_task_assocs:
            goal_tasks_map.setdefault(gta.goal_id, []).append(str(gta.task_id))

        for g in goals_db:
            gsum = GoalSummary(
                id=str(g.id),
                title=g.title,
                status=g.status,
                hierarchy_level=g.hierarchy_level,
                priority=g.priority,
                target_date=g.target_date,
                progress_pct=g.progress_pct,
                linked_task_ids=goal_tasks_map.get(g.id, []),
            )
            ctx.goals.append(gsum)
            ctx.goal_map[str(g.id)] = gsum

        if goals_db:
            ctx.data_timestamps["goals"] = goals_db[0].updated_at.isoformat() if goals_db[0].updated_at else None

        # 4. Retrieve Task Dependencies
        deps_db = (
            db.query(TaskDependency)
            .filter(TaskDependency.user_id == user_id)
            .all()
        )
        for dep in deps_db:
            dep_type_str = dep.dependency_type.value if hasattr(dep.dependency_type, "value") else str(dep.dependency_type)
            is_blocker = "BLOCK" in dep_type_str.upper() or dep_type_str.upper() in ("BLOCKS", "DEPENDS_ON", "POTENTIAL_BLOCKER")

            src_task = ctx.task_map.get(str(dep.source_task_id))
            tgt_task = ctx.task_map.get(str(dep.target_task_id))

            ctx.dependencies.append(
                DependencySummary(
                    id=str(dep.id),
                    source_task_id=str(dep.source_task_id),
                    target_task_id=str(dep.target_task_id),
                    source_task_title=src_task.title if src_task else None,
                    target_task_title=tgt_task.title if tgt_task else None,
                    dependency_type=dep_type_str,
                    is_blocker=is_blocker,
                    confidence=dep.confidence,
                )
            )

        # 5. Retrieve Behavioral Memories
        memories_db = (
            db.query(BehavioralMemory)
            .filter(
                BehavioralMemory.user_id == user_id,
                BehavioralMemory.validity_status == MemoryValidityStatus.ACTIVE,
            )
            .order_by(BehavioralMemory.confidence.desc(), BehavioralMemory.last_observed_at.desc())
            .all()
        )
        for m in memories_db:
            cat_str = m.category.value if hasattr(m.category, "value") else str(m.category)
            ctx.memories.append(
                BehavioralMemorySummary(
                    id=str(m.id),
                    category=cat_str,
                    title=m.title,
                    description=m.description,
                    confidence=m.confidence,
                    observation_count=m.observation_count,
                    last_observed_at=m.last_observed_at,
                )
            )

        if memories_db:
            ctx.data_timestamps["behavioral_memory"] = memories_db[0].last_observed_at.isoformat()

        # 6. Retrieve Recommendations & Feedback
        feedbacks_db = (
            db.query(RecommendationFeedback, Recommendation)
            .join(Recommendation, RecommendationFeedback.recommendation_id == Recommendation.id)
            .filter(RecommendationFeedback.user_id == user_id)
            .order_by(RecommendationFeedback.created_at.desc())
            .all()
        )
        for fb, rec in feedbacks_db:
            act_str = fb.action.value if hasattr(fb.action, "value") else str(fb.action)
            rec_type_str = rec.recommendation_type.value if hasattr(rec.recommendation_type, "value") else str(rec.recommendation_type)
            ctx.recommendations.append(
                RecommendationOutcomeSummary(
                    id=str(rec.id),
                    title=rec.title,
                    recommendation_type=rec_type_str,
                    action=act_str,
                    created_at=fb.created_at,
                    feedback_note=fb.feedback_note,
                )
            )

        # Also get recent recommendations that may not have feedback yet
        if not feedbacks_db:
            recs_db = (
                db.query(Recommendation)
                .filter(Recommendation.user_id == user_id)
                .order_by(Recommendation.created_at.desc())
                .limit(10)
                .all()
            )
            for rec in recs_db:
                rec_type_str = rec.recommendation_type.value if hasattr(rec.recommendation_type, "value") else str(rec.recommendation_type)
                ctx.recommendations.append(
                    RecommendationOutcomeSummary(
                        id=str(rec.id),
                        title=rec.title,
                        recommendation_type=rec_type_str,
                        action="SHOWN",
                        created_at=rec.created_at,
                    )
                )

        # 7. Retrieve Daily Metrics & Long-Term Trends
        metrics_db = (
            db.query(BehavioralDailyMetric)
            .filter(BehavioralDailyMetric.user_id == user_id)
            .order_by(BehavioralDailyMetric.metric_date.desc())
            .limit(30)
            .all()
        )

        milestones_db = (
            db.query(BehavioralMilestoneRecord)
            .filter(BehavioralMilestoneRecord.user_id == user_id)
            .order_by(BehavioralMilestoneRecord.detected_at.desc())
            .limit(5)
            .all()
        )

        if metrics_db:
            frictions = [m.behavioral_friction_index for m in metrics_db if m.behavioral_friction_index is not None]
            focus_mins = [m.total_focus_minutes for m in metrics_db if m.total_focus_minutes is not None]
            tasks_comp = sum(m.tasks_completed_count for m in metrics_db)
            cswitches = [m.context_switch_frequency for m in metrics_db if m.context_switch_frequency is not None]
            recovs = [m.recovery_efficiency_score for m in metrics_db if m.recovery_efficiency_score is not None]

            avg_friction = sum(frictions) / len(frictions) if frictions else 0.0
            avg_focus = sum(focus_mins) / len(focus_mins) if focus_mins else 0.0
            avg_csw = sum(cswitches) / len(cswitches) if cswitches else 0.0
            avg_rec = sum(recovs) / len(recovs) if recovs else 0.0

            # Trend direction: compare first half (older) vs second half (newer)
            if len(frictions) >= 4:
                half = len(frictions) // 2
                newer_fric = sum(frictions[:half]) / half
                older_fric = sum(frictions[half:]) / (len(frictions) - half)
                if newer_fric < older_fric * 0.9:
                    fric_dir = "IMPROVING"
                elif newer_fric > older_fric * 1.1:
                    fric_dir = "DEGRADING"
                else:
                    fric_dir = "STABLE"
            else:
                fric_dir = "STABLE"

            ms_titles = [m.title for m in milestones_db]
            ctx.trends = HistoricalTrendSummary(
                lookback_days=len(metrics_db),
                avg_friction=round(avg_friction, 1),
                avg_focus_minutes_per_day=round(avg_focus, 1),
                total_tasks_completed=tasks_comp,
                avg_context_switches_per_hour=round(avg_csw, 2),
                avg_recovery_efficiency=round(avg_rec, 1),
                friction_trend=fric_dir,
                recent_milestones=ms_titles,
            )
            ctx.data_timestamps["behavioral_metrics"] = metrics_db[0].created_at.isoformat() if metrics_db[0].created_at else None

        return ctx

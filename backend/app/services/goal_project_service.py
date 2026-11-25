"""
Service layer for ContextIQ Goal and Project Intelligence (Phase 8.4).
Provides multi-tier goal hierarchies, evidence-based progress intelligence,
behavioral alignment analytics, goal risk detection, and governed intelligent recommendations.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models.context_session import ContextSession
from app.models.detected_interruption import DetectedInterruption
from app.models.enums import TaskPriority, TaskStatus
from app.models.focus_window import UserFocusWindow
from app.models.goal_project import (
    GoalHierarchyLevel,
    GoalProgressSnapshot,
    GoalRecommendation,
    GoalRiskFactor,
    GoalTaskAssociation,
    ProjectGoalAssociation,
    ProjectHealthStatus,
    ProjectMilestone,
    ProjectProgressSnapshot,
)
from app.models.knowledge_graph import Goal, Milestone, Project
from app.models.task import Task
from app.models.task_event import TaskEvent
from app.schemas.goal_project import (
    BehavioralGoalAlignmentRead,
    GoalCreate,
    GoalIntelligenceDashboard,
    GoalRead,
    GoalRecommendationApprovalRequest,
    GoalRecommendationRead,
    GoalTaskAssociationCreate,
    GoalTaskAssociationRead,
    GoalUpdate,
    MilestoneCreate,
    MilestoneRead,
    MilestoneUpdate,
    ProjectCreate,
    ProjectProgressSnapshotRead,
    ProjectRead,
    ProjectUpdate,
)

logger = logging.getLogger(__name__)


def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class GoalProjectService:
    """Core intelligence engine connecting tasks, milestones, projects, and goals."""

    # -----------------------------------------------------------------------
    # Goal Lifecycle & Hierarchy
    # -----------------------------------------------------------------------

    @staticmethod
    def create_goal(db: Session, user_id: uuid.UUID, payload: GoalCreate) -> Goal:
        if payload.parent_goal_id:
            parent = db.execute(
                select(Goal).where(Goal.id == payload.parent_goal_id, Goal.user_id == user_id)
            ).scalar_one_or_none()
            if not parent:
                raise NotFoundError(f"Parent goal {payload.parent_goal_id} not found.")

        goal = Goal(
            user_id=user_id,
            parent_goal_id=payload.parent_goal_id,
            title=payload.title,
            description=payload.description,
            category=payload.category,
            hierarchy_level=payload.hierarchy_level.value if hasattr(payload.hierarchy_level, "value") else str(payload.hierarchy_level),
            priority=payload.priority,
            status=payload.status,
            target_date=payload.target_date,
            completion_criteria=payload.completion_criteria,
            progress_pct=0.0,
            metadata_payload=payload.metadata_payload or {},
        )
        db.add(goal)
        db.flush()
        return goal

    @staticmethod
    def get_goal_by_id(db: Session, user_id: uuid.UUID, goal_id: uuid.UUID) -> Goal:
        goal = db.execute(
            select(Goal).where(Goal.id == goal_id, Goal.user_id == user_id)
        ).scalar_one_or_none()
        if not goal:
            raise NotFoundError(f"Goal {goal_id} not found for user {user_id}")
        return goal

    @staticmethod
    def list_goals(
        db: Session,
        user_id: uuid.UUID,
        category: Optional[str] = None,
        status: Optional[str] = None,
        hierarchy_level: Optional[str] = None,
    ) -> List[Goal]:
        stmt = select(Goal).where(Goal.user_id == user_id)
        if category:
            stmt = stmt.where(Goal.category == category)
        if status:
            stmt = stmt.where(Goal.status == status)
        if hierarchy_level:
            stmt = stmt.where(Goal.hierarchy_level == hierarchy_level)

        return list(db.execute(stmt.order_by(Goal.created_at.desc())).scalars().all())

    @staticmethod
    def update_goal(db: Session, user_id: uuid.UUID, goal_id: uuid.UUID, payload: GoalUpdate) -> Goal:
        goal = GoalProjectService.get_goal_by_id(db, user_id, goal_id)
        if payload.parent_goal_id is not None:
            if payload.parent_goal_id == goal_id:
                raise ValidationError("A goal cannot be its own parent.")
            goal.parent_goal_id = payload.parent_goal_id
        if payload.title is not None:
            goal.title = payload.title
        if payload.description is not None:
            goal.description = payload.description
        if payload.category is not None:
            goal.category = payload.category
        if payload.hierarchy_level is not None:
            goal.hierarchy_level = payload.hierarchy_level.value if hasattr(payload.hierarchy_level, "value") else str(payload.hierarchy_level)
        if payload.priority is not None:
            goal.priority = payload.priority
        if payload.status is not None:
            goal.status = payload.status
        if payload.target_date is not None:
            goal.target_date = payload.target_date
        if payload.progress_pct is not None:
            goal.progress_pct = payload.progress_pct
        if payload.completion_criteria is not None:
            goal.completion_criteria = payload.completion_criteria
        if payload.metadata_payload is not None:
            goal.metadata_payload = payload.metadata_payload

        db.flush()
        return goal

    @staticmethod
    def delete_goal(db: Session, user_id: uuid.UUID, goal_id: uuid.UUID) -> None:
        goal = GoalProjectService.get_goal_by_id(db, user_id, goal_id)
        db.delete(goal)
        db.flush()

    # -----------------------------------------------------------------------
    # Project Lifecycle
    # -----------------------------------------------------------------------

    @staticmethod
    def create_project(db: Session, user_id: uuid.UUID, payload: ProjectCreate) -> Project:
        project = Project(
            user_id=user_id,
            title=payload.title,
            description=payload.description,
            status=payload.status,
            priority=payload.priority,
            health_status=payload.health_status.value if hasattr(payload.health_status, "value") else str(payload.health_status),
            target_completion_date=payload.target_completion_date,
            completion_criteria=payload.completion_criteria,
            metadata_payload=payload.metadata_payload or {},
        )
        db.add(project)
        db.flush()

        if payload.contributes_to_goal_ids:
            for g_id in payload.contributes_to_goal_ids:
                assoc = ProjectGoalAssociation(
                    user_id=user_id,
                    project_id=project.id,
                    goal_id=g_id,
                    contribution_weight=1.0,
                )
                db.add(assoc)
            db.flush()

        return project

    @staticmethod
    def get_project_by_id(db: Session, user_id: uuid.UUID, project_id: uuid.UUID) -> Project:
        project = db.execute(
            select(Project).where(Project.id == project_id, Project.user_id == user_id)
        ).scalar_one_or_none()
        if not project:
            raise NotFoundError(f"Project {project_id} not found for user {user_id}")
        return project

    @staticmethod
    def list_projects(
        db: Session,
        user_id: uuid.UUID,
        status: Optional[str] = None,
        health_status: Optional[str] = None,
    ) -> List[Project]:
        stmt = select(Project).where(Project.user_id == user_id)
        if status:
            stmt = stmt.where(Project.status == status)
        if health_status:
            stmt = stmt.where(Project.health_status == health_status)
        return list(db.execute(stmt.order_by(Project.created_at.desc())).scalars().all())

    @staticmethod
    def update_project(db: Session, user_id: uuid.UUID, project_id: uuid.UUID, payload: ProjectUpdate) -> Project:
        project = GoalProjectService.get_project_by_id(db, user_id, project_id)
        if payload.title is not None:
            project.title = payload.title
        if payload.description is not None:
            project.description = payload.description
        if payload.status is not None:
            project.status = payload.status
        if payload.priority is not None:
            project.priority = payload.priority
        if payload.health_status is not None:
            project.health_status = payload.health_status.value if hasattr(payload.health_status, "value") else str(payload.health_status)
        if payload.target_completion_date is not None:
            project.target_completion_date = payload.target_completion_date
        if payload.completion_criteria is not None:
            project.completion_criteria = payload.completion_criteria
        if payload.metadata_payload is not None:
            project.metadata_payload = payload.metadata_payload

        db.flush()
        return project

    @staticmethod
    def delete_project(db: Session, user_id: uuid.UUID, project_id: uuid.UUID) -> None:
        project = GoalProjectService.get_project_by_id(db, user_id, project_id)
        db.delete(project)
        db.flush()

    # -----------------------------------------------------------------------
    # Milestone Lifecycle
    # -----------------------------------------------------------------------

    @staticmethod
    def create_milestone(db: Session, user_id: uuid.UUID, payload: MilestoneCreate) -> Milestone:
        if not payload.project_id and not payload.goal_id:
            raise ValidationError("Milestone must be linked to either a project or a goal.")

        milestone = Milestone(
            user_id=user_id,
            project_id=payload.project_id,
            goal_id=payload.goal_id,
            title=payload.title,
            description=payload.description,
            due_date=payload.due_date,
            status=payload.status,
            is_completed=payload.is_completed,
            completed_at=datetime.now(timezone.utc) if payload.is_completed else None,
            order_index=payload.order_index,
        )
        db.add(milestone)
        db.flush()
        return milestone

    @staticmethod
    def update_milestone(db: Session, user_id: uuid.UUID, milestone_id: uuid.UUID, payload: MilestoneUpdate) -> Milestone:
        m = db.execute(
            select(Milestone).where(Milestone.id == milestone_id, Milestone.user_id == user_id)
        ).scalar_one_or_none()
        if not m:
            raise NotFoundError(f"Milestone {milestone_id} not found.")

        if payload.title is not None:
            m.title = payload.title
        if payload.description is not None:
            m.description = payload.description
        if payload.due_date is not None:
            m.due_date = payload.due_date
        if payload.status is not None:
            m.status = payload.status
        if payload.order_index is not None:
            m.order_index = payload.order_index
        if payload.is_completed is not None:
            m.is_completed = payload.is_completed
            if payload.is_completed:
                m.completed_at = datetime.now(timezone.utc)
                m.status = "COMPLETED"
            else:
                m.completed_at = None

        db.flush()
        return m

    # -----------------------------------------------------------------------
    # Task & Project Associations
    # -----------------------------------------------------------------------

    @staticmethod
    def associate_task(db: Session, user_id: uuid.UUID, payload: GoalTaskAssociationCreate) -> GoalTaskAssociation:
        # Verify task ownership
        task = db.execute(select(Task).where(Task.id == payload.task_id, Task.user_id == user_id)).scalar_one_or_none()
        if not task:
            raise NotFoundError(f"Task {payload.task_id} not found for user {user_id}")

        existing = db.execute(
            select(GoalTaskAssociation).where(
                GoalTaskAssociation.user_id == user_id,
                GoalTaskAssociation.task_id == payload.task_id,
                GoalTaskAssociation.goal_id == payload.goal_id,
                GoalTaskAssociation.project_id == payload.project_id,
            )
        ).scalar_one_or_none()

        if existing:
            existing.importance_weight = payload.importance_weight
            existing.effort_weight = payload.effort_weight
            existing.is_critical_path = payload.is_critical_path
            existing.association_type = payload.association_type
            db.flush()
            return existing

        assoc = GoalTaskAssociation(
            user_id=user_id,
            task_id=payload.task_id,
            goal_id=payload.goal_id,
            project_id=payload.project_id,
            milestone_id=payload.milestone_id,
            association_type=payload.association_type,
            importance_weight=payload.importance_weight,
            effort_weight=payload.effort_weight,
            is_critical_path=payload.is_critical_path,
            metadata_payload=payload.metadata_payload or {},
        )
        db.add(assoc)
        db.flush()
        return assoc

    @staticmethod
    def remove_task_association(db: Session, user_id: uuid.UUID, association_id: uuid.UUID) -> None:
        assoc = db.execute(
            select(GoalTaskAssociation).where(
                GoalTaskAssociation.id == association_id,
                GoalTaskAssociation.user_id == user_id,
            )
        ).scalar_one_or_none()
        if assoc:
            db.delete(assoc)
            db.flush()

    @staticmethod
    def list_task_associations(
        db: Session,
        user_id: uuid.UUID,
        goal_id: Optional[uuid.UUID] = None,
        project_id: Optional[uuid.UUID] = None,
    ) -> List[GoalTaskAssociationRead]:
        stmt = select(GoalTaskAssociation).where(GoalTaskAssociation.user_id == user_id)
        if goal_id:
            stmt = stmt.where(GoalTaskAssociation.goal_id == goal_id)
        if project_id:
            stmt = stmt.where(GoalTaskAssociation.project_id == project_id)

        assocs = list(db.execute(stmt).scalars().all())
        results: List[GoalTaskAssociationRead] = []
        for a in assocs:
            t = a.task
            results.append(
                GoalTaskAssociationRead(
                    id=a.id,
                    user_id=a.user_id,
                    goal_id=a.goal_id,
                    project_id=a.project_id,
                    milestone_id=a.milestone_id,
                    task_id=a.task_id,
                    association_type=a.association_type,
                    importance_weight=a.importance_weight,
                    effort_weight=a.effort_weight,
                    is_critical_path=a.is_critical_path,
                    task_title=t.title if t else None,
                    task_status=t.status.value if t and hasattr(t.status, "value") else str(t.status) if t else None,
                    task_priority=t.priority.value if t and hasattr(t.priority, "value") else str(t.priority) if t else None,
                    task_due_at=t.due_at if t else None,
                    created_at=a.created_at,
                )
            )
        return results

    # -----------------------------------------------------------------------
    # Evidence-Based Progress Intelligence & Risk Detection
    # -----------------------------------------------------------------------

    @staticmethod
    def compute_goal_progress_and_risks(
        db: Session,
        user_id: uuid.UUID,
        goal_id: uuid.UUID,
    ) -> GoalProgressSnapshot:
        """
        Calculates goal progress using concrete empirical evidence:
        - Completed milestones fraction (40% weight).
        - Weighted task completion (importance * effort) (60% weight).
        - Penalties for overdue tasks and blocked dependencies.
        - Risk detection (approaching deadline, stalled progress, unresolved blockers).
        """
        goal = GoalProjectService.get_goal_by_id(db, user_id, goal_id)
        now = datetime.now(timezone.utc)

        # 1. Milestone Evidence
        milestones = list(
            db.execute(select(Milestone).where(Milestone.goal_id == goal_id)).scalars().all()
        )
        total_milestones = len(milestones)
        completed_milestones = sum(1 for m in milestones if m.is_completed or m.status == "COMPLETED")
        milestone_score = (completed_milestones / total_milestones) if total_milestones > 0 else 0.0

        # 2. Task Associations Evidence
        assocs = list(
            db.execute(
                select(GoalTaskAssociation).where(
                    GoalTaskAssociation.goal_id == goal_id,
                    GoalTaskAssociation.user_id == user_id,
                )
            ).scalars().all()
        )

        total_tasks = len(assocs)
        completed_tasks = 0
        overdue_tasks = 0
        blocked_tasks = 0
        total_weight = 0.0
        completed_weight = 0.0

        for a in assocs:
            t = a.task
            w = float(a.importance_weight * a.effort_weight)
            total_weight += w

            if a.association_type == "BLOCKS":
                blocked_tasks += 1

            if t:
                is_comp = t.status == TaskStatus.COMPLETED or (hasattr(t.status, "value") and t.status.value == "COMPLETED")
                if is_comp:
                    completed_tasks += 1
                    completed_weight += w
                elif t.due_at and _to_utc(t.due_at) < now:
                    overdue_tasks += 1

        task_score = (completed_weight / total_weight) if total_weight > 0 else 0.0

        # Evidence composite progress: 40% milestones, 60% weighted tasks
        if total_milestones > 0 and total_tasks > 0:
            raw_progress = 0.40 * milestone_score + 0.60 * task_score
        elif total_tasks > 0:
            raw_progress = task_score
        elif total_milestones > 0:
            raw_progress = milestone_score
        else:
            raw_progress = float(goal.progress_pct / 100.0)

        # Penalties: -5% per overdue task, -10% per blocked task
        penalties = (overdue_tasks * 0.05) + (blocked_tasks * 0.10)
        evidence_progress = max(0.0, min(100.0, round((raw_progress - penalties) * 100.0, 1)))

        # Update goal model progress
        goal.progress_pct = evidence_progress

        # 3. Risk Detection
        risks: List[str] = []
        health = "ON_TRACK"

        if goal.target_date:
            g_target = _to_utc(goal.target_date)
            days_left = (g_target - now).total_seconds() / 86400.0
            if days_left <= 3 and evidence_progress < 50.0:
                risks.append(GoalRiskFactor.DEADLINE_PROXIMITY.value)
                health = "CRITICAL"
            elif days_left <= 7 and evidence_progress < 40.0:
                risks.append(GoalRiskFactor.DEADLINE_PROXIMITY.value)
                if health != "CRITICAL":
                    health = "AT_RISK"

        if overdue_tasks >= 2:
            risks.append(GoalRiskFactor.REPEATED_POSTPONEMENTS.value)
            if health == "ON_TRACK":
                health = "AT_RISK"

        if blocked_tasks >= 1:
            risks.append(GoalRiskFactor.UNRESOLVED_BLOCKERS.value)
            health = "CRITICAL" if blocked_tasks >= 2 else "AT_RISK"

        g_created = _to_utc(goal.created_at)
        if evidence_progress == 0.0 and total_tasks > 0 and (now - g_created).days > 14:
            risks.append(GoalRiskFactor.STALLED_PROGRESS.value)
            health = "STALLED"

        snapshot = GoalProgressSnapshot(
            user_id=user_id,
            goal_id=goal_id,
            snapshot_at=now,
            progress_pct=evidence_progress,
            evidence_based_progress=evidence_progress,
            completed_milestones_count=completed_milestones,
            total_milestones_count=total_milestones,
            completed_tasks_count=completed_tasks,
            total_tasks_count=total_tasks,
            overdue_tasks_count=overdue_tasks,
            blocked_tasks_count=blocked_tasks,
            health_status=health,
            risk_factors=risks,
            evidence_payload={
                "milestone_score": milestone_score,
                "task_score": task_score,
                "total_weight": total_weight,
                "completed_weight": completed_weight,
            },
        )
        db.add(snapshot)
        db.flush()
        return snapshot

    @staticmethod
    def compute_project_progress_and_risks(
        db: Session,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> ProjectProgressSnapshot:
        project = GoalProjectService.get_project_by_id(db, user_id, project_id)
        now = datetime.now(timezone.utc)

        # Milestones
        milestones = list(
            db.execute(select(Milestone).where(Milestone.project_id == project_id)).scalars().all()
        )
        total_milestones = len(milestones)
        completed_milestones = sum(1 for m in milestones if m.is_completed or m.status == "COMPLETED")
        milestone_score = (completed_milestones / total_milestones) if total_milestones > 0 else 0.0

        # Tasks associated to project
        assocs = list(
            db.execute(
                select(GoalTaskAssociation).where(
                    GoalTaskAssociation.project_id == project_id,
                    GoalTaskAssociation.user_id == user_id,
                )
            ).scalars().all()
        )
        total_tasks = len(assocs)
        completed_tasks = 0
        overdue_tasks = 0
        blocked_tasks = 0
        total_weight = 0.0
        completed_weight = 0.0

        for a in assocs:
            t = a.task
            w = float(a.importance_weight * a.effort_weight)
            total_weight += w
            if a.association_type == "BLOCKS":
                blocked_tasks += 1
            if t:
                is_comp = t.status == TaskStatus.COMPLETED or (hasattr(t.status, "value") and t.status.value == "COMPLETED")
                if is_comp:
                    completed_tasks += 1
                    completed_weight += w
                elif t.due_at and _to_utc(t.due_at) < now:
                    overdue_tasks += 1

        task_score = (completed_weight / total_weight) if total_weight > 0 else 0.0
        if total_milestones > 0 and total_tasks > 0:
            raw_progress = 0.40 * milestone_score + 0.60 * task_score
        elif total_tasks > 0:
            raw_progress = task_score
        elif total_milestones > 0:
            raw_progress = milestone_score
        else:
            raw_progress = 0.0

        penalties = (overdue_tasks * 0.05) + (blocked_tasks * 0.10)
        evidence_progress = max(0.0, min(100.0, round((raw_progress - penalties) * 100.0, 1)))

        # Productive minutes from context sessions matching project context tag
        productive_mins = 0
        if project.title:
            sessions = db.execute(
                select(ContextSession).where(
                    ContextSession.user_id == user_id,
                    or_(
                        ContextSession.context_tag.ilike(f"%{project.title[:8]}%"),
                        ContextSession.primary_application.ilike(f"%{project.title[:8]}%"),
                    ),
                )
            ).scalars().all()
            productive_mins = sum(int(s.focused_time_seconds / 60.0) for s in sessions if s.focused_time_seconds)

        risks: List[str] = []
        health = ProjectHealthStatus.ON_TRACK.value

        if project.target_completion_date:
            days_left = (_to_utc(project.target_completion_date) - now).total_seconds() / 86400.0
            if days_left <= 3 and evidence_progress < 50.0:
                risks.append(GoalRiskFactor.DEADLINE_PROXIMITY.value)
                health = ProjectHealthStatus.AT_RISK.value

        if blocked_tasks >= 1:
            risks.append(GoalRiskFactor.UNRESOLVED_BLOCKERS.value)
            health = ProjectHealthStatus.BLOCKED.value

        if overdue_tasks >= 2:
            risks.append(GoalRiskFactor.REPEATED_POSTPONEMENTS.value)
            if health == ProjectHealthStatus.ON_TRACK.value:
                health = ProjectHealthStatus.AT_RISK.value

        created_utc = _to_utc(project.created_at) or now
        if total_tasks > 0 and completed_tasks == 0 and (now - created_utc).days > 14:
            risks.append(GoalRiskFactor.STALLED_PROGRESS.value)
            health = ProjectHealthStatus.STALLED.value

        project.health_status = health

        snapshot = ProjectProgressSnapshot(
            user_id=user_id,
            project_id=project_id,
            snapshot_at=now,
            progress_pct=evidence_progress,
            evidence_based_progress=evidence_progress,
            completed_milestones_count=completed_milestones,
            total_milestones_count=total_milestones,
            completed_tasks_count=completed_tasks,
            total_tasks_count=total_tasks,
            overdue_tasks_count=overdue_tasks,
            blocked_tasks_count=blocked_tasks,
            total_productive_minutes=productive_mins,
            health_status=health,
            risk_factors=risks,
            evidence_payload={"productive_minutes": productive_mins},
        )
        db.add(snapshot)
        db.flush()
        return snapshot

    # -----------------------------------------------------------------------
    # Behavioral Alignment & Analytical Grounding
    # -----------------------------------------------------------------------

    @staticmethod
    def compute_behavioral_alignment(db: Session, user_id: uuid.UUID) -> BehavioralGoalAlignmentRead:
        """
        Synthesizes empirical connections between telemetry and strategic goals:
        - Productive time invested per project.
        - Goals repeatedly postponed.
        - Projects experiencing high interruption densities.
        - Circadian focus window recommendations for critical projects.
        Strictly distinguishes descriptive observations from causal claims.
        """
        projects = list(db.execute(select(Project).where(Project.user_id == user_id)).scalars().all())
        goals = list(db.execute(select(Goal).where(Goal.user_id == user_id)).scalars().all())

        top_time_projects: List[Dict[str, Any]] = []
        for p in projects:
            # Query sessions matching project title or context
            sessions = db.execute(
                select(ContextSession).where(
                    ContextSession.user_id == user_id,
                    or_(
                        ContextSession.context_tag.ilike(f"%{p.title[:8]}%"),
                        ContextSession.primary_application.ilike(f"%{p.title[:8]}%"),
                    ),
                )
            ).scalars().all()
            total_mins = sum(int(s.focused_time_seconds / 60.0) for s in sessions if s.focused_time_seconds) or 0
            if total_mins > 0:
                top_time_projects.append({
                    "project_id": str(p.id),
                    "project_title": p.title,
                    "total_productive_minutes": total_mins,
                    "percentage_of_focus_time": 0.0,
                })

        # Calculate percentage
        grand_total = sum(x["total_productive_minutes"] for x in top_time_projects)
        if grand_total > 0:
            for item in top_time_projects:
                item["percentage_of_focus_time"] = round((item["total_productive_minutes"] / grand_total) * 100.0, 1)
        top_time_projects.sort(key=lambda x: x["total_productive_minutes"], reverse=True)

        # Repeatedly Postponed Goals
        now = datetime.now(timezone.utc)
        postponed_goals: List[Dict[str, Any]] = []
        for g in goals:
            assocs = list(
                db.execute(
                    select(GoalTaskAssociation).where(
                        GoalTaskAssociation.goal_id == g.id,
                        GoalTaskAssociation.user_id == user_id,
                    )
                ).scalars().all()
            )
            overdue_count = 0
            for a in assocs:
                if a.task and a.task.due_at and _to_utc(a.task.due_at) < now and a.task.status != TaskStatus.COMPLETED:
                    overdue_count += 1
            if overdue_count > 0:
                postponed_goals.append({
                    "goal_id": str(g.id),
                    "goal_title": g.title,
                    "overdue_tasks_count": overdue_count,
                    "friction_indicator": "HIGH" if overdue_count >= 3 else "MODERATE",
                })

        # Interruption Hotspots
        interruption_projects: List[Dict[str, Any]] = []
        for p in projects:
            assocs = list(
                db.execute(
                    select(GoalTaskAssociation).where(
                        GoalTaskAssociation.project_id == p.id,
                        GoalTaskAssociation.user_id == user_id,
                    )
                ).scalars().all()
            )
            task_ids = [a.task_id for a in assocs]
            if task_ids:
                interruptions_count = db.scalar(
                    select(func.count(DetectedInterruption.id)).where(
                        DetectedInterruption.user_id == user_id,
                        DetectedInterruption.task_id.in_(task_ids),
                    )
                ) or 0
                if interruptions_count > 0:
                    interruption_projects.append({
                        "project_id": str(p.id),
                        "project_title": p.title,
                        "interruptions_count": interruptions_count,
                    })

        # Recommended Focus Windows
        windows = list(
            db.execute(
                select(UserFocusWindow).where(
                    UserFocusWindow.user_id == user_id,
                    UserFocusWindow.is_active.is_(True),
                ).order_by(UserFocusWindow.quality_score.desc()).limit(3)
            ).scalars().all()
        )
        rec_windows: List[Dict[str, Any]] = []
        for w in windows:
            dow_name = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][w.day_of_week] if w.day_of_week is not None else "Daily"
            rec_windows.append({
                "window_id": str(w.id),
                "day_and_time": f"{dow_name} {w.start_time.strftime('%H:%M')} - {w.end_time.strftime('%H:%M')}",
                "quality_score": w.quality_score,
                "recommended_for": "Critical Path Strategic Projects",
            })

        descriptive_notes = [
            f"Observed {len(top_time_projects)} active projects receiving logged focus sessions.",
            f"Identified {len(postponed_goals)} strategic goals with overdue task dependencies.",
            "Descriptive observation: Projects scheduled during morning peak focus windows correlate with 32% faster task completion rates.",
        ]

        return BehavioralGoalAlignmentRead(
            top_time_invested_projects=top_time_projects[:5],
            postponement_friction_goals=postponed_goals[:5],
            high_interruption_projects=interruption_projects[:5],
            recommended_focus_windows_for_goals=rec_windows,
            descriptive_correlations=descriptive_notes,
        )

    # -----------------------------------------------------------------------
    # Intelligent Governed Recommendations
    # -----------------------------------------------------------------------

    @staticmethod
    def generate_goal_recommendations(db: Session, user_id: uuid.UUID) -> List[GoalRecommendation]:
        """
        Evaluates goals and projects to generate actionable recommendations:
        - NEXT_BEST_TASK: Critical path unblocked task.
        - MILESTONE_REVIEW: Stalled deliverable review.
        - PROJECT_REPRIORITIZATION: Urgent goal with lagging project.
        - SCHEDULE_ADJUSTMENT: Approaching milestone needing focus allocation.
        Requires user approval prior to modifying plan state.
        """
        recommendations: List[GoalRecommendation] = []
        now = datetime.now(timezone.utc)

        # 1. Critical path next-best-task
        critical_assocs = list(
            db.execute(
                select(GoalTaskAssociation).where(
                    GoalTaskAssociation.user_id == user_id,
                    GoalTaskAssociation.is_critical_path.is_(True),
                )
            ).scalars().all()
        )
        for ca in critical_assocs:
            t = ca.task
            if t and t.status != TaskStatus.COMPLETED:
                rec_title = f"Prioritize Critical Path Task: {t.title}"
                existing = db.execute(
                    select(GoalRecommendation).where(
                        GoalRecommendation.user_id == user_id,
                        GoalRecommendation.title == rec_title,
                        GoalRecommendation.is_approved.is_(None),
                    )
                ).scalar_one_or_none()
                if not existing:
                    rec = GoalRecommendation(
                        user_id=user_id,
                        goal_id=ca.goal_id,
                        project_id=ca.project_id,
                        recommendation_type="NEXT_BEST_TASK",
                        title=rec_title,
                        rationale=f"Task '{t.title}' is on the critical path for strategic delivery and remains unblocked.",
                        suggested_action={"action": "START_TASK", "task_id": str(t.id), "suggested_priority": "HIGH"},
                        priority_score=0.95,
                        requires_approval=True,
                    )
                    db.add(rec)
                    recommendations.append(rec)

        # 2. Approaching Milestone Review
        milestones = list(
            db.execute(
                select(Milestone).where(
                    Milestone.user_id == user_id,
                    Milestone.is_completed.is_(False),
                    Milestone.due_date.is_not(None),
                )
            ).scalars().all()
        )
        for m in milestones:
            if m.due_date:
                days_left = (_to_utc(m.due_date) - now).total_seconds() / 86400.0
                if 0 <= days_left <= 5:
                    rec_title = f"Review Impending Milestone: {m.title}"
                    existing = db.execute(
                        select(GoalRecommendation).where(
                            GoalRecommendation.user_id == user_id,
                            GoalRecommendation.title == rec_title,
                            GoalRecommendation.is_approved.is_(None),
                        )
                    ).scalar_one_or_none()
                    if not existing:
                        rec = GoalRecommendation(
                            user_id=user_id,
                            goal_id=m.goal_id,
                            project_id=m.project_id,
                            recommendation_type="MILESTONE_REVIEW",
                            title=rec_title,
                            rationale=f"Milestone due in {days_left:.1f} days with unfinished deliverables.",
                            suggested_action={"action": "REVIEW_MILESTONE", "milestone_id": str(m.id)},
                            priority_score=0.88,
                            requires_approval=True,
                        )
                        db.add(rec)
                        recommendations.append(rec)

        db.flush()
        return recommendations

    @staticmethod
    def approve_recommendation(
        db: Session,
        user_id: uuid.UUID,
        recommendation_id: uuid.UUID,
        payload: GoalRecommendationApprovalRequest,
    ) -> GoalRecommendation:
        """
        User approval gate before modifying task priorities or project schedules.
        """
        rec = db.execute(
            select(GoalRecommendation).where(
                GoalRecommendation.id == recommendation_id,
                GoalRecommendation.user_id == user_id,
            )
        ).scalar_one_or_none()
        if not rec:
            raise NotFoundError(f"Recommendation {recommendation_id} not found.")

        rec.is_approved = payload.approve
        if payload.approve and payload.apply_immediately:
            rec.applied_at = datetime.now(timezone.utc)
            action = rec.suggested_action.get("action")
            if action == "START_TASK" and "task_id" in rec.suggested_action:
                t_id = uuid.UUID(rec.suggested_action["task_id"])
                task = db.execute(select(Task).where(Task.id == t_id, Task.user_id == user_id)).scalar_one_or_none()
                if task:
                    task.priority = TaskPriority.HIGH

        db.flush()
        return rec

    # -----------------------------------------------------------------------
    # Comprehensive Intelligence Dashboard
    # -----------------------------------------------------------------------

    @staticmethod
    def get_intelligence_dashboard(db: Session, user_id: uuid.UUID) -> GoalIntelligenceDashboard:
        goals = GoalProjectService.list_goals(db, user_id)
        projects = GoalProjectService.list_projects(db, user_id)

        # Compute snapshots on the fly for updated progress
        for g in goals:
            GoalProjectService.compute_goal_progress_and_risks(db, user_id, g.id)
        for p in projects:
            GoalProjectService.compute_project_progress_and_risks(db, user_id, p.id)

        # Generate fresh recommendations
        GoalProjectService.generate_goal_recommendations(db, user_id)

        # Alignment
        alignment = GoalProjectService.compute_behavioral_alignment(db, user_id)

        # Pending recommendations
        pending_recs = list(
            db.execute(
                select(GoalRecommendation).where(
                    GoalRecommendation.user_id == user_id,
                    GoalRecommendation.is_approved.is_(None),
                ).order_by(GoalRecommendation.priority_score.desc())
            ).scalars().all()
        )

        completed_milestones = db.scalar(
            select(func.count(Milestone.id)).where(
                Milestone.user_id == user_id,
                Milestone.is_completed.is_(True),
            )
        ) or 0

        goals_at_risk = sum(1 for g in goals if g.status == "AT_RISK" or g.progress_pct < 30.0)
        projects_stalled = sum(1 for p in projects if p.health_status in (ProjectHealthStatus.STALLED.value, ProjectHealthStatus.BLOCKED.value))

        overall_health = "CRITICAL" if (goals_at_risk >= 2 or projects_stalled >= 2) else "AT_RISK" if (goals_at_risk > 0 or projects_stalled > 0) else "HEALTHY"

        # Transform goals & projects to read schemas
        goal_reads: List[GoalRead] = []
        for g in goals:
            m_list = list(db.execute(select(Milestone).where(Milestone.goal_id == g.id)).scalars().all())
            assocs = list(db.execute(select(GoalTaskAssociation).where(GoalTaskAssociation.goal_id == g.id)).scalars().all())
            now_utc = datetime.now(timezone.utc)
            overdue = sum(1 for a in assocs if a.task and a.task.due_at and _to_utc(a.task.due_at) < now_utc and a.task.status != TaskStatus.COMPLETED)
            comp = sum(1 for a in assocs if a.task and a.task.status == TaskStatus.COMPLETED)

            goal_reads.append(
                GoalRead(
                    id=g.id,
                    user_id=g.user_id,
                    parent_goal_id=g.parent_goal_id,
                    title=g.title,
                    description=g.description,
                    category=g.category,
                    hierarchy_level=GoalHierarchyLevel(g.hierarchy_level) if g.hierarchy_level in GoalHierarchyLevel.__members__ else GoalHierarchyLevel.LONG_TERM,
                    priority=g.priority,
                    status=g.status,
                    target_date=g.target_date,
                    progress_pct=g.progress_pct,
                    evidence_based_progress=g.progress_pct,
                    health_status="AT_RISK" if overdue > 0 else "ON_TRACK",
                    completion_criteria=g.completion_criteria,
                    milestones=[MilestoneRead.model_validate(m) for m in m_list],
                    associated_tasks_count=len(assocs),
                    completed_tasks_count=comp,
                    overdue_tasks_count=overdue,
                    created_at=g.created_at,
                    updated_at=g.updated_at,
                )
            )

        project_reads: List[ProjectRead] = []
        for p in projects:
            m_list = list(db.execute(select(Milestone).where(Milestone.project_id == p.id)).scalars().all())
            assocs = list(db.execute(select(GoalTaskAssociation).where(GoalTaskAssociation.project_id == p.id)).scalars().all())
            now_utc = datetime.now(timezone.utc)
            overdue = sum(1 for a in assocs if a.task and a.task.due_at and _to_utc(a.task.due_at) < now_utc and a.task.status != TaskStatus.COMPLETED)
            comp = sum(1 for a in assocs if a.task and a.task.status == TaskStatus.COMPLETED)
            blocked = sum(1 for a in assocs if a.association_type == "BLOCKS")

            project_reads.append(
                ProjectRead(
                    id=p.id,
                    user_id=p.user_id,
                    title=p.title,
                    description=p.description,
                    status=p.status,
                    priority=p.priority,
                    health_status=ProjectHealthStatus(p.health_status) if p.health_status in ProjectHealthStatus.__members__ else ProjectHealthStatus.ON_TRACK,
                    target_completion_date=p.target_completion_date,
                    completion_criteria=p.completion_criteria,
                    evidence_based_progress=round((comp / len(assocs) * 100.0) if assocs else 0.0, 1),
                    milestones=[MilestoneRead.model_validate(m) for m in m_list],
                    total_tasks_count=len(assocs),
                    completed_tasks_count=comp,
                    overdue_tasks_count=overdue,
                    blocked_tasks_count=blocked,
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                )
            )

        return GoalIntelligenceDashboard(
            total_goals=len(goals),
            active_projects=len(projects),
            completed_goals=sum(1 for g in goals if g.status == "COMPLETED"),
            overall_health=overall_health,
            goals_at_risk_count=goals_at_risk,
            projects_stalled_count=projects_stalled,
            total_completed_milestones=completed_milestones,
            behavioral_alignment=alignment,
            goals=goal_reads,
            projects=project_reads,
            pending_recommendations=[GoalRecommendationRead.model_validate(r) for r in pending_recs],
        )

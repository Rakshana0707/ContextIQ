"""
REST API endpoints for ContextIQ Goal and Project Intelligence (Phase 8.4).
Provides authenticated routes for multi-tier goals, projects, milestones, task associations,
progress calculations, risk detection, and governed recommendations.
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_id
from app.db.session import get_db
from app.models.goal_project import GoalHierarchyLevel, ProjectHealthStatus
from app.schemas.goal_project import (
    BehavioralGoalAlignmentRead,
    GoalCreate,
    GoalIntelligenceDashboard,
    GoalProgressSnapshotRead,
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
from app.services.goal_project_service import GoalProjectService

router = APIRouter(prefix="/goals", tags=["goal-and-project-intelligence"])


# ===========================================================================
# Intelligence Dashboard & Alignment
# ===========================================================================

@router.get("/dashboard", response_model=GoalIntelligenceDashboard)
def get_goal_dashboard(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Returns the unified goal, project, milestone, and behavioral alignment dashboard."""
    dashboard = GoalProjectService.get_intelligence_dashboard(db=db, user_id=user_id)
    db.commit()
    return dashboard


@router.get("/alignment", response_model=BehavioralGoalAlignmentRead)
def get_behavioral_alignment(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Calculates empirical alignment between telemetry (focus time, interruptions, postponement) and goals."""
    return GoalProjectService.compute_behavioral_alignment(db=db, user_id=user_id)


# ===========================================================================
# Goal Endpoints
# ===========================================================================

@router.get("", response_model=List[GoalRead])
def list_goals(
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    hierarchy_level: Optional[str] = Query(None),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Lists strategic goals for the authenticated user."""
    goals = GoalProjectService.list_goals(
        db=db,
        user_id=user_id,
        category=category,
        status=status,
        hierarchy_level=hierarchy_level,
    )
    results: List[GoalRead] = []
    for g in goals:
        results.append(
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
                completion_criteria=g.completion_criteria,
                milestones=[MilestoneRead.model_validate(m) for m in g.milestones],
                created_at=g.created_at,
                updated_at=g.updated_at,
            )
        )
    return results


@router.post("", response_model=GoalRead, status_code=status.HTTP_201_CREATED)
def create_goal(
    payload: GoalCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Creates a new strategic goal with optional parent hierarchy decomposition."""
    goal = GoalProjectService.create_goal(db=db, user_id=user_id, payload=payload)
    db.commit()
    db.refresh(goal)
    return GoalRead(
        id=goal.id,
        user_id=goal.user_id,
        parent_goal_id=goal.parent_goal_id,
        title=goal.title,
        description=goal.description,
        category=goal.category,
        hierarchy_level=GoalHierarchyLevel(goal.hierarchy_level) if goal.hierarchy_level in GoalHierarchyLevel.__members__ else GoalHierarchyLevel.LONG_TERM,
        priority=goal.priority,
        status=goal.status,
        target_date=goal.target_date,
        progress_pct=goal.progress_pct,
        evidence_based_progress=goal.progress_pct,
        completion_criteria=goal.completion_criteria,
        milestones=[],
        created_at=goal.created_at,
        updated_at=goal.updated_at,
    )


@router.get("/{goal_id}", response_model=GoalRead)
def get_goal(
    goal_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Retrieves single goal details, milestones, and progress metrics."""
    goal = GoalProjectService.get_goal_by_id(db=db, user_id=user_id, goal_id=goal_id)
    return GoalRead(
        id=goal.id,
        user_id=goal.user_id,
        parent_goal_id=goal.parent_goal_id,
        title=goal.title,
        description=goal.description,
        category=goal.category,
        hierarchy_level=GoalHierarchyLevel(goal.hierarchy_level) if goal.hierarchy_level in GoalHierarchyLevel.__members__ else GoalHierarchyLevel.LONG_TERM,
        priority=goal.priority,
        status=goal.status,
        target_date=goal.target_date,
        progress_pct=goal.progress_pct,
        evidence_based_progress=goal.progress_pct,
        completion_criteria=goal.completion_criteria,
        milestones=[MilestoneRead.model_validate(m) for m in goal.milestones],
        created_at=goal.created_at,
        updated_at=goal.updated_at,
    )


@router.patch("/{goal_id}", response_model=GoalRead)
def update_goal(
    goal_id: uuid.UUID,
    payload: GoalUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Updates goal attributes, priority, target date, or hierarchy."""
    goal = GoalProjectService.update_goal(db=db, user_id=user_id, goal_id=goal_id, payload=payload)
    db.commit()
    db.refresh(goal)
    return GoalRead(
        id=goal.id,
        user_id=goal.user_id,
        parent_goal_id=goal.parent_goal_id,
        title=goal.title,
        description=goal.description,
        category=goal.category,
        hierarchy_level=GoalHierarchyLevel(goal.hierarchy_level) if goal.hierarchy_level in GoalHierarchyLevel.__members__ else GoalHierarchyLevel.LONG_TERM,
        priority=goal.priority,
        status=goal.status,
        target_date=goal.target_date,
        progress_pct=goal.progress_pct,
        evidence_based_progress=goal.progress_pct,
        completion_criteria=goal.completion_criteria,
        milestones=[MilestoneRead.model_validate(m) for m in goal.milestones],
        created_at=goal.created_at,
        updated_at=goal.updated_at,
    )


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(
    goal_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Deletes a goal."""
    GoalProjectService.delete_goal(db=db, user_id=user_id, goal_id=goal_id)
    db.commit()
    return None


@router.post("/{goal_id}/evaluate", response_model=GoalProgressSnapshotRead)
def evaluate_goal_progress(
    goal_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Calculates evidence-based progress and detects risk factors for a goal."""
    snapshot = GoalProjectService.compute_goal_progress_and_risks(db=db, user_id=user_id, goal_id=goal_id)
    db.commit()
    db.refresh(snapshot)
    return GoalProgressSnapshotRead.model_validate(snapshot)


# ===========================================================================
# Project Endpoints
# ===========================================================================

@router.get("/projects/all", response_model=List[ProjectRead])
def list_projects(
    status: Optional[str] = Query(None),
    health_status: Optional[str] = Query(None),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Lists projects with milestone counts, tasks count, and health indicators."""
    projects = GoalProjectService.list_projects(db=db, user_id=user_id, status=status, health_status=health_status)
    return [
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
            milestones=[MilestoneRead.model_validate(m) for m in p.milestones],
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in projects
    ]


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Creates a project and links it to contributing strategic goals."""
    proj = GoalProjectService.create_project(db=db, user_id=user_id, payload=payload)
    db.commit()
    db.refresh(proj)
    return ProjectRead(
        id=proj.id,
        user_id=proj.user_id,
        title=proj.title,
        description=proj.description,
        status=proj.status,
        priority=proj.priority,
        health_status=ProjectHealthStatus(proj.health_status) if proj.health_status in ProjectHealthStatus.__members__ else ProjectHealthStatus.ON_TRACK,
        target_completion_date=proj.target_completion_date,
        completion_criteria=proj.completion_criteria,
        milestones=[],
        created_at=proj.created_at,
        updated_at=proj.updated_at,
    )


@router.get("/projects/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Gets project details, milestones, and health status."""
    proj = GoalProjectService.get_project_by_id(db=db, user_id=user_id, project_id=project_id)
    return ProjectRead(
        id=proj.id,
        user_id=proj.user_id,
        title=proj.title,
        description=proj.description,
        status=proj.status,
        priority=proj.priority,
        health_status=ProjectHealthStatus(proj.health_status) if proj.health_status in ProjectHealthStatus.__members__ else ProjectHealthStatus.ON_TRACK,
        target_completion_date=proj.target_completion_date,
        completion_criteria=proj.completion_criteria,
        milestones=[MilestoneRead.model_validate(m) for m in proj.milestones],
        created_at=proj.created_at,
        updated_at=proj.updated_at,
    )


@router.patch("/projects/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Updates project properties or health status."""
    proj = GoalProjectService.update_project(db=db, user_id=user_id, project_id=project_id, payload=payload)
    db.commit()
    db.refresh(proj)
    return ProjectRead(
        id=proj.id,
        user_id=proj.user_id,
        title=proj.title,
        description=proj.description,
        status=proj.status,
        priority=proj.priority,
        health_status=ProjectHealthStatus(proj.health_status) if proj.health_status in ProjectHealthStatus.__members__ else ProjectHealthStatus.ON_TRACK,
        target_completion_date=proj.target_completion_date,
        completion_criteria=proj.completion_criteria,
        milestones=[MilestoneRead.model_validate(m) for m in proj.milestones],
        created_at=proj.created_at,
        updated_at=proj.updated_at,
    )


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Deletes a project."""
    GoalProjectService.delete_project(db=db, user_id=user_id, project_id=project_id)
    db.commit()
    return None


@router.post("/projects/{project_id}/evaluate", response_model=ProjectProgressSnapshotRead)
def evaluate_project_progress(
    project_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Evaluates evidence-based progress and health factors for a project."""
    snapshot = GoalProjectService.compute_project_progress_and_risks(db=db, user_id=user_id, project_id=project_id)
    db.commit()
    db.refresh(snapshot)
    return ProjectProgressSnapshotRead.model_validate(snapshot)


# ===========================================================================
# Milestone Endpoints
# ===========================================================================

@router.post("/milestones", response_model=MilestoneRead, status_code=status.HTTP_201_CREATED)
def create_milestone(
    payload: MilestoneCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Creates a milestone for a project or goal."""
    m = GoalProjectService.create_milestone(db=db, user_id=user_id, payload=payload)
    db.commit()
    db.refresh(m)
    return MilestoneRead.model_validate(m)


@router.patch("/milestones/{milestone_id}", response_model=MilestoneRead)
def update_milestone(
    milestone_id: uuid.UUID,
    payload: MilestoneUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Updates milestone status, completion, or due date."""
    m = GoalProjectService.update_milestone(db=db, user_id=user_id, milestone_id=milestone_id, payload=payload)
    db.commit()
    db.refresh(m)
    return MilestoneRead.model_validate(m)


# ===========================================================================
# Task Association Endpoints
# ===========================================================================

@router.post("/associations/task", response_model=GoalTaskAssociationRead, status_code=status.HTTP_201_CREATED)
def associate_task(
    payload: GoalTaskAssociationCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Connects an everyday task to a strategic goal or project with importance weights."""
    assoc = GoalProjectService.associate_task(db=db, user_id=user_id, payload=payload)
    db.commit()
    db.refresh(assoc)
    t = assoc.task
    return GoalTaskAssociationRead(
        id=assoc.id,
        user_id=assoc.user_id,
        goal_id=assoc.goal_id,
        project_id=assoc.project_id,
        milestone_id=assoc.milestone_id,
        task_id=assoc.task_id,
        association_type=assoc.association_type,
        importance_weight=assoc.importance_weight,
        effort_weight=assoc.effort_weight,
        is_critical_path=assoc.is_critical_path,
        task_title=t.title if t else None,
        task_status=t.status.value if t and hasattr(t.status, "value") else str(t.status) if t else None,
        task_priority=t.priority.value if t and hasattr(t.priority, "value") else str(t.priority) if t else None,
        task_due_at=t.due_at if t else None,
        created_at=assoc.created_at,
    )


@router.get("/associations/task", response_model=List[GoalTaskAssociationRead])
def list_task_associations(
    goal_id: Optional[uuid.UUID] = Query(None),
    project_id: Optional[uuid.UUID] = Query(None),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Lists task associations for a goal or project."""
    return GoalProjectService.list_task_associations(
        db=db,
        user_id=user_id,
        goal_id=goal_id,
        project_id=project_id,
    )


@router.delete("/associations/task/{association_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_task_association(
    association_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Removes a task association from a goal or project."""
    GoalProjectService.remove_task_association(db=db, user_id=user_id, association_id=association_id)
    db.commit()
    return None


# ===========================================================================
# Governed Recommendations Endpoints
# ===========================================================================

@router.get("/recommendations", response_model=List[GoalRecommendationRead])
def list_recommendations(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Returns generated recommendations for next best tasks and schedule adjustments."""
    recs = GoalProjectService.generate_goal_recommendations(db=db, user_id=user_id)
    db.commit()
    return [GoalRecommendationRead.model_validate(r) for r in recs]


@router.post("/recommendations/{recommendation_id}/approve", response_model=GoalRecommendationRead)
def approve_recommendation(
    recommendation_id: uuid.UUID,
    payload: GoalRecommendationApprovalRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Approves or rejects an intelligent recommendation, optionally applying schedule adjustments immediately."""
    rec = GoalProjectService.approve_recommendation(
        db=db,
        user_id=user_id,
        recommendation_id=recommendation_id,
        payload=payload,
    )
    db.commit()
    db.refresh(rec)
    return GoalRecommendationRead.model_validate(rec)

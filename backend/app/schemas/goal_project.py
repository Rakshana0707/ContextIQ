"""
Pydantic v2 schemas for ContextIQ Goal and Project Intelligence (Phase 8.4).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.goal_project import (
    GoalHierarchyLevel,
    GoalRiskFactor,
    ProjectHealthStatus,
)


# ===========================================================================
# Milestone Schemas
# ===========================================================================

class MilestoneBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    status: str = "PENDING"
    is_completed: bool = False
    order_index: int = 0


class MilestoneCreate(MilestoneBase):
    project_id: Optional[uuid.UUID] = None
    goal_id: Optional[uuid.UUID] = None


class MilestoneUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    status: Optional[str] = None
    is_completed: Optional[bool] = None
    order_index: Optional[int] = None


class MilestoneRead(MilestoneBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    project_id: Optional[uuid.UUID] = None
    goal_id: Optional[uuid.UUID] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# ===========================================================================
# Task Association Schemas
# ===========================================================================

class GoalTaskAssociationCreate(BaseModel):
    task_id: uuid.UUID
    goal_id: Optional[uuid.UUID] = None
    project_id: Optional[uuid.UUID] = None
    milestone_id: Optional[uuid.UUID] = None
    association_type: str = "CONTRIBUTES_TO"
    importance_weight: float = Field(default=1.0, ge=0.1, le=5.0)
    effort_weight: float = Field(default=1.0, ge=0.1, le=10.0)
    is_critical_path: bool = False
    metadata_payload: Optional[Dict[str, Any]] = None


class GoalTaskAssociationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    goal_id: Optional[uuid.UUID] = None
    project_id: Optional[uuid.UUID] = None
    milestone_id: Optional[uuid.UUID] = None
    task_id: uuid.UUID
    association_type: str
    importance_weight: float
    effort_weight: float
    is_critical_path: bool
    task_title: Optional[str] = None
    task_status: Optional[str] = None
    task_priority: Optional[str] = None
    task_due_at: Optional[datetime] = None
    created_at: datetime


# ===========================================================================
# Goal Schemas
# ===========================================================================

class GoalBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    category: str = "PRODUCTIVITY"
    hierarchy_level: GoalHierarchyLevel = GoalHierarchyLevel.LONG_TERM
    priority: str = "MEDIUM"
    status: str = "ACTIVE"
    target_date: Optional[datetime] = None
    completion_criteria: Optional[str] = None


class GoalCreate(GoalBase):
    parent_goal_id: Optional[uuid.UUID] = None
    metadata_payload: Optional[Dict[str, Any]] = None


class GoalUpdate(BaseModel):
    parent_goal_id: Optional[uuid.UUID] = None
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = None
    hierarchy_level: Optional[GoalHierarchyLevel] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    target_date: Optional[datetime] = None
    progress_pct: Optional[float] = Field(None, ge=0.0, le=100.0)
    completion_criteria: Optional[str] = None
    metadata_payload: Optional[Dict[str, Any]] = None


class GoalRead(GoalBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    parent_goal_id: Optional[uuid.UUID] = None
    progress_pct: float
    evidence_based_progress: float = 0.0
    health_status: str = "ON_TRACK"
    risk_factors: List[str] = Field(default_factory=list)
    milestones: List[MilestoneRead] = Field(default_factory=list)
    associated_projects_count: int = 0
    associated_tasks_count: int = 0
    completed_tasks_count: int = 0
    overdue_tasks_count: int = 0
    created_at: datetime
    updated_at: datetime


# ===========================================================================
# Project Schemas
# ===========================================================================

class ProjectBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    status: str = "ACTIVE"
    priority: str = "MEDIUM"
    health_status: ProjectHealthStatus = ProjectHealthStatus.ON_TRACK
    target_completion_date: Optional[datetime] = None
    completion_criteria: Optional[str] = None


class ProjectCreate(ProjectBase):
    contributes_to_goal_ids: Optional[List[uuid.UUID]] = None
    metadata_payload: Optional[Dict[str, Any]] = None


class ProjectUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    health_status: Optional[ProjectHealthStatus] = None
    target_completion_date: Optional[datetime] = None
    completion_criteria: Optional[str] = None
    metadata_payload: Optional[Dict[str, Any]] = None


class ProjectRead(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    evidence_based_progress: float = 0.0
    milestones: List[MilestoneRead] = Field(default_factory=list)
    contributing_to_goals: List[str] = Field(default_factory=list)
    total_tasks_count: int = 0
    completed_tasks_count: int = 0
    overdue_tasks_count: int = 0
    blocked_tasks_count: int = 0
    total_productive_minutes: int = 0
    risk_factors: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# ===========================================================================
# Snapshot & Recommendation Schemas
# ===========================================================================

class GoalProgressSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    goal_id: uuid.UUID
    snapshot_at: datetime
    progress_pct: float
    evidence_based_progress: float
    completed_milestones_count: int
    total_milestones_count: int
    completed_tasks_count: int
    total_tasks_count: int
    overdue_tasks_count: int
    blocked_tasks_count: int
    health_status: str
    risk_factors: List[str]
    evidence_payload: Dict[str, Any]


class ProjectProgressSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    project_id: uuid.UUID
    snapshot_at: datetime
    progress_pct: float
    evidence_based_progress: float
    completed_milestones_count: int
    total_milestones_count: int
    completed_tasks_count: int
    total_tasks_count: int
    overdue_tasks_count: int
    blocked_tasks_count: int
    total_productive_minutes: int
    health_status: str
    risk_factors: List[str]
    evidence_payload: Dict[str, Any]


class GoalRecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    goal_id: Optional[uuid.UUID] = None
    project_id: Optional[uuid.UUID] = None
    recommendation_type: str
    title: str
    rationale: str
    suggested_action: Dict[str, Any]
    priority_score: float
    requires_approval: bool
    is_approved: Optional[bool] = None
    applied_at: Optional[datetime] = None
    created_at: datetime


class GoalRecommendationApprovalRequest(BaseModel):
    approve: bool
    apply_immediately: bool = True
    user_notes: Optional[str] = None


# ===========================================================================
# Intelligence Dashboard Schemas
# ===========================================================================

class BehavioralGoalAlignmentRead(BaseModel):
    top_time_invested_projects: List[Dict[str, Any]] = Field(default_factory=list)
    postponement_friction_goals: List[Dict[str, Any]] = Field(default_factory=list)
    high_interruption_projects: List[Dict[str, Any]] = Field(default_factory=list)
    recommended_focus_windows_for_goals: List[Dict[str, Any]] = Field(default_factory=list)
    descriptive_correlations: List[str] = Field(default_factory=list)


class GoalIntelligenceDashboard(BaseModel):
    total_goals: int
    active_projects: int
    completed_goals: int
    overall_health: str
    goals_at_risk_count: int
    projects_stalled_count: int
    total_completed_milestones: int
    behavioral_alignment: BehavioralGoalAlignmentRead
    goals: List[GoalRead]
    projects: List[ProjectRead]
    pending_recommendations: List[GoalRecommendationRead]

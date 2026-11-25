"""
Pydantic schemas for Cross-Task Dependency Discovery and Intelligent Relationship Analysis (Phase 8.5).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.task_dependency import (
    DependencyDetectionMethod,
    DependencyValidationStatus,
    TaskDependencyType,
)


class TaskDependencyBase(BaseModel):
    source_task_id: uuid.UUID
    target_task_id: uuid.UUID
    dependency_type: TaskDependencyType = TaskDependencyType.EXPLICIT_DEPENDENCY
    notes: Optional[str] = None


class TaskDependencyCreate(TaskDependencyBase):
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    is_inferred: bool = False
    detection_method: DependencyDetectionMethod = DependencyDetectionMethod.EXPLICIT_INPUT
    validation_status: DependencyValidationStatus = DependencyValidationStatus.CONVERTED_EXPLICIT
    supporting_observations: Dict[str, Any] = Field(default_factory=dict)


class TaskDependencyUpdate(BaseModel):
    dependency_type: Optional[TaskDependencyType] = None
    validation_status: Optional[DependencyValidationStatus] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    notes: Optional[str] = None


class TaskDependencyConfirmation(BaseModel):
    action: Literal["CONFIRM", "REJECT", "CONVERT_EXPLICIT"]
    corrected_type: Optional[TaskDependencyType] = None
    notes: Optional[str] = None


class TaskDependencyRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    source_task_id: uuid.UUID
    target_task_id: uuid.UUID
    source_task_title: Optional[str] = None
    target_task_title: Optional[str] = None
    source_task_status: Optional[str] = None
    target_task_status: Optional[str] = None
    source_task_priority: Optional[str] = None
    target_task_priority: Optional[str] = None
    dependency_type: str
    is_inferred: bool
    confidence: float
    detection_method: str
    validation_status: str
    supporting_observations: Dict[str, Any] = Field(default_factory=dict)
    first_observed_at: datetime
    last_observed_at: datetime
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DependencyDiscoveryRequest(BaseModel):
    lookback_days: int = Field(default=30, ge=1, le=365)
    min_confidence: float = Field(default=0.40, ge=0.1, le=1.0)
    include_temporal: bool = True
    include_project_goals: bool = True
    include_resource_conflicts: bool = True


class DependencyDiscoveryResult(BaseModel):
    discovered_count: int
    updated_count: int
    dependencies: List[TaskDependencyRead]
    summary: Dict[str, Any]


class ImpactAnalysisRequest(BaseModel):
    task_id: uuid.UUID
    hypothetical_delay_days: float = Field(default=3.0, ge=0.1, le=90.0)
    is_blocked: bool = True


class ImpactedTaskItem(BaseModel):
    task_id: uuid.UUID
    title: str
    status: str
    priority: str
    due_at: Optional[datetime] = None
    dependency_type: str
    confidence: float
    hop_distance: int
    critical_path: bool
    projected_delay_days: float


class ImpactedMilestoneItem(BaseModel):
    milestone_id: uuid.UUID
    title: str
    due_date: Optional[datetime] = None
    is_completed: bool
    at_risk: bool
    days_until_due: Optional[float] = None
    project_id: Optional[uuid.UUID] = None
    goal_id: Optional[uuid.UUID] = None


class ImpactedProjectItem(BaseModel):
    project_id: uuid.UUID
    title: str
    health_status: str
    projected_health_status: str
    is_stalled: bool = False


class ImpactedGoalItem(BaseModel):
    goal_id: uuid.UUID
    title: str
    hierarchy_level: str
    priority: str
    risk_level: str


class ImpactAnalysisResult(BaseModel):
    focal_task_id: uuid.UUID
    focal_task_title: str
    hypothetical_delay_days: float
    is_blocked: bool
    total_downstream_tasks: int
    critical_path_tasks_count: int
    affected_milestones: List[ImpactedMilestoneItem]
    affected_projects: List[ImpactedProjectItem]
    affected_goals: List[ImpactedGoalItem]
    downstream_tasks: List[ImpactedTaskItem]
    critical_path_risk: bool
    impact_severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    analysis_summary: str


class DependencyGraphNode(BaseModel):
    id: str
    label: str
    entity_type: Literal["TASK", "PROJECT", "GOAL", "MILESTONE"]
    status: Optional[str] = None
    priority: Optional[str] = None
    is_critical: bool = False
    entity_id: Optional[uuid.UUID] = None


class DependencyGraphEdge(BaseModel):
    id: str
    source: str
    target: str
    dependency_type: str
    confidence: float
    is_inferred: bool
    validation_status: str


class DependencyGraphResponse(BaseModel):
    nodes: List[DependencyGraphNode]
    edges: List[DependencyGraphEdge]
    total_explicit: int
    total_inferred: int
    potential_blockers_count: int

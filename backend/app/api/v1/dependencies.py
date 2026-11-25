"""
API Router for Cross-Task Dependency Discovery and Intelligent Relationship Analysis (Phase 8.5).
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.task_dependency import (
    DependencyDiscoveryRequest,
    DependencyDiscoveryResult,
    DependencyGraphResponse,
    ImpactAnalysisRequest,
    ImpactAnalysisResult,
    TaskDependencyConfirmation,
    TaskDependencyCreate,
    TaskDependencyRead,
    TaskDependencyUpdate,
)
from app.services.task_dependency_service import TaskDependencyService

dependencies_router = APIRouter(prefix="/dependencies", tags=["task-dependencies"])


@dependencies_router.get(
    "",
    response_model=List[TaskDependencyRead],
    summary="List cross-task dependencies",
)
def list_dependencies(
    source_task_id: Optional[uuid.UUID] = Query(None, description="Filter by source task ID"),
    target_task_id: Optional[uuid.UUID] = Query(None, description="Filter by target task ID"),
    dependency_type: Optional[str] = Query(None, description="Filter by dependency type"),
    validation_status: Optional[str] = Query(None, description="Filter by validation status"),
    is_inferred: Optional[bool] = Query(None, description="Filter by explicit vs inferred"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Retrieves all task dependencies for the authenticated user."""
    deps = TaskDependencyService.list_dependencies(
        db=db,
        user_id=user_id,
        source_task_id=source_task_id,
        target_task_id=target_task_id,
        dependency_type=dependency_type,
        validation_status=validation_status,
        is_inferred=is_inferred,
    )
    return [TaskDependencyService._to_read_schema(db, d) for d in deps]


@dependencies_router.post(
    "",
    response_model=TaskDependencyRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an explicit dependency",
)
def create_explicit_dependency(
    payload: TaskDependencyCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Declares a direct explicit dependency constraint between two tasks."""
    dep = TaskDependencyService.create_explicit_dependency(db, user_id, payload)
    return TaskDependencyService._to_read_schema(db, dep)


@dependencies_router.post(
    "/discover",
    response_model=DependencyDiscoveryResult,
    summary="Discover latent cross-task relationships",
)
def discover_dependencies(
    payload: DependencyDiscoveryRequest = DependencyDiscoveryRequest(),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Executes algorithmic discovery over task history, event sequences,
    shared project/goal structures, and temporal execution baskets.
    """
    return TaskDependencyService.discover_dependencies(db, user_id, payload)


@dependencies_router.post(
    "/impact-analysis",
    response_model=ImpactAnalysisResult,
    summary="Run cascading multi-hop impact analysis",
)
def run_impact_analysis(
    payload: ImpactAnalysisRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Simulates the cascading downstream impact of a task delay or blocker
    across dependent tasks, milestones, projects, and strategic goals.
    """
    return TaskDependencyService.run_impact_analysis(db, user_id, payload)


@dependencies_router.get(
    "/graph",
    response_model=DependencyGraphResponse,
    summary="Get dependency graph structure",
)
def get_dependency_graph(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Returns serialized graph nodes and edges for visualization."""
    return TaskDependencyService.get_dependency_graph(db, user_id)


@dependencies_router.get(
    "/{dependency_id}",
    response_model=TaskDependencyRead,
    summary="Get dependency details",
)
def get_dependency(
    dependency_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Fetches details and supporting evidence for a dependency."""
    dep = TaskDependencyService.get_dependency(db, user_id, dependency_id)
    return TaskDependencyService._to_read_schema(db, dep)


@dependencies_router.patch(
    "/{dependency_id}",
    response_model=TaskDependencyRead,
    summary="Update dependency",
)
def update_dependency(
    dependency_id: uuid.UUID,
    payload: TaskDependencyUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Updates dependency attributes, type, or notes."""
    dep = TaskDependencyService.update_dependency(db, user_id, dependency_id, payload)
    return TaskDependencyService._to_read_schema(db, dep)


@dependencies_router.post(
    "/{dependency_id}/confirm",
    response_model=TaskDependencyRead,
    summary="Review or confirm proposed dependency",
)
def confirm_or_review_dependency(
    dependency_id: uuid.UUID,
    payload: TaskDependencyConfirmation,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    User review gate:
    - CONFIRM: Accepts relationship without forcing execution constraints.
    - REJECT: Flags relationship as spurious.
    - CONVERT_EXPLICIT: Promotes relationship to explicit execution constraint.
    """
    dep = TaskDependencyService.confirm_or_review_dependency(db, user_id, dependency_id, payload)
    return TaskDependencyService._to_read_schema(db, dep)


@dependencies_router.delete(
    "/{dependency_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete dependency",
)
def delete_dependency(
    dependency_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Deletes or archives a dependency relationship."""
    TaskDependencyService.delete_dependency(db, user_id, dependency_id)
    return None

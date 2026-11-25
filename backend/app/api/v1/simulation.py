"""
Behavioral Digital Twin Simulation and Workflow Orchestration REST API Endpoints (ContextIQ Phase 6.9).

Exposes:
- Scenario hypothesis simulation and counterfactual delta analysis.
- Scenario persistence, listing, updating, comparison, and plan activation.
- Proposed multi-step workflow generation, approval, execution, cancellation, and rollback.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_id
from app.core.errors import NotFoundError
from app.db.session import get_db
from app.models.simulation_models import ProposedWorkflow
from app.schemas.digital_twin_simulation import (
    ProposedWorkflowResponse,
    ScenarioCompareRequest,
    ScenarioCompareResponse,
    ScenarioCreateRequest,
    ScenarioResponse,
    ScenarioSimulationRequest,
    ScenarioSimulationResult,
    ScenarioType,
    ScenarioUpdateRequest,
    WorkflowApprovalRequest,
    WorkflowExecutionResponse,
    WorkflowRollbackResponse,
    WorkflowStatus,
)
from app.services.simulation_service import SimulationService
from app.services.workflow_orchestrator import WorkflowOrchestrator

router = APIRouter(prefix="/simulation", tags=["behavioral-simulation"])


# ---------------------------------------------------------------------------
# Scenario Lab Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/scenarios/simulate",
    response_model=ScenarioSimulationResult,
    summary="Execute digital twin scenario simulation (ephemeral)",
)
def simulate_scenario(
    request: ScenarioSimulationRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ScenarioSimulationResult:
    """
    Executes a counterfactual digital twin simulation without modifying live user data.
    Computes baseline vs. proposed metrics, counterfactual deltas, and model assumptions.
    """
    if request.user_id is None:
        request.user_id = user_id
    return SimulationService.simulate_scenario(db=db, request=request)


@router.post(
    "/scenarios",
    response_model=ScenarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save a simulation scenario",
)
def create_saved_scenario(
    request: ScenarioCreateRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ScenarioResponse:
    """Saves a simulation scenario with model/feature version tracking for reproducibility."""
    return SimulationService.create_saved_scenario(db=db, user_id=user_id, request=request)


@router.get(
    "/scenarios",
    response_model=List[ScenarioResponse],
    summary="List user's saved scenarios",
)
def list_saved_scenarios(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> List[ScenarioResponse]:
    """Retrieves all saved scenarios belonging to the active user."""
    return SimulationService.list_saved_scenarios(db=db, user_id=user_id)


@router.get(
    "/scenarios/{scenario_id}",
    response_model=ScenarioResponse,
    summary="Retrieve single saved scenario by ID",
)
def get_saved_scenario(
    scenario_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ScenarioResponse:
    """Retrieves a specific saved scenario by ID."""
    return SimulationService.get_saved_scenario(db=db, user_id=user_id, scenario_id=scenario_id)


@router.put(
    "/scenarios/{scenario_id}",
    response_model=ScenarioResponse,
    summary="Update or rename a saved scenario",
)
def update_saved_scenario(
    scenario_id: uuid.UUID,
    request: ScenarioUpdateRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ScenarioResponse:
    """Renames, updates description, or activates a saved scenario."""
    return SimulationService.update_saved_scenario(
        db=db, user_id=user_id, scenario_id=scenario_id, update_req=request
    )


@router.delete(
    "/scenarios/{scenario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a saved scenario",
)
def delete_saved_scenario(
    scenario_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> None:
    """Deletes a saved scenario."""
    SimulationService.delete_saved_scenario(db=db, user_id=user_id, scenario_id=scenario_id)


@router.post(
    "/compare",
    response_model=ScenarioCompareResponse,
    summary="Compare multiple saved scenarios against baseline",
)
def compare_scenarios(
    request: ScenarioCompareRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ScenarioCompareResponse:
    """Compares 2 to 5 saved scenarios, building a relative ranking and trade-off matrix."""
    return SimulationService.compare_scenarios(db=db, user_id=user_id, request=request)


@router.post(
    "/scenarios/{scenario_id}/activate",
    response_model=ScenarioResponse,
    summary="Activate saved scenario as target baseline plan",
)
def activate_scenario(
    scenario_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ScenarioResponse:
    """Sets a scenario as the user's active target plan."""
    return SimulationService.activate_scenario(db=db, user_id=user_id, scenario_id=scenario_id)


# ---------------------------------------------------------------------------
# Proposed Workflow Orchestration Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/workflows/propose",
    response_model=ProposedWorkflowResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Propose a multi-step workflow from scenario",
)
def propose_workflow(
    scenario_type: ScenarioType = Query(default=ScenarioType.ADD_RECOVERY_BUFFER),
    scenario_id: Optional[uuid.UUID] = Query(default=None),
    task_id: Optional[uuid.UUID] = Query(default=None),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ProposedWorkflowResponse:
    """
    Generates a proposed multi-step workflow with action previews.
    Strictly initialized in PROPOSED state requiring user approval before execution.
    """
    wf = WorkflowOrchestrator.propose_workflow_from_scenario(
        db=db,
        user_id=user_id,
        scenario_type=scenario_type,
        scenario_id=scenario_id,
        task_id=task_id,
    )
    return ProposedWorkflowResponse(
        id=wf.id,
        user_id=wf.user_id,
        title=wf.title,
        scenario_id=wf.scenario_id,
        status=WorkflowStatus(wf.status),
        idempotency_key=wf.idempotency_key,
        actions=wf.actions,
        permission_audit=wf.permission_audit,
        is_reversible=wf.is_reversible,
        created_at=wf.created_at,
        approved_at=wf.approved_at,
        executed_at=wf.executed_at,
    )


@router.get(
    "/workflows/{workflow_id}",
    response_model=ProposedWorkflowResponse,
    summary="Retrieve proposed workflow status and action preview",
)
def get_workflow(
    workflow_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ProposedWorkflowResponse:
    """Retrieves proposed workflow details and action previews."""
    wf = db.get(ProposedWorkflow, workflow_id)
    if not wf or wf.user_id != user_id:
        raise NotFoundError(f"Workflow '{workflow_id}' not found.")
    return ProposedWorkflowResponse(
        id=wf.id,
        user_id=wf.user_id,
        title=wf.title,
        scenario_id=wf.scenario_id,
        status=WorkflowStatus(wf.status),
        idempotency_key=wf.idempotency_key,
        actions=wf.actions,
        permission_audit=wf.permission_audit,
        is_reversible=wf.is_reversible,
        created_at=wf.created_at,
        approved_at=wf.approved_at,
        executed_at=wf.executed_at,
    )


@router.post(
    "/workflows/{workflow_id}/approve",
    response_model=ProposedWorkflowResponse,
    summary="Explicitly approve or reject proposed workflow",
)
def approve_workflow(
    workflow_id: uuid.UUID,
    approval_req: WorkflowApprovalRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ProposedWorkflowResponse:
    """Records explicit user approval or rejection for proposed external workflow."""
    wf = db.get(ProposedWorkflow, workflow_id)
    if not wf or wf.user_id != user_id:
        raise NotFoundError(f"Workflow '{workflow_id}' not found.")
    wf = WorkflowOrchestrator.approve_workflow(db=db, workflow=wf, approval_req=approval_req)
    return ProposedWorkflowResponse(
        id=wf.id,
        user_id=wf.user_id,
        title=wf.title,
        scenario_id=wf.scenario_id,
        status=WorkflowStatus(wf.status),
        idempotency_key=wf.idempotency_key,
        actions=wf.actions,
        permission_audit=wf.permission_audit,
        is_reversible=wf.is_reversible,
        created_at=wf.created_at,
        approved_at=wf.approved_at,
        executed_at=wf.executed_at,
    )


@router.post(
    "/workflows/{workflow_id}/execute",
    response_model=WorkflowExecutionResponse,
    summary="Execute an approved workflow with audit logging",
)
def execute_workflow(
    workflow_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> WorkflowExecutionResponse:
    """Executes actions of an approved workflow. Enforces approval and idempotency."""
    wf = db.get(ProposedWorkflow, workflow_id)
    if not wf or wf.user_id != user_id:
        raise NotFoundError(f"Workflow '{workflow_id}' not found.")
    return WorkflowOrchestrator.execute_workflow(db=db, workflow=wf)


@router.post(
    "/workflows/{workflow_id}/cancel",
    response_model=ProposedWorkflowResponse,
    summary="Cancel a proposed or approved workflow",
)
def cancel_workflow(
    workflow_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ProposedWorkflowResponse:
    """Cancels a workflow before execution."""
    wf = db.get(ProposedWorkflow, workflow_id)
    if not wf or wf.user_id != user_id:
        raise NotFoundError(f"Workflow '{workflow_id}' not found.")
    wf = WorkflowOrchestrator.cancel_workflow(db=db, workflow=wf)
    return ProposedWorkflowResponse(
        id=wf.id,
        user_id=wf.user_id,
        title=wf.title,
        scenario_id=wf.scenario_id,
        status=WorkflowStatus(wf.status),
        idempotency_key=wf.idempotency_key,
        actions=wf.actions,
        permission_audit=wf.permission_audit,
        is_reversible=wf.is_reversible,
        created_at=wf.created_at,
        approved_at=wf.approved_at,
        executed_at=wf.executed_at,
    )


@router.post(
    "/workflows/{workflow_id}/rollback",
    response_model=WorkflowRollbackResponse,
    summary="Rollback / undo an executed workflow",
)
def rollback_workflow(
    workflow_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> WorkflowRollbackResponse:
    """Reverts external changes made by a completed workflow."""
    wf = db.get(ProposedWorkflow, workflow_id)
    if not wf or wf.user_id != user_id:
        raise NotFoundError(f"Workflow '{workflow_id}' not found.")
    return WorkflowOrchestrator.rollback_workflow(db=db, workflow=wf)

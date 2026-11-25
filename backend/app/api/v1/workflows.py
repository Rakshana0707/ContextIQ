"""
FastAPI router for Multi-Step Workflow Planning, Orchestration,
Action Registry, and LLM Proposal Compilation (ContextIQ Phase 7.4).
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.workflow_schemas import (
    ActionContractSchema,
    IntelligentPlanningRequest,
    LLMWorkflowProposal,
    PlanTransitionRequest,
    WorkflowCategory,
    WorkflowExecutionPlanResponse,
    WorkflowLifecycleState,
)
from app.services.action_registry import ActionRegistry
from app.services.llm_workflow_adapter import LLMWorkflowAdapter
from app.services.workflow_planner import WorkflowPlanner
from app.services.workflow_validator import WorkflowValidationError

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("/actions", response_model=List[ActionContractSchema])
def list_registered_actions(
    category: Optional[str] = Query(default=None, description="Optional category filter"),
) -> List[ActionContractSchema]:
    """Returns the immutable catalog of registered action contracts."""
    cat_enum = None
    if category:
        try:
            cat_enum = WorkflowCategory(category.upper())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid category '{category}'.",
            )
    return ActionRegistry.list_actions(category=cat_enum)


@router.post("/plan", response_model=WorkflowExecutionPlanResponse, status_code=status.HTTP_201_CREATED)
def plan_workflow_from_signals(
    req: IntelligentPlanningRequest,
    db: Session = Depends(get_db),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> WorkflowExecutionPlanResponse:
    """
    Synthesizes a structured 7-step multi-step workflow proposal in response to
    behavioral insights, forgetting risks, or calendar conflicts.
    """
    try:
        plan = WorkflowPlanner.plan_behavioral_workflow(
            db=db,
            user_id=current_user_id,
            trigger_type=req.trigger_type,
            behavioral_context=req.behavioral_context,
            task_id=req.task_id,
            desired_strategy=req.desired_strategy or "BALANCED",
            generate_alternatives=req.generate_alternatives,
        )
        return WorkflowExecutionPlanResponse.model_validate(plan)
    except WorkflowValidationError as ex:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(ex), "errors": ex.errors},
        )


@router.post("/proposals/compile", response_model=WorkflowExecutionPlanResponse, status_code=status.HTTP_201_CREATED)
def compile_llm_proposal(
    proposal: LLMWorkflowProposal,
    db: Session = Depends(get_db),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> WorkflowExecutionPlanResponse:
    """
    Ingests and deterministically validates an LLM-drafted workflow proposal.
    Rejects unregistered actions and circular dependencies. Places proposal in AWAITING_APPROVAL.
    """
    try:
        plan = LLMWorkflowAdapter.validate_and_compile_proposal(
            db=db,
            user_id=current_user_id,
            raw_proposal=proposal,
        )
        return WorkflowExecutionPlanResponse.model_validate(plan)
    except WorkflowValidationError as ex:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(ex), "errors": ex.errors},
        )


@router.get("/plans", response_model=List[WorkflowExecutionPlanResponse])
def list_execution_plans(
    status_filter: Optional[str] = Query(default=None, description="Optional status filter"),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> List[WorkflowExecutionPlanResponse]:
    """Retrieves workflow execution plans for current user."""
    plans = WorkflowPlanner.list_plans(
        db=db,
        user_id=current_user_id,
        status=status_filter,
        limit=limit,
    )
    return [WorkflowExecutionPlanResponse.model_validate(p) for p in plans]


@router.get("/plans/{plan_id}", response_model=WorkflowExecutionPlanResponse)
def get_execution_plan(
    plan_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> WorkflowExecutionPlanResponse:
    """Fetches full execution plan details, steps, dependencies, and comparison metadata."""
    plan = WorkflowPlanner.get_plan(db=db, plan_id=plan_id, user_id=current_user_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow execution plan '{plan_id}' not found.",
        )
    return WorkflowExecutionPlanResponse.model_validate(plan)


@router.post("/plans/{plan_id}/transition", response_model=WorkflowExecutionPlanResponse)
def transition_plan_status(
    plan_id: uuid.UUID,
    req: PlanTransitionRequest,
    db: Session = Depends(get_db),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> WorkflowExecutionPlanResponse:
    """
    Executes a governed state transition on a workflow plan (e.g. APPROVED, CANCELLED).
    Validates permissible transitions using the 13-state FSM.
    """
    try:
        updated_plan = WorkflowPlanner.transition_plan_status(
            db=db,
            plan_id=plan_id,
            user_id=current_user_id,
            target_state=req.target_state,
            reason=req.reason,
        )
        return WorkflowExecutionPlanResponse.model_validate(updated_plan)
    except ValueError as ex:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ex))
    except WorkflowValidationError as ex:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(ex), "errors": ex.errors},
        )

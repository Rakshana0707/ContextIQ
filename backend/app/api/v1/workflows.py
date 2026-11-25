"""
FastAPI router for Multi-Step Workflow Planning, Orchestration,
Action Registry, and LLM Proposal Compilation (ContextIQ Phase 7.4).
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_id
from app.db.session import SessionLocal, get_db
from app.models.workflow_models import WorkflowExecutionPlan, WorkflowStepExecution
from app.schemas.workflow_schemas import (
    ActionContractSchema,
    IntelligentPlanningRequest,
    LLMWorkflowProposal,
    PlanTransitionRequest,
    WorkflowCategory,
    WorkflowExecuteRequest,
    WorkflowExecutionPlanResponse,
    WorkflowExecutionProgressResponse,
    WorkflowLifecycleState,
    WorkflowStepExecutionResponse,
)
from app.services.action_registry import ActionRegistry
from app.services.llm_workflow_adapter import LLMWorkflowAdapter
from app.services.workflow_execution_engine import (
    ApprovalVerificationError,
    DuplicateExecutionError,
    WorkflowExecutionEngine,
)
from app.services.workflow_planner import WorkflowPlanner
from app.services.workflow_validator import WorkflowValidationError

router = APIRouter(prefix="/workflows", tags=["workflows"])


def _run_workflow_in_background(plan_id: uuid.UUID, user_id: uuid.UUID, auto_rollback: bool) -> None:
    """Worker task executed in FastAPI background pool."""
    db = SessionLocal()
    try:
        WorkflowExecutionEngine.execute_plan(
            db=db,
            plan_id=plan_id,
            user_id=user_id,
            auto_rollback_on_failure=auto_rollback,
        )
    finally:
        db.close()


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


@router.post("/plans/{plan_id}/execute", response_model=WorkflowExecutionPlanResponse, status_code=status.HTTP_202_ACCEPTED)
def execute_workflow_plan(
    plan_id: uuid.UUID,
    req: Optional[WorkflowExecuteRequest] = None,
    sync: bool = Query(default=False, description="Whether to execute synchronously (for deterministic tests)"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> WorkflowExecutionPlanResponse:
    """
    Safely initiates execution of an approved workflow plan.
    Validates approval, checks version integrity, and dispatches steps.
    """
    plan = WorkflowPlanner.get_plan(db=db, plan_id=plan_id, user_id=current_user_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Plan '{plan_id}' not found.")

    auto_rollback = req.auto_rollback_on_failure if req else False

    try:
        if sync:
            executed_plan = WorkflowExecutionEngine.execute_plan(
                db=db,
                plan_id=plan_id,
                user_id=current_user_id,
                auto_rollback_on_failure=auto_rollback,
            )
            return WorkflowExecutionPlanResponse.model_validate(executed_plan)
        else:
            # Pre-validate approval before scheduling background task
            WorkflowExecutionEngine.verify_approval(db, plan, current_user_id)
            plan.status = WorkflowLifecycleState.EXECUTING.value
            db.commit()
            db.refresh(plan)

            background_tasks.add_task(
                _run_workflow_in_background,
                plan_id=plan_id,
                user_id=current_user_id,
                auto_rollback=auto_rollback,
            )
            return WorkflowExecutionPlanResponse.model_validate(plan)
    except ApprovalVerificationError as ex:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(ex))
    except DuplicateExecutionError as ex:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ex))


@router.get("/plans/{plan_id}/execution", response_model=WorkflowExecutionProgressResponse)
def get_execution_progress(
    plan_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> WorkflowExecutionProgressResponse:
    """Returns live step-by-step execution progress, receipts, and failure details."""
    plan = WorkflowPlanner.get_plan(db=db, plan_id=plan_id, user_id=current_user_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Plan '{plan_id}' not found.")

    step_execs = db.execute(
        select(WorkflowStepExecution)
        .where(WorkflowStepExecution.plan_id == plan_id)
        .order_by(WorkflowStepExecution.created_at)
    ).scalars().all()

    total_steps = len(plan.plan_steps or [])
    completed_steps = sum(1 for s in step_execs if s.status in ("COMPLETED", "COMPENSATED"))
    failed_steps = sum(1 for s in step_execs if s.status == "FAILED")
    skipped_steps = sum(1 for s in step_execs if s.status == "SKIPPED")

    pct = 0.0
    if total_steps > 0:
        pct = round(min(100.0, (completed_steps / total_steps) * 100.0), 1)

    return WorkflowExecutionProgressResponse(
        plan_id=plan.id,
        title=plan.title,
        status=plan.status,
        version=plan.version,
        total_steps=total_steps,
        completed_steps=completed_steps,
        failed_steps=failed_steps,
        skipped_steps=skipped_steps,
        progress_percentage=pct,
        step_executions=[WorkflowStepExecutionResponse.model_validate(s) for s in step_execs],
        executed_at=plan.executed_at,
        is_reversible=plan.reversibility_summary.get("is_fully_reversible", True),
    )


@router.post("/plans/{plan_id}/cancel", response_model=WorkflowExecutionPlanResponse)
def cancel_workflow_execution(
    plan_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> WorkflowExecutionPlanResponse:
    """Cancels an in-flight or approved workflow plan."""
    try:
        cancelled = WorkflowExecutionEngine.cancel_plan(db, plan_id, current_user_id)
        return WorkflowExecutionPlanResponse.model_validate(cancelled)
    except ValueError as ex:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ex))


@router.post("/plans/{plan_id}/rollback", response_model=WorkflowExecutionPlanResponse)
def rollback_workflow_execution(
    plan_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> WorkflowExecutionPlanResponse:
    """Reverts all completed side effects via compensating actions."""
    try:
        rolled_back = WorkflowExecutionEngine.rollback_plan(db, plan_id, current_user_id)
        return WorkflowExecutionPlanResponse.model_validate(rolled_back)
    except ValueError as ex:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ex))


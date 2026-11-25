"""
FastAPI router for Workflow Auditability, Rollback, and Emergency Stop (ContextIQ Phase 7.7).
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_id
from app.db.session import get_db
from app.models.safety_models import (
    EmergencyStopEvent,
    WorkflowAuditEvent,
    WorkflowRollbackRecord,
)
from app.models.workflow_models import (
    WorkflowExecutionPlan,
)
from app.schemas.workflow_schemas import (
    WorkflowLifecycleState,
)
from app.schemas.safety_schemas import (
    EmergencyStatusSummary,
    EmergencyStopLiftRequest,
    EmergencyStopRequest,
    EmergencyStopResponse,
    EmergencyStopScope,
    RollbackRecordResponse,
    RollbackRequest,
    SafetyOverviewResponse,
    WorkflowAuditEventResponse,
)
from app.services.safety_engine import (
    AuditLogger,
    EmergencyStopEngine,
    RollbackManager,
)

router = APIRouter(prefix="/safety", tags=["safety"])


@router.get("/overview", response_model=SafetyOverviewResponse)
def get_safety_overview(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> SafetyOverviewResponse:
    """Returns overview of automation safety, active stops, and recent audit events."""
    is_stopped, _ = EmergencyStopEngine.is_emergency_stop_active(db, user_id)
    active_stops = EmergencyStopEngine.list_active_stops(db, user_id)

    # Count plans
    plans = db.execute(
        select(WorkflowExecutionPlan).where(WorkflowExecutionPlan.user_id == user_id)
    ).scalars().all()

    active_count = sum(
        1 for p in plans if p.status in [
            WorkflowLifecycleState.APPROVED.value,
            WorkflowLifecycleState.SCHEDULED.value,
            WorkflowLifecycleState.EXECUTING.value,
        ]
    )
    awaiting_count = sum(
        1 for p in plans if p.status == WorkflowLifecycleState.AWAITING_APPROVAL.value
    )
    failed_count = sum(
        1 for p in plans if p.status in [
            WorkflowLifecycleState.FAILED.value,
            WorkflowLifecycleState.PARTIALLY_COMPLETED.value,
        ]
    )
    reversible_count = sum(
        1 for p in plans if p.status in [
            WorkflowLifecycleState.COMPLETED.value,
            WorkflowLifecycleState.PARTIALLY_COMPLETED.value,
            WorkflowLifecycleState.FAILED.value,
        ]
    )

    recent_events = AuditLogger.list_events(db, user_id, limit=10)

    return SafetyOverviewResponse(
        active_plans_count=active_count,
        awaiting_approval_count=awaiting_count,
        failed_plans_count=failed_count,
        reversible_plans_count=reversible_count,
        emergency_stop_active=is_stopped,
        recent_audit_events=[WorkflowAuditEventResponse.model_validate(e) for e in recent_events],
        active_emergency_stops=[EmergencyStopResponse.model_validate(s) for s in active_stops],
    )


@router.post("/emergency-stop", response_model=EmergencyStopResponse)
def trigger_emergency_stop(
    payload: EmergencyStopRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> EmergencyStopResponse:
    """Triggers an immediate Emergency Stop, cancelling pending workflows and halting execution."""
    stop_event = EmergencyStopEngine.trigger_emergency_stop(
        db=db,
        scope=payload.scope,
        user_id=user_id if payload.scope == EmergencyStopScope.USER_LEVEL else None,
        reason=payload.reason,
        triggered_by="USER",
        auto_cancel_pending=payload.auto_cancel_pending,
    )
    return EmergencyStopResponse.model_validate(stop_event)


@router.post("/emergency-stop/lift", response_model=EmergencyStopResponse)
def lift_emergency_stop(
    payload: EmergencyStopLiftRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> EmergencyStopResponse:
    """Lifts an active emergency stop event."""
    try:
        lifted = EmergencyStopEngine.lift_emergency_stop(
            db=db,
            emergency_stop_id=payload.emergency_stop_id,
            user_id=user_id,
            notes=payload.notes,
        )
        return EmergencyStopResponse.model_validate(lifted)
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.get("/emergency-stop/status", response_model=EmergencyStatusSummary)
def get_emergency_status(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> EmergencyStatusSummary:
    """Returns the current emergency stop state for the user and system."""
    is_stopped, _ = EmergencyStopEngine.is_emergency_stop_active(db, user_id)
    active_stops = EmergencyStopEngine.list_active_stops(db, user_id)
    global_active = any(s.scope == EmergencyStopScope.ADMIN_GLOBAL.value for s in active_stops)
    user_active = any(s.scope == EmergencyStopScope.USER_LEVEL.value and s.user_id == user_id for s in active_stops)

    return EmergencyStatusSummary(
        is_stopped=is_stopped,
        active_stops=[EmergencyStopResponse.model_validate(s) for s in active_stops],
        global_kill_switch_active=global_active,
        user_stop_active=user_active,
    )


@router.get("/audit/events", response_model=List[WorkflowAuditEventResponse])
def get_audit_events(
    plan_id: Optional[uuid.UUID] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> List[WorkflowAuditEventResponse]:
    """Retrieves immutable append-only audit records for the user's workflows."""
    events = AuditLogger.list_events(db=db, user_id=user_id, plan_id=plan_id, limit=limit)
    return [WorkflowAuditEventResponse.model_validate(e) for e in events]


@router.get("/rollback/check/{plan_id}")
def check_plan_reversibility(
    plan_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Inspects a plan to determine if its completed steps can be safely compensated."""
    can_reverse, summary, details = RollbackManager.is_plan_reversible(db, plan_id, user_id)
    return {
        "plan_id": plan_id,
        "is_reversible": can_reverse,
        "summary": summary,
        "step_details": details,
    }


@router.post("/rollback/{plan_id}", response_model=RollbackRecordResponse)
def execute_plan_rollback(
    plan_id: uuid.UUID,
    payload: RollbackRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> RollbackRecordResponse:
    """Executes inverse compensating actions in reverse order for an eligible workflow plan."""
    try:
        record = RollbackManager.execute_plan_rollback(
            db=db,
            plan_id=plan_id,
            user_id=user_id,
            triggered_by="USER_MANUAL",
            reason=payload.reason,
            force=payload.force,
        )
        return RollbackRecordResponse.model_validate(record)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.get("/rollback/records", response_model=List[RollbackRecordResponse])
def get_rollback_records(
    plan_id: Optional[uuid.UUID] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> List[RollbackRecordResponse]:
    """Lists structured rollback execution records."""
    query = select(WorkflowRollbackRecord).where(WorkflowRollbackRecord.user_id == user_id)
    if plan_id:
        query = query.where(WorkflowRollbackRecord.plan_id == plan_id)
    query = query.order_by(WorkflowRollbackRecord.started_at.desc()).limit(limit)
    records = db.execute(query).scalars().all()
    return [RollbackRecordResponse.model_validate(r) for r in records]

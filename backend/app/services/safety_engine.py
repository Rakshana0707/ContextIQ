"""
Safety, Auditability, Rollback, and Emergency Stop Engine (ContextIQ Phase 7.7).
Provides:
1. Append-only, sanitized audit logging for all workflow operations.
2. User-level and Administrator-level Emergency Stop (operational kill switch).
3. Reversibility verification, structured compensation, and duplicate rollback protection.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.automation_rule import AutomationRule
from app.models.safety_models import (
    EmergencyStopEvent,
    WorkflowApprovalRecord,
    WorkflowAuditEvent,
    WorkflowRollbackRecord,
)
from app.models.workflow_models import (
    WorkflowExecutionPlan,
    WorkflowStepExecution,
)
from app.schemas.workflow_schemas import (
    WorkflowLifecycleState,
)
from app.schemas.safety_schemas import (
    AuditEventType,
    EmergencyStopScope,
    RollbackStatusEnum,
    RollbackTriggerSource,
)
from app.services.action_handlers import ActionHandlers, ActionResult
from app.services.action_registry import ActionRegistry

logger = logging.getLogger(__name__)

# Keys that must never appear in raw audit logs
SENSITIVE_KEY_SUBSTRINGS = (
    "token",
    "secret",
    "password",
    "passwd",
    "api_key",
    "authorization",
    "bearer",
    "cookie",
    "credential",
    "private_key",
)


def sanitize_payload(payload: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Recursively scrubs secrets, OAuth tokens, and credentials from audit payloads.
    """
    if not payload or not isinstance(payload, dict):
        return payload

    sanitized = {}
    for k, v in payload.items():
        k_lower = str(k).lower()
        if any(sens in k_lower for sens in SENSITIVE_KEY_SUBSTRINGS):
            sanitized[k] = "[REDACTED]"
        elif isinstance(v, dict):
            sanitized[k] = sanitize_payload(v)
        elif isinstance(v, list):
            sanitized[k] = [
                sanitize_payload(item) if isinstance(item, dict) else item
                for item in v
            ]
        else:
            sanitized[k] = v
    return sanitized


class AuditLogger:
    """Append-only audit trail logger for all workflow, approval, and emergency operations."""

    @classmethod
    def record_event(
        cls,
        db: Session,
        user_id: uuid.UUID,
        event_type: AuditEventType | str,
        plan_id: Optional[uuid.UUID] = None,
        workflow_version: int = 1,
        action_identifier: Optional[str] = None,
        step_key: Optional[str] = None,
        policy_decision: Optional[str] = None,
        approval_reference: Optional[str] = None,
        result_status: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> WorkflowAuditEvent:
        """Appends an immutable audit event."""
        event_str = event_type.value if hasattr(event_type, "value") else str(event_type)
        audit_event = WorkflowAuditEvent(
            user_id=user_id,
            plan_id=plan_id,
            workflow_version=workflow_version,
            event_type=event_str,
            action_identifier=action_identifier,
            step_key=step_key,
            execution_timestamp=datetime.now(timezone.utc),
            policy_decision=policy_decision,
            approval_reference=approval_reference,
            result_status=result_status,
            error_details=sanitize_payload(error_details),
            correlation_id=correlation_id,
            sanitized_payload=sanitize_payload(payload),
        )
        db.add(audit_event)
        try:
            db.commit()
            db.refresh(audit_event)
        except Exception as e:
            logger.error(f"Failed to commit workflow audit event: {e}")
            db.rollback()
        return audit_event

    @classmethod
    def list_events(
        cls,
        db: Session,
        user_id: uuid.UUID,
        plan_id: Optional[uuid.UUID] = None,
        limit: int = 50,
    ) -> List[WorkflowAuditEvent]:
        query = select(WorkflowAuditEvent).where(WorkflowAuditEvent.user_id == user_id)
        if plan_id:
            query = query.where(WorkflowAuditEvent.plan_id == plan_id)
        query = query.order_by(WorkflowAuditEvent.execution_timestamp.desc()).limit(limit)
        return db.execute(query).scalars().all()

    @classmethod
    def record_approval(
        cls,
        db: Session,
        plan_id: uuid.UUID,
        user_id: uuid.UUID,
        decision: str,
        approver_type: str = "USER_EXPLICIT",
        reason: Optional[str] = None,
        plan_version: int = 1,
    ) -> WorkflowApprovalRecord:
        record = WorkflowApprovalRecord(
            plan_id=plan_id,
            user_id=user_id,
            decision=decision,
            approver_type=approver_type,
            reason=reason,
            plan_version=plan_version,
            timestamp=datetime.now(timezone.utc),
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        event_type = (
            AuditEventType.WORKFLOW_PLAN_APPROVED
            if decision == "APPROVED"
            else AuditEventType.WORKFLOW_PLAN_REJECTED
        )
        cls.record_event(
            db=db,
            user_id=user_id,
            event_type=event_type,
            plan_id=plan_id,
            workflow_version=plan_version,
            approval_reference=str(record.id),
            result_status=decision,
            payload={"reason": reason, "approver_type": approver_type},
        )
        return record


class EmergencyStopEngine:
    """Circuit breaker and kill-switch management."""

    @classmethod
    def is_emergency_stop_active(
        cls,
        db: Session,
        user_id: Optional[uuid.UUID] = None,
    ) -> Tuple[bool, Optional[EmergencyStopEvent]]:
        """
        Returns True if an emergency stop is active (either ADMIN_GLOBAL or USER_LEVEL for user).
        """
        # Check global stop
        global_stop = db.execute(
            select(EmergencyStopEvent).where(
                and_(
                    EmergencyStopEvent.scope == EmergencyStopScope.ADMIN_GLOBAL.value,
                    EmergencyStopEvent.is_active == True,  # noqa: E712
                )
            )
        ).scalars().first()

        if global_stop:
            return True, global_stop

        # Check user-level stop
        if user_id:
            user_stop = db.execute(
                select(EmergencyStopEvent).where(
                    and_(
                        EmergencyStopEvent.scope == EmergencyStopScope.USER_LEVEL.value,
                        EmergencyStopEvent.user_id == user_id,
                        EmergencyStopEvent.is_active == True,  # noqa: E712
                    )
                )
            ).scalars().first()
            if user_stop:
                return True, user_stop

        return False, None

    @classmethod
    def trigger_emergency_stop(
        cls,
        db: Session,
        scope: EmergencyStopScope = EmergencyStopScope.USER_LEVEL,
        user_id: Optional[uuid.UUID] = None,
        reason: str = "Emergency stop initiated",
        triggered_by: str = "USER",
        auto_cancel_pending: bool = True,
    ) -> EmergencyStopEvent:
        """
        Activates an emergency stop, halts running workflows, and cancels scheduled actions.
        """
        # Check if already active
        is_active, existing = cls.is_emergency_stop_active(db, user_id=user_id)
        if is_active and existing and existing.scope == scope.value:
            return existing

        now = datetime.now(timezone.utc)
        stop_event = EmergencyStopEvent(
            scope=scope.value,
            user_id=user_id if scope == EmergencyStopScope.USER_LEVEL else None,
            triggered_by=triggered_by,
            reason=reason,
            is_active=True,
            started_at=now,
        )
        db.add(stop_event)
        db.commit()
        db.refresh(stop_event)

        affected_plans_count = 0
        affected_rules_count = 0

        # Cascade cancellations if enabled
        if auto_cancel_pending:
            plan_query = select(WorkflowExecutionPlan).where(
                WorkflowExecutionPlan.status.in_([
                    WorkflowLifecycleState.CREATED.value,
                    WorkflowLifecycleState.DRAFT.value,
                    WorkflowLifecycleState.VALIDATING.value,
                    WorkflowLifecycleState.AWAITING_APPROVAL.value,
                    WorkflowLifecycleState.APPROVED.value,
                    WorkflowLifecycleState.SCHEDULED.value,
                    WorkflowLifecycleState.EXECUTING.value,
                ])
            )
            if scope == EmergencyStopScope.USER_LEVEL and user_id:
                plan_query = plan_query.where(WorkflowExecutionPlan.user_id == user_id)

            plans = db.execute(plan_query).scalars().all()
            for p in plans:
                p.status = WorkflowLifecycleState.CANCELLED.value
                tc = dict(p.trigger_context or {})
                tc["cancellation_reason"] = f"Emergency stop triggered ({scope.value}): {reason}"
                p.trigger_context = tc
                p.updated_at = now
                affected_plans_count += 1

                # Mark active step executions as BLOCKED_BY_POLICY
                step_execs = db.execute(
                    select(WorkflowStepExecution).where(
                        and_(
                            WorkflowStepExecution.plan_id == p.id,
                            WorkflowStepExecution.status.in_(["PENDING", "EXECUTING"]),
                        )
                    )
                ).scalars().all()
                for se in step_execs:
                    se.status = "BLOCKED_BY_POLICY"
                    se.error_message = f"Emergency stop active ({scope.value})"
                    se.completed_at = now

            # Disable or pause automation rules
            rule_query = select(AutomationRule).where(AutomationRule.is_enabled == True)  # noqa: E712
            if scope == EmergencyStopScope.USER_LEVEL and user_id:
                rule_query = rule_query.where(AutomationRule.user_id == user_id)

            rules = db.execute(rule_query).scalars().all()
            for r in rules:
                r.is_enabled = False
                affected_rules_count += 1

            stop_event.affected_plans_count = affected_plans_count
            stop_event.affected_rules_count = affected_rules_count
            db.commit()

        # Audit event
        effective_user_id = user_id or uuid.UUID("00000000-0000-0000-0000-000000000000")
        AuditLogger.record_event(
            db=db,
            user_id=effective_user_id,
            event_type=AuditEventType.EMERGENCY_STOP_TRIGGERED,
            policy_decision="EMERGENCY_HALT",
            result_status="STOP_ACTIVATED",
            payload={
                "scope": scope.value,
                "reason": reason,
                "triggered_by": triggered_by,
                "affected_plans": affected_plans_count,
                "affected_rules": affected_rules_count,
            },
        )

        return stop_event

    @classmethod
    def lift_emergency_stop(
        cls,
        db: Session,
        emergency_stop_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        notes: Optional[str] = None,
    ) -> EmergencyStopEvent:
        """Lifts an active emergency stop."""
        stop_event = db.get(EmergencyStopEvent, emergency_stop_id)
        if not stop_event:
            raise ValueError(f"Emergency stop event '{emergency_stop_id}' not found.")

        if user_id and stop_event.scope == EmergencyStopScope.USER_LEVEL.value:
            if stop_event.user_id != user_id:
                raise PermissionError("Cannot lift emergency stop belonging to another user.")

        stop_event.is_active = False
        stop_event.lifted_at = datetime.now(timezone.utc)
        db.commit()

        effective_user_id = user_id or stop_event.user_id or uuid.UUID("00000000-0000-0000-0000-000000000000")
        AuditLogger.record_event(
            db=db,
            user_id=effective_user_id,
            event_type=AuditEventType.EMERGENCY_STOP_LIFTED,
            result_status="STOP_LIFTED",
            payload={"stop_id": str(stop_event.id), "notes": notes},
        )
        return stop_event

    @classmethod
    def list_active_stops(
        cls,
        db: Session,
        user_id: Optional[uuid.UUID] = None,
    ) -> List[EmergencyStopEvent]:
        query = select(EmergencyStopEvent).where(EmergencyStopEvent.is_active == True)  # noqa: E712
        if user_id:
            query = query.where(
                (EmergencyStopEvent.scope == EmergencyStopScope.ADMIN_GLOBAL.value)
                | (EmergencyStopEvent.user_id == user_id)
            )
        return db.execute(query).scalars().all()


class RollbackManager:
    """Manages reversible operations, duplicate prevention, and inverse compensation."""

    @classmethod
    def is_plan_reversible(
        cls,
        db: Session,
        plan_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """
        Determines whether a plan's completed operations are eligible for rollback.
        """
        plan = db.execute(
            select(WorkflowExecutionPlan).where(
                and_(
                    WorkflowExecutionPlan.id == plan_id,
                    WorkflowExecutionPlan.user_id == user_id,
                )
            )
        ).scalar_one_or_none()

        if not plan:
            return False, "Plan not found", []

        step_execs = db.execute(
            select(WorkflowStepExecution).where(
                and_(
                    WorkflowStepExecution.plan_id == plan_id,
                    WorkflowStepExecution.status == "COMPLETED",
                )
            )
        ).scalars().all()

        if not step_execs:
            return False, "No completed steps to roll back.", []

        details = []
        is_all_reversible = True

        for se in step_execs:
            contract = ActionRegistry.get(se.action_identifier)
            can_reverse = (
                contract.is_reversible
                if contract
                else (se.compensation_receipt is not None)
            )
            if not can_reverse:
                is_all_reversible = False

            details.append({
                "step_key": se.step_key,
                "action_identifier": se.action_identifier,
                "is_reversible": can_reverse,
                "has_receipt": se.compensation_receipt is not None,
                "compensation_status": se.compensation_status,
            })

        summary = (
            "All completed steps have registered compensating actions."
            if is_all_reversible
            else "Some completed steps cannot be automatically reversed."
        )
        return is_all_reversible, summary, details

    @classmethod
    def execute_plan_rollback(
        cls,
        db: Session,
        plan_id: uuid.UUID,
        user_id: uuid.UUID,
        triggered_by: str = "USER_MANUAL",
        reason: Optional[str] = None,
        force: bool = False,
    ) -> WorkflowRollbackRecord:
        """
        Executes inverse compensation for all eligible steps in reverse order.
        Prevents duplicate rollbacks and records a structured RollbackRecord.
        """
        plan = db.execute(
            select(WorkflowExecutionPlan).where(
                and_(
                    WorkflowExecutionPlan.id == plan_id,
                    WorkflowExecutionPlan.user_id == user_id,
                )
            )
        ).scalar_one_or_none()

        if not plan:
            raise ValueError(f"Plan '{plan_id}' not found.")

        # Duplicate rollback check
        existing_record = db.execute(
            select(WorkflowRollbackRecord).where(
                and_(
                    WorkflowRollbackRecord.plan_id == plan_id,
                    WorkflowRollbackRecord.status.in_([
                        RollbackStatusEnum.IN_PROGRESS.value,
                        RollbackStatusEnum.COMPLETED.value,
                    ]),
                )
            )
        ).scalars().first()

        if existing_record and not force:
            raise ValueError(
                f"Rollback already {existing_record.status.lower()} for plan '{plan_id}'."
            )

        # Retrieve completed steps with compensation receipts in reverse execution order
        step_execs = db.execute(
            select(WorkflowStepExecution)
            .where(
                and_(
                    WorkflowStepExecution.plan_id == plan_id,
                    WorkflowStepExecution.status == "COMPLETED",
                    WorkflowStepExecution.compensation_status == "PENDING",
                )
            )
            .order_by(WorkflowStepExecution.completed_at.desc())
        ).scalars().all()

        now = datetime.now(timezone.utc)
        record = WorkflowRollbackRecord(
            plan_id=plan_id,
            user_id=user_id,
            triggered_by=triggered_by,
            status=RollbackStatusEnum.IN_PROGRESS.value,
            total_steps_to_compensate=len(step_execs),
            compensated_steps_count=0,
            failed_compensations=[],
            compensation_details={"reason": reason},
            started_at=now,
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        AuditLogger.record_event(
            db=db,
            user_id=user_id,
            event_type=AuditEventType.ROLLBACK_TRIGGERED,
            plan_id=plan_id,
            payload={"reason": reason, "total_steps": len(step_execs)},
        )

        compensated_count = 0
        failed_list = []

        for se in step_execs:
            if not se.compensation_receipt:
                failed_list.append({
                    "step_key": se.step_key,
                    "action_identifier": se.action_identifier,
                    "error": "No compensation receipt recorded for step.",
                })
                continue

            try:
                comp_result = ActionHandlers.compensate(
                    db=db,
                    action_identifier=se.action_identifier,
                    compensation_payload=se.compensation_receipt,
                    user_id=user_id,
                )
                if comp_result.success:
                    se.compensation_status = "COMPLETED"
                    se.status = "COMPENSATED"
                    compensated_count += 1
                    AuditLogger.record_event(
                        db=db,
                        user_id=user_id,
                        event_type=AuditEventType.STEP_COMPENSATED,
                        plan_id=plan_id,
                        action_identifier=se.action_identifier,
                        step_key=se.step_key,
                        result_status="COMPENSATED",
                        payload=comp_result.output_payload,
                    )
                else:
                    failed_list.append({
                        "step_key": se.step_key,
                        "action_identifier": se.action_identifier,
                        "error": comp_result.error_message,
                    })
            except Exception as ex:
                failed_list.append({
                    "step_key": se.step_key,
                    "action_identifier": se.action_identifier,
                    "error": str(ex),
                })

        record.compensated_steps_count = compensated_count
        record.failed_compensations = failed_list
        record.completed_at = datetime.now(timezone.utc)

        if not failed_list:
            record.status = RollbackStatusEnum.COMPLETED.value
            plan.status = WorkflowLifecycleState.ROLLED_BACK.value
            AuditLogger.record_event(
                db=db,
                user_id=user_id,
                event_type=AuditEventType.ROLLBACK_COMPLETED,
                plan_id=plan_id,
                result_status="ROLLBACK_SUCCESSFUL",
                payload={"compensated_steps": compensated_count},
            )
        elif compensated_count > 0:
            record.status = RollbackStatusEnum.PARTIALLY_COMPLETED.value
            plan.status = WorkflowLifecycleState.PARTIALLY_COMPLETED.value
            AuditLogger.record_event(
                db=db,
                user_id=user_id,
                event_type=AuditEventType.ROLLBACK_FAILED,
                plan_id=plan_id,
                result_status="PARTIAL_ROLLBACK",
                payload={"failed_count": len(failed_list)},
            )
        else:
            record.status = RollbackStatusEnum.FAILED.value
            AuditLogger.record_event(
                db=db,
                user_id=user_id,
                event_type=AuditEventType.ROLLBACK_FAILED,
                plan_id=plan_id,
                result_status="ROLLBACK_FAILED",
                payload={"errors": failed_list},
            )

        plan.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(record)
        return record

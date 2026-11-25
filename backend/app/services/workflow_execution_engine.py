"""
Reliable Workflow Execution Engine (ContextIQ Phase 7.5).
Orchestrates:
- Strict approval and version verification
- Transactional state transitions (13-State FSM)
- Duplicate execution prevention and concurrency fencing
- Topological step traversal across DAG dependencies
- Bounded retries with exponential backoff on transient errors
- Step execution tracking, audit receipts, and partial failure handling
- Rollback and compensation stack unwinding
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.workflow_models import (
    WorkflowExecutionPlan,
    WorkflowPlanVersion,
    WorkflowStepExecution,
)
from app.schemas.workflow_schemas import (
    DependencyType,
    WorkflowDependencySchema,
    WorkflowLifecycleState,
    WorkflowStepSchema,
)
from app.schemas.safety_schemas import AuditEventType
from app.services.action_handlers import ActionHandlers, ActionResult
from app.services.policy_engine import PolicyEngine
from app.services.safety_engine import AuditLogger, EmergencyStopEngine, RollbackManager
from app.services.workflow_validator import WorkflowValidator
from app.core.metrics import metrics_registry

logger = logging.getLogger(__name__)


class ExecutionEngineError(Exception):
    pass


class ApprovalVerificationError(ExecutionEngineError):
    pass


class DuplicateExecutionError(ExecutionEngineError):
    pass


class EmergencyStopActiveError(ExecutionEngineError):
    pass


class WorkflowExecutionEngine:
    """
    Core executor that safely runs approved multi-step workflow plans.
    """

    MAX_STEP_RETRIES: int = 3
    INITIAL_BACKOFF_SECONDS: float = 0.05  # fast backoff for tests/microservices

    @classmethod
    def verify_approval(cls, db: Session, plan: WorkflowExecutionPlan, user_id: uuid.UUID) -> None:
        """
        Validates that user approval:
        1. Belongs to the correct user.
        2. Applies to the exact workflow version.
        3. Has not expired.
        4. Is in APPROVED or SCHEDULED state.
        """
        if plan.user_id != user_id:
            raise ApprovalVerificationError(f"Unauthorized: Plan '{plan.id}' does not belong to user '{user_id}'.")

        now = datetime.now(timezone.utc)
        if plan.expires_at is not None:
            # Normalize naive / aware comparison
            exp = plan.expires_at if plan.expires_at.tzinfo else plan.expires_at.replace(tzinfo=timezone.utc)
            if exp < now:
                plan.status = WorkflowLifecycleState.EXPIRED.value
                db.commit()
                raise ApprovalVerificationError(f"Approval expired on {exp.isoformat()}. Fresh proposal required.")

        allowed_exec_states = (
            WorkflowLifecycleState.APPROVED.value,
            WorkflowLifecycleState.SCHEDULED.value,
        )
        if plan.status not in allowed_exec_states:
            raise ApprovalVerificationError(
                f"Cannot execute workflow in status '{plan.status}'. Must be in 'APPROVED' or 'SCHEDULED' state."
            )

    @classmethod
    def execute_plan(
        cls,
        db: Session,
        plan_id: uuid.UUID,
        user_id: uuid.UUID,
        auto_rollback_on_failure: bool = False,
    ) -> WorkflowExecutionPlan:
        """
        Executes an approved workflow plan through its topological DAG.
        Safe against duplicate execution, tracks step receipts, and manages partial failures.
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
            raise ValueError(f"Workflow execution plan '{plan_id}' not found.")

        # 0. Emergency Stop & Kill Switch Check
        is_stopped, stop_event = EmergencyStopEngine.is_emergency_stop_active(db, user_id)
        if is_stopped and stop_event:
            raise EmergencyStopActiveError(
                f"Workflow execution halted: Emergency stop '{stop_event.scope}' is active. Reason: {stop_event.reason}"
            )

        # 1. Approval & Expiration Check
        cls.verify_approval(db, plan, user_id)

        start_time = time.perf_counter()

        # 2. Concurrency Fencing / State Transition to EXECUTING
        if plan.status == WorkflowLifecycleState.EXECUTING.value:
            raise DuplicateExecutionError(f"Workflow plan '{plan_id}' is already executing.")

        now = datetime.now(timezone.utc)
        plan.status = WorkflowLifecycleState.EXECUTING.value
        plan.executed_at = now
        plan.updated_at = now
        db.commit()

        # 3. Parse and Resolve Topological DAG Execution Order
        raw_steps = plan.plan_steps or []
        raw_deps = plan.plan_dependencies or []

        step_schemas = [WorkflowStepSchema.model_validate(s) for s in raw_steps]
        dep_schemas = [WorkflowDependencySchema.model_validate(d) for d in raw_deps]
        step_map = {s.step_key: s for s in step_schemas}

        execution_order = WorkflowValidator.resolve_execution_order(step_schemas, dep_schemas)

        # Dependency lookup maps
        # target_step_key -> list of dependencies it requires
        incoming_deps: Dict[str, List[WorkflowDependencySchema]] = {s: [] for s in execution_order}
        for d in dep_schemas:
            incoming_deps[d.target_step_key].append(d)

        # Step results cache
        step_status_map: Dict[str, str] = {}
        rollback_stack: List[Tuple[str, Dict[str, Any]]] = []  # [(action_id, comp_payload)]

        has_critical_failure = False
        has_optional_failure = False

        # 4. Sequential Topological Execution
        for step_key in execution_order:
            step = step_map[step_key]
            step_deps = incoming_deps.get(step_key, [])

            # Check if plan was cancelled in-flight
            db.refresh(plan)
            if plan.status == WorkflowLifecycleState.CANCELLED.value:
                logger.info(f"Execution of plan {plan_id} cancelled during processing.")
                break

            # Check if emergency stop tripped during in-flight execution
            is_stopped, stop_event = EmergencyStopEngine.is_emergency_stop_active(db, user_id)
            if is_stopped and stop_event:
                logger.warning(f"In-flight emergency stop triggered for plan {plan_id}.")
                plan.status = WorkflowLifecycleState.CANCELLED.value
                tc = dict(plan.trigger_context or {})
                tc["cancellation_reason"] = f"Emergency stop activated in-flight ({stop_event.scope}): {stop_event.reason}"
                plan.trigger_context = tc
                db.commit()
                break

            # Check dependency satisfaction
            deps_satisfied, skip_reason = cls._check_dependencies_satisfied(step_deps, step_status_map)
            if not deps_satisfied:
                step_status_map[step_key] = "SKIPPED"
                cls._record_step_execution(
                    db=db,
                    plan_id=plan.id,
                    step=step,
                    status="SKIPPED",
                    error_message=skip_reason,
                )
                if not step.is_optional:
                    has_critical_failure = True
                continue

            # Execute Step with Bounded Retries & Backoff
            step_result, step_exec_record = cls._execute_step_with_retries(
                db=db,
                plan_id=plan.id,
                step=step,
                user_id=user_id,
            )

            if step_result.success:
                step_status_map[step_key] = "COMPLETED"
                if step_result.compensation_payload:
                    rollback_stack.append((step.action_identifier, step_result.compensation_payload))
            else:
                step_status_map[step_key] = "FAILED"
                if step.is_optional:
                    has_optional_failure = True
                    logger.warning(f"Optional step '{step_key}' failed: {step_result.error_message}. Continuing workflow.")
                else:
                    has_critical_failure = True
                    logger.error(f"Critical step '{step_key}' failed: {step_result.error_message}. Halting workflow.")
                    break

        # 5. Determine Final Workflow State
        db.refresh(plan)
        if plan.status != WorkflowLifecycleState.CANCELLED.value:
            now = datetime.now(timezone.utc)
            plan.updated_at = now

            if has_critical_failure:
                plan.status = WorkflowLifecycleState.FAILED.value
                if auto_rollback_on_failure and rollback_stack:
                    logger.info(f"Auto-rollback triggered for failed plan {plan_id}.")
                    cls._unwind_rollback_stack(db, rollback_stack, user_id)
                    plan.status = WorkflowLifecycleState.ROLLED_BACK.value
            elif has_optional_failure:
                plan.status = WorkflowLifecycleState.PARTIALLY_COMPLETED.value
            else:
                plan.status = WorkflowLifecycleState.COMPLETED.value

            db.commit()
            db.refresh(plan)

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        success = plan.status in (
            WorkflowLifecycleState.COMPLETED.value,
            WorkflowLifecycleState.PARTIALLY_COMPLETED.value,
        )
        metrics_registry.record_workflow_execution(duration_ms, success)

        return plan

    @classmethod
    def _check_dependencies_satisfied(
        cls,
        deps: List[WorkflowDependencySchema],
        step_status_map: Dict[str, str],
    ) -> Tuple[bool, Optional[str]]:
        """Verifies if incoming dependencies for a step are satisfied."""
        for d in deps:
            src_status = step_status_map.get(d.source_step_key, "PENDING")
            if d.dependency_type == DependencyType.SUCCESS:
                if src_status != "COMPLETED":
                    return False, f"Dependent step '{d.source_step_key}' status is '{src_status}' (required COMPLETED)."
            elif d.dependency_type == DependencyType.COMPLETION:
                if src_status not in ("COMPLETED", "FAILED", "SKIPPED"):
                    return False, f"Dependent step '{d.source_step_key}' has not completed yet."
            elif d.dependency_type == DependencyType.FAILURE:
                if src_status != "FAILED":
                    return False, f"Failure branch dependent step '{d.source_step_key}' did not fail."
        return True, None

    @classmethod
    def _execute_step_with_retries(
        cls,
        db: Session,
        plan_id: uuid.UUID,
        step: WorkflowStepSchema,
        user_id: uuid.UUID,
    ) -> Tuple[ActionResult, WorkflowStepExecution]:
        """
        Executes a step with bounded retry attempts and exponential backoff on retriable errors.
        """
        idempotency_key = f"{plan_id}:{step.step_key}"

        # Fetch or initialize step execution record
        step_exec = db.execute(
            select(WorkflowStepExecution).where(
                and_(
                    WorkflowStepExecution.plan_id == plan_id,
                    WorkflowStepExecution.step_key == step.step_key,
                )
            )
        ).scalar_one_or_none()

        if not step_exec:
            step_exec = WorkflowStepExecution(
                plan_id=plan_id,
                step_key=step.step_key,
                action_identifier=step.action_identifier,
                status="EXECUTING",
                attempt_count=0,
                max_attempts=cls.MAX_STEP_RETRIES,
                idempotency_key=idempotency_key,
                input_payload=step.parameters,
                started_at=datetime.now(timezone.utc),
            )
            db.add(step_exec)
            db.commit()
            db.refresh(step_exec)
        else:
            step_exec.status = "EXECUTING"
            step_exec.started_at = datetime.now(timezone.utc)
            db.commit()

        # Deterministic Policy & Consent check prior to execution
        policy_eval = PolicyEngine.evaluate_action_policy(
            db=db,
            user_id=user_id,
            action_identifier=step.action_identifier,
            parameters=step.parameters,
            context={"plan_id": str(plan_id), "step_key": step.step_key, "is_approved": True, "is_executing": True},
        )
        if not policy_eval.allowed:
            step_exec.status = "BLOCKED_BY_POLICY"
            step_exec.error_message = f"Policy violation: {policy_eval.denial_reason}"
            step_exec.error_details = {
                "scope_required": policy_eval.scope_required.value if policy_eval.scope_required else None,
                "risk_tier": policy_eval.risk_tier.value if policy_eval.risk_tier else None,
            }
            step_exec.completed_at = datetime.now(timezone.utc)
            db.commit()
            AuditLogger.record_event(
                db=db,
                user_id=user_id,
                event_type=AuditEventType.STEP_BLOCKED_BY_POLICY,
                plan_id=plan_id,
                action_identifier=step.action_identifier,
                step_key=step.step_key,
                policy_decision="BLOCKED",
                error_details=step_exec.error_details,
            )
            return ActionResult(
                success=False,
                output_payload=step_exec.error_details or {},
                is_retriable=False,
                error_message=step_exec.error_message,
            ), step_exec

        # Record step dispatch audit
        AuditLogger.record_event(
            db=db,
            user_id=user_id,
            event_type=AuditEventType.STEP_DISPATCHED,
            plan_id=plan_id,
            action_identifier=step.action_identifier,
            step_key=step.step_key,
            payload=step.parameters,
        )

        # Retry loop
        last_result: Optional[ActionResult] = None
        while step_exec.attempt_count < step_exec.max_attempts:
            step_exec.attempt_count += 1
            step_idemp = f"{idempotency_key}:attempt_{step_exec.attempt_count}"

            result = ActionHandlers.execute(
                db=db,
                action_identifier=step.action_identifier,
                parameters=step.parameters,
                user_id=user_id,
                idempotency_key=step_idemp,
            )
            last_result = result

            if result.success:
                step_exec.status = "COMPLETED"
                step_exec.output_payload = result.output_payload
                step_exec.completed_at = datetime.now(timezone.utc)
                step_exec.error_message = None
                if result.compensation_payload:
                    step_exec.compensation_status = "PENDING"
                    step_exec.compensation_receipt = result.compensation_payload
                db.commit()
                AuditLogger.record_event(
                    db=db,
                    user_id=user_id,
                    event_type=AuditEventType.STEP_COMPLETED,
                    plan_id=plan_id,
                    action_identifier=step.action_identifier,
                    step_key=step.step_key,
                    result_status="COMPLETED",
                    payload=result.output_payload,
                )
                return result, step_exec

            # If failure is not retriable (e.g. auth failed, invalid parameters), break early
            if not result.is_retriable:
                break

            # Exponential backoff before next attempt
            if step_exec.attempt_count < step_exec.max_attempts:
                backoff = cls.INITIAL_BACKOFF_SECONDS * (2 ** (step_exec.attempt_count - 1))
                time.sleep(backoff)

        # Mark step as FAILED
        step_exec.status = "FAILED"
        step_exec.completed_at = datetime.now(timezone.utc)
        step_exec.error_message = last_result.error_message if last_result else "Execution failed"
        db.commit()
        AuditLogger.record_event(
            db=db,
            user_id=user_id,
            event_type=AuditEventType.STEP_FAILED,
            plan_id=plan_id,
            action_identifier=step.action_identifier,
            step_key=step.step_key,
            result_status="FAILED",
            error_details={"error": step_exec.error_message},
        )
        return last_result or ActionResult(success=False, output_payload={}, error_message="Failed"), step_exec

    @classmethod
    def _record_step_execution(
        cls,
        db: Session,
        plan_id: uuid.UUID,
        step: WorkflowStepSchema,
        status: str,
        error_message: Optional[str] = None,
    ) -> WorkflowStepExecution:
        now = datetime.now(timezone.utc)
        idemp = f"{plan_id}:{step.step_key}:skipped"
        step_exec = WorkflowStepExecution(
            plan_id=plan_id,
            step_key=step.step_key,
            action_identifier=step.action_identifier,
            status=status,
            attempt_count=0,
            max_attempts=cls.MAX_STEP_RETRIES,
            idempotency_key=idemp,
            input_payload=step.parameters,
            error_message=error_message,
            started_at=now,
            completed_at=now,
        )
        db.add(step_exec)
        db.commit()
        return step_exec

    @classmethod
    def _unwind_rollback_stack(
        cls,
        db: Session,
        rollback_stack: List[Tuple[str, Dict[str, Any]]],
        user_id: uuid.UUID,
    ) -> None:
        """Unwinds compensating actions in reverse order of execution."""
        while rollback_stack:
            action_id, comp_payload = rollback_stack.pop()
            try:
                res = ActionHandlers.compensate(db, action_id, comp_payload, user_id)
                logger.info(f"Compensated {action_id}: {res.success}")
            except Exception as ex:
                logger.error(f"Failed to compensate {action_id}: {ex}")

    @classmethod
    def rollback_plan(cls, db: Session, plan_id: uuid.UUID, user_id: uuid.UUID, reason: Optional[str] = None) -> WorkflowExecutionPlan:
        """Rolls back all completed steps for a completed or partially completed plan."""
        RollbackManager.execute_plan_rollback(db, plan_id, user_id, triggered_by="USER_MANUAL", reason=reason)
        plan = db.get(WorkflowExecutionPlan, plan_id)
        if not plan:
            raise ValueError(f"Plan '{plan_id}' not found.")
        return plan

    @classmethod
    def cancel_plan(cls, db: Session, plan_id: uuid.UUID, user_id: uuid.UUID) -> WorkflowExecutionPlan:
        """Cancels an in-flight or approved workflow execution plan."""
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

        plan.status = WorkflowLifecycleState.CANCELLED.value
        plan.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(plan)
        return plan

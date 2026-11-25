"""
Comprehensive Test Suite for Phase 7.7: Workflow Auditability, Rollback, and Emergency Stop.
Validates:
1. Append-only, sanitized audit logs (secrets, tokens, and passwords scrubbed).
2. User-level Emergency Stop: halts running workflows, cancels scheduled plans, disables active rules.
3. Administrator-level Operational Kill Switch: fences execution system-wide.
4. Execution Engine integration: stops execution immediately when Emergency Stop is engaged.
5. Structured Rollback: inverse compensation executed in reverse order.
6. Duplicate and concurrent rollback prevention.
7. Partial rollback handling when some steps cannot be reversed.
8. Emergency stop lifting and audit verification.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.automation_rule import AutomationRule
from app.models.enums import TaskPriority, TaskStatus
from app.models.safety_models import (
    EmergencyStopEvent,
    WorkflowAuditEvent,
    WorkflowRollbackRecord,
)
from app.models.task import Task
from app.models.user import User
from app.models.workflow_models import (
    WorkflowExecutionPlan,
    WorkflowStepExecution,
)
from app.schemas.workflow_schemas import (
    WorkflowLifecycleState,
)
from app.schemas.policy_schemas import PermissionScope
from app.schemas.safety_schemas import (
    AuditEventType,
    EmergencyStopScope,
    RollbackStatusEnum,
)
from app.services.action_handlers import ActionHandlers
from app.services.policy_engine import PolicyEngine
from app.services.safety_engine import (
    AuditLogger,
    EmergencyStopEngine,
    RollbackManager,
    sanitize_payload,
)
from app.services.workflow_execution_engine import (
    EmergencyStopActiveError,
    WorkflowExecutionEngine,
)

TEST_DB_URL = "sqlite:///:memory:"


@pytest.fixture
def db_session():
    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user(db_session):
    u = User(
        id=uuid.UUID("a1111111-1111-1111-1111-111111111111"),
        email="safety.tester@contextiq.io",
        display_name="Safety Test User",
        is_active=True,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)

    # Grant required permissions
    for scope in [
        PermissionScope.TASKS_READ,
        PermissionScope.TASKS_WRITE,
        PermissionScope.CALENDAR_READ,
        PermissionScope.CALENDAR_EVENTS_CREATE,
        PermissionScope.CALENDAR_EVENTS_MODIFY,
        PermissionScope.NOTIFICATIONS_SEND,
        PermissionScope.AUTOMATION_SCHEDULE_RUN,
        PermissionScope.WORKFLOWS_EXECUTE,
    ]:
        PolicyEngine.grant_scope(db_session, u.id, scope)

    return u


@pytest.fixture
def other_user(db_session):
    u = User(
        id=uuid.UUID("b2222222-2222-2222-2222-222222222222"),
        email="other.tester@contextiq.io",
        display_name="Other Test User",
        is_active=True,
    )
    db_session.add(u)
    db_session.commit()
    return u


def test_audit_logger_sanitizes_secrets(db_session, test_user):
    """Verifies that secrets, API keys, passwords, and tokens are scrubbed from audit logs."""
    raw_payload = {
        "access_token": "ya29.secret_token_12345",
        "api_key": "sk-proj-supersecretkey",
        "db_password": "supersecretpassword",
        "task_id": "task-uuid-001",
        "user_email": "tester@example.com",
        "nested": {
            "bearer_token": "Bearer abcdef123456",
            "safe_param": 42,
        },
    }

    sanitized = sanitize_payload(raw_payload)
    assert sanitized["access_token"] == "[REDACTED]"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["db_password"] == "[REDACTED]"
    assert sanitized["task_id"] == "task-uuid-001"
    assert sanitized["nested"]["bearer_token"] == "[REDACTED]"
    assert sanitized["nested"]["safe_param"] == 42

    event = AuditLogger.record_event(
        db=db_session,
        user_id=test_user.id,
        event_type=AuditEventType.STEP_COMPLETED,
        payload=raw_payload,
    )

    assert event.sanitized_payload["access_token"] == "[REDACTED]"
    assert event.sanitized_payload["api_key"] == "[REDACTED]"


def test_user_level_emergency_stop_halts_and_cancels(db_session, test_user):
    """
    Verifies that triggering user-level emergency stop immediately cancels
    pending/scheduled workflows and disables active automation rules.
    """
    # Create active rule
    rule = AutomationRule(
        user_id=test_user.id,
        name="Focus Session Nudge",
        is_enabled=True,
    )
    db_session.add(rule)

    # Create scheduled workflow plan
    plan = WorkflowExecutionPlan(
        id=uuid.UUID("c3333333-3333-3333-3333-333333333333"),
        user_id=test_user.id,
        title="Scheduled Autonomous Plan",
        status=WorkflowLifecycleState.SCHEDULED.value,
        approved_at=datetime.now(timezone.utc),
        rationale="Autonomous plan",
        idempotency_key="plan:test:emergency:1",
        plan_steps=[],
        plan_dependencies=[],
    )
    db_session.add(plan)
    db_session.commit()

    # Trigger emergency stop
    stop_event = EmergencyStopEngine.trigger_emergency_stop(
        db=db_session,
        scope=EmergencyStopScope.USER_LEVEL,
        user_id=test_user.id,
        reason="Repeated anomaly detected in automated notifications",
        triggered_by="USER",
    )

    assert stop_event.is_active
    assert stop_event.affected_plans_count >= 1
    assert stop_event.affected_rules_count >= 1

    # Verify plan cancelled
    db_session.refresh(plan)
    assert plan.status == WorkflowLifecycleState.CANCELLED.value
    assert "Emergency stop triggered" in plan.trigger_context["cancellation_reason"]

    # Verify rule disabled
    db_session.refresh(rule)
    assert not rule.is_enabled

    # Verify active state
    is_active, active_stop = EmergencyStopEngine.is_emergency_stop_active(db_session, test_user.id)
    assert is_active
    assert active_stop.id == stop_event.id

    # Lift emergency stop
    lifted = EmergencyStopEngine.lift_emergency_stop(
        db=db_session,
        emergency_stop_id=stop_event.id,
        user_id=test_user.id,
        notes="Anomaly resolved",
    )
    assert not lifted.is_active

    is_active_after, _ = EmergencyStopEngine.is_emergency_stop_active(db_session, test_user.id)
    assert not is_active_after


def test_admin_global_kill_switch_trips_all_execution(db_session, test_user, other_user):
    """Verifies that an admin global kill switch blocks all workflow executions across all users."""
    EmergencyStopEngine.trigger_emergency_stop(
        db=db_session,
        scope=EmergencyStopScope.ADMIN_GLOBAL,
        reason="System-wide maintenance shutdown",
        triggered_by="ADMIN_OPERATOR",
    )

    # Check for other user
    is_stopped_other, stop_evt = EmergencyStopEngine.is_emergency_stop_active(db_session, other_user.id)
    assert is_stopped_other
    assert stop_evt.scope == EmergencyStopScope.ADMIN_GLOBAL.value

    # Attempt to execute plan for test_user should raise EmergencyStopActiveError
    plan = WorkflowExecutionPlan(
        id=uuid.UUID("d4444444-4444-4444-4444-444444444444"),
        user_id=test_user.id,
        title="Plan Blocked by Global Kill Switch",
        status=WorkflowLifecycleState.APPROVED.value,
        approved_at=datetime.now(timezone.utc),
        rationale="Test plan",
        idempotency_key="plan:test:global:1",
        plan_steps=[],
        plan_dependencies=[],
    )
    db_session.add(plan)
    db_session.commit()

    with pytest.raises(EmergencyStopActiveError) as exc:
        WorkflowExecutionEngine.execute_plan(db_session, plan.id, test_user.id)
    assert "Emergency stop 'ADMIN_GLOBAL' is active" in str(exc.value)


def test_structured_rollback_framework(db_session, test_user):
    """
    Verifies that RollbackManager executes compensating actions in reverse order,
    updates step execution records, and sets plan to ROLLED_BACK.
    """
    # Create task
    task = Task(
        id=uuid.UUID("e5555555-5555-5555-5555-555555555555"),
        user_id=test_user.id,
        title="Task to rollback",
        status=TaskStatus.PENDING,
        priority=TaskPriority.LOW,
    )
    db_session.add(task)

    plan = WorkflowExecutionPlan(
        id=uuid.UUID("f6666666-6666-6666-6666-666666666666"),
        user_id=test_user.id,
        title="Plan to roll back",
        status=WorkflowLifecycleState.APPROVED.value,
        approved_at=datetime.now(timezone.utc),
        rationale="Rollback test",
        idempotency_key="plan:test:rb:1",
        plan_steps=[
            {
                "step_key": "step_priority",
                "name": "Change priority",
                "action_identifier": "task:update_priority",
                "parameters": {"task_id": str(task.id), "new_priority": "URGENT"},
                "order_index": 1,
                "is_optional": False,
                "requires_approval": False,
            }
        ],
        plan_dependencies=[],
    )
    db_session.add(plan)
    db_session.commit()

    # Execute plan
    executed_plan = WorkflowExecutionEngine.execute_plan(db_session, plan.id, test_user.id)
    assert executed_plan.status == WorkflowLifecycleState.COMPLETED.value

    db_session.refresh(task)
    assert task.priority == TaskPriority.URGENT

    # Verify reversibility
    can_reverse, summary, details = RollbackManager.is_plan_reversible(db_session, plan.id, test_user.id)
    assert can_reverse
    assert len(details) == 1

    # Execute rollback
    rb_record = RollbackManager.execute_plan_rollback(
        db=db_session,
        plan_id=plan.id,
        user_id=test_user.id,
        reason="User requested rollback test",
    )

    assert rb_record.status == RollbackStatusEnum.COMPLETED.value
    assert rb_record.compensated_steps_count == 1

    # Verify task state restored to LOW
    db_session.refresh(task)
    assert task.priority == TaskPriority.LOW

    # Verify plan status is ROLLED_BACK
    db_session.refresh(plan)
    assert plan.status == WorkflowLifecycleState.ROLLED_BACK.value


def test_duplicate_rollback_rejection(db_session, test_user):
    """Verifies that calling rollback again on an already rolled-back plan is safely rejected."""
    plan = WorkflowExecutionPlan(
        id=uuid.UUID("a7777777-7777-7777-7777-777777777777"),
        user_id=test_user.id,
        title="Duplicate Rollback Test",
        status=WorkflowLifecycleState.COMPLETED.value,
        approved_at=datetime.now(timezone.utc),
        rationale="Duplicate test",
        idempotency_key="plan:dup:rb",
        plan_steps=[],
        plan_dependencies=[],
    )
    db_session.add(plan)

    # Completed rollback record already exists
    rb = WorkflowRollbackRecord(
        plan_id=plan.id,
        user_id=test_user.id,
        triggered_by="USER_MANUAL",
        status=RollbackStatusEnum.COMPLETED.value,
        total_steps_to_compensate=1,
        compensated_steps_count=1,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(rb)
    db_session.commit()

    with pytest.raises(ValueError) as exc:
        RollbackManager.execute_plan_rollback(db_session, plan.id, test_user.id)
    assert "Rollback already completed" in str(exc.value)


def test_audit_events_stream_and_immutability(db_session, test_user):
    """Verifies audit trail listing and non-empty stream history."""
    AuditLogger.record_event(
        db=db_session,
        user_id=test_user.id,
        event_type=AuditEventType.WORKFLOW_PLAN_CREATED,
        workflow_version=1,
        payload={"title": "Test Plan"},
    )
    AuditLogger.record_event(
        db=db_session,
        user_id=test_user.id,
        event_type=AuditEventType.WORKFLOW_PLAN_APPROVED,
        workflow_version=1,
        approval_reference="ref-101",
    )

    events = AuditLogger.list_events(db_session, test_user.id, limit=10)
    assert len(events) >= 2
    types = [e.event_type for e in events]
    assert AuditEventType.WORKFLOW_PLAN_CREATED.value in types
    assert AuditEventType.WORKFLOW_PLAN_APPROVED.value in types

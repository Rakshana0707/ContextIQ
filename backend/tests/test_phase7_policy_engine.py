"""
Comprehensive Test Suite for Phase 7.6: Permission, Consent, and Policy Enforcement Engine.
Validates:
1. Consent grants and listing
2. Deterministic policy evaluation & scope requirements
3. Cross-user isolation / tenant boundary enforcement
4. Consequential action approval requirements
5. Quiet hours notification suppression
6. Revocation cascade: cancels active workflows requiring revoked scope
7. Workflow execution engine integration: blocks unconsented actions (BLOCKED_BY_POLICY) without retries
8. Immutable policy audit trails
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.enums import TaskPriority, TaskStatus
from app.models.notification_models import UserNotificationPreference
from app.models.policy_models import PolicyAuditTrail, UserPolicyConsent
from app.models.task import Task
from app.models.user import User
from app.models.workflow_models import (
    WorkflowExecutionPlan,
    WorkflowStepExecution,
)
from app.schemas.workflow_schemas import (
    WorkflowLifecycleState,
    WorkflowStepSchema,
)
from app.schemas.policy_schemas import (
    ActionRiskTier,
    ConsentSource,
    ConsentStatusEnum,
    PermissionScope,
)
from app.schemas.workflow_schemas import WorkflowStepSchema
from app.services.policy_engine import PolicyEngine
from app.services.workflow_execution_engine import WorkflowExecutionEngine

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
def user_a(db_session):
    u = User(
        id=uuid.UUID("a1111111-1111-1111-1111-111111111111"),
        email="usera@contextiq.ai",
        display_name="User A",
        hashed_password="pw",
    )
    db_session.add(u)
    db_session.commit()
    return u


@pytest.fixture
def user_b(db_session):
    u = User(
        id=uuid.UUID("b2222222-2222-2222-2222-222222222222"),
        email="userb@contextiq.ai",
        display_name="User B",
        hashed_password="pw",
    )
    db_session.add(u)
    db_session.commit()
    return u


def test_grant_and_list_permissions(db_session, user_a):
    """Verifies granting and listing permission scopes."""
    consent = PolicyEngine.grant_scope(
        db=db_session,
        user_id=user_a.id,
        scope=PermissionScope.TASKS_WRITE,
        source=ConsentSource.USER_EXPLICIT,
    )

    assert consent.scope == PermissionScope.TASKS_WRITE.value
    assert consent.consent_status == ConsentStatusEnum.GRANTED.value
    assert consent.user_id == user_a.id

    overview = PolicyEngine.get_user_policy_overview(db_session, user_a.id)
    assert PermissionScope.TASKS_WRITE.value in overview["active_scopes"]
    assert len(overview["permissions"]) == 1


def test_unconsented_action_denied(db_session, user_a):
    """Verifies deterministic denial when scope is not granted."""
    result = PolicyEngine.evaluate_action_policy(
        db=db_session,
        user_id=user_a.id,
        action_identifier="task:update_priority",
        parameters={"task_id": "none"},
    )

    assert not result.allowed
    assert result.scope_required == PermissionScope.TASKS_WRITE
    assert "not granted" in result.denial_reason


def test_tenant_boundary_violation_denied(db_session, user_a, user_b):
    """Verifies that an action targeting another user's task is strictly denied."""
    # Grant User A tasks:write permission
    PolicyEngine.grant_scope(
        db=db_session,
        user_id=user_a.id,
        scope=PermissionScope.TASKS_WRITE,
    )

    # Create task belonging to User B
    b_task = Task(
        id=uuid.UUID("e5555555-5555-5555-5555-555555555555"),
        user_id=user_b.id,
        title="User B Secret Project",
        status=TaskStatus.PENDING,
        priority=TaskPriority.LOW,
    )
    db_session.add(b_task)
    db_session.commit()

    # User A attempts to mutate User B's task
    result = PolicyEngine.evaluate_action_policy(
        db=db_session,
        user_id=user_a.id,
        action_identifier="task:update_priority",
        parameters={"task_id": str(b_task.id), "new_priority": "URGENT"},
    )

    assert not result.allowed
    assert "Tenant boundary violation" in result.denial_reason


def test_consequential_action_approval_requirement(db_session, user_a):
    """Verifies that Tier 2 & Tier 3 actions require explicit approval before execution."""
    PolicyEngine.grant_scope(
        db=db_session,
        user_id=user_a.id,
        scope=PermissionScope.CALENDAR_EVENTS_MODIFY,
    )

    # Executing without is_approved=True
    result = PolicyEngine.evaluate_action_policy(
        db=db_session,
        user_id=user_a.id,
        action_identifier="calendar:reschedule_event",
        parameters={"event_id": "cal-01"},
        context={"is_executing": True, "is_approved": False},
    )

    assert not result.allowed
    assert result.risk_tier == ActionRiskTier.CONSEQUENTIAL_EXTERNAL_ACTION
    assert "requires explicit user approval" in result.denial_reason

    # Executing with is_approved=True
    approved_result = PolicyEngine.evaluate_action_policy(
        db=db_session,
        user_id=user_a.id,
        action_identifier="calendar:reschedule_event",
        parameters={"event_id": "cal-01"},
        context={"is_executing": True, "is_approved": True},
    )
    assert approved_result.allowed


def test_quiet_hours_notification_suppression(db_session, user_a):
    """Verifies that notifications are blocked when quiet hours are active."""
    PolicyEngine.grant_scope(
        db=db_session,
        user_id=user_a.id,
        scope=PermissionScope.NOTIFICATIONS_SEND,
    )

    # Set quiet hours preference (22:00 to 08:00)
    pref = UserNotificationPreference(
        user_id=user_a.id,
        quiet_hours_enabled=True,
        quiet_hours_start=22,
        quiet_hours_end=8,
    )
    db_session.add(pref)
    db_session.commit()

    # Current UTC hour is 23:00 (during quiet hours)
    assert PolicyEngine.is_quiet_hours_active(db_session, user_a.id, current_hour=23)
    # Current UTC hour is 14:00 (outside quiet hours)
    assert not PolicyEngine.is_quiet_hours_active(db_session, user_a.id, current_hour=14)


def test_revocation_cascades_to_scheduled_workflows(db_session, user_a):
    """Verifies that revoking consent automatically cancels affected plans."""
    PolicyEngine.grant_scope(
        db=db_session,
        user_id=user_a.id,
        scope=PermissionScope.CALENDAR_EVENTS_CREATE,
    )

    # Create plan requiring calendar:insert_focus_block
    plan = WorkflowExecutionPlan(
        id=uuid.UUID("f6666666-6666-6666-6666-666666666666"),
        user_id=user_a.id,
        title="Calendar Scheduling Plan",
        status=WorkflowLifecycleState.APPROVED.value,
        approved_at=datetime.now(timezone.utc),
        rationale="Calendar scheduling plan",
        idempotency_key="plan:test:cal",
        plan_steps=[
            {
                "step_key": "step_1",
                "name": "Add focus block",
                "action_identifier": "calendar:insert_focus_block",
                "parameters": {"title": "Focus Time"},
                "order_index": 1,
                "is_optional": False,
                "requires_approval": True,
            }
        ],
        plan_dependencies=[],
    )
    db_session.add(plan)
    db_session.commit()

    # Revoke scope
    PolicyEngine.revoke_scope(
        db=db_session,
        user_id=user_a.id,
        scope=PermissionScope.CALENDAR_EVENTS_CREATE,
        reason="Revoked by user in settings",
    )

    db_session.refresh(plan)
    assert plan.status == WorkflowLifecycleState.CANCELLED.value
    assert "revoked permission scope" in plan.trigger_context.get("cancellation_reason", "")


def test_execution_engine_blocks_unconsented_step(db_session, user_a):
    """
    Verifies that the workflow execution engine stops at step execution
    if permission scope is missing, setting BLOCKED_BY_POLICY with no retries.
    """
    # Do NOT grant tasks:write to user_a
    plan = WorkflowExecutionPlan(
        id=uuid.UUID("d4444444-4444-4444-4444-444444444444"),
        user_id=user_a.id,
        title="Unconsented Task Priority Modification",
        status=WorkflowLifecycleState.APPROVED.value,
        approved_at=datetime.now(timezone.utc),
        rationale="Priority modification plan",
        idempotency_key="plan:unconsented:1",
        plan_steps=[
            {
                "step_key": "step_priority",
                "name": "Update Priority",
                "action_identifier": "task:update_priority",
                "parameters": {"task_id": "dummy", "new_priority": "HIGH"},
                "order_index": 1,
                "is_optional": False,
                "requires_approval": False,
            }
        ],
        plan_dependencies=[],
    )
    db_session.add(plan)
    db_session.commit()

    executed_plan = WorkflowExecutionEngine.execute_plan(
        db=db_session,
        plan_id=plan.id,
        user_id=user_a.id,
    )

    assert executed_plan.status == WorkflowLifecycleState.FAILED.value

    step_exec = db_session.query(WorkflowStepExecution).filter(
        WorkflowStepExecution.plan_id == plan.id
    ).first()

    assert step_exec is not None
    assert step_exec.status == "BLOCKED_BY_POLICY"
    assert "Policy violation" in step_exec.error_message
    assert step_exec.attempt_count == 0  # No retry loop initiated


def test_policy_audit_trail_recorded(db_session, user_a):
    """Verifies that every evaluation and grant generates an immutable audit trail."""
    PolicyEngine.grant_scope(
        db=db_session,
        user_id=user_a.id,
        scope=PermissionScope.TASKS_READ,
    )

    PolicyEngine.evaluate_action_policy(
        db=db_session,
        user_id=user_a.id,
        action_identifier="tasks:read",
    )

    records = db_session.query(PolicyAuditTrail).filter(
        PolicyAuditTrail.user_id == user_a.id
    ).all()

    assert len(records) >= 2
    decisions = [r.decision for r in records]
    assert "GRANTED" in decisions
    assert "ALLOWED" in decisions

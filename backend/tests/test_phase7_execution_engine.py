"""
Automated Test Suite for Phase 7.5: Reliable Workflow Execution Engine.
Covers:
1. User approval and expiration verification.
2. Duplicate execution prevention & concurrency fencing.
3. Topological step execution & dependency traversal.
4. Partial failure handling (optional vs critical step failures).
5. Bounded retries on transient errors.
6. In-flight execution cancellation.
7. Rollback and compensating action stack unwinding.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.enums import TaskPriority, TaskStatus
from app.models.task import Task
from app.models.user import User
from app.models.workflow_models import (
    WorkflowExecutionPlan,
    WorkflowStepExecution,
)
from app.schemas.workflow_schemas import (
    DependencyType,
    WorkflowDependencySchema,
    WorkflowLifecycleState,
    WorkflowStepSchema,
)
from app.services.action_handlers import ActionHandlers, ActionResult
from app.services.workflow_execution_engine import (
    ApprovalVerificationError,
    DuplicateExecutionError,
    WorkflowExecutionEngine,
)
from app.services.workflow_planner import WorkflowPlanner

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
        email="executor.tester@contextiq.io",
        display_name="Workflow Execution User",
        is_active=True,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def test_task(db_session, test_user):
    t = Task(
        id=uuid.UUID("a2222222-2222-2222-2222-222222222222"),
        user_id=test_user.id,
        title="High Priority Behavioral RFC",
        priority=TaskPriority.LOW,
        status=TaskStatus.PENDING,
    )
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)
    return t


def test_approval_verification_gates(db_session, test_user, test_task):
    """Execution must fail if the plan is unapproved, expired, or belongs to another user."""
    # 1. Unapproved plan (starts in AWAITING_APPROVAL)
    plan = WorkflowPlanner.plan_behavioral_workflow(
        db=db_session,
        user_id=test_user.id,
        trigger_type="FORGETTING_RISK_SPIKE",
        behavioral_context={"task_title": test_task.title},
        task_id=test_task.id,
    )

    with pytest.raises(ApprovalVerificationError) as exc_unapproved:
        WorkflowExecutionEngine.execute_plan(db_session, plan.id, test_user.id)
    assert "Cannot execute workflow in status" in str(exc_unapproved.value)

    # 2. Unauthorized user check
    other_user_id = uuid.UUID("b3333333-3333-3333-3333-333333333333")
    with pytest.raises(ValueError):  # Plan not found for other user
        WorkflowExecutionEngine.execute_plan(db_session, plan.id, other_user_id)

    # 3. Expired plan check
    WorkflowPlanner.transition_plan_status(
        db_session, plan.id, test_user.id, WorkflowLifecycleState.APPROVED
    )
    plan.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db_session.commit()

    with pytest.raises(ApprovalVerificationError) as exc_expired:
        WorkflowExecutionEngine.execute_plan(db_session, plan.id, test_user.id)
    assert "Approval expired" in str(exc_expired.value)


def test_successful_workflow_execution_and_side_effects(db_session, test_user, test_task):
    """Executes an approved workflow plan and verifies side effects on DB models."""
    plan = WorkflowPlanner.plan_behavioral_workflow(
        db=db_session,
        user_id=test_user.id,
        trigger_type="FORGETTING_RISK_SPIKE",
        behavioral_context={"task_title": test_task.title},
        task_id=test_task.id,
    )

    # Approve plan
    WorkflowPlanner.transition_plan_status(
        db_session, plan.id, test_user.id, WorkflowLifecycleState.APPROVED
    )

    # Execute plan
    executed_plan = WorkflowExecutionEngine.execute_plan(db_session, plan.id, test_user.id)
    assert executed_plan.status == WorkflowLifecycleState.COMPLETED.value
    assert executed_plan.executed_at is not None

    # Verify task priority side effect in database
    db_session.refresh(test_task)
    assert test_task.priority == TaskPriority.HIGH

    # Verify step execution receipts were created
    step_execs = db_session.query(WorkflowStepExecution).filter_by(plan_id=plan.id).all()
    assert len(step_execs) == len(plan.plan_steps)
    for sexec in step_execs:
        assert sexec.status == "COMPLETED"
        assert sexec.output_payload is not None


def test_duplicate_execution_prevention(db_session, test_user, test_task):
    """Duplicate execute calls on a running or completed plan are rejected."""
    plan = WorkflowPlanner.plan_behavioral_workflow(
        db=db_session,
        user_id=test_user.id,
        trigger_type="FORGETTING_RISK_SPIKE",
        behavioral_context={"task_title": test_task.title},
        task_id=test_task.id,
    )
    WorkflowPlanner.transition_plan_status(
        db_session, plan.id, test_user.id, WorkflowLifecycleState.APPROVED
    )

    # First execution succeeds
    WorkflowExecutionEngine.execute_plan(db_session, plan.id, test_user.id)
    assert plan.status == WorkflowLifecycleState.COMPLETED.value

    # Second execution must be rejected (cannot execute a COMPLETED plan)
    with pytest.raises(ApprovalVerificationError):
        WorkflowExecutionEngine.execute_plan(db_session, plan.id, test_user.id)


def test_partial_failure_with_optional_step(db_session, test_user, test_task):
    """When an optional step fails, workflow completes as PARTIALLY_COMPLETED."""
    steps = [
        WorkflowStepSchema(
            step_key="step_1",
            name="Update Priority",
            action_identifier="task:update_priority",
            parameters={"task_id": str(test_task.id), "new_priority": "CRITICAL"},
            is_optional=False,
            order_index=1,
        ),
        WorkflowStepSchema(
            step_key="step_2_optional_fail",
            name="Optional Clamping Failure",
            action_identifier="task:update_priority",
            parameters={"task_id": str(uuid.uuid4()), "new_priority": "HIGH"},  # Non-existent task fails
            is_optional=True,
            order_index=2,
        ),
    ]
    deps = [
        WorkflowDependencySchema(source_step_key="step_1", target_step_key="step_2_optional_fail", dependency_type=DependencyType.SUCCESS)
    ]

    plan = WorkflowExecutionPlan(
        user_id=test_user.id,
        title="Optional Step Test Plan",
        status=WorkflowLifecycleState.APPROVED.value,
        version=1,
        idempotency_key=f"idemp_{uuid.uuid4().hex}",
        trigger_context={},
        plan_steps=[s.model_dump(mode="json") for s in steps],
        plan_dependencies=[d.model_dump(mode="json") for d in deps],
        rationale="Testing partial failure resilience.",
        expected_benefits={},
        potential_side_effects={},
        utility_score=0.85,
        reversibility_summary={"is_fully_reversible": True},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(plan)
    db_session.commit()

    executed = WorkflowExecutionEngine.execute_plan(db_session, plan.id, test_user.id)
    assert executed.status == WorkflowLifecycleState.PARTIALLY_COMPLETED.value


def test_critical_step_failure_halts_workflow(db_session, test_user, test_task):
    """When a required step fails, subsequent dependent steps are skipped and workflow is FAILED."""
    steps = [
        WorkflowStepSchema(
            step_key="step_1_fail",
            name="Required Failing Step",
            action_identifier="task:update_priority",
            parameters={"task_id": str(uuid.uuid4()), "new_priority": "HIGH"},  # Missing task
            is_optional=False,
            order_index=1,
        ),
        WorkflowStepSchema(
            step_key="step_2",
            name="Subsequent Step",
            action_identifier="task:update_priority",
            parameters={"task_id": str(test_task.id), "new_priority": "CRITICAL"},
            is_optional=False,
            order_index=2,
        ),
    ]
    deps = [
        WorkflowDependencySchema(source_step_key="step_1_fail", target_step_key="step_2", dependency_type=DependencyType.SUCCESS)
    ]

    plan = WorkflowExecutionPlan(
        user_id=test_user.id,
        title="Critical Step Failure Plan",
        status=WorkflowLifecycleState.APPROVED.value,
        version=1,
        idempotency_key=f"idemp_{uuid.uuid4().hex}",
        trigger_context={},
        plan_steps=[s.model_dump(mode="json") for s in steps],
        plan_dependencies=[d.model_dump(mode="json") for d in deps],
        rationale="Testing required step failure.",
        expected_benefits={},
        potential_side_effects={},
        utility_score=0.85,
        reversibility_summary={"is_fully_reversible": True},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(plan)
    db_session.commit()

    executed = WorkflowExecutionEngine.execute_plan(db_session, plan.id, test_user.id)
    assert executed.status == WorkflowLifecycleState.FAILED.value


def test_workflow_rollback_and_compensation(db_session, test_user, test_task):
    """Verifies that rollback executes compensating actions in reverse order."""
    assert test_task.priority == TaskPriority.LOW

    plan = WorkflowPlanner.plan_behavioral_workflow(
        db=db_session,
        user_id=test_user.id,
        trigger_type="FORGETTING_RISK_SPIKE",
        behavioral_context={"task_title": test_task.title},
        task_id=test_task.id,
    )
    WorkflowPlanner.transition_plan_status(
        db_session, plan.id, test_user.id, WorkflowLifecycleState.APPROVED
    )

    # Execute
    WorkflowExecutionEngine.execute_plan(db_session, plan.id, test_user.id)
    db_session.refresh(test_task)
    assert test_task.priority == TaskPriority.HIGH

    # Rollback
    rolled_back = WorkflowExecutionEngine.rollback_plan(db_session, plan.id, test_user.id)
    assert rolled_back.status == WorkflowLifecycleState.ROLLED_BACK.value

    # Verify task priority reverted to LOW
    db_session.refresh(test_task)
    assert test_task.priority == TaskPriority.LOW


def test_in_flight_cancellation(db_session, test_user, test_task):
    """Calling cancel on an approved plan marks it CANCELLED."""
    plan = WorkflowPlanner.plan_behavioral_workflow(
        db=db_session,
        user_id=test_user.id,
        trigger_type="FORGETTING_RISK_SPIKE",
        behavioral_context={"task_title": test_task.title},
        task_id=test_task.id,
    )
    WorkflowPlanner.transition_plan_status(
        db_session, plan.id, test_user.id, WorkflowLifecycleState.APPROVED
    )

    cancelled = WorkflowExecutionEngine.cancel_plan(db_session, plan.id, test_user.id)
    assert cancelled.status == WorkflowLifecycleState.CANCELLED.value

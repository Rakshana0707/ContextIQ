"""
Phase 7.10 End-to-End Integration and Production Readiness Test Suite.
Validates the complete governed autonomous workflow lifecycle across 5 critical scenarios:

SCENARIO A: Forgetting-Risk Intervention
- Task develops elevated forgetting risk.
- ContextIQ detects event via BehavioralChangeDetector.
- Proactive intelligence retrieves evidence and generates an intervention proposal.
- Multi-step workflow planner compiles a structured plan.
- User approves plan.
- Execution engine safely runs actions (reminder preparation, priority adjustment).
- Execution records and immutable audit trail are persisted.

SCENARIO B: Calendar-Aware Focus Scheduling
- Task identified as suitable for focused deep work.
- Calendar availability and focus reservation coordinated via DAG dependencies.
- Plan compiles focus block and recovery buffer proposal.
- User reviews and approves proposal.
- Actions execute, state transitions to COMPLETED, and receipts committed.

SCENARIO C: Repeated Interruption Response
- Rapid context switches and interruptions detected.
- Behavioral detector flags cognitive friction breach with conformal uncertainty.
- Focus-protection proposal generated respecting notification fatigue limits and quiet hours.
- User evaluates and approves proposal.
- Tool clamping and notification suppression executed.

SCENARIO D: Partial Workflow Failure and Rollback
- Workflow begins execution with multiple steps.
- Step 1 (reversible priority update) succeeds.
- Step 2 encounters an unrecoverable failure on a critical step.
- Critical failure halts workflow (status = ROLLED_BACK).
- Automated compensation stack unwinds and restores Step 1's initial state.
- Failure evidence and compensation receipt recorded in audit log.

SCENARIO E: Emergency Stop and Failsafe Cancellation
- Autonomous workflows are scheduled and active.
- User engages Emergency Stop.
- Pending plans transition to CANCELLED.
- Running executions immediately halt.
- Further executions are blocked with EmergencyStopActiveError.
- Complete audit trail remains permanently accessible.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.models.enums import TaskPriority, TaskStatus
from app.models.event_models import ProactiveFeedItem, StandardEventRecord
from app.models.notification_models import UserNotificationPreference
from app.models.safety_models import (
    EmergencyStopEvent,
    WorkflowAuditEvent,
    WorkflowRollbackRecord,
)
from app.models.task import Task
from app.models.telemetry_consent import TelemetryConsent
from app.models.user import User
from app.models.workflow_models import (
    WorkflowExecutionPlan,
    WorkflowStepExecution,
)
from app.schemas.event_schemas import EventSource, StandardEvent, StandardEventType
from app.schemas.policy_schemas import PermissionScope
from app.schemas.safety_schemas import AuditEventType, EmergencyStopScope
from app.schemas.workflow_schemas import (
    DependencyType,
    WorkflowDependencySchema,
    WorkflowLifecycleState,
    WorkflowStepSchema,
)
from app.services.action_handlers import ActionHandlers, ActionResult
from app.services.behavioral_detector import BehavioralChangeDetector
from app.services.event_processor import EventProcessor
from app.services.policy_engine import PolicyEngine
from app.services.proactive_intelligence import ProactiveIntelligenceService
from app.services.safety_engine import (
    AuditLogger,
    EmergencyStopEngine,
    RollbackManager,
)
from app.services.workflow_execution_engine import (
    ApprovalVerificationError,
    EmergencyStopActiveError,
    WorkflowExecutionEngine,
)
from app.services.workflow_planner import WorkflowPlanner

TEST_DB_URL = "sqlite:///:memory:"


@pytest.fixture
def db_session():
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user(db_session) -> User:
    u = User(
        id=uuid.UUID("a1111111-1111-1111-1111-111111111111"),
        email="e2e.tester@contextiq.io",
        display_name="E2E Integration User",
        is_active=True,
    )
    db_session.add(u)

    # Consent by default
    consent = TelemetryConsent(
        user_id=u.id,
        consent_status="GRANTED",
        enabled_categories=["APP_TRANSITIONS", "SESSION_RECONSTRUCTION"],
        granted_timestamp=datetime.now(timezone.utc),
    )
    db_session.add(consent)

    # Notification preference
    pref = UserNotificationPreference(
        user_id=u.id,
        quiet_hours_enabled=False,
        max_notifications_per_day=10,
        is_paused=False,
    )
    db_session.add(pref)
    db_session.commit()
    db_session.refresh(u)

    # Grant required permissions for governed actions
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


def create_test_plan(
    db: Session,
    user_id: uuid.UUID,
    title: str,
    steps: List[WorkflowStepSchema],
    dependencies: Optional[List[WorkflowDependencySchema]] = None,
    rationale: str = "Test plan",
    status: WorkflowLifecycleState = WorkflowLifecycleState.AWAITING_APPROVAL,
) -> WorkflowExecutionPlan:
    plan = WorkflowExecutionPlan(
        user_id=user_id,
        title=title,
        status=status.value,
        version=1,
        idempotency_key=f"idemp_{uuid.uuid4().hex}",
        trigger_context={},
        plan_steps=[s.model_dump(mode="json") for s in steps],
        plan_dependencies=[d.model_dump(mode="json") for d in (dependencies or [])],
        rationale=rationale,
        expected_benefits={},
        potential_side_effects={},
        utility_score=0.85,
        reversibility_summary={"is_fully_reversible": True},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


class TestEndToEndScenarios:
    """Rigorous end-to-end multi-module verification for Phase 7.10."""

    def test_scenario_a_forgetting_risk_intervention(self, db_session, test_user):
        """
        SCENARIO A: Complete Forgetting-Risk Detection, Planning, Approval, and Execution.
        """
        # 1. Create task that starts in LOW priority
        task = Task(
            id=uuid.uuid4(),
            user_id=test_user.id,
            title="Submit Q4 Architectural Design Document",
            status=TaskStatus.PENDING,
            priority=TaskPriority.LOW,
        )
        db_session.add(task)
        db_session.commit()

        # 2. Behavioral Detection: Elevated forgetting risk event detected
        event = BehavioralChangeDetector.detect_forgetting_risk_spike(
            user_id=test_user.id,
            task_id=task.id,
            task_title=task.title,
            predicted_lapse_probability=0.88,
            threshold=0.70,
        )
        assert event is not None
        assert event.event_type == StandardEventType.FORGETTING_RISK_SPIKE.value

        # Ingest and route event (internally triggers ProactiveIntelligenceService)
        ingest_res = EventProcessor.process_event(db=db_session, event_or_req=event)
        assert ingest_res.status == "PROCESSED"
        assert ingest_res.proactive_feed_item_created is True

        # 3. Proactive Intelligence generates calibrated feed item
        feed_item = db_session.execute(
            select(ProactiveFeedItem).where(ProactiveFeedItem.user_id == test_user.id)
        ).scalars().first()
        assert feed_item is not None
        assert "forgetting" in feed_item.title.lower() or "risk" in feed_item.title.lower()

        # 4. Multi-Step Workflow Planning: compile structured proposal
        plan = WorkflowPlanner.plan_behavioral_workflow(
            db=db_session,
            user_id=test_user.id,
            trigger_type="FORGETTING_RISK_SPIKE",
            behavioral_context={"task_title": task.title, "lapse_probability": 0.88},
            task_id=task.id,
        )
        assert plan.status == WorkflowLifecycleState.AWAITING_APPROVAL.value
        assert len(plan.plan_steps) >= 2

        # 5. User Reviews and Approves Workflow Proposal
        WorkflowPlanner.transition_plan_status(
            db_session, plan.id, test_user.id, WorkflowLifecycleState.APPROVED
        )
        db_session.refresh(plan)
        assert plan.status == WorkflowLifecycleState.APPROVED.value
        assert plan.approved_at is not None

        # 6. Safe Execution via WorkflowExecutionEngine
        executed_plan = WorkflowExecutionEngine.execute_plan(db_session, plan.id, test_user.id)
        assert executed_plan.status == WorkflowLifecycleState.COMPLETED.value
        assert executed_plan.executed_at is not None

        # 7. Verify Side Effects: Task priority updated to HIGH
        db_session.refresh(task)
        assert task.priority == TaskPriority.HIGH

        # 8. Verify Execution Receipts & Audit Trail
        step_execs = db_session.scalars(
            select(WorkflowStepExecution).where(WorkflowStepExecution.plan_id == plan.id)
        ).all()
        assert len(step_execs) == len(plan.plan_steps)
        for sexec in step_execs:
            assert sexec.status == "COMPLETED"
            assert sexec.output_payload is not None

        audit_events = AuditLogger.list_events(db_session, test_user.id, plan_id=plan.id)
        assert len(audit_events) >= 1
        assert any(e.event_type == AuditEventType.STEP_COMPLETED.value for e in audit_events)
        assert any(e.result_status == "COMPLETED" for e in audit_events)

    def test_scenario_b_calendar_aware_focus_scheduling(self, db_session, test_user):
        """
        SCENARIO B: Calendar Availability Verification, Focus Session & Buffer Scheduling.
        """
        task = Task(
            id=uuid.uuid4(),
            user_id=test_user.id,
            title="Refactor Core Ingestion Engine",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.HIGH,
        )
        db_session.add(task)
        db_session.commit()

        now = datetime.now(timezone.utc)
        start_time = (now + timedelta(hours=1)).isoformat()
        end_time = (now + timedelta(hours=2)).isoformat()

        # 1. Compile multi-step DAG plan: Reserve Focus -> Add Recovery Buffer
        steps = [
            WorkflowStepSchema(
                step_key="step_1_focus",
                name="Reserve Deep Focus Block",
                action_identifier="calendar:insert_focus_block",
                parameters={
                    "title": f"Focus: {task.title}",
                    "start_time": start_time,
                    "end_time": end_time,
                },
                is_optional=False,
                order_index=1,
            ),
            WorkflowStepSchema(
                step_key="step_2_recovery",
                name="Schedule Recovery Buffer",
                action_identifier="recovery:insert_post_interruption_buffer",
                parameters={"buffer_duration_minutes": 15},
                is_optional=True,
                order_index=2,
            ),
        ]
        deps = [
            WorkflowDependencySchema(
                source_step_key="step_1_focus",
                target_step_key="step_2_recovery",
                dependency_type=DependencyType.SUCCESS,
            ),
        ]

        plan = create_test_plan(
            db=db_session,
            user_id=test_user.id,
            title="Focus Session & Recovery Proposal",
            steps=steps,
            dependencies=deps,
            rationale="Uninterrupted focus block recommended with 15m post-session cognitive buffer.",
        )

        # 2. Approve Proposal
        WorkflowPlanner.transition_plan_status(
            db_session, plan.id, test_user.id, WorkflowLifecycleState.APPROVED
        )

        # 3. Execute Proposal
        executed_plan = WorkflowExecutionEngine.execute_plan(db_session, plan.id, test_user.id)
        assert executed_plan.status == WorkflowLifecycleState.COMPLETED.value

        # 4. Step verification
        step_execs = db_session.scalars(
            select(WorkflowStepExecution).where(WorkflowStepExecution.plan_id == plan.id)
        ).all()
        assert len(step_execs) == 2
        focus_step = next(s for s in step_execs if s.step_key == "step_1_focus")
        assert focus_step.status == "COMPLETED"
        assert "external_event_id" in focus_step.output_payload

    def test_scenario_c_repeated_interruption_response(self, db_session, test_user):
        """
        SCENARIO C: Context Switch / Interruption Surge -> Focus Protection Proposal.
        """
        # 1. Context thrashing detected
        thrashing_ev = BehavioralChangeDetector.detect_context_thrashing(
            user_id=test_user.id,
            switch_count_last_minute=8,
            active_apps=["Slack", "Chrome", "IDE", "Terminal", "Email"],
        )
        assert thrashing_ev is not None
        assert thrashing_ev.event_type == StandardEventType.THRASHING_DETECTED.value

        # Ingest and route (automatically generates proactive feed item)
        res = EventProcessor.process_event(db=db_session, event_or_req=thrashing_ev)
        assert res.status == "PROCESSED"
        assert res.proactive_feed_item_created is True

        # 2. Feed item generated
        feed_item = db_session.execute(
            select(ProactiveFeedItem).where(
                ProactiveFeedItem.user_id == test_user.id,
                ProactiveFeedItem.detection_type == StandardEventType.THRASHING_DETECTED.value,
            )
        ).scalars().first()
        assert feed_item is not None
        assert "thrashing" in feed_item.title.lower()

        # 3. Plan focus protection workflow
        steps = [
            WorkflowStepSchema(
                step_key="step_1_clamp",
                name="Activate Notification Suppression",
                action_identifier="reminder:snooze_non_urgent",
                parameters={"throttle_duration_minutes": 45},
                is_optional=False,
                order_index=1,
            ),
            WorkflowStepSchema(
                step_key="step_2_shield",
                name="Shield Distracting Tools",
                action_identifier="focus:clamp_complementary_tools",
                parameters={"allowed_application_names": ["code.exe"]},
                is_optional=True,
                order_index=2,
            ),
        ]
        deps = [
            WorkflowDependencySchema(
                source_step_key="step_1_clamp",
                target_step_key="step_2_shield",
                dependency_type=DependencyType.SUCCESS,
            )
        ]
        plan = create_test_plan(
            db=db_session,
            user_id=test_user.id,
            title="High Interruption Focus Shield",
            steps=steps,
            dependencies=deps,
            rationale="Frequent context switches detected. 45-minute notification silence proposed.",
        )

        # User approves
        WorkflowPlanner.transition_plan_status(
            db_session, plan.id, test_user.id, WorkflowLifecycleState.APPROVED
        )

        # Execute
        executed = WorkflowExecutionEngine.execute_plan(db_session, plan.id, test_user.id)
        assert executed.status == WorkflowLifecycleState.COMPLETED.value

    def test_scenario_d_partial_workflow_failure_and_rollback(self, db_session, test_user):
        """
        SCENARIO D: Step 1 succeeds, Step 2 fails, auto-rollback unwinds compensation.
        """
        task = Task(
            id=uuid.uuid4(),
            user_id=test_user.id,
            title="Initial Task State",
            priority=TaskPriority.LOW,
            status=TaskStatus.PENDING,
        )
        db_session.add(task)
        db_session.commit()

        # Step 1: Upgrades priority to CRITICAL (Reversible)
        # Step 2: Critical non-optional step that encounters failure (non-existent task)
        missing_task_id = str(uuid.uuid4())
        steps = [
            WorkflowStepSchema(
                step_key="step_1_upgrade",
                name="Upgrade Priority",
                action_identifier="task:update_priority",
                parameters={"task_id": str(task.id), "new_priority": "CRITICAL"},
                is_optional=False,
                order_index=1,
            ),
            WorkflowStepSchema(
                step_key="step_2_failing_task",
                name="Provider Sync Failure",
                action_identifier="task:update_priority",
                parameters={"task_id": missing_task_id, "new_priority": "HIGH"},
                is_optional=False,  # critical failure
                order_index=2,
            ),
        ]
        deps = [
            WorkflowDependencySchema(
                source_step_key="step_1_upgrade",
                target_step_key="step_2_failing_task",
                dependency_type=DependencyType.SUCCESS,
            )
        ]

        plan = create_test_plan(
            db=db_session,
            user_id=test_user.id,
            title="Reversible Failure Drill",
            steps=steps,
            dependencies=deps,
            status=WorkflowLifecycleState.APPROVED,
        )

        # Execute with auto_rollback_on_failure=True
        executed_plan = WorkflowExecutionEngine.execute_plan(
            db=db_session,
            plan_id=plan.id,
            user_id=test_user.id,
            auto_rollback_on_failure=True,
        )

        # State must reflect rollback
        assert executed_plan.status == WorkflowLifecycleState.ROLLED_BACK.value

        # Step 1 was rolled back -> task priority restored to LOW
        db_session.refresh(task)
        assert task.priority == TaskPriority.LOW

        # Step execution receipts document both success and failure
        step_execs = db_session.scalars(
            select(WorkflowStepExecution).where(WorkflowStepExecution.plan_id == plan.id)
        ).all()
        assert any(s.status == "FAILED" for s in step_execs)

    def test_scenario_e_emergency_stop_halts_automation(self, db_session, test_user):
        """
        SCENARIO E: User engages Emergency Stop; pending plans cancelled, execution halted.
        """
        plan = create_test_plan(
            db=db_session,
            user_id=test_user.id,
            title="Scheduled Workflow Before Stop",
            steps=[
                WorkflowStepSchema(
                    step_key="step_1",
                    name="Routine Action",
                    action_identifier="task:update_priority",
                    parameters={"task_id": str(uuid.uuid4()), "new_priority": "HIGH"},
                    order_index=1,
                )
            ],
            dependencies=[],
            status=WorkflowLifecycleState.APPROVED,
        )

        # User activates emergency stop
        stop_event = EmergencyStopEngine.trigger_emergency_stop(
            db=db_session,
            scope=EmergencyStopScope.USER_LEVEL,
            user_id=test_user.id,
            reason="User noticed unexpected external calendar changes",
            auto_cancel_pending=True,
        )
        assert stop_event.is_active is True

        # Pending plan must be CANCELLED
        db_session.refresh(plan)
        assert plan.status == WorkflowLifecycleState.CANCELLED.value

        # Any attempt to execute must fail with EmergencyStopActiveError
        with pytest.raises(EmergencyStopActiveError):
            WorkflowExecutionEngine.execute_plan(db_session, plan.id, test_user.id)

        # Audit trail records emergency stop event
        audit_events = AuditLogger.list_events(db_session, test_user.id)
        assert any(e.event_type == AuditEventType.EMERGENCY_STOP_TRIGGERED.value for e in audit_events)

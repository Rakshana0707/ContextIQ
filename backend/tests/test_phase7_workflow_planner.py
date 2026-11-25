"""
Automated Test Suite for Phase 7.4: Intelligent Multi-Step Workflow Planning and Orchestration.
Covers:
1. Deterministic validation of registered vs unregistered action contracts.
2. Circular dependency and cycle detection in workflow DAGs.
3. Strict Pydantic rejection of malformed LLM outputs.
4. Lifecycle state machine transitions and invalid transition rejection (13-State FSM).
5. Multi-attribute utility plan scoring and strategy comparison.
6. Plan versioning and audit history snapshots.
7. Separation of planning from execution (approval gating).
"""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.user import User
from app.models.workflow_models import (
    WorkflowExecutionPlan,
    WorkflowPlanVersion,
)
from app.schemas.workflow_schemas import (
    DependencyType,
    LLMWorkflowProposal,
    WorkflowDependencySchema,
    WorkflowLifecycleState,
    WorkflowStepSchema,
)
from app.services.action_registry import ActionRegistry
from app.services.llm_workflow_adapter import LLMWorkflowAdapter
from app.services.plan_scorer import PlanScorer
from app.services.workflow_planner import WorkflowPlanner
from app.services.workflow_validator import WorkflowValidationError, WorkflowValidator

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
        email="planner.tester@contextiq.io",
        display_name="Workflow Planning User",
        is_active=True,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


def test_registered_action_catalog_and_unregistered_rejection():
    """Verifies that registered action contracts are validated and unregistered actions are rejected."""
    # 1. Registered action check
    assert ActionRegistry.is_registered("calendar:insert_focus_block") is True
    assert ActionRegistry.is_registered("task:update_priority") is True
    assert ActionRegistry.is_registered("recovery:insert_post_interruption_buffer") is True

    # 2. Unregistered action check
    assert ActionRegistry.is_registered("arbitrary:system_shell_exec") is False

    # 3. Validation should reject unregistered action
    steps = [
        WorkflowStepSchema(
            step_key="step_1",
            name="Execute Malicious Shell Command",
            action_identifier="arbitrary:system_shell_exec",
            parameters={"cmd": "rm -rf /"},
        )
    ]
    errors = WorkflowValidator.validate_workflow_structure(steps, [])
    assert len(errors) > 0
    assert "specifies unregistered action identifier" in errors[0]


def test_circular_dependency_cycle_detection():
    """Detects cycles in workflow DAGs and rejects circular execution paths."""
    steps = [
        WorkflowStepSchema(
            step_key="step_A",
            name="Review Task",
            action_identifier="task:update_priority",
            parameters={"task_id": "tsk-1", "new_priority": "HIGH"},
        ),
        WorkflowStepSchema(
            step_key="step_B",
            name="Reserve Calendar Block",
            action_identifier="calendar:insert_focus_block",
            parameters={"title": "Focus Block", "start_time": "2026-11-26T10:00:00Z", "end_time": "2026-11-26T11:00:00Z"},
        ),
        WorkflowStepSchema(
            step_key="step_C",
            name="Inject Recovery Buffer",
            action_identifier="recovery:insert_post_interruption_buffer",
            parameters={"buffer_duration_minutes": 10},
        ),
    ]

    # Create cycle: A -> B -> C -> A
    cyclic_deps = [
        WorkflowDependencySchema(source_step_key="step_A", target_step_key="step_B", dependency_type=DependencyType.SUCCESS),
        WorkflowDependencySchema(source_step_key="step_B", target_step_key="step_C", dependency_type=DependencyType.SUCCESS),
        WorkflowDependencySchema(source_step_key="step_C", target_step_key="step_A", dependency_type=DependencyType.SUCCESS),
    ]

    errors = WorkflowValidator.validate_workflow_structure(steps, cyclic_deps)
    assert len(errors) > 0
    assert any("Circular dependency cycle detected" in err for err in errors)


def test_acyclic_dag_topological_sort_resolution():
    """Resolves correct topological execution order for a multi-step DAG."""
    steps = [
        WorkflowStepSchema(
            step_key="step_1",
            name="Review Task",
            action_identifier="task:update_priority",
            parameters={"task_id": "tsk-1", "new_priority": "HIGH"},
            order_index=1,
        ),
        WorkflowStepSchema(
            step_key="step_2",
            name="Reschedule Conflict",
            action_identifier="calendar:reschedule_event",
            parameters={"external_event_id": "cal-1", "new_start_time": "...", "new_end_time": "..."},
            order_index=2,
        ),
        WorkflowStepSchema(
            step_key="step_3",
            name="Reserve Block",
            action_identifier="calendar:insert_focus_block",
            parameters={"title": "Focus", "start_time": "...", "end_time": "..."},
            order_index=3,
        ),
    ]

    deps = [
        WorkflowDependencySchema(source_step_key="step_1", target_step_key="step_2", dependency_type=DependencyType.SUCCESS),
        WorkflowDependencySchema(source_step_key="step_2", target_step_key="step_3", dependency_type=DependencyType.SUCCESS),
    ]

    errors = WorkflowValidator.validate_workflow_structure(steps, deps)
    assert len(errors) == 0

    order = WorkflowValidator.resolve_execution_order(steps, deps)
    assert order == ["step_1", "step_2", "step_3"]


def test_malformed_llm_output_rejection(db_session, test_user):
    """Verifies that malformed or schema-violating LLM proposals are rejected."""
    # 1. Missing required field 'steps'
    malformed_json = {
        "title": "Invalid Plan",
        "rationale": "Missing steps completely",
        "target_objective": "Test",
        # "steps" omitted
        "trade_off_analysis": "None",
    }

    with pytest.raises(WorkflowValidationError) as exc_info:
        LLMWorkflowAdapter.validate_and_compile_proposal(db_session, test_user.id, malformed_json)
    assert "Malformed LLM proposal schema" in str(exc_info.value)

    # 2. LLM hallucinating an unregistered action contract
    hallucinated_action_proposal = {
        "title": "Hallucinated Plan",
        "rationale": "Attempting arbitrary unregistered action",
        "target_objective": "Hacking",
        "steps": [
            {
                "step_key": "step_1",
                "name": "Run Arbitrary Script",
                "action_identifier": "llm:eval_python_code",
                "parameters": {"code": "print('exploit')"},
            }
        ],
        "dependencies": [],
        "trade_off_analysis": "Dangerous",
    }

    with pytest.raises(WorkflowValidationError) as exc_info2:
        LLMWorkflowAdapter.validate_and_compile_proposal(db_session, test_user.id, hallucinated_action_proposal)
    assert "failed deterministic action or DAG validation" in str(exc_info2.value)


def test_lifecycle_13_state_transitions(db_session, test_user):
    """Enforces valid transitions and rejects invalid state jumps in the 13-state machine."""
    # 1. Plan creation starts in AWAITING_APPROVAL
    plan = WorkflowPlanner.plan_behavioral_workflow(
        db=db_session,
        user_id=test_user.id,
        trigger_type="FORGETTING_RISK_SPIKE",
        behavioral_context={"task_title": "Q4 Analytics", "lapse_probability": 0.82},
    )
    assert plan.status == WorkflowLifecycleState.AWAITING_APPROVAL.value
    assert plan.version == 1

    # 2. Permissible transition: AWAITING_APPROVAL -> APPROVED
    approved_plan = WorkflowPlanner.transition_plan_status(
        db=db_session,
        plan_id=plan.id,
        user_id=test_user.id,
        target_state=WorkflowLifecycleState.APPROVED,
        reason="User approved proposal via UI",
    )
    assert approved_plan.status == WorkflowLifecycleState.APPROVED.value
    assert approved_plan.version == 2
    assert approved_plan.approved_at is not None

    # 3. Impermissible transition: APPROVED cannot jump directly back to CREATED or DRAFT
    with pytest.raises(WorkflowValidationError) as exc_info:
        WorkflowPlanner.transition_plan_status(
            db=db_session,
            plan_id=plan.id,
            user_id=test_user.id,
            target_state=WorkflowLifecycleState.CREATED,
        )
    assert "Invalid state transition" in str(exc_info.value)

    # 4. Permissible: APPROVED -> EXECUTING -> COMPLETED -> ROLLED_BACK
    executing_plan = WorkflowPlanner.transition_plan_status(
        db=db_session,
        plan_id=plan.id,
        user_id=test_user.id,
        target_state=WorkflowLifecycleState.EXECUTING,
    )
    assert executing_plan.status == WorkflowLifecycleState.EXECUTING.value

    completed_plan = WorkflowPlanner.transition_plan_status(
        db=db_session,
        plan_id=plan.id,
        user_id=test_user.id,
        target_state=WorkflowLifecycleState.COMPLETED,
    )
    assert completed_plan.status == WorkflowLifecycleState.COMPLETED.value

    # Rollback undo
    rolled_back = WorkflowPlanner.transition_plan_status(
        db=db_session,
        plan_id=plan.id,
        user_id=test_user.id,
        target_state=WorkflowLifecycleState.ROLLED_BACK,
        reason="User requested undo",
    )
    assert rolled_back.status == WorkflowLifecycleState.ROLLED_BACK.value


def test_plan_scoring_and_multi_attribute_comparison():
    """Verifies multi-attribute plan scoring calculates expected dimensions and penalties."""
    steps = [
        WorkflowStepSchema(
            step_key="s1",
            name="Verify Task",
            action_identifier="task:update_priority",
            parameters={"task_id": "tsk-1", "new_priority": "HIGH"},
        ),
        WorkflowStepSchema(
            step_key="s2",
            name="Focus Session",
            action_identifier="focus:create_session_block",
            parameters={"session_duration_minutes": 50},
        ),
        WorkflowStepSchema(
            step_key="s3",
            name="Recovery Buffer",
            action_identifier="recovery:insert_post_interruption_buffer",
            parameters={"buffer_duration_minutes": 10},
        ),
    ]

    context = {
        "task_priority": "HIGH",
        "lapse_probability": 0.82,
        "has_calendar_conflict": True,
        "confidence_score": 0.90,
    }

    scores = PlanScorer.score_plan(steps, context, strategy="BALANCED_BUFFERED")
    assert 0.0 <= scores["utility_score"] <= 1.0
    assert scores["task_benefit_score"] >= 0.80
    assert scores["recovery_impact_score"] >= 0.80  # Has recovery buffer

    alternatives = PlanScorer.generate_plan_alternatives(steps, context)
    assert len(alternatives) == 3
    strategies = [a.strategy for a in alternatives]
    assert "BALANCED_BUFFERED" in strategies
    assert "AGGRESSIVE_FOCUS" in strategies
    assert "MINIMAL_INTRUSION" in strategies


def test_plan_versioning_and_snapshot_audit(db_session, test_user):
    """Verifies that plan mutations create immutable version history records."""
    plan = WorkflowPlanner.plan_behavioral_workflow(
        db=db_session,
        user_id=test_user.id,
        trigger_type="FORGETTING_RISK_SPIKE",
        behavioral_context={"task_title": "Audit Review"},
    )
    assert plan.version == 1

    # Transition twice
    WorkflowPlanner.transition_plan_status(
        db=db_session,
        plan_id=plan.id,
        user_id=test_user.id,
        target_state=WorkflowLifecycleState.APPROVED,
        reason="Approval",
    )
    WorkflowPlanner.transition_plan_status(
        db=db_session,
        plan_id=plan.id,
        user_id=test_user.id,
        target_state=WorkflowLifecycleState.CANCELLED,
        reason="User cancelled before execution",
    )

    versions = db_session.query(WorkflowPlanVersion).filter_by(plan_id=plan.id).all()
    assert len(versions) == 3
    version_numbers = [v.version for v in versions]
    assert sorted(version_numbers) == [1, 2, 3]


def test_llm_compiled_proposal_requires_approval(db_session, test_user):
    """Verifies valid LLM proposals compile into AWAITING_APPROVAL execution plans."""
    valid_llm_proposal = {
        "title": "LLM Focus Strategy for Interrupted Sprint",
        "rationale": "High context thrashing and task lapse detected.",
        "target_objective": "Shield deep focus window",
        "steps": [
            {
                "step_key": "step_1",
                "name": "Elevate Task Priority",
                "action_identifier": "task:update_priority",
                "parameters": {"task_id": "tsk-abc", "new_priority": "CRITICAL"},
                "order_index": 1,
            },
            {
                "step_key": "step_2",
                "name": "Shield Workstation",
                "action_identifier": "focus:clamp_complementary_tools",
                "parameters": {"allowed_application_names": ["code.exe"]},
                "order_index": 2,
            },
        ],
        "dependencies": [
            {
                "source_step_key": "step_1",
                "target_step_key": "step_2",
                "dependency_type": "SUCCESS",
            }
        ],
        "expected_benefits": {"friction_reduction": "High"},
        "potential_side_effects": {"apps_minimized": "True"},
        "trade_off_analysis": "Distraction apps clamped for 50 minutes.",
    }

    plan = LLMWorkflowAdapter.validate_and_compile_proposal(
        db=db_session,
        user_id=test_user.id,
        raw_proposal=valid_llm_proposal,
    )
    assert plan.status == WorkflowLifecycleState.AWAITING_APPROVAL.value
    assert len(plan.plan_steps) == 2
    assert plan.utility_score > 0.0

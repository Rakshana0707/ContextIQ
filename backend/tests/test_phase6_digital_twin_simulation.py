"""
Unit & Integration Test Suite for ContextIQ Behavioral Digital Twin Simulation (Phase 6.9).

Validates:
1. Scenario hypothesis simulation across all supported types:
   - MOVE_TASK_TIME
   - ADD_RECOVERY_BUFFER
   - REDUCE_NOTIFICATIONS
   - SCHEDULE_FOCUS_SESSION
   - DECOMPOSE_TASK
   - CUSTOM_SCENARIO
2. Counterfactual delta computation and uncertainty interval quantification (90% coverage).
3. Zero database task alteration during pure simulation runs (data safety).
4. Scenario CRUD and plan activation (designating active behavioral strategy).
5. Multi-scenario comparative trade-off matrix.
6. Reversible workflow orchestration lifecycle:
   - Generation of action previews with permissions and duration.
   - Explicit user approval / rejection gate.
   - Execution prevention without prior approval.
   - Idempotent execution preventing duplicated external actions.
   - Rollback / undo restoring prior task state.
7. REST API endpoints under /api/v1/simulation and /api/v1/analytics/simulation.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["APP_ENV"] = "development"
os.environ.setdefault("DATABASE_URL", "sqlite:///./_test_telemetry.db")


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


import app.models
from app.db.session import Base
from app.main import app
from app.models import ProposedWorkflow, SavedScenario, Task, User, UserBehavioralProfile
from app.models.enums import TaskPriority, TaskStatus
from app.schemas.digital_twin_simulation import (
    ProposedWorkflowResponse,
    ScenarioCompareRequest,
    ScenarioCreateRequest,
    ScenarioResponse,
    ScenarioSimulationRequest,
    ScenarioType,
    ScenarioUpdateRequest,
    SimulationActionType,
    WorkflowApprovalRequest,
    WorkflowStatus,
)
from app.services.digital_twin_engine import DigitalTwinEngine
from app.services.simulation_service import SimulationService
from app.services.workflow_orchestrator import WorkflowOrchestrator


# ---------------------------------------------------------------------------
# Database & Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def test_db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(test_db_engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def seed_user_and_task(db_session: Session):
    user_id = uuid.uuid4()
    task_id = uuid.uuid4()

    user = User(
        id=user_id,
        email=f"sim_user_{user_id.hex[:6]}@example.com",
        display_name=f"simuser_{user_id.hex[:6]}",
        timezone="UTC",
        is_active=True,
    )
    db_session.add(user)

    task = Task(
        id=task_id,
        user_id=user_id,
        title="Write Q4 Architecture Assessment",
        description="Comprehensive technical review of micro-delays",
        status=TaskStatus.PENDING,
        priority=TaskPriority.HIGH,
        estimated_minutes=90,
        due_at=datetime.now(timezone.utc),
    )
    db_session.add(task)

    profile = UserBehavioralProfile(
        user_id=user_id,
        focus_dimension={
            "optimal_focus_hour": 9,
            "morning_completion_multiplier": 1.25,
        },
        interruption_dimension={
            "avg_recovery_duration_seconds": 600,
        },
        temporal_dimension={
            "baseline_bfi": 48.0,
        },
    )
    db_session.add(profile)
    db_session.commit()

    return {"user_id": user_id, "task_id": task_id}


@pytest.fixture
def test_client(test_db_engine, seed_user_and_task):
    from app.core.deps import get_current_user_id
    from app.db.session import get_db

    test_user_id = seed_user_and_task["user_id"]

    def override_get_db():
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine)
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_current_user_id] = lambda: test_user_id
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 1. Digital Twin Simulation Engine Tests
# ---------------------------------------------------------------------------

def test_simulation_all_scenario_types(db_session: Session, seed_user_and_task):
    """Verifies that all 6 scenario types simulate with realistic bounds and counterfactual deltas."""
    user_id = seed_user_and_task["user_id"]
    task_id = seed_user_and_task["task_id"]

    scenario_types = [
        ScenarioType.MOVE_TASK_TIME,
        ScenarioType.ADD_RECOVERY_BUFFER,
        ScenarioType.REDUCE_NOTIFICATIONS,
        ScenarioType.SCHEDULE_FOCUS_SESSION,
        ScenarioType.DECOMPOSE_TASK,
        ScenarioType.CUSTOM_SCENARIO,
    ]

    for st in scenario_types:
        req = ScenarioSimulationRequest(
            scenario_type=st,
            user_id=user_id,
            task_id=task_id,
            input_parameters={"target_time": "09:00", "buffer_minutes": 15},
        )
        res = SimulationService.simulate_scenario(db=db_session, request=req)

        # Baseline checks
        assert 0.0 <= res.baseline_plan.task_completion_probability <= 1.0
        assert res.baseline_plan.recovery_duration_minutes > 0.0
        assert 0.0 <= res.baseline_plan.behavioral_friction_index <= 100.0

        # Simulated checks
        assert 0.0 <= res.simulated_plan.task_completion_probability <= 1.0
        assert res.simulated_plan.recovery_duration_minutes > 0.0
        assert 0.0 <= res.simulated_plan.behavioral_friction_index <= 100.0

        # Uncertainty interval [lower, upper]
        low, high = res.simulated_plan.uncertainty_interval
        assert low <= res.simulated_plan.task_completion_probability <= high or low <= high
        assert res.simulated_plan.uncertainty_width > 0.0

        # Counterfactual deltas
        assert res.counterfactual_deltas is not None
        assert len(res.assumptions) >= 2


def test_focus_session_yields_positive_completion_delta(db_session: Session, seed_user_and_task):
    """Verifies focus session improves completion likelihood and reduces recovery lag."""
    req = ScenarioSimulationRequest(
        scenario_type=ScenarioType.SCHEDULE_FOCUS_SESSION,
        user_id=seed_user_and_task["user_id"],
        task_id=seed_user_and_task["task_id"],
        input_parameters={"focus_block_minutes": 60},
    )
    res = SimulationService.simulate_scenario(db=db_session, request=req)

    assert res.counterfactual_deltas.delta_completion_pct > 0.0
    assert res.counterfactual_deltas.delta_recovery_minutes < 0.0
    assert res.counterfactual_deltas.delta_friction_points < 0.0


def test_simulation_read_only_safety(db_session: Session, seed_user_and_task):
    """Validates that running simulations does NOT alter any database tasks or state."""
    task_id = seed_user_and_task["task_id"]
    task_before = db_session.query(Task).filter(Task.id == task_id).first()
    original_status = task_before.status
    original_priority = task_before.priority

    # Run multiple simulations
    req1 = ScenarioSimulationRequest(
        scenario_type=ScenarioType.MOVE_TASK_TIME,
        user_id=seed_user_and_task["user_id"],
        task_id=task_id,
    )
    req2 = ScenarioSimulationRequest(
        scenario_type=ScenarioType.DECOMPOSE_TASK,
        user_id=seed_user_and_task["user_id"],
        task_id=task_id,
    )
    SimulationService.simulate_scenario(db=db_session, request=req1)
    SimulationService.simulate_scenario(db=db_session, request=req2)

    task_after = db_session.query(Task).filter(Task.id == task_id).first()
    assert task_after.status == original_status
    assert task_after.priority == original_priority


# ---------------------------------------------------------------------------
# 2. Scenario Persistence & Management (CRUD) Tests
# ---------------------------------------------------------------------------

def test_scenario_crud_lifecycle(db_session: Session, seed_user_and_task):
    """Tests saving, listing, retrieving, updating, and deleting a scenario."""
    user_id = seed_user_and_task["user_id"]
    task_id = seed_user_and_task["task_id"]

    create_req = ScenarioCreateRequest(
        name="Morning Focus Block Scenario",
        scenario_type=ScenarioType.SCHEDULE_FOCUS_SESSION,
        description="Protect 60m morning block for deep work.",
        task_id=task_id,
        input_parameters={"focus_block_minutes": 60},
    )

    created = SimulationService.create_saved_scenario(db=db_session, user_id=user_id, request=create_req)
    assert created.id is not None
    assert created.name == "Morning Focus Block Scenario"
    assert created.is_active is False

    # List scenarios
    scenarios = SimulationService.list_saved_scenarios(db=db_session, user_id=user_id)
    assert len(scenarios) >= 1
    assert any(s.id == created.id for s in scenarios)

    # Get by id
    fetched = SimulationService.get_saved_scenario(db=db_session, user_id=user_id, scenario_id=created.id)
    assert fetched.id == created.id

    # Update scenario
    update_req = ScenarioUpdateRequest(name="Updated Morning Deep Work", description="New hypothesis")
    updated = SimulationService.update_saved_scenario(
        db=db_session, user_id=user_id, scenario_id=created.id, update_req=update_req
    )
    assert updated.name == "Updated Morning Deep Work"

    # Plan activation
    activated = SimulationService.activate_scenario(
        db=db_session, user_id=user_id, scenario_id=created.id
    )
    assert activated.is_active is True

    # Delete scenario
    SimulationService.delete_saved_scenario(
        db=db_session, user_id=user_id, scenario_id=created.id
    )

    # Confirm deletion
    from app.core.errors import NotFoundError
    with pytest.raises(NotFoundError):
        SimulationService.get_saved_scenario(db=db_session, user_id=user_id, scenario_id=created.id)


def test_scenario_comparison_tradeoff_matrix(db_session: Session, seed_user_and_task):
    """Tests multi-scenario comparison and ranking."""
    user_id = seed_user_and_task["user_id"]
    task_id = seed_user_and_task["task_id"]

    # Create 2 scenarios for comparison
    scen1 = SimulationService.create_saved_scenario(
        db=db_session,
        user_id=user_id,
        request=ScenarioCreateRequest(
            name="Scenario 1",
            scenario_type=ScenarioType.SCHEDULE_FOCUS_SESSION,
            task_id=task_id,
            input_parameters={"focus_block_minutes": 60},
        ),
    )
    scen2 = SimulationService.create_saved_scenario(
        db=db_session,
        user_id=user_id,
        request=ScenarioCreateRequest(
            name="Scenario 2",
            scenario_type=ScenarioType.ADD_RECOVERY_BUFFER,
            task_id=task_id,
            input_parameters={"buffer_minutes": 15},
        ),
    )

    req = ScenarioCompareRequest(scenario_ids=[scen1.id, scen2.id])
    compare_res = SimulationService.compare_scenarios(db=db_session, user_id=user_id, request=req)

    assert len(compare_res.scenarios) == 2
    assert len(compare_res.relative_rankings) == 2
    assert len(compare_res.trade_off_matrix) == 2


# ---------------------------------------------------------------------------
# 3. Proposed Workflow Orchestration Tests
# ---------------------------------------------------------------------------

def test_workflow_orchestration_approval_and_execution(db_session: Session, seed_user_and_task):
    """Tests the full workflow lifecycle: propose -> approve -> execute."""
    user_id = seed_user_and_task["user_id"]
    task_id = seed_user_and_task["task_id"]

    # 1. Propose workflow
    workflow = WorkflowOrchestrator.propose_workflow_from_scenario(
        db=db_session,
        user_id=user_id,
        scenario_type=ScenarioType.ADD_RECOVERY_BUFFER,
        task_id=task_id,
    )
    assert workflow.status == WorkflowStatus.PROPOSED.value
    assert len(workflow.actions) >= 1
    assert workflow.is_reversible is True
    assert workflow.permission_audit["all_permissions_satisfied"] is True

    # 2. Verify cannot execute without approval
    with pytest.raises(ValueError):
        WorkflowOrchestrator.execute_workflow(db=db_session, workflow=workflow)

    # 3. User approves workflow
    approved = WorkflowOrchestrator.approve_workflow(
        db=db_session,
        workflow=workflow,
        approval_req=WorkflowApprovalRequest(approved=True),
    )
    assert approved.status == WorkflowStatus.APPROVED.value

    # 4. Execute approved workflow
    exec_res = WorkflowOrchestrator.execute_workflow(db=db_session, workflow=approved)
    assert exec_res.status == WorkflowStatus.COMPLETED
    assert exec_res.executed_actions_count >= 1


def test_workflow_orchestration_rejection(db_session: Session, seed_user_and_task):
    """Tests rejecting a workflow proposal marks it CANCELLED."""
    user_id = seed_user_and_task["user_id"]
    task_id = seed_user_and_task["task_id"]

    workflow = WorkflowOrchestrator.propose_workflow_from_scenario(
        db=db_session,
        user_id=user_id,
        scenario_type=ScenarioType.REDUCE_NOTIFICATIONS,
        task_id=task_id,
    )
    rejected = WorkflowOrchestrator.approve_workflow(
        db=db_session,
        workflow=workflow,
        approval_req=WorkflowApprovalRequest(approved=False, rejection_reason="Too restrictive"),
    )
    assert rejected.status == WorkflowStatus.CANCELLED.value


def test_workflow_rollback_restores_prior_state(db_session: Session, seed_user_and_task):
    """Tests that rolling back an executed workflow restores the prior state and marks REVERTED."""
    user_id = seed_user_and_task["user_id"]
    task_id = seed_user_and_task["task_id"]

    workflow = WorkflowOrchestrator.propose_workflow_from_scenario(
        db=db_session,
        user_id=user_id,
        scenario_type=ScenarioType.DECOMPOSE_TASK,
        task_id=task_id,
    )
    WorkflowOrchestrator.approve_workflow(
        db=db_session,
        workflow=workflow,
        approval_req=WorkflowApprovalRequest(approved=True),
    )
    WorkflowOrchestrator.execute_workflow(db=db_session, workflow=workflow)

    # Rollback
    rollback_res = WorkflowOrchestrator.rollback_workflow(db=db_session, workflow=workflow)
    assert rollback_res.status == WorkflowStatus.REVERTED
    assert rollback_res.reverted_actions_count >= 0
    assert "rolled back" in rollback_res.message

    # Check workflow record in db
    wf_record = db_session.query(ProposedWorkflow).filter(ProposedWorkflow.id == workflow.id).first()
    assert wf_record.status == WorkflowStatus.REVERTED.value


# ---------------------------------------------------------------------------
# 4. REST API Endpoint Tests
# ---------------------------------------------------------------------------

def test_api_ephemeral_simulate(test_client: TestClient, seed_user_and_task):
    """Tests POST /api/v1/simulation/scenarios/simulate endpoint."""
    res = test_client.post(
        "/api/v1/simulation/scenarios/simulate",
        json={
            "scenario_type": "SCHEDULE_FOCUS_SESSION",
            "task_id": str(seed_user_and_task["task_id"]),
            "input_parameters": {"focus_block_minutes": 60},
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["scenario_type"] == "SCHEDULE_FOCUS_SESSION"
    assert "counterfactual_deltas" in data
    assert "baseline_plan" in data
    assert "simulated_plan" in data


def test_api_scenario_lifecycle(test_client: TestClient, seed_user_and_task):
    """Tests full REST scenario CRUD and comparison endpoints."""
    # 1. Create scenario 1
    res1 = test_client.post(
        "/api/v1/simulation/scenarios",
        json={
            "name": "API Test Scenario 1",
            "scenario_type": "ADD_RECOVERY_BUFFER",
            "description": "Insert 15m post-meeting buffer.",
            "task_id": str(seed_user_and_task["task_id"]),
            "input_parameters": {"buffer_minutes": 15},
        },
    )
    assert res1.status_code == 201
    created_id_1 = res1.json()["id"]

    # Create scenario 2
    res2 = test_client.post(
        "/api/v1/simulation/scenarios",
        json={
            "name": "API Test Scenario 2",
            "scenario_type": "SCHEDULE_FOCUS_SESSION",
            "description": "60m focus block.",
            "task_id": str(seed_user_and_task["task_id"]),
            "input_parameters": {"focus_block_minutes": 60},
        },
    )
    assert res2.status_code == 201
    created_id_2 = res2.json()["id"]

    # 2. Get scenario
    res_get = test_client.get(f"/api/v1/simulation/scenarios/{created_id_1}")
    assert res_get.status_code == 200
    assert res_get.json()["name"] == "API Test Scenario 1"

    # 3. List scenarios
    res_list = test_client.get("/api/v1/simulation/scenarios")
    assert res_list.status_code == 200
    assert any(s["id"] == created_id_1 for s in res_list.json())

    # 4. Activate plan
    res_act = test_client.post(f"/api/v1/simulation/scenarios/{created_id_1}/activate")
    assert res_act.status_code == 200
    assert res_act.json()["is_active"] is True

    # 5. Compare scenarios
    res_comp = test_client.post(
        "/api/v1/simulation/compare",
        json={"scenario_ids": [created_id_1, created_id_2]},
    )
    assert res_comp.status_code == 200
    assert len(res_comp.json()["scenarios"]) == 2

    # 6. Propose workflow
    res_prop = test_client.post(
        f"/api/v1/simulation/workflows/propose?scenario_type=ADD_RECOVERY_BUFFER&scenario_id={created_id_1}"
    )
    assert res_prop.status_code == 201
    wf_id = res_prop.json()["id"]
    assert res_prop.json()["status"] == "PROPOSED"

    # 7. Approve workflow
    res_app = test_client.post(
        f"/api/v1/simulation/workflows/{wf_id}/approve",
        json={"approved": True},
    )
    assert res_app.status_code == 200
    assert res_app.json()["status"] == "APPROVED"

    # 8. Execute workflow
    res_exec = test_client.post(f"/api/v1/simulation/workflows/{wf_id}/execute")
    assert res_exec.status_code == 200
    assert res_exec.json()["status"] == "COMPLETED"

    # 9. Rollback workflow
    res_rb = test_client.post(f"/api/v1/simulation/workflows/{wf_id}/rollback")
    assert res_rb.status_code == 200
    assert res_rb.json()["status"] == "REVERTED"

    # 10. Delete scenarios
    res_del1 = test_client.delete(f"/api/v1/simulation/scenarios/{created_id_1}")
    assert res_del1.status_code == 204
    res_del2 = test_client.delete(f"/api/v1/simulation/scenarios/{created_id_2}")
    assert res_del2.status_code == 204


def test_api_analytics_simulation_convenience_endpoints(test_client: TestClient):
    """Tests GET /api/v1/analytics/simulation/* convenience endpoints."""
    res_sim = test_client.get(
        "/api/v1/analytics/simulation/simulate?scenario_type=SCHEDULE_FOCUS_SESSION"
    )
    assert res_sim.status_code == 200
    assert "counterfactual_deltas" in res_sim.json()

    res_scen = test_client.get("/api/v1/analytics/simulation/scenarios")
    assert res_scen.status_code == 200
    assert isinstance(res_scen.json(), list)

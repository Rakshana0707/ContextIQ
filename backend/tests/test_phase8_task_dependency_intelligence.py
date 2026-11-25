"""
Test suite for ContextIQ Phase 8.5: Cross-Task Dependency Discovery and Intelligent Relationship Analysis.

Verifies:
1. Explicit vs. inferred dependency contracts and epistemic separation.
2. Rule-based dependency discovery (shared project, shared goal, deadline sequencing, resource conflict).
3. Association rule mining (co-completion support, confidence, lift) and temporal sequence analysis (directional probabilities).
4. User confirmation, rejection, type correction, and explicit promotion.
5. Cascading multi-hop impact analysis (downstream tasks, milestones, projects, goals, critical path alert).
6. Cross-tenant user isolation.
7. REST API endpoints.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

from app.core.deps import get_current_user_id
from app.core.errors import NotFoundError, ValidationError
from app.db.session import Base, get_db
from app.main import app
from app.models.enums import TaskEventType, TaskPriority, TaskStatus
from app.models.goal_project import GoalTaskAssociation, ProjectGoalAssociation
from app.models.knowledge_graph import Goal, KnowledgeGraphNode, Milestone, Project
from app.models.task import Task
from app.models.task_dependency import (
    DependencyDetectionMethod,
    DependencyValidationStatus,
    TaskDependency,
    TaskDependencyType,
)
from app.models.task_event import TaskEvent
from app.models.user import User
from app.schemas.task_dependency import (
    DependencyDiscoveryRequest,
    ImpactAnalysisRequest,
    TaskDependencyConfirmation,
    TaskDependencyCreate,
    TaskDependencyUpdate,
)
from app.services.task_dependency_service import TaskDependencyService


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(test_engine):
    connection = test_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, autoflush=False, autocommit=False)
    session = session_factory()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def test_user(db_session: Session) -> User:
    u = User(
        id=uuid.uuid4(),
        email=f"dep_user_{uuid.uuid4().hex[:8]}@contextiq.io",
        display_name="Dependency Explorer User",
        timezone="UTC",
    )
    db_session.add(u)
    db_session.flush()
    return u


@pytest.fixture
def other_user(db_session: Session) -> User:
    u = User(
        id=uuid.uuid4(),
        email=f"other_{uuid.uuid4().hex[:8]}@contextiq.io",
        display_name="Other User",
        timezone="UTC",
    )
    db_session.add(u)
    db_session.flush()
    return u


@pytest.fixture
def auth_client(test_user: User, db_session: Session):
    def override_get_db():
        yield db_session

    def override_get_current_user_id():
        return test_user.id

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_id] = override_get_current_user_id

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Unit & Functional Tests
# ---------------------------------------------------------------------------

def test_explicit_dependency_creation_and_self_dependency_guard(db_session: Session, test_user: User):
    """Verifies creating explicit dependencies and blocks self-referencing dependencies."""
    t1 = Task(id=uuid.uuid4(), user_id=test_user.id, title="Schema Design", priority=TaskPriority.HIGH)
    t2 = Task(id=uuid.uuid4(), user_id=test_user.id, title="Service Implementation", priority=TaskPriority.HIGH)
    db_session.add_all([t1, t2])
    db_session.flush()

    # Self-dependency should raise ValidationError
    with pytest.raises(ValidationError):
        TaskDependencyService.create_explicit_dependency(
            db_session,
            test_user.id,
            TaskDependencyCreate(
                source_task_id=t1.id,
                target_task_id=t1.id,
                dependency_type=TaskDependencyType.EXPLICIT_DEPENDENCY,
            ),
        )

    # Valid explicit dependency
    dep = TaskDependencyService.create_explicit_dependency(
        db_session,
        test_user.id,
        TaskDependencyCreate(
            source_task_id=t1.id,
            target_task_id=t2.id,
            dependency_type=TaskDependencyType.EXPLICIT_DEPENDENCY,
            confidence=1.0,
            notes="Mandatory prerequisite",
        ),
    )
    assert dep.id is not None
    assert dep.source_task_id == t1.id
    assert dep.target_task_id == t2.id
    assert dep.is_inferred is False
    assert dep.confidence == 1.0
    assert dep.validation_status == DependencyValidationStatus.CONVERTED_EXPLICIT.value


def test_epistemic_separation_and_user_confirmation_workflow(db_session: Session, test_user: User):
    """
    Verifies that inferred dependencies start in PROPOSED state and are not treated
    as hard execution constraints until reviewed or promoted by the user.
    """
    t1 = Task(id=uuid.uuid4(), user_id=test_user.id, title="Data Ingestion", priority=TaskPriority.MEDIUM)
    t2 = Task(id=uuid.uuid4(), user_id=test_user.id, title="Data Cleaning", priority=TaskPriority.MEDIUM)
    db_session.add_all([t1, t2])
    db_session.flush()

    now = datetime.now(timezone.utc)
    inferred_dep = TaskDependency(
        user_id=test_user.id,
        source_task_id=t1.id,
        target_task_id=t2.id,
        dependency_type=TaskDependencyType.POTENTIAL_BLOCKER.value,
        is_inferred=True,
        confidence=0.72,
        detection_method=DependencyDetectionMethod.RULE_BASED.value,
        validation_status=DependencyValidationStatus.PROPOSED.value,
        supporting_observations={"reason": "Hypothetical blocker"},
        first_observed_at=now,
        last_observed_at=now,
    )
    db_session.add(inferred_dep)
    db_session.flush()

    assert inferred_dep.is_inferred is True
    assert inferred_dep.validation_status == DependencyValidationStatus.PROPOSED.value

    # 1. Type correction + Confirmation
    confirmed = TaskDependencyService.confirm_or_review_dependency(
        db_session,
        test_user.id,
        inferred_dep.id,
        TaskDependencyConfirmation(
            action="CONFIRM",
            corrected_type=TaskDependencyType.TEMPORAL_ASSOCIATION,
            notes="Sequenced but not hard-blocked",
        ),
    )
    assert confirmed.validation_status == DependencyValidationStatus.CONFIRMED.value
    assert confirmed.dependency_type == TaskDependencyType.TEMPORAL_ASSOCIATION.value
    assert confirmed.is_inferred is True  # Remains inferred, but user-confirmed

    # 2. Rejection workflow
    rejected = TaskDependencyService.confirm_or_review_dependency(
        db_session,
        test_user.id,
        inferred_dep.id,
        TaskDependencyConfirmation(action="REJECT"),
    )
    assert rejected.validation_status == DependencyValidationStatus.REJECTED.value
    assert rejected.confidence == 0.0

    # 3. Explicit promotion workflow
    converted = TaskDependencyService.confirm_or_review_dependency(
        db_session,
        test_user.id,
        inferred_dep.id,
        TaskDependencyConfirmation(action="CONVERT_EXPLICIT"),
    )
    assert converted.validation_status == DependencyValidationStatus.CONVERTED_EXPLICIT.value
    assert converted.is_inferred is False
    assert converted.confidence == 1.0


def test_rule_based_shared_project_and_goal_discovery(db_session: Session, test_user: User):
    """Verifies discovery of shared project and shared goal associations."""
    project = Project(id=uuid.uuid4(), user_id=test_user.id, title="Core Platform Upgrade", status="ACTIVE")
    goal = Goal(id=uuid.uuid4(), user_id=test_user.id, title="Reliability Q4", priority="HIGH")
    db_session.add_all([project, goal])
    db_session.flush()

    t1 = Task(id=uuid.uuid4(), user_id=test_user.id, title="DB Migration", priority=TaskPriority.HIGH)
    t2 = Task(id=uuid.uuid4(), user_id=test_user.id, title="Cache Layer", priority=TaskPriority.HIGH)
    db_session.add_all([t1, t2])
    db_session.flush()

    # Associate both tasks to project and goal
    a1 = GoalTaskAssociation(user_id=test_user.id, task_id=t1.id, project_id=project.id, goal_id=goal.id)
    a2 = GoalTaskAssociation(user_id=test_user.id, task_id=t2.id, project_id=project.id, goal_id=goal.id)
    db_session.add_all([a1, a2])
    db_session.flush()

    result = TaskDependencyService.discover_dependencies(
        db_session,
        test_user.id,
        DependencyDiscoveryRequest(min_confidence=0.5, include_project_goals=True),
    )

    types = {d.dependency_type for d in result.dependencies}
    assert TaskDependencyType.SHARED_PROJECT.value in types
    assert TaskDependencyType.SHARED_GOAL.value in types


def test_deadline_dependency_and_potential_blocker_discovery(db_session: Session, test_user: User):
    """Verifies that uncompleted upstream tasks with earlier deadlines are flagged as POTENTIAL_BLOCKER."""
    now = datetime.now(timezone.utc)
    project = Project(id=uuid.uuid4(), user_id=test_user.id, title="Security Hardening")
    db_session.add(project)
    db_session.flush()

    t_upstream = Task(
        id=uuid.uuid4(),
        user_id=test_user.id,
        title="Patch CVE Vulnerabilities",
        status=TaskStatus.PENDING,
        due_at=now - timedelta(hours=6),  # Overdue!
        priority=TaskPriority.HIGH,
    )
    t_downstream = Task(
        id=uuid.uuid4(),
        user_id=test_user.id,
        title="Deploy to Staging",
        status=TaskStatus.PENDING,
        due_at=now + timedelta(hours=18),
        priority=TaskPriority.HIGH,
    )
    db_session.add_all([t_upstream, t_downstream])
    db_session.flush()

    a1 = GoalTaskAssociation(user_id=test_user.id, task_id=t_upstream.id, project_id=project.id, is_critical_path=True)
    a2 = GoalTaskAssociation(user_id=test_user.id, task_id=t_downstream.id, project_id=project.id)
    db_session.add_all([a1, a2])
    db_session.flush()

    result = TaskDependencyService.discover_dependencies(
        db_session,
        test_user.id,
        DependencyDiscoveryRequest(min_confidence=0.5),
    )

    blocker_deps = [
        d for d in result.dependencies
        if d.dependency_type == TaskDependencyType.POTENTIAL_BLOCKER.value
        and d.source_task_id == t_upstream.id
        and d.target_task_id == t_downstream.id
    ]
    assert len(blocker_deps) == 1
    assert blocker_deps[0].confidence >= 0.80
    assert blocker_deps[0].supporting_observations.get("is_upstream_overdue") is True


def test_resource_conflict_discovery(db_session: Session, test_user: User):
    """Verifies discovery of resource conflicts when two pending tasks compete for same time window."""
    now = datetime.now(timezone.utc)
    t1 = Task(
        id=uuid.uuid4(),
        user_id=test_user.id,
        title="Client Demo Preparation",
        status=TaskStatus.PENDING,
        due_at=now + timedelta(hours=24),
        priority=TaskPriority.HIGH,
    )
    t2 = Task(
        id=uuid.uuid4(),
        user_id=test_user.id,
        title="Production Incident Post-Mortem",
        status=TaskStatus.PENDING,
        due_at=now + timedelta(hours=24, minutes=30),  # within 30 min of t1!
        priority=TaskPriority.HIGH,
    )
    db_session.add_all([t1, t2])
    db_session.flush()

    result = TaskDependencyService.discover_dependencies(
        db_session,
        test_user.id,
        DependencyDiscoveryRequest(min_confidence=0.5, include_resource_conflicts=True),
    )

    conflicts = [
        d for d in result.dependencies
        if d.dependency_type == TaskDependencyType.RESOURCE_CONFLICT.value
    ]
    assert len(conflicts) >= 1
    assert conflicts[0].supporting_observations.get("time_delta_hours") <= 1.0


def test_temporal_sequence_and_repeated_workflow_mining(db_session: Session, test_user: User):
    """
    Verifies that directional sequential completions across multiple days
    discover REPEATED_WORKFLOW with calibrated support, confidence, and lift.
    """
    now = datetime.now(timezone.utc)
    t_review = Task(id=uuid.uuid4(), user_id=test_user.id, title="Code Review", status=TaskStatus.COMPLETED)
    t_test = Task(id=uuid.uuid4(), user_id=test_user.id, title="Run Regression Tests", status=TaskStatus.COMPLETED)
    db_session.add_all([t_review, t_test])
    db_session.flush()

    # Simulate 3 distinct days of completion events where review precedes test
    for day_offset in [5, 3, 1]:
        base_time = now - timedelta(days=day_offset)
        ev1 = TaskEvent(
            id=uuid.uuid4(),
            user_id=test_user.id,
            task_id=t_review.id,
            event_type=TaskEventType.COMPLETED,
            occurred_at=base_time,
        )
        ev2 = TaskEvent(
            id=uuid.uuid4(),
            user_id=test_user.id,
            task_id=t_test.id,
            event_type=TaskEventType.COMPLETED,
            occurred_at=base_time + timedelta(minutes=20),
        )
        db_session.add_all([ev1, ev2])

    db_session.flush()

    result = TaskDependencyService.discover_dependencies(
        db_session,
        test_user.id,
        DependencyDiscoveryRequest(min_confidence=0.5, include_temporal=True),
    )

    workflows = [
        d for d in result.dependencies
        if d.dependency_type == TaskDependencyType.REPEATED_WORKFLOW.value
        and d.source_task_id == t_review.id
        and d.target_task_id == t_test.id
    ]
    assert len(workflows) == 1
    assert workflows[0].confidence >= 0.70
    assert workflows[0].supporting_observations.get("transition_probability") >= 0.80
    assert workflows[0].supporting_observations.get("co_occurrence_count") >= 2


def test_cascading_multi_hop_impact_analysis(db_session: Session, test_user: User):
    """
    Verifies multi-hop cascading impact traversal:
    Task A (blocked) -> Task B (hop 1) -> Task C (hop 2, critical path).
    Ensures milestones, projects, goals, and critical path risks are correctly evaluated.
    """
    project = Project(id=uuid.uuid4(), user_id=test_user.id, title="Flagship Release", health_status="ON_TRACK")
    goal = Goal(id=uuid.uuid4(), user_id=test_user.id, title="Q4 Launch Target", priority="HIGH")
    milestone = Milestone(
        id=uuid.uuid4(),
        user_id=test_user.id,
        project_id=project.id,
        goal_id=goal.id,
        title="Beta Release Milestone",
        due_date=datetime.now(timezone.utc) + timedelta(days=2),
        is_completed=False,
    )
    db_session.add_all([project, goal, milestone])
    db_session.flush()

    tA = Task(id=uuid.uuid4(), user_id=test_user.id, title="Core Module A", status=TaskStatus.IN_PROGRESS)
    tB = Task(id=uuid.uuid4(), user_id=test_user.id, title="Integration Module B", status=TaskStatus.PENDING)
    tC = Task(id=uuid.uuid4(), user_id=test_user.id, title="Final Release Verification C", status=TaskStatus.PENDING)
    db_session.add_all([tA, tB, tC])
    db_session.flush()

    # Link tC as critical path in project & goal
    db_session.add(
        GoalTaskAssociation(
            user_id=test_user.id,
            task_id=tC.id,
            project_id=project.id,
            goal_id=goal.id,
            is_critical_path=True,
        )
    )

    # Multi-hop dependencies: tA -> tB -> tC
    dep1 = TaskDependency(
        user_id=test_user.id,
        source_task_id=tA.id,
        target_task_id=tB.id,
        dependency_type=TaskDependencyType.POTENTIAL_BLOCKER.value,
        is_inferred=False,
        confidence=1.0,
        validation_status=DependencyValidationStatus.CONFIRMED.value,
    )
    dep2 = TaskDependency(
        user_id=test_user.id,
        source_task_id=tB.id,
        target_task_id=tC.id,
        dependency_type=TaskDependencyType.POTENTIAL_BLOCKER.value,
        is_inferred=False,
        confidence=1.0,
        validation_status=DependencyValidationStatus.CONFIRMED.value,
    )
    db_session.add_all([dep1, dep2])
    db_session.flush()

    impact = TaskDependencyService.run_impact_analysis(
        db_session,
        test_user.id,
        ImpactAnalysisRequest(task_id=tA.id, hypothetical_delay_days=4.0, is_blocked=True),
    )

    assert impact.total_downstream_tasks == 2
    assert impact.critical_path_risk is True
    assert impact.impact_severity in ("HIGH", "CRITICAL")
    assert len(impact.downstream_tasks) == 2

    # Check hops
    tB_item = next(t for t in impact.downstream_tasks if t.task_id == tB.id)
    tC_item = next(t for t in impact.downstream_tasks if t.task_id == tC.id)
    assert tB_item.hop_distance == 1
    assert tC_item.hop_distance == 2
    assert tC_item.critical_path is True

    # Check milestone breach risk
    assert len(impact.affected_milestones) == 1
    assert impact.affected_milestones[0].at_risk is True


def test_cross_tenant_user_isolation(db_session: Session, test_user: User, other_user: User):
    """Ensures a user cannot view, discover, or modify another user's dependencies."""
    t_other1 = Task(id=uuid.uuid4(), user_id=other_user.id, title="Other Task 1")
    t_other2 = Task(id=uuid.uuid4(), user_id=other_user.id, title="Other Task 2")
    db_session.add_all([t_other1, t_other2])
    db_session.flush()

    dep_other = TaskDependency(
        user_id=other_user.id,
        source_task_id=t_other1.id,
        target_task_id=t_other2.id,
        dependency_type=TaskDependencyType.EXPLICIT_DEPENDENCY.value,
        is_inferred=False,
        confidence=1.0,
        validation_status=DependencyValidationStatus.CONFIRMED.value,
    )
    db_session.add(dep_other)
    db_session.flush()

    # test_user cannot see other_user's dependency
    deps_user = TaskDependencyService.list_dependencies(db_session, test_user.id)
    assert dep_other.id not in [d.id for d in deps_user]

    # test_user cannot get or modify other_user's dependency
    with pytest.raises(NotFoundError):
        TaskDependencyService.get_dependency(db_session, test_user.id, dep_other.id)

    with pytest.raises(NotFoundError):
        TaskDependencyService.confirm_or_review_dependency(
            db_session,
            test_user.id,
            dep_other.id,
            TaskDependencyConfirmation(action="CONFIRM"),
        )


def test_rest_api_dependency_endpoints(auth_client: TestClient, db_session: Session, test_user: User):
    """End-to-end test of the REST API endpoints."""
    t1 = Task(id=uuid.uuid4(), user_id=test_user.id, title="API Endpoint Development")
    t2 = Task(id=uuid.uuid4(), user_id=test_user.id, title="Frontend Integration")
    db_session.add_all([t1, t2])
    db_session.flush()

    # 1. Create explicit dependency
    create_res = auth_client.post(
        "/api/v1/dependencies",
        json={
            "source_task_id": str(t1.id),
            "target_task_id": str(t2.id),
            "dependency_type": "EXPLICIT_DEPENDENCY",
            "confidence": 1.0,
            "notes": "Verified API contract",
        },
    )
    assert create_res.status_code == 201
    dep_id = create_res.json()["id"]

    # 2. List dependencies
    list_res = auth_client.get("/api/v1/dependencies")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 3. Discover dependencies
    disc_res = auth_client.post(
        "/api/v1/dependencies/discover",
        json={"lookback_days": 15, "min_confidence": 0.3},
    )
    assert disc_res.status_code == 200
    assert "discovered_count" in disc_res.json()

    # 4. Review / Confirm dependency
    conf_res = auth_client.post(
        f"/api/v1/dependencies/{dep_id}/confirm",
        json={"action": "CONFIRM", "notes": "Approved by engineering lead"},
    )
    assert conf_res.status_code == 200
    assert conf_res.json()["validation_status"] == "CONFIRMED"

    # 5. Impact Analysis endpoint
    impact_res = auth_client.post(
        "/api/v1/dependencies/impact-analysis",
        json={"task_id": str(t1.id), "hypothetical_delay_days": 2.5, "is_blocked": True},
    )
    assert impact_res.status_code == 200
    assert impact_res.json()["focal_task_id"] == str(t1.id)
    assert "downstream_tasks" in impact_res.json()

    # 6. Graph endpoint
    graph_res = auth_client.get("/api/v1/dependencies/graph")
    assert graph_res.status_code == 200
    assert "nodes" in graph_res.json()
    assert "edges" in graph_res.json()

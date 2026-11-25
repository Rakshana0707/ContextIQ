"""
Test suite for ContextIQ Phase 8.4: Goal and Project Intelligence.
Verifies multi-tier goal hierarchies, project health, milestone tracking, task associations,
evidence-based progress intelligence, behavioral alignment, risk detection, and governed recommendations.
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
from app.db.session import Base, get_db
from app.main import app
from app.models.enums import TaskPriority, TaskStatus
from app.models.focus_window import UserFocusWindow
from app.models.goal_project import (
    GoalHierarchyLevel,
    GoalProgressSnapshot,
    GoalRecommendation,
    GoalRiskFactor,
    GoalTaskAssociation,
    ProjectGoalAssociation,
    ProjectHealthStatus,
    ProjectMilestone,
    ProjectProgressSnapshot,
)
from app.models.knowledge_graph import Goal, Milestone, Project
from app.models.task import Task
from app.models.user import User
from app.schemas.goal_project import (
    GoalCreate,
    GoalRecommendationApprovalRequest,
    GoalTaskAssociationCreate,
    GoalUpdate,
    MilestoneCreate,
    MilestoneUpdate,
    ProjectCreate,
    ProjectUpdate,
)
from app.services.goal_project_service import GoalProjectService


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


@pytest.fixture(scope="function")
def test_user(db_session: Session) -> User:
    user = User(
        email=f"goal-{uuid.uuid4().hex[:8]}@contextiq.ai",
        display_name="Goal Lead",
        hashed_password="test_hash_password",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def second_user(db_session: Session) -> User:
    user = User(
        email=f"goal2-{uuid.uuid4().hex[:8]}@contextiq.ai",
        display_name="Second Lead",
        hashed_password="test_hash_password",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def client(db_session: Session, test_user: User):
    def override_get_db():
        yield db_session

    def override_get_current_user_id():
        return test_user.id

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_id] = override_get_current_user_id
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Service Tests
# ---------------------------------------------------------------------------

def test_goal_lifecycle_and_hierarchy(db_session: Session, test_user: User):
    """Verifies creation of multi-tier goal hierarchies (LONG_TERM -> INTERMEDIATE -> SHORT_TERM)."""
    parent_goal = GoalProjectService.create_goal(
        db=db_session,
        user_id=test_user.id,
        payload=GoalCreate(
            title="Launch Autonomous Micro-Delay Intelligence Platform",
            description="3-year strategic platform goal.",
            category="STRATEGY",
            hierarchy_level=GoalHierarchyLevel.LONG_TERM,
            priority="HIGH",
            completion_criteria="Full Phase 1-8 deployment.",
        ),
    )
    db_session.commit()

    assert parent_goal.id is not None
    assert parent_goal.hierarchy_level == "LONG_TERM"
    assert parent_goal.parent_goal_id is None

    # Child goal
    child_goal = GoalProjectService.create_goal(
        db=db_session,
        user_id=test_user.id,
        payload=GoalCreate(
            parent_goal_id=parent_goal.id,
            title="Implement Phase 8 Intelligence Subsystems",
            description="Intermediate quarter milestone goal.",
            category="ENGINEERING",
            hierarchy_level=GoalHierarchyLevel.INTERMEDIATE,
            priority="HIGH",
        ),
    )
    db_session.commit()

    assert child_goal.parent_goal_id == parent_goal.id
    assert child_goal.hierarchy_level == "INTERMEDIATE"

    # Self-reference validation
    with pytest.raises(Exception):
        GoalProjectService.update_goal(
            db=db_session,
            user_id=test_user.id,
            goal_id=child_goal.id,
            payload=GoalUpdate(parent_goal_id=child_goal.id),
        )


def test_project_lifecycle_and_goal_association(db_session: Session, test_user: User):
    """Tests project creation with health tracking and association to strategic goals."""
    goal = GoalProjectService.create_goal(
        db=db_session,
        user_id=test_user.id,
        payload=GoalCreate(title="Strategic Target"),
    )
    db_session.commit()

    project = GoalProjectService.create_project(
        db=db_session,
        user_id=test_user.id,
        payload=ProjectCreate(
            title="Core Graph Engine",
            description="Graph adjacency tables and traversal algorithms.",
            priority="HIGH",
            health_status=ProjectHealthStatus.ON_TRACK,
            contributes_to_goal_ids=[goal.id],
        ),
    )
    db_session.commit()

    assert project.id is not None
    assert project.health_status == "ON_TRACK"

    # Verify association was created
    assoc = db_session.execute(
        select(ProjectGoalAssociation).where(
            ProjectGoalAssociation.project_id == project.id,
            ProjectGoalAssociation.goal_id == goal.id,
        )
    ).scalar_one_or_none()
    assert assoc is not None
    assert assoc.contribution_weight == 1.0


def test_milestone_management(db_session: Session, test_user: User):
    """Tests milestone creation, ordering, and completion triggers."""
    goal = GoalProjectService.create_goal(
        db=db_session,
        user_id=test_user.id,
        payload=GoalCreate(title="Goal with Milestones"),
    )
    db_session.commit()

    m1 = GoalProjectService.create_milestone(
        db=db_session,
        user_id=test_user.id,
        payload=MilestoneCreate(
            goal_id=goal.id,
            title="Design Graph Schema",
            order_index=1,
            is_completed=True,
        ),
    )
    m2 = GoalProjectService.create_milestone(
        db=db_session,
        user_id=test_user.id,
        payload=MilestoneCreate(
            goal_id=goal.id,
            title="Deploy Graph Endpoints",
            order_index=2,
            is_completed=False,
        ),
    )
    db_session.commit()

    assert m1.is_completed is True
    assert m1.completed_at is not None
    assert m2.is_completed is False

    # Complete m2
    updated_m2 = GoalProjectService.update_milestone(
        db=db_session,
        user_id=test_user.id,
        milestone_id=m2.id,
        payload=MilestoneUpdate(is_completed=True),
    )
    db_session.commit()

    assert updated_m2.is_completed is True
    assert updated_m2.status == "COMPLETED"
    assert updated_m2.completed_at is not None


def test_task_associations(db_session: Session, test_user: User):
    """Tests many-to-many associations linking tasks to goals and projects with importance weights."""
    goal = GoalProjectService.create_goal(db=db_session, user_id=test_user.id, payload=GoalCreate(title="Goal 1"))
    task = Task(user_id=test_user.id, title="Database Migration Task", status=TaskStatus.IN_PROGRESS)
    db_session.add(task)
    db_session.commit()

    assoc = GoalProjectService.associate_task(
        db=db_session,
        user_id=test_user.id,
        payload=GoalTaskAssociationCreate(
            goal_id=goal.id,
            task_id=task.id,
            importance_weight=2.5,
            effort_weight=1.5,
            is_critical_path=True,
        ),
    )
    db_session.commit()

    assert assoc.id is not None
    assert assoc.importance_weight == 2.5
    assert assoc.is_critical_path is True

    assocs = GoalProjectService.list_task_associations(db_session, test_user.id, goal_id=goal.id)
    assert len(assocs) == 1
    assert assocs[0].task_title == "Database Migration Task"


def test_evidence_based_progress_calculation(db_session: Session, test_user: User):
    """
    Validates evidence-based progress calculation:
    - 40% milestone completion weight
    - 60% task weighted effort
    - Penalties for overdue and blocked tasks
    """
    goal = GoalProjectService.create_goal(db=db_session, user_id=test_user.id, payload=GoalCreate(title="Progress Goal"))
    m1 = GoalProjectService.create_milestone(
        db=db_session, user_id=test_user.id,
        payload=MilestoneCreate(goal_id=goal.id, title="Milestone 1", is_completed=True),
    )
    m2 = GoalProjectService.create_milestone(
        db=db_session, user_id=test_user.id,
        payload=MilestoneCreate(goal_id=goal.id, title="Milestone 2", is_completed=False),
    )

    t1 = Task(user_id=test_user.id, title="Completed Task", status=TaskStatus.COMPLETED)
    t2 = Task(user_id=test_user.id, title="In Progress Task", status=TaskStatus.IN_PROGRESS)
    db_session.add_all([t1, t2])
    db_session.commit()

    GoalProjectService.associate_task(
        db=db_session, user_id=test_user.id,
        payload=GoalTaskAssociationCreate(goal_id=goal.id, task_id=t1.id, importance_weight=1.0, effort_weight=1.0),
    )
    GoalProjectService.associate_task(
        db=db_session, user_id=test_user.id,
        payload=GoalTaskAssociationCreate(goal_id=goal.id, task_id=t2.id, importance_weight=1.0, effort_weight=1.0),
    )
    db_session.commit()

    snapshot = GoalProjectService.compute_goal_progress_and_risks(db=db_session, user_id=test_user.id, goal_id=goal.id)
    db_session.commit()

    # 50% milestone (0.4 * 50 = 20), 50% task (0.6 * 50 = 30) -> 50% progress
    assert snapshot.evidence_based_progress == 50.0
    assert snapshot.completed_milestones_count == 1
    assert snapshot.completed_tasks_count == 1


def test_goal_risk_detection(db_session: Session, test_user: User):
    """Verifies detection of approaching deadlines, overdue tasks, and blockers."""
    urgent_date = datetime.now(timezone.utc) + timedelta(days=2)
    goal = GoalProjectService.create_goal(
        db=db_session,
        user_id=test_user.id,
        payload=GoalCreate(
            title="Urgent Deliverable",
            target_date=urgent_date,
        ),
    )

    # Add blocked task
    blocked_task = Task(user_id=test_user.id, title="Blocked Deliverable", status=TaskStatus.PENDING)
    db_session.add(blocked_task)
    db_session.commit()

    GoalProjectService.associate_task(
        db=db_session,
        user_id=test_user.id,
        payload=GoalTaskAssociationCreate(
            goal_id=goal.id,
            task_id=blocked_task.id,
            association_type="BLOCKS",
        ),
    )
    db_session.commit()

    snapshot = GoalProjectService.compute_goal_progress_and_risks(db_session, test_user.id, goal.id)
    db_session.commit()

    assert GoalRiskFactor.DEADLINE_PROXIMITY.value in snapshot.risk_factors
    assert GoalRiskFactor.UNRESOLVED_BLOCKERS.value in snapshot.risk_factors
    assert snapshot.health_status in ("AT_RISK", "CRITICAL")


def test_behavioral_alignment_analytics(db_session: Session, test_user: User):
    """Tests behavioral alignment computation connecting focus time and postponement friction to goals."""
    from datetime import time
    proj = GoalProjectService.create_project(
        db=db_session, user_id=test_user.id,
        payload=ProjectCreate(title="Architecture Engine"),
    )
    focus_win = UserFocusWindow(
        user_id=test_user.id,
        start_time=time(9, 0),
        end_time=time(11, 0),
        duration_minutes=120,
        quality_score=94.0,
        is_active=True,
    )
    db_session.add(focus_win)
    db_session.commit()

    alignment = GoalProjectService.compute_behavioral_alignment(db_session, test_user.id)
    assert len(alignment.recommended_focus_windows_for_goals) >= 1
    assert any("Descriptive observation" in c for c in alignment.descriptive_correlations)


def test_intelligent_recommendation_governance(db_session: Session, test_user: User):
    """Verifies that generated recommendations require user approval before applying changes."""
    goal = GoalProjectService.create_goal(db=db_session, user_id=test_user.id, payload=GoalCreate(title="Test Goal"))
    task = Task(user_id=test_user.id, title="Critical Unfinished Task", priority=TaskPriority.LOW, status=TaskStatus.PENDING)
    db_session.add(task)
    db_session.commit()

    GoalProjectService.associate_task(
        db=db_session, user_id=test_user.id,
        payload=GoalTaskAssociationCreate(
            goal_id=goal.id, task_id=task.id, is_critical_path=True,
        ),
    )
    db_session.commit()

    recs = GoalProjectService.generate_goal_recommendations(db_session, test_user.id)
    db_session.commit()

    assert len(recs) >= 1
    rec = recs[0]
    assert rec.requires_approval is True
    assert rec.is_approved is None

    # User approves and applies
    approved_rec = GoalProjectService.approve_recommendation(
        db=db_session,
        user_id=test_user.id,
        recommendation_id=rec.id,
        payload=GoalRecommendationApprovalRequest(approve=True, apply_immediately=True),
    )
    db_session.commit()

    assert approved_rec.is_approved is True
    assert approved_rec.applied_at is not None

    # Verify task priority was updated to HIGH upon approval
    db_session.refresh(task)
    assert task.priority == TaskPriority.HIGH


# ---------------------------------------------------------------------------
# API Integration Tests
# ---------------------------------------------------------------------------

def test_api_goal_dashboard_endpoint(client: TestClient, db_session: Session, test_user: User):
    """Tests GET /api/v1/goals/dashboard."""
    res = client.get("/api/v1/goals/dashboard")
    assert res.status_code == 200
    data = res.json()
    assert "total_goals" in data
    assert "active_projects" in data
    assert "overall_health" in data
    assert "behavioral_alignment" in data


def test_api_goal_crud_endpoints(client: TestClient, db_session: Session, test_user: User):
    """Tests POST, GET, PATCH, and DELETE on /api/v1/goals."""
    create_payload = {
        "title": "API Strategic Goal",
        "description": "Via REST endpoint",
        "category": "PRODUCTIVITY",
        "hierarchy_level": "LONG_TERM",
        "priority": "HIGH",
    }
    post_res = client.post("/api/v1/goals", json=create_payload)
    assert post_res.status_code == 201
    goal_id = post_res.json()["id"]

    get_res = client.get(f"/api/v1/goals/{goal_id}")
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "API Strategic Goal"

    patch_res = client.patch(f"/api/v1/goals/{goal_id}", json={"priority": "URGENT"})
    assert patch_res.status_code == 200
    assert patch_res.json()["priority"] == "URGENT"

    eval_res = client.post(f"/api/v1/goals/{goal_id}/evaluate")
    assert eval_res.status_code == 200
    assert "evidence_based_progress" in eval_res.json()

    del_res = client.delete(f"/api/v1/goals/{goal_id}")
    assert del_res.status_code == 204


def test_api_project_and_association_endpoints(client: TestClient, db_session: Session, test_user: User):
    """Tests project and task association REST endpoints."""
    # Create project
    proj_res = client.post("/api/v1/goals/projects", json={"title": "REST Project", "priority": "HIGH"})
    assert proj_res.status_code == 201
    proj_id = proj_res.json()["id"]

    # Create task
    task = Task(user_id=test_user.id, title="API Task", status=TaskStatus.PENDING)
    db_session.add(task)
    db_session.commit()

    # Link task
    assoc_res = client.post(
        "/api/v1/goals/associations/task",
        json={"project_id": proj_id, "task_id": str(task.id), "importance_weight": 2.0},
    )
    assert assoc_res.status_code == 201
    assoc_id = assoc_res.json()["id"]

    # List associations
    list_res = client.get(f"/api/v1/goals/associations/task?project_id={proj_id}")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # Delete association
    del_assoc = client.delete(f"/api/v1/goals/associations/task/{assoc_id}")
    assert del_assoc.status_code == 204

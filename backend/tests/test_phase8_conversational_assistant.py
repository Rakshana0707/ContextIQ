"""
Test suite for ContextIQ Phase 8.8: Knowledge-Grounded Conversational Assistant.

Verifies:
1. Grounded context retrieval strictly scoped to the authenticated user (no cross-tenant leakage).
2. Answer synthesis for canonical scenarios:
   - "What should I focus on today?"
   - "Which project is falling behind?"
   - "Why do I keep postponing this task?"
   - "Which tasks are blocking my current goal?"
   - "What changed in my productivity this month?"
   - "Which recommendations have worked well historically?"
3. Anti-hallucination guardrail validation and explicit missing data disclosure.
4. Separation of conversational recommendations from governed execution (Phase 7).
5. Conversation session persistence, retrieval, and archiving.
6. REST API endpoints via FastAPI TestClient.
"""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

from app.core.deps import get_current_user_id
from app.db.session import Base, get_db
from app.main import app
from app.models.assistant import AssistantConversation, AssistantMessage
from app.models.behavioral_memory import (
    BehavioralMemory,
    MemoryCategory,
    MemorySourceType,
    MemoryValidityStatus,
)
from app.models.behavioral_trend import (
    BehavioralDailyMetric,
    BehavioralMilestoneRecord,
    TrendCategory,
    TrendDirection,
)
from app.models.enums import (
    RecommendationFeedbackAction,
    TaskEventType,
    TaskPriority,
    TaskStatus,
)
from app.models.goal_project import GoalTaskAssociation, ProjectMilestone
from app.models.knowledge_graph import Goal, Project
from app.models.project_forecast import DelayRiskTier, ProjectForecast
from app.models.recommendation import Recommendation
from app.models.recommendation_feedback import RecommendationFeedback
from app.models.task import Task
from app.models.task_dependency import TaskDependency, TaskDependencyType
from app.models.task_event import TaskEvent
from app.models.user import User
from app.services.assistant_context_retriever import AssistantContextRetriever
from app.services.assistant_service import AntiHallucinationGuard, AssistantService


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


@pytest.fixture
def db_session(test_engine):
    connection = test_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection)
    session = session_factory()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def user_a(db_session: Session) -> User:
    u = User(
        id=uuid.uuid4(),
        email=f"user_a_{uuid.uuid4().hex[:6]}@example.com",
        display_name=f"user_a_{uuid.uuid4().hex[:6]}",
        hashed_password="pw",
    )
    db_session.add(u)
    db_session.flush()
    return u


@pytest.fixture
def user_b(db_session: Session) -> User:
    u = User(
        id=uuid.uuid4(),
        email=f"user_b_{uuid.uuid4().hex[:6]}@example.com",
        display_name=f"user_b_{uuid.uuid4().hex[:6]}",
        hashed_password="pw",
    )
    db_session.add(u)
    db_session.flush()
    return u


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_user_scoped_isolation(db_session: Session, user_a: User, user_b: User):
    """
    Guarantees User A cannot see or retrieve User B's confidential tasks,
    projects, or metrics through the conversational assistant.
    """
    now = datetime.now(timezone.utc)

    # User B has a confidential task and project
    secret_task = Task(
        id=uuid.uuid4(),
        user_id=user_b.id,
        title="Classified Project Blackbird Deliverable",
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.URGENT,
        due_at=now + timedelta(days=1),
    )
    db_session.add(secret_task)
    db_session.flush()

    # User A asks for focus guidance
    conv, msg, resp = AssistantService.ask(
        db=db_session,
        user_id=user_a.id,
        query="What should I focus on today?",
    )

    # Assert no leakage of user B's secret task
    assert "Blackbird" not in resp.direct_answer
    for ent in resp.relevant_entities:
        assert ent.entity_id != str(secret_task.id)
        assert ent.title != secret_task.title
    for ev in resp.supporting_evidence:
        assert ev.entity_id != str(secret_task.id)

    # User A specifically inquires about Blackbird
    conv2, msg2, resp2 = AssistantService.ask(
        db=db_session,
        user_id=user_a.id,
        query="What is the status of Classified Project Blackbird?",
    )

    # Must be marked as unobserved / missing data
    assert resp2.uncertainty_level == "UNCERTAIN"
    assert any("Blackbird" in info or "matching" in info.lower() for info in resp2.missing_information)
    assert len(resp2.relevant_entities) == 0


def test_focus_today_prioritization(db_session: Session, user_a: User):
    """
    Verifies that 'What should I focus on today?' prioritizes overdue tasks,
    orders by urgency, and references focus habits.
    """
    now = datetime.now(timezone.utc)

    # 1 Overdue task
    overdue_task = Task(
        id=uuid.uuid4(),
        user_id=user_a.id,
        title="Complete Quarterly Security Audit",
        status=TaskStatus.PENDING,
        priority=TaskPriority.HIGH,
        due_at=now - timedelta(hours=4),
    )
    # 1 Future task
    future_task = Task(
        id=uuid.uuid4(),
        user_id=user_a.id,
        title="Draft Architecture RFC",
        status=TaskStatus.PENDING,
        priority=TaskPriority.MEDIUM,
        due_at=now + timedelta(days=2),
    )
    db_session.add_all([overdue_task, future_task])

    # Focus memory
    memory = BehavioralMemory(
        id=uuid.uuid4(),
        user_id=user_a.id,
        category=MemoryCategory.FOCUS_PATTERNS,
        title="Peak Focus Window Morning",
        description="Peak focus is 9:00 AM to 11:30 AM with minimal context switching.",
        confidence=0.92,
        observation_count=15,
        validity_status=MemoryValidityStatus.ACTIVE,
    )
    db_session.add(memory)
    db_session.flush()

    conv, msg, resp = AssistantService.ask(
        db=db_session,
        user_id=user_a.id,
        query="What should I focus on today?",
    )

    # Assert overdue task is prioritized first
    assert "Complete Quarterly Security Audit" in resp.direct_answer
    assert "overdue" in resp.direct_answer.lower()
    assert len(resp.relevant_entities) >= 1
    assert resp.relevant_entities[0].entity_id == str(overdue_task.id)

    # Proposes governed priority escalation or review
    assert len(resp.action_proposals) >= 1
    assert resp.action_proposals[0].requires_governed_approval is True
    assert resp.action_proposals[0].action_identifier == "task:update_priority"


def test_falling_behind_projects(db_session: Session, user_a: User):
    """
    Verifies that 'Which project is falling behind?' detects projects marked
    AT_RISK or with high forecast delay risk and overdue milestones.
    """
    now = datetime.now(timezone.utc)

    # Project at risk
    p_risk = Project(
        id=uuid.uuid4(),
        user_id=user_a.id,
        title="Mobile App Redesign",
        status="ACTIVE",
        health_status="AT_RISK",
        priority="HIGH",
        target_completion_date=now + timedelta(days=10),
    )
    # Project on track
    p_track = Project(
        id=uuid.uuid4(),
        user_id=user_a.id,
        title="Backend Infrastructure Migration",
        status="ACTIVE",
        health_status="ON_TRACK",
        priority="MEDIUM",
        target_completion_date=now + timedelta(days=30),
    )
    db_session.add_all([p_risk, p_track])
    db_session.flush()

    # Forecast with delay risk
    forecast = ProjectForecast(
        id=uuid.uuid4(),
        user_id=user_a.id,
        project_id=p_risk.id,
        delay_risk_tier=DelayRiskTier.HIGH.value,
        on_time_probability=0.35,
        data_sufficiency="DATA_SUFFICIENT",
        model_name="GRADIENT_BOOSTING",
    )
    db_session.add(forecast)
    db_session.flush()

    conv, msg, resp = AssistantService.ask(
        db=db_session,
        user_id=user_a.id,
        query="Which project is falling behind?",
    )

    assert "Mobile App Redesign" in resp.direct_answer
    assert "AT_RISK" in resp.direct_answer
    assert any(ent.entity_id == str(p_risk.id) for ent in resp.relevant_entities)
    assert any(ev.confidence_or_metric == "HIGH" or ev.confidence_or_metric == "AT_RISK" for ev in resp.supporting_evidence)


def test_why_postponing_task_with_blocker(db_session: Session, user_a: User):
    """
    Verifies diagnosis for postponed tasks: identifies postponement events,
    upstream dependency blockers, and proposes subtask decomposition.
    """
    now = datetime.now(timezone.utc)

    task_blocker = Task(
        id=uuid.uuid4(),
        user_id=user_a.id,
        title="Obtain API Credentials",
        status=TaskStatus.PENDING,
        priority=TaskPriority.HIGH,
    )
    task_postponed = Task(
        id=uuid.uuid4(),
        user_id=user_a.id,
        title="Integrate Payment Gateway",
        status=TaskStatus.PENDING,
        priority=TaskPriority.MEDIUM,
    )
    db_session.add_all([task_blocker, task_postponed])
    db_session.flush()

    # 3 postponement events
    for _ in range(3):
        ev = TaskEvent(
            id=uuid.uuid4(),
            user_id=user_a.id,
            task_id=task_postponed.id,
            event_type=TaskEventType.PAUSED,
            occurred_at=now - timedelta(days=1),
        )
        db_session.add(ev)

    # Dependency: task_blocker blocks task_postponed
    dep = TaskDependency(
        id=uuid.uuid4(),
        user_id=user_a.id,
        source_task_id=task_blocker.id,
        target_task_id=task_postponed.id,
        dependency_type=TaskDependencyType.POTENTIAL_BLOCKER.value,
        confidence=0.95,
        is_inferred=True,
    )
    db_session.add(dep)
    db_session.flush()

    conv, msg, resp = AssistantService.ask(
        db=db_session,
        user_id=user_a.id,
        query="Why do I keep postponing Integrate Payment Gateway?",
    )

    assert "Integrate Payment Gateway" in resp.direct_answer
    assert "3 time(s)" in resp.direct_answer or "3" in resp.direct_answer
    assert "Obtain API Credentials" in resp.direct_answer or "blocked" in resp.direct_answer.lower()
    assert any(prop.action_identifier == "task:decompose_into_subtasks" for prop in resp.action_proposals)
    assert resp.action_proposals[0].requires_governed_approval is True


def test_tasks_blocking_current_goal(db_session: Session, user_a: User):
    """
    Verifies that 'Which tasks are blocking my current goal?' correctly identifies
    active goals, linked tasks, and blocker relationships.
    """
    now = datetime.now(timezone.utc)

    goal = Goal(
        id=uuid.uuid4(),
        user_id=user_a.id,
        title="Launch Product Beta Q4",
        status="ACTIVE",
        hierarchy_level="LONG_TERM",
        progress_pct=0.45,
    )
    db_session.add(goal)
    db_session.flush()

    task_target = Task(
        id=uuid.uuid4(),
        user_id=user_a.id,
        title="Deploy Staging Cluster",
        status=TaskStatus.PENDING,
        priority=TaskPriority.HIGH,
    )
    task_blocker = Task(
        id=uuid.uuid4(),
        user_id=user_a.id,
        title="Resolve Cloud IAM Policy Errors",
        status=TaskStatus.PENDING,
        priority=TaskPriority.URGENT,
    )
    db_session.add_all([task_target, task_blocker])
    db_session.flush()

    # Link task_target to goal
    gta = GoalTaskAssociation(
        id=uuid.uuid4(),
        user_id=user_a.id,
        goal_id=goal.id,
        task_id=task_target.id,
        importance_weight=1.0,
    )
    db_session.add(gta)

    # Blocker dependency
    dep = TaskDependency(
        id=uuid.uuid4(),
        user_id=user_a.id,
        source_task_id=task_blocker.id,
        target_task_id=task_target.id,
        dependency_type=TaskDependencyType.POTENTIAL_BLOCKER.value,
        confidence=0.9,
        is_inferred=True,
    )
    db_session.add(dep)
    db_session.flush()

    conv, msg, resp = AssistantService.ask(
        db=db_session,
        user_id=user_a.id,
        query="Which tasks are blocking my current goal Launch Product Beta Q4?",
    )

    assert "Launch Product Beta Q4" in resp.direct_answer
    assert "Resolve Cloud IAM Policy Errors" in resp.direct_answer
    assert any(ent.entity_id == str(task_blocker.id) for ent in resp.relevant_entities)


def test_monthly_productivity_trends(db_session: Session, user_a: User):
    """
    Verifies monthly behavioral change explanation from 30-day aggregated metrics.
    """
    now = datetime.now(timezone.utc)

    # Insert 14 daily metrics
    for i in range(14):
        d = (now - timedelta(days=14 - i)).date()
        m = BehavioralDailyMetric(
            user_id=user_a.id,
            metric_date=d,
            total_focus_minutes=180.0,
            behavioral_friction_index=22.0 if i >= 7 else 38.0,
            recovery_efficiency_score=0.85,
            tasks_completed_count=2,
            context_switch_frequency=2.1,
            deadline_adherence_rate=0.9,
            data_coverage_ratio=0.9,
        )
        db_session.add(m)
    db_session.flush()

    conv, msg, resp = AssistantService.ask(
        db=db_session,
        user_id=user_a.id,
        query="What changed in my productivity this month?",
    )

    assert "Friction Trajectory" in resp.direct_answer
    assert "IMPROVING" in resp.direct_answer
    assert "180.0 minutes" in resp.direct_answer
    assert resp.uncertainty_level == "LOW"


def test_recommendations_worked_well(db_session: Session, user_a: User):
    """
    Verifies query on historical recommendation effectiveness.
    """
    now = datetime.now(timezone.utc)

    rec = Recommendation(
        id=uuid.uuid4(),
        user_id=user_a.id,
        title="Shift Deep Work to 9:00 AM",
        message="Recommended morning focus window protection",
        recommendation_type="SCHEDULE_SHIFT",
        created_at=now - timedelta(days=5),
    )
    db_session.add(rec)
    db_session.flush()

    fb = RecommendationFeedback(
        id=uuid.uuid4(),
        user_id=user_a.id,
        recommendation_id=rec.id,
        action=RecommendationFeedbackAction.ACCEPTED,
        created_at=now - timedelta(days=5),
        feedback_note="Significantly reduced morning interruptions",
    )
    db_session.add(fb)
    db_session.flush()

    conv, msg, resp = AssistantService.ask(
        db=db_session,
        user_id=user_a.id,
        query="Which recommendations have worked well historically?",
    )

    assert "SCHEDULE_SHIFT" in resp.direct_answer
    assert "ACCEPTED" in resp.direct_answer or "accepted 1 recommendation" in resp.direct_answer.lower()
    assert any(ent.entity_id == str(rec.id) for ent in resp.relevant_entities)


def test_conversation_session_crud(db_session: Session, user_a: User):
    """
    Verifies session persistence, multi-turn history, and archiving.
    """
    conv, msg1, resp1 = AssistantService.ask(
        db=db_session,
        user_id=user_a.id,
        query="First question: What should I focus on today?",
    )

    conv_id = conv.id

    # Follow-up in same conversation
    conv_ref, msg2, resp2 = AssistantService.ask(
        db=db_session,
        user_id=user_a.id,
        query="Second question: Which project is falling behind?",
        conversation_id=conv_id,
    )

    assert conv_ref.id == conv_id

    # List conversations
    conv_list = AssistantService.list_conversations(db=db_session, user_id=user_a.id)
    assert len(conv_list) >= 1
    found = next((c for c in conv_list if c.id == conv_id), None)
    assert found is not None
    assert found.message_count == 4  # 2 user messages + 2 assistant messages

    # Get conversation
    fetched = AssistantService.get_conversation(db=db_session, user_id=user_a.id, conversation_id=conv_id)
    assert fetched is not None
    assert len(fetched.recent_messages) == 4

    # Archive conversation
    archived = AssistantService.archive_conversation(db=db_session, user_id=user_a.id, conversation_id=conv_id)
    assert archived is True

    # Active list no longer shows archived session
    conv_list_active = AssistantService.list_conversations(db=db_session, user_id=user_a.id, include_archived=False)
    assert not any(c.id == conv_id for c in conv_list_active)


def test_anti_hallucination_guard_validation(user_a: User):
    """
    Directly exercises AntiHallucinationGuard to ensure fabricated entities
    or contradictory statuses are rejected.
    """
    from app.schemas.assistant import ActionProposal, EntityReference, StructuredAssistantResponse
    from app.services.assistant_context_retriever import RetrievedUserContext, TaskSummary

    now = datetime.now(timezone.utc)
    task_real = TaskSummary(
        id=str(uuid.uuid4()),
        title="Real Task",
        status="PENDING",
        priority="MEDIUM",
        due_at=now,
        is_overdue=False,
        estimated_minutes=30,
        completed_at=None,
        postponement_count=0,
        context_tag=None,
    )

    ctx = RetrievedUserContext(
        user_id=user_a.id,
        now=now,
        tasks=[task_real],
        task_map={task_real.id: task_real},
    )

    # Valid response
    valid_resp = StructuredAssistantResponse(
        direct_answer="Focus on Real Task.",
        supporting_evidence=[],
        relevant_entities=[
            EntityReference(entity_type="TASK", entity_id=task_real.id, title="Real Task", status="PENDING")
        ],
        action_proposals=[
            ActionProposal(
                action_identifier="task:defer_task",
                parameters={},
                rationale="Deferral",
                requires_governed_approval=True,
            )
        ],
    )
    is_valid, violations = AntiHallucinationGuard.validate(valid_resp, ctx)
    assert is_valid is True
    assert len(violations) == 0

    # Fabricated entity ID
    fake_id = str(uuid.uuid4())
    hallucinated_resp = StructuredAssistantResponse(
        direct_answer="Focus on Phantom Task.",
        supporting_evidence=[],
        relevant_entities=[
            EntityReference(entity_type="TASK", entity_id=fake_id, title="Phantom Task", status="PENDING")
        ],
    )
    is_valid2, violations2 = AntiHallucinationGuard.validate(hallucinated_resp, ctx)
    assert is_valid2 is False
    assert any("unknown task ID" in v for v in violations2)

    # Status contradiction
    contradictory_resp = StructuredAssistantResponse(
        direct_answer="Real Task is done.",
        supporting_evidence=[],
        relevant_entities=[
            EntityReference(entity_type="TASK", entity_id=task_real.id, title="Real Task", status="COMPLETED")
        ],
    )
    is_valid3, violations3 = AntiHallucinationGuard.validate(contradictory_resp, ctx)
    assert is_valid3 is False
    assert any("contradiction" in v.lower() for v in violations3)


def test_assistant_api_client(db_session: Session, user_a: User):
    """
    Tests REST endpoints via FastAPI TestClient with authenticated user.
    """
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user_id] = lambda: user_a.id

    client = TestClient(app)

    try:
        # 1. Ask assistant
        ask_resp = client.post(
            "/api/v1/assistant/ask",
            json={
                "query": "What should I focus on today?",
                "include_evidence": True,
                "include_proposals": True,
            },
        )
        assert ask_resp.status_code == 200
        data = ask_resp.json()
        assert "conversation_id" in data
        assert "response" in data
        assert "direct_answer" in data["response"]

        conv_id = data["conversation_id"]

        # 2. List conversations
        list_resp = client.get("/api/v1/assistant/conversations")
        assert list_resp.status_code == 200
        list_data = list_resp.json()
        assert list_data["total"] >= 1

        # 3. Get conversation details
        get_resp = client.get(f"/api/v1/assistant/conversations/{conv_id}")
        assert get_resp.status_code == 200
        get_data = get_resp.json()
        assert get_data["id"] == conv_id
        assert len(get_data["recent_messages"]) >= 2

        # 4. Archive conversation
        del_resp = client.delete(f"/api/v1/assistant/conversations/{conv_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "archived"

    finally:
        app.dependency_overrides.clear()

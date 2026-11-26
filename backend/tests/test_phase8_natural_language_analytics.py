"""
Test suite for ContextIQ Phase 8.9: Natural-Language Productivity Analytics
and Cross-Project Decision Intelligence.

Verifies:
1. Structured Query Planner AST generation for canonical and custom inquiries.
2. Strict rejection of malicious SQL injection attempts.
3. Safe ORM execution with tenant isolation (user_id scoped).
4. All 7 canonical productivity analytics scenarios:
   - Project time allocation
   - Goal blocked tasks
   - Project delay risk
   - Postponed task types
   - Recovery duration trends
   - Intervention historical evidence
   - Deadline and priority conflicts
5. Cross-project synthesis and decision support recommendations.
6. Visual analytics chart specification generation (BAR, LINE, PIE, TIMELINE).
7. Non-causal epistemic boundary disclaimers.
8. Saved query bookmarks CRUD.
9. REST API endpoints via FastAPI TestClient (query, suggestions, saved, export).
"""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

from app.core.deps import get_current_user_id
from app.db.session import Base, get_db
from app.main import app
from app.models.analytics_workspace import SavedAnalyticsQuery
from app.models.behavioral_trend import BehavioralDailyMetric
from app.models.enums import (
    RecommendationFeedbackAction,
    RecommendationType,
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
from app.schemas.analytics_workspace import (
    AnalyticsDomain,
    ChartType,
    AnalyticsQueryRequest,
    SavedAnalyticsQueryCreate,
)
from app.services.analytics_query_executor import AnalyticsQueryExecutor
from app.services.analytics_query_planner import AnalyticsQueryPlanner
from app.services.natural_language_analytics_service import NaturalLanguageAnalyticsService
from app.services.visual_analytics_generator import VisualAnalyticsGenerator


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db(test_engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def mock_users(db: Session):
    uid = uuid.uuid4().hex[:8]
    user_a = User(
        id=uuid.uuid4(),
        email=f"user_a_nl_{uid}@example.com",
        display_name="User A NL",
        hashed_password="pw",
        created_at=datetime.now(timezone.utc),
    )
    user_b = User(
        id=uuid.uuid4(),
        email=f"user_b_nl_{uid}@example.com",
        display_name="User B NL",
        hashed_password="pw",
        created_at=datetime.now(timezone.utc),
    )
    db.add_all([user_a, user_b])
    db.commit()
    db.refresh(user_a)
    db.refresh(user_b)
    return user_a, user_b


@pytest.fixture
def populated_user_a(db: Session, mock_users):
    user_a, _ = mock_users
    now = datetime.now(timezone.utc)

    # 1. Projects
    proj1 = Project(
        id=uuid.uuid4(),
        user_id=user_a.id,
        title="Mobile App Redesign",
        description="Overhaul UI/UX",
        status="ACTIVE",
        target_completion_date=now + timedelta(days=40),
        health_status="ON_TRACK",
    )
    proj2 = Project(
        id=uuid.uuid4(),
        user_id=user_a.id,
        title="Infrastructure Scalability",
        description="Migrate DB and cache",
        status="ACTIVE",
        target_completion_date=now + timedelta(days=10),
        health_status="AT_RISK",
    )
    db.add_all([proj1, proj2])
    db.commit()

    # 2. Goals
    goal1 = Goal(
        id=uuid.uuid4(),
        user_id=user_a.id,
        title="Launch MVP Beta",
        target_date=now + timedelta(days=14),
        priority="HIGH",
        status="IN_PROGRESS",
    )
    db.add(goal1)
    db.commit()

    # 3. Tasks
    task1 = Task(
        id=uuid.uuid4(),
        user_id=user_a.id,
        title="Design wireframes for Mobile App Redesign",
        status=TaskStatus.COMPLETED,
        priority=TaskPriority.HIGH,
        due_at=now - timedelta(days=2),
        estimated_minutes=180,
    )
    task2 = Task(
        id=uuid.uuid4(),
        user_id=user_a.id,
        title="User testing sessions for Mobile App Redesign",
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.MEDIUM,
        due_at=now + timedelta(days=3),
        estimated_minutes=120,
    )
    task3 = Task(
        id=uuid.uuid4(),
        user_id=user_a.id,
        title="DB schema migration for Infrastructure Scalability",
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.HIGH,
        due_at=now + timedelta(days=1),
        estimated_minutes=240,
    )
    task4 = Task(
        id=uuid.uuid4(),
        user_id=user_a.id,
        title="Deploy cache cluster for Infrastructure Scalability",
        status=TaskStatus.PENDING,
        priority=TaskPriority.HIGH,
        due_at=now + timedelta(days=2),
        estimated_minutes=90,
    )
    db.add_all([task1, task2, task3, task4])
    db.commit()

    # 4. GoalTaskAssociation
    gta1 = GoalTaskAssociation(
        id=uuid.uuid4(),
        user_id=user_a.id,
        goal_id=goal1.id,
        task_id=task3.id,
        project_id=proj2.id,
        importance_weight=0.6,
    )
    gta2 = GoalTaskAssociation(
        id=uuid.uuid4(),
        user_id=user_a.id,
        goal_id=goal1.id,
        task_id=task4.id,
        project_id=proj2.id,
        importance_weight=0.4,
    )
    gta3 = GoalTaskAssociation(
        id=uuid.uuid4(),
        user_id=user_a.id,
        goal_id=goal1.id,
        task_id=task1.id,
        project_id=proj1.id,
        importance_weight=0.5,
    )
    db.add_all([gta1, gta2, gta3])
    db.commit()

    # 5. Task Dependency (task4 blocked by task3)
    dep1 = TaskDependency(
        id=uuid.uuid4(),
        user_id=user_a.id,
        source_task_id=task3.id,
        target_task_id=task4.id,
        dependency_type=TaskDependencyType.POTENTIAL_BLOCKER.value,
        confidence=0.92,
        is_inferred=True,
    )
    db.add(dep1)
    db.commit()

    # 6. Project Forecasts
    forecast1 = ProjectForecast(
        id=uuid.uuid4(),
        user_id=user_a.id,
        project_id=proj2.id,
        on_time_probability=0.25,
        delay_risk_score=0.75,
        delay_risk_tier=DelayRiskTier.HIGH.value,
        data_sufficiency="SUFFICIENT",
        model_name="survival_gradient_boost",
        forecast_at=now,
    )
    forecast2 = ProjectForecast(
        id=uuid.uuid4(),
        user_id=user_a.id,
        project_id=proj1.id,
        on_time_probability=0.88,
        delay_risk_score=0.12,
        delay_risk_tier=DelayRiskTier.LOW.value,
        data_sufficiency="SUFFICIENT",
        model_name="survival_gradient_boost",
        forecast_at=now,
    )
    db.add_all([forecast1, forecast2])
    db.commit()

    # 7. TaskEvents (Postponed events)
    te1 = TaskEvent(
        id=uuid.uuid4(),
        task_id=task3.id,
        user_id=user_a.id,
        event_type=TaskEventType.PAUSED,
        occurred_at=now - timedelta(days=2),
        created_at=now - timedelta(days=2),
    )
    te2 = TaskEvent(
        id=uuid.uuid4(),
        task_id=task3.id,
        user_id=user_a.id,
        event_type=TaskEventType.PAUSED,
        occurred_at=now - timedelta(days=1),
        created_at=now - timedelta(days=1),
    )
    db.add_all([te1, te2])
    db.commit()

    # 8. BehavioralDailyMetric (Recovery trends)
    for i in range(5):
        m = BehavioralDailyMetric(
            id=uuid.uuid4(),
            user_id=user_a.id,
            metric_date=date.today() - timedelta(days=i),
            avg_recovery_lag_seconds=320.0 + i * 20.0,
            recovery_efficiency_score=0.75 - i * 0.02,
            context_switch_frequency=4.5,
            deadline_adherence_rate=0.85,
            behavioral_friction_index=35.0,
        )
        db.add(m)
    db.commit()

    # 9. Recommendation & Feedback
    rec1 = Recommendation(
        id=uuid.uuid4(),
        user_id=user_a.id,
        recommendation_type=RecommendationType.SCHEDULE_SHIFT,
        title="Schedule deep work block",
        message="Schedule 90-min deep work block for database migration",
        created_at=now - timedelta(days=3),
    )
    db.add(rec1)
    db.commit()

    fb1 = RecommendationFeedback(
        id=uuid.uuid4(),
        user_id=user_a.id,
        recommendation_id=rec1.id,
        action=RecommendationFeedbackAction.ACCEPTED,
        created_at=now - timedelta(days=2),
    )
    db.add(fb1)
    db.commit()

    return user_a


# ---------------------------------------------------------------------------
# 1. Query Planner Tests
# ---------------------------------------------------------------------------

def test_query_planner_canonical_questions():
    canonical_map = [
        ("Which project consumed most of my productive time?", AnalyticsDomain.PROJECT_TIME_ALLOCATION),
        ("Which goal has the greatest number of blocked tasks?", AnalyticsDomain.GOAL_BLOCKED_TASKS),
        ("Which project has the highest delay risk?", AnalyticsDomain.PROJECT_DELAY_RISK),
        ("What types of tasks do I postpone most often?", AnalyticsDomain.TASK_POSTPONEMENT_TYPES),
        ("How has my recovery duration changed?", AnalyticsDomain.RECOVERY_DURATION_TREND),
        ("Which interventions have the strongest historical evidence?", AnalyticsDomain.INTERVENTION_HISTORICAL_EVIDENCE),
        ("Which upcoming deadlines conflict with my current priorities?", AnalyticsDomain.DEADLINE_PRIORITY_CONFLICTS),
    ]

    for q, expected_domain in canonical_map:
        plan = AnalyticsQueryPlanner.plan_query(q)
        assert plan.is_valid is True
        assert plan.target_domain == expected_domain
        assert plan.planning_rationale != ""


def test_query_planner_rejects_sql_injection():
    malicious_queries = [
        "SELECT * FROM users;",
        "Which project took time? DROP TABLE tasks; --",
        "UNION SELECT password_hash FROM users",
        "Show my goals; DELETE FROM goals WHERE 1=1;",
        "ALTER TABLE tasks ADD COLUMN hacked TEXT;",
        "INSERT INTO user_profiles VALUES ('test')",
    ]

    for mal in malicious_queries:
        with pytest.raises(ValueError) as exc:
            AnalyticsQueryPlanner.plan_query(mal)
        assert "Security Policy Violation" in str(exc.value)


# ---------------------------------------------------------------------------
# 2. Query Executor & Canonical Scenarios Tests
# ---------------------------------------------------------------------------

def test_query_executor_canonical_scenarios(db: Session, populated_user_a):
    user_a = populated_user_a

    # 1. Time Allocation
    plan1 = AnalyticsQueryPlanner.plan_query("Which project consumed most of my productive time?")
    res1 = AnalyticsQueryExecutor.execute(db=db, user_id=user_a.id, plan=plan1)
    viz1 = VisualAnalyticsGenerator.generate(plan=plan1, result=res1)
    assert "productive time" in res1.summary_answer.lower()
    assert len(res1.supporting_records) > 0
    assert "total_hours" in res1.calculation_details
    assert viz1.chart_type == ChartType.BAR

    # 2. Blocked Tasks
    plan2 = AnalyticsQueryPlanner.plan_query("Which goal has the greatest number of blocked tasks?")
    res2 = AnalyticsQueryExecutor.execute(db=db, user_id=user_a.id, plan=plan2)
    viz2 = VisualAnalyticsGenerator.generate(plan=plan2, result=res2)
    assert "Launch MVP Beta" in res2.summary_answer
    assert len(res2.supporting_records) > 0
    assert res2.calculation_details["top_goal_blocked_count"] >= 1
    assert viz2.chart_type == ChartType.BAR

    # 3. Delay Risk
    plan3 = AnalyticsQueryPlanner.plan_query("Which project has the highest delay risk?")
    res3 = AnalyticsQueryExecutor.execute(db=db, user_id=user_a.id, plan=plan3)
    viz3 = VisualAnalyticsGenerator.generate(plan=plan3, result=res3)
    assert "Infrastructure Scalability" in res3.summary_answer
    assert res3.supporting_records[0]["delay_risk_score"] == 0.75
    assert viz3.chart_type == ChartType.BAR

    # 4. Postponed Tasks
    plan4 = AnalyticsQueryPlanner.plan_query("What types of tasks do I postpone most often?")
    res4 = AnalyticsQueryExecutor.execute(db=db, user_id=user_a.id, plan=plan4)
    viz4 = VisualAnalyticsGenerator.generate(plan=plan4, result=res4)
    assert "postpone" in res4.summary_answer.lower()
    assert len(res4.supporting_records) > 0
    assert viz4.chart_type == ChartType.PIE

    # 5. Recovery Duration
    plan5 = AnalyticsQueryPlanner.plan_query("How has my recovery duration changed?")
    res5 = AnalyticsQueryExecutor.execute(db=db, user_id=user_a.id, plan=plan5)
    viz5 = VisualAnalyticsGenerator.generate(plan=plan5, result=res5)
    assert "recovery duration" in res5.summary_answer.lower()
    assert len(res5.supporting_records) > 0
    assert viz5.chart_type == ChartType.LINE

    # 6. Intervention Evidence
    plan6 = AnalyticsQueryPlanner.plan_query("Which interventions have the strongest historical evidence?")
    res6 = AnalyticsQueryExecutor.execute(db=db, user_id=user_a.id, plan=plan6)
    assert "historical evidence" in res6.summary_answer.lower()
    assert len(res6.supporting_records) > 0

    # 7. Deadline Conflicts
    plan7 = AnalyticsQueryPlanner.plan_query("Which upcoming deadlines conflict with my current priorities?")
    res7 = AnalyticsQueryExecutor.execute(db=db, user_id=user_a.id, plan=plan7)
    viz7 = VisualAnalyticsGenerator.generate(plan=plan7, result=res7)
    assert "deadline" in res7.summary_answer.lower()
    assert len(res7.supporting_records) > 0
    assert viz7.chart_type in [ChartType.TABLE, ChartType.TIMELINE]


def test_query_executor_empty_dataset(db: Session, mock_users):
    _, user_b = mock_users

    plan = AnalyticsQueryPlanner.plan_query("Which project consumed most of my productive time?")
    res = AnalyticsQueryExecutor.execute(db=db, user_id=user_b.id, plan=plan)

    assert "0 projects" in res.summary_answer or "No active projects" in res.limitations[0]
    assert len(res.supporting_records) == 0
    assert any("No active" in lim or "No tracked" in lim for lim in res.limitations)


def test_cross_user_isolation(db: Session, populated_user_a, mock_users):
    user_a = populated_user_a
    _, user_b = mock_users

    plan = AnalyticsQueryPlanner.plan_query("Which project has the highest delay risk?")

    # User A gets Infrastructure Scalability
    res_a = AnalyticsQueryExecutor.execute(db=db, user_id=user_a.id, plan=plan)
    assert len(res_a.supporting_records) == 2

    # User B has no records
    res_b = AnalyticsQueryExecutor.execute(db=db, user_id=user_b.id, plan=plan)
    assert len(res_b.supporting_records) == 0
    assert "0 projects" in res_b.summary_answer


# ---------------------------------------------------------------------------
# 3. Decision Support & Service Tests
# ---------------------------------------------------------------------------

def test_natural_language_analytics_service(db: Session, populated_user_a):
    user_a = populated_user_a

    req = AnalyticsQueryRequest(
        query="Which project has the highest delay risk?",
        lookback_days=30,
    )
    resp = NaturalLanguageAnalyticsService.execute_query(db=db, user_id=user_a.id, request=req)

    assert resp.summary_answer != ""
    assert resp.plan.target_domain == AnalyticsDomain.PROJECT_DELAY_RISK
    assert len(resp.suggested_decisions) > 0
    assert resp.suggested_decisions[0].target_title == "Infrastructure Scalability"
    assert resp.suggested_decisions[0].score > 0.0
    assert "ContextIQ natural-language analytics are computed deterministically" in resp.epistemic_disclaimer


def test_saved_queries_crud(db: Session, populated_user_a):
    user_a = populated_user_a

    # 1. Create
    saved = NaturalLanguageAnalyticsService.save_query(
        db=db,
        user_id=user_a.id,
        payload=SavedAnalyticsQueryCreate(
            title="My Saved Delay Risk Query",
            query_text="Which project has the highest delay risk?",
            target_domain=AnalyticsDomain.PROJECT_DELAY_RISK.value,
        ),
    )
    assert saved.title == "My Saved Delay Risk Query"

    # 2. List
    all_saved = NaturalLanguageAnalyticsService.list_saved_queries(db=db, user_id=user_a.id)
    assert len(all_saved) == 1
    assert all_saved[0].id == saved.id

    # 3. Get
    fetched = NaturalLanguageAnalyticsService.get_saved_query(db=db, user_id=user_a.id, query_id=saved.id)
    assert fetched is not None
    assert fetched.id == saved.id

    # 4. Delete
    deleted = NaturalLanguageAnalyticsService.delete_saved_query(db=db, user_id=user_a.id, query_id=saved.id)
    assert deleted is True

    # 5. Verify deleted
    all_saved_after = NaturalLanguageAnalyticsService.list_saved_queries(db=db, user_id=user_a.id)
    assert len(all_saved_after) == 0


# ---------------------------------------------------------------------------
# 4. API Endpoints Tests
# ---------------------------------------------------------------------------

def test_api_analytics_workspace(db: Session, populated_user_a):
    user_a = populated_user_a

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user_id] = lambda: user_a.id

    client = TestClient(app)

    # 1. POST /query
    q_res = client.post(
        "/api/v1/analytics-workspace/query",
        json={"query": "Which project consumed most of my productive time?", "lookback_days": 30},
    )
    assert q_res.status_code == 200
    q_json = q_res.json()
    assert "Infrastructure Scalability" in q_json["summary_answer"]
    assert q_json["plan"]["target_domain"] == "PROJECT_TIME_ALLOCATION"

    # 2. GET /suggestions
    sug_res = client.get("/api/v1/analytics-workspace/suggestions")
    assert sug_res.status_code == 200
    sug_json = sug_res.json()
    assert len(sug_json) >= 7

    # 3. POST /saved
    save_res = client.post(
        "/api/v1/analytics-workspace/saved",
        json={
            "title": "Time Allocation Analysis",
            "query_text": "Which project consumed most of my productive time?",
            "target_domain": "PROJECT_TIME_ALLOCATION",
        },
    )
    assert save_res.status_code == 201
    saved_obj = save_res.json()
    saved_id = saved_obj["id"]

    # 4. GET /saved
    list_res = client.get("/api/v1/analytics-workspace/saved")
    assert list_res.status_code == 200
    assert len(list_res.json()["queries"]) >= 1

    # 5. GET /export (json)
    exp_json = client.get(
        "/api/v1/analytics-workspace/export?query=Which+project+consumed+most+of+my+productive+time%3F&format=json"
    )
    assert exp_json.status_code == 200
    assert exp_json.headers["content-type"] == "application/json"

    # 6. GET /export (csv)
    exp_csv = client.get(
        "/api/v1/analytics-workspace/export?query=Which+project+consumed+most+of+my+productive+time%3F&format=csv"
    )
    assert exp_csv.status_code == 200
    assert "text/csv" in exp_csv.headers["content-type"]
    assert "project_title" in exp_csv.text

    # 7. DELETE /saved/{id}
    del_res = client.delete(f"/api/v1/analytics-workspace/saved/{saved_id}")
    assert del_res.status_code == 200

    app.dependency_overrides.clear()


"""
Test suite for ContextIQ Phase 8.6: Intelligent Project Progress Forecasting.

Verifies:
1. Leakage-safe feature extraction preventing temporal lookahead.
2. Multi-model forecasting with probabilistic uncertainty bounds (P10, P50, P90).
3. Major delay contributors and explainable remediation attribution.
4. Milestone-level progress and deadline breach forecasting.
5. What-if counterfactual scenario simulation (interventions, focus hours, blocker resolution).
6. Data sufficiency evaluation and explicit low-data heuristic fallback.
7. Model benchmarking metrics (MAE, RMSE, Brier score, coverage).
8. Cross-tenant user isolation and REST API endpoints.
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
from app.core.errors import NotFoundError
from app.db.session import Base, get_db
from app.main import app
from app.models.context_session import ContextSession
from app.models.enums import TaskEventType, TaskPriority, TaskStatus
from app.models.goal_project import GoalTaskAssociation
from app.models.knowledge_graph import Milestone, Project
from app.models.project_forecast import (
    DataSufficiencyStatus,
    DelayRiskTier,
    ForecastingModelType,
    ProjectForecast,
)
from app.models.task import Task
from app.models.task_dependency import TaskDependency, TaskDependencyType
from app.models.task_event import TaskEvent
from app.models.user import User
from app.schemas.project_forecast import (
    ForecastScenarioRequest,
    ProjectForecastGenerateRequest,
)
from app.services.project_forecast_service import ProjectForecastService


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
        email=f"forecaster_{uuid.uuid4().hex[:8]}@contextiq.io",
        display_name="Forecaster User",
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

def test_leakage_safe_feature_extraction(db_session: Session, test_user: User):
    """
    Verifies that feature extraction at cutoff strictly ignores future events,
    ensuring no temporal data leakage.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=7)

    project = Project(
        id=uuid.uuid4(),
        user_id=test_user.id,
        title="Predictive Release",
        target_completion_date=now + timedelta(days=20),
    )
    db_session.add(project)
    db_session.flush()

    # Task 1: Completed before cutoff
    t1 = Task(
        id=uuid.uuid4(),
        user_id=test_user.id,
        title="Pre-cutoff deliverable",
        status=TaskStatus.COMPLETED,
        created_at=cutoff - timedelta(days=5),
        completed_at=cutoff - timedelta(days=2),
    )
    # Task 2: Completed AFTER cutoff (should be treated as remaining at cutoff!)
    t2 = Task(
        id=uuid.uuid4(),
        user_id=test_user.id,
        title="Post-cutoff deliverable",
        status=TaskStatus.COMPLETED,
        created_at=cutoff - timedelta(days=3),
        completed_at=cutoff + timedelta(days=2),
    )
    # Task 3: Uncompleted
    t3 = Task(
        id=uuid.uuid4(),
        user_id=test_user.id,
        title="Still pending",
        status=TaskStatus.PENDING,
        created_at=cutoff - timedelta(days=1),
    )
    db_session.add_all([t1, t2, t3])
    db_session.flush()

    # Associate tasks with project
    for t in [t1, t2, t3]:
        db_session.add(GoalTaskAssociation(user_id=test_user.id, task_id=t.id, project_id=project.id))
    db_session.flush()

    features = ProjectForecastService.extract_features_at_cutoff(
        db_session, test_user.id, project.id, cutoff
    )

    # Exactly 1 completed at cutoff (t1), and 2 remaining (t2 and t3)
    assert features["completed_tasks"] == 1
    assert features["remaining_tasks"] == 2


def test_probabilistic_forecasting_and_uncertainty_bounds(db_session: Session, test_user: User):
    """
    Verifies generation of P10, P50, and P90 completion estimates and calibrated on-time probability.
    """
    now = datetime.now(timezone.utc)
    project = Project(
        id=uuid.uuid4(),
        user_id=test_user.id,
        title="ContextIQ Machine Learning Engine",
        target_completion_date=now + timedelta(days=18),
    )
    milestone = Milestone(
        id=uuid.uuid4(),
        user_id=test_user.id,
        project_id=project.id,
        title="Model Validation",
        due_date=now + timedelta(days=10),
        is_completed=False,
    )
    db_session.add_all([project, milestone])
    db_session.flush()

    # Create 5 completed tasks and 3 pending tasks
    for i in range(5):
        t = Task(
            id=uuid.uuid4(),
            user_id=test_user.id,
            title=f"Historical Task {i}",
            status=TaskStatus.COMPLETED,
            completed_at=now - timedelta(days=i + 1),
            estimated_minutes=60,
        )
        db_session.add(t)
        db_session.flush()
        db_session.add(GoalTaskAssociation(user_id=test_user.id, task_id=t.id, project_id=project.id))

    for i in range(3):
        t = Task(
            id=uuid.uuid4(),
            user_id=test_user.id,
            title=f"Upcoming Task {i}",
            status=TaskStatus.PENDING,
            due_at=now + timedelta(days=i + 3),
            estimated_minutes=90,
            priority=TaskPriority.HIGH if i == 0 else TaskPriority.MEDIUM,
        )
        db_session.add(t)
        db_session.flush()
        db_session.add(GoalTaskAssociation(user_id=test_user.id, task_id=t.id, project_id=project.id))

    # Add focus sessions
    for i in range(4):
        db_session.add(
            ContextSession(
                user_id=test_user.id,
                started_at=now - timedelta(days=i * 3, hours=2),
                ended_at=now - timedelta(days=i * 3),
                focused_time_seconds=7200.0,
                created_at=now - timedelta(days=i * 3),
            )
        )
    db_session.flush()

    forecast = ProjectForecastService.generate_project_forecast(
        db_session,
        test_user.id,
        ProjectForecastGenerateRequest(project_id=project.id),
    )

    assert forecast.id is not None
    assert forecast.p10_completion_date is not None
    assert forecast.estimated_completion_date is not None
    assert forecast.p90_completion_date is not None

    # Uncertainty order: P10 <= P50 <= P90
    assert forecast.p10_completion_date <= forecast.estimated_completion_date
    assert forecast.estimated_completion_date <= forecast.p90_completion_date
    assert forecast.uncertainty_spread_days > 0.0

    # On-time probability bounds
    assert 0.0 <= forecast.on_time_probability <= 1.0
    assert forecast.delay_risk_tier in (t.value for t in DelayRiskTier)
    assert forecast.data_sufficiency == DataSufficiencyStatus.DATA_SUFFICIENT.value

    # Milestone predictions
    assert len(forecast.milestone_forecasts) >= 1
    m_pred = forecast.milestone_forecasts[0]
    assert m_pred["title"] == "Model Validation"
    assert "on_time_probability" in m_pred


def test_delay_contributors_attribution_and_remediation(db_session: Session, test_user: User):
    """
    Verifies that blockers, velocity deficits, and overdue tasks trigger explainable delay contributors.
    """
    now = datetime.now(timezone.utc)
    project = Project(
        id=uuid.uuid4(),
        user_id=test_user.id,
        title="Bottlenecked Project",
        target_completion_date=now + timedelta(days=5),  # Tight deadline
    )
    db_session.add(project)
    db_session.flush()

    t_blocker = Task(id=uuid.uuid4(), user_id=test_user.id, title="Prerequisite API", status=TaskStatus.PENDING)
    t_target = Task(
        id=uuid.uuid4(),
        user_id=test_user.id,
        title="Client UI",
        status=TaskStatus.PENDING,
        due_at=now - timedelta(hours=12),  # Overdue
    )
    db_session.add_all([t_blocker, t_target])
    db_session.flush()

    db_session.add(GoalTaskAssociation(user_id=test_user.id, task_id=t_target.id, project_id=project.id))

    # Add active blocker dependency
    db_session.add(
        TaskDependency(
            user_id=test_user.id,
            source_task_id=t_blocker.id,
            target_task_id=t_target.id,
            dependency_type=TaskDependencyType.POTENTIAL_BLOCKER.value,
            validation_status="CONFIRMED",
            confidence=0.95,
        )
    )
    db_session.flush()

    forecast = ProjectForecastService.generate_project_forecast(
        db_session,
        test_user.id,
        ProjectForecastGenerateRequest(project_id=project.id),
    )

    factors = {c["factor"] for c in forecast.major_delay_contributors}
    assert "UNRESOLVED_BLOCKERS" in factors
    assert "OVERDUE_TASK_ACCUMULATION" in factors
    for c in forecast.major_delay_contributors:
        assert len(c["remediation_suggestion"]) > 5


def test_what_if_counterfactual_scenario_simulation(db_session: Session, test_user: User):
    """
    Verifies what-if scenario simulations evaluate counterfactual parameter adjustments:
    adding focus hours, resolving blockers, and extending deadlines.
    """
    now = datetime.now(timezone.utc)
    project = Project(
        id=uuid.uuid4(),
        user_id=test_user.id,
        title="Flagship Initiative",
        target_completion_date=now + timedelta(days=8),
    )
    db_session.add(project)
    db_session.flush()

    for i in range(4):
        t = Task(
            id=uuid.uuid4(),
            user_id=test_user.id,
            title=f"Task {i}",
            status=TaskStatus.PENDING,
            estimated_minutes=120,
        )
        db_session.add(t)
        db_session.flush()
        db_session.add(GoalTaskAssociation(user_id=test_user.id, task_id=t.id, project_id=project.id))

    db_session.flush()

    # Run scenario: +6 focus hours/week, resolve blockers, +5 day deadline extension
    scenario_res = ProjectForecastService.run_scenario_simulation(
        db_session,
        test_user.id,
        ForecastScenarioRequest(
            project_id=project.id,
            additional_focus_hours_per_week=6.0,
            resolve_blockers=True,
            deadline_extension_days=5.0,
            prioritize_overdue_tasks=True,
        ),
    )

    assert scenario_res.project_id == project.id
    assert scenario_res.scenario_on_time_probability >= scenario_res.baseline_on_time_probability
    assert scenario_res.probability_lift >= 0.0
    assert scenario_res.days_saved >= 0.0
    assert len(scenario_res.recommended_interventions) >= 2


def test_insufficient_data_explicit_fallback(db_session: Session, test_user: User):
    """
    Verifies that projects with little or no historical evidence fall back cleanly
    to heuristic priors with wide uncertainty spreads rather than claiming false precision.
    """
    now = datetime.now(timezone.utc)
    project = Project(
        id=uuid.uuid4(),
        user_id=test_user.id,
        title="Brand New Empty Project",
        target_completion_date=now + timedelta(days=14),
    )
    db_session.add(project)
    db_session.flush()

    forecast = ProjectForecastService.generate_project_forecast(
        db_session,
        test_user.id,
        ProjectForecastGenerateRequest(project_id=project.id),
    )

    assert forecast.data_sufficiency == DataSufficiencyStatus.INSUFFICIENT_DATA.value
    # Uncertainty spread is wide due to insufficiency penalty
    assert forecast.uncertainty_spread_days > 0.0


def test_model_benchmarking_evaluation(db_session: Session, test_user: User):
    """Verifies retrieval of multi-model benchmark metrics (MAE, RMSE, Brier score, coverage)."""
    benchmarks = ProjectForecastService.benchmark_models(db_session, test_user.id)

    assert len(benchmarks.models_evaluated) == 4
    assert ForecastingModelType.ENSEMBLE_FORECASTER.value in benchmarks.models_evaluated
    assert benchmarks.recommended_model == ForecastingModelType.ENSEMBLE_FORECASTER.value
    assert benchmarks.interval_coverage_p10_p90[ForecastingModelType.ENSEMBLE_FORECASTER.value] >= 0.80
    assert "7_days" in benchmarks.horizon_performance


def test_cross_tenant_forecasting_isolation(db_session: Session, test_user: User, other_user: User):
    """Ensures users cannot view or simulate forecasts for projects owned by other users."""
    proj_other = Project(id=uuid.uuid4(), user_id=other_user.id, title="Confidential Project")
    db_session.add(proj_other)
    db_session.flush()

    with pytest.raises(NotFoundError):
        ProjectForecastService.get_forecast_dashboard(db_session, test_user.id, proj_other.id)

    with pytest.raises(NotFoundError):
        ProjectForecastService.generate_project_forecast(
            db_session, test_user.id, ProjectForecastGenerateRequest(project_id=proj_other.id)
        )


def test_rest_api_forecast_endpoints(auth_client: TestClient, db_session: Session, test_user: User):
    """End-to-end test of the forecasting REST API endpoints."""
    now = datetime.now(timezone.utc)
    project = Project(
        id=uuid.uuid4(),
        user_id=test_user.id,
        title="REST Forecast Verification",
        target_completion_date=now + timedelta(days=12),
    )
    db_session.add(project)
    db_session.flush()

    # 1. Generate forecast
    gen_res = auth_client.post(
        f"/api/v1/forecasts/projects/{project.id}/generate",
        json={"project_id": str(project.id), "model_type": "ENSEMBLE_FORECASTER"},
    )
    assert gen_res.status_code == 201
    assert "on_time_probability" in gen_res.json()
    assert "uncertainty_spread_days" in gen_res.json()

    # 2. Get dashboard
    dash_res = auth_client.get(f"/api/v1/forecasts/projects/{project.id}")
    assert dash_res.status_code == 200
    assert dash_res.json()["project_title"] == "REST Forecast Verification"
    assert "milestone_predictions" in dash_res.json()

    # 3. Run scenario simulation
    scen_res = auth_client.post(
        f"/api/v1/forecasts/projects/{project.id}/scenario",
        json={
            "project_id": str(project.id),
            "additional_focus_hours_per_week": 4.0,
            "deadline_extension_days": 3.0,
        },
    )
    assert scen_res.status_code == 200
    assert "probability_lift" in scen_res.json()
    assert "days_saved" in scen_res.json()

    # 4. Get benchmarks
    bench_res = auth_client.get("/api/v1/forecasts/benchmark")
    assert bench_res.status_code == 200
    assert "mae_days_by_model" in bench_res.json()

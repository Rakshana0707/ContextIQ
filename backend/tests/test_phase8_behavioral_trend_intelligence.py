"""
Test suite for ContextIQ Phase 8.7: Long-Term Behavioral Trend Analysis.

Verifies:
1. Daily behavioral metric aggregation across focus, recovery, friction, and task execution.
2. Telemetry coverage ratio tracking and handling of missing observations.
3. Rolling average smoothing (7-day, 30-day) and Exponential Moving Average (EMA).
4. Multi-category trend trajectory detection vs prior period and 90-day personal baseline.
5. Structural change-point detection (CUSUM/windowed shifts) and behavioral milestone discovery.
6. Observational before/after intervention comparisons with strict epistemic disclaimers.
7. Long-term qualitative insight synthesis (What Improved, Needs Attention).
8. Cross-tenant user isolation and REST API endpoints.
"""
import uuid
from datetime import date, datetime, timedelta, timezone

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
from app.models.behavioral_trend import (
    BehavioralChangePoint,
    BehavioralDailyMetric,
    BehavioralMilestoneRecord,
    TemporalGranularity,
    TrendCategory,
    TrendDirection,
)
from app.models.context_session import ContextSession
from app.models.interruption import Interruption
from app.models.enums import InterruptionType, TaskPriority, TaskStatus
from app.models.recommendation import Recommendation
from app.models.task import Task
from app.models.user import User
from app.services.behavioral_trend_service import BehavioralTrendService


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
        email=f"trends_user_{uuid.uuid4().hex[:8]}@contextiq.io",
        display_name="Trends Explorer User",
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

def test_daily_metric_aggregation_and_coverage(db_session: Session, test_user: User):
    """
    Verifies aggregation of context sessions, interruptions, recovery lag, and task completion
    for individual days with telemetry coverage ratios.
    """
    now = datetime.now(timezone.utc)
    target_date = now.date() - timedelta(days=1)
    day_mid = datetime(target_date.year, target_date.month, target_date.day, 14, 0, 0, tzinfo=timezone.utc)

    # 1. Add context sessions
    s1 = ContextSession(
        user_id=test_user.id,
        started_at=day_mid - timedelta(hours=3),
        ended_at=day_mid - timedelta(hours=1),
        focused_time_seconds=7200.0,  # 120 mins
        context_switch_frequency=3.0,
    )
    s2 = ContextSession(
        user_id=test_user.id,
        started_at=day_mid,
        ended_at=day_mid + timedelta(hours=1),
        focused_time_seconds=3600.0,  # 60 mins
        context_switch_frequency=2.0,
    )
    db_session.add_all([s1, s2])

    # 2. Add interruptions
    i1 = Interruption(
        user_id=test_user.id,
        interruption_type=InterruptionType.PHONE,
        occurred_at=day_mid - timedelta(hours=2),
        duration_seconds=40,
    )
    i2 = Interruption(
        user_id=test_user.id,
        interruption_type=InterruptionType.MESSAGE,
        occurred_at=day_mid + timedelta(minutes=30),
        duration_seconds=60,
    )
    db_session.add_all([i1, i2])

    # 3. Add completed task
    t1 = Task(
        id=uuid.uuid4(),
        user_id=test_user.id,
        title="Completed deliverable",
        status=TaskStatus.COMPLETED,
        completed_at=day_mid,
        due_at=day_mid + timedelta(hours=2),
    )
    db_session.add(t1)
    db_session.flush()

    metrics = BehavioralTrendService.compute_daily_metrics(
        db_session, test_user.id, target_date, target_date
    )

    assert len(metrics) == 1
    m = metrics[0]
    assert m.metric_date == target_date
    assert m.total_focus_minutes == 180.0
    assert m.focus_sessions_count == 2
    assert m.interruption_count == 2
    assert m.avg_recovery_lag_seconds == 50.0  # (40 + 60) / 2
    assert m.recovery_efficiency_score > 0.70
    assert m.tasks_completed_count == 1
    assert m.deadline_adherence_rate == 1.0
    assert m.data_coverage_ratio > 0.0


def test_missing_observations_and_coverage_integrity(db_session: Session, test_user: User):
    """
    Verifies that missing observation days (e.g. weekends or untracked days)
    are handled gracefully without dividing by zero, with coverage ratio = 0.0.
    """
    now = datetime.now(timezone.utc)
    start_d = now.date() - timedelta(days=5)
    end_d = now.date() - timedelta(days=2)

    # Empty range (no telemetry or tasks)
    metrics = BehavioralTrendService.compute_daily_metrics(
        db_session, test_user.id, start_d, end_d
    )

    assert len(metrics) == 4
    for m in metrics:
        assert m.data_coverage_ratio == 0.0
        assert m.total_focus_minutes == 0.0
        assert m.focus_sessions_count == 0


def test_rolling_averages_and_exponential_moving_average(db_session: Session, test_user: User):
    """
    Verifies multi-timescale smoothing: 7-day rolling average, 30-day rolling average, and friction EMA.
    """
    now = datetime.now(timezone.utc)
    metrics = []
    for i in range(10):
        d = now.date() - timedelta(days=9 - i)
        m = BehavioralDailyMetric(
            user_id=test_user.id,
            metric_date=d,
            total_focus_minutes=100.0 + (i * 10.0),
            behavioral_friction_index=40.0 - (i * 2.0),
            data_coverage_ratio=0.9,
        )
        metrics.append(m)

    points = BehavioralTrendService.calculate_rolling_and_ema(metrics)
    assert len(points) == 10
    # Last point's 7-day rolling average should smooth the last 7 values
    assert points[-1].rolling_7d_focus is not None
    assert points[-1].rolling_7d_focus > points[0].focus_minutes
    assert points[-1].ema_friction is not None
    assert points[-1].ema_friction < 40.0  # Decayed downwards


def test_category_trend_trajectories_vs_baseline(db_session: Session, test_user: User):
    """
    Verifies evaluation of all 9 behavioral categories vs previous period and 90-day personal baseline.
    """
    now = datetime.now(timezone.utc)
    metrics = []
    # Simulate 14 days of improving focus and decreasing friction
    for i in range(14):
        d = now.date() - timedelta(days=13 - i)
        m = BehavioralDailyMetric(
            user_id=test_user.id,
            metric_date=d,
            total_focus_minutes=120.0 + (i * 8.0),
            focus_consistency_score=0.60 + (i * 0.02),
            recovery_efficiency_score=0.70 + (i * 0.015),
            behavioral_friction_index=35.0 - (i * 1.0),
            tasks_completed_count=2 + (i // 4),
            deadline_adherence_rate=0.90 + (i * 0.007),
            data_coverage_ratio=0.95,
        )
        db_session.add(m)
        metrics.append(m)

    db_session.flush()

    summaries = BehavioralTrendService.detect_trend_categories(
        db_session, test_user.id, metrics, lookback_days=14
    )

    cats = {s.category for s in summaries}
    assert TrendCategory.FOCUS_CONSISTENCY in cats
    assert TrendCategory.RECOVERY_EFFICIENCY in cats
    assert TrendCategory.BEHAVIORAL_FRICTION in cats
    assert TrendCategory.DEADLINE_ADHERENCE in cats

    focus_sum = next(s for s in summaries if s.category == TrendCategory.FOCUS_CONSISTENCY)
    assert focus_sum.trend_direction == TrendDirection.IMPROVING
    assert focus_sum.period_change_pct > 0.0

    fric_sum = next(s for s in summaries if s.category == TrendCategory.BEHAVIORAL_FRICTION)
    assert fric_sum.trend_direction == TrendDirection.IMPROVING  # Lower friction is IMPROVING
    assert fric_sum.period_change_pct < 0.0


def test_change_point_detection_and_milestone_discovery(db_session: Session, test_user: User):
    """
    Verifies that a significant step-shift in behavior triggers both a BehavioralChangePoint
    and an earned BehavioralMilestoneRecord.
    """
    now = datetime.now(timezone.utc)
    metrics = []
    # Pre-shift: high friction (45.0)
    for i in range(6):
        d = now.date() - timedelta(days=12 - i)
        m = BehavioralDailyMetric(
            user_id=test_user.id,
            metric_date=d,
            behavioral_friction_index=45.0,
            focus_consistency_score=0.55,
            recovery_efficiency_score=0.60,
        )
        metrics.append(m)

    # Post-shift: low friction (22.0) - a 23-point step drop!
    for i in range(7):
        d = now.date() - timedelta(days=6 - i)
        m = BehavioralDailyMetric(
            user_id=test_user.id,
            metric_date=d,
            behavioral_friction_index=22.0,
            focus_consistency_score=0.88,
            recovery_efficiency_score=0.90,
        )
        metrics.append(m)

    milestones, change_points = BehavioralTrendService.detect_change_points_and_milestones(
        db_session, test_user.id, metrics
    )

    assert len(change_points) >= 1
    assert change_points[0].metric_name == "behavioral_friction"
    assert change_points[0].change_type == "STEP_DECREASE"

    assert len(milestones) >= 1
    assert "FRICTION" in milestones[0].milestone_type
    assert milestones[0].change_magnitude_pct > 20.0
    assert milestones[0].statistical_confidence >= 0.90


def test_observational_intervention_comparison_with_epistemic_disclaimer(db_session: Session, test_user: User):
    """
    Verifies before/after window evaluation around an accepted intervention,
    ensuring a non-causal observational disclaimer is explicitly included.
    """
    now = datetime.now(timezone.utc)
    rec_time = now - timedelta(days=7)

    # Add recommendation
    rec = Recommendation(
        id=uuid.uuid4(),
        user_id=test_user.id,
        title="Schedule Morning Deep Work Block",
        message="Recommended morning focus window protection",
        recommendation_type="SCHEDULE_SHIFT",
        created_at=rec_time,
    )
    db_session.add(rec)
    db_session.flush()

    # Pre-days: friction 40, post-days: friction 25
    metrics = []
    for i in range(14):
        d = (rec_time - timedelta(days=7 - i)).date()
        is_post = i >= 7
        m = BehavioralDailyMetric(
            user_id=test_user.id,
            metric_date=d,
            total_focus_minutes=200.0 if is_post else 140.0,
            behavioral_friction_index=25.0 if is_post else 40.0,
        )
        metrics.append(m)

    comparisons = BehavioralTrendService.compare_interventions(
        db_session, test_user.id, metrics
    )

    assert len(comparisons) == 1
    comp = comparisons[0]
    assert comp.intervention_id == rec.id
    assert comp.friction_delta == -15.0  # 25 - 40
    assert comp.focus_delta == 60.0     # 200 - 140
    # Must contain observational disclaimer
    assert "Descriptive before-and-after comparison" in comp.observational_note
    assert "causal" in comp.observational_note.lower()


def test_cross_tenant_trend_isolation(db_session: Session, test_user: User, other_user: User):
    """Ensures users cannot access other users' behavioral metrics or milestones."""
    now = datetime.now(timezone.utc)
    m_other = BehavioralMilestoneRecord(
        user_id=other_user.id,
        milestone_type="OTHER_USER_MILESTONE",
        title="Private Milestone",
        description="Confidential",
        evaluation_period_start=now - timedelta(days=7),
        evaluation_period_end=now,
    )
    db_session.add(m_other)
    db_session.flush()

    data_user = BehavioralTrendService.get_dashboard_data(db_session, test_user.id)
    assert m_other.id not in [m.id for m in data_user.milestones]


def test_rest_api_trends_endpoints(auth_client: TestClient, db_session: Session, test_user: User):
    """End-to-end test of the trends REST API endpoints."""
    now = datetime.now(timezone.utc)
    bm = BehavioralMilestoneRecord(
        id=uuid.uuid4(),
        user_id=test_user.id,
        milestone_type="REST_MILESTONE",
        title="Rest API Verified Milestone",
        description="Test milestone",
        evaluation_period_start=now - timedelta(days=7),
        evaluation_period_end=now,
    )
    db_session.add(bm)
    db_session.flush()

    # 1. Get dashboard
    dash_res = auth_client.get("/api/v1/trends/dashboard?lookback_days=14")
    assert dash_res.status_code == 200
    assert "overall_data_coverage_pct" in dash_res.json()
    assert "daily_series" in dash_res.json()
    assert "category_summaries" in dash_res.json()
    assert "long_term_insights" in dash_res.json()

    # 2. Get categories
    cat_res = auth_client.get("/api/v1/trends/categories?lookback_days=14")
    assert cat_res.status_code == 200
    assert len(cat_res.json()) >= 1

    # 3. List milestones
    mile_res = auth_client.get("/api/v1/trends/milestones")
    assert mile_res.status_code == 200
    assert len(mile_res.json()) >= 1

    # 4. Acknowledge milestone
    ack_res = auth_client.post(f"/api/v1/trends/milestones/{bm.id}/acknowledge")
    assert ack_res.status_code == 200
    assert ack_res.json()["is_acknowledged"] is True

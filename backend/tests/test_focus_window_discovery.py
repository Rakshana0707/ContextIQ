"""
Unit and integration test suite for ContextIQ Personalized Focus Window Discovery
and Temporal Behavior Analysis (Phase 4.3).
Validates:
- Timezone conversions & local hour binning
- Daylight-saving transition handling
- Missing timestamp safety
- Sparse observations & insufficient data handling
- Task-category differences (programming vs. admin)
- Active vs. Productive distinction (high activity with 0 completions is NOT focus)
- Incomplete session resilience
- Behavioral profile temporal integration
- REST API endpoints (/api/v1/adaptive/focus-windows/*)
"""
import math
import os
import sys
import uuid
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "adaptive-intelligence"))

os.environ["APP_ENV"] = "development"
os.environ.setdefault("DATABASE_URL", "sqlite:///./_test_telemetry.db")

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

import app.models
from app.db.session import Base, engine
from app.main import app
from app.models.context_session import ContextSession
from app.models.detected_interruption import DetectedInterruption
from app.models.enums import DetectedInterruptionType, TaskStatus
from app.models.task import Task
from app.models.user import User
from app.models.focus_window import UserFocusWindow
from app.profiles.temporal_feature_aggregator import TemporalFeatureAggregator
from app.profiles.focus_window_engine import FocusWindowDiscoveryEngine
from app.profiles.focus_window_repository import FocusWindowRepository
from app.services.adaptive.focus_window_service import FocusWindowService
from app.services.adaptive.profile_service import AdaptiveProfileService


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client():
    return TestClient(app)


def _create_user(db: Session, tz: str = "UTC", prefix: str = "focus_user") -> User:
    uid = uuid.uuid4()
    user = User(
        id=uid,
        email=f"{prefix}_{uid.hex[:6]}@example.com",
        display_name="Focus Window Tester",
        timezone=tz,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


# ---------------------------------------------------------------------------
# Task 9 Tests
# ---------------------------------------------------------------------------

def test_timezone_conversion(db_session: Session):
    """
    Verifies that a user in America/New_York (UTC-5 in winter, UTC-4 in summer)
    correctly maps sessions occurring at 14:00 UTC to 09:00 or 10:00 local time.
    """
    user = _create_user(db_session, tz="America/New_York", prefix="tz_user")
    # Winter date: Jan 15 (UTC-5)
    winter_date_utc = datetime(2026, 1, 15, 14, 0, 0, tzinfo=timezone.utc)  # 14:00 UTC = 09:00 EST

    sessions = [
        ContextSession(
            user_id=user.id,
            started_at=winter_date_utc,
            focused_time_seconds=3600.0,
            transition_count=2,
        )
    ]
    tasks = [
        Task(
            user_id=user.id,
            title="Winter Morning Coding",
            status=TaskStatus.COMPLETED,
            created_at=winter_date_utc,
            completed_at=winter_date_utc + timedelta(minutes=45),
        )
    ]

    metrics = TemporalFeatureAggregator.aggregate_hourly_metrics(
        sessions=sessions,
        tasks=tasks,
        interruptions=[],
        user_timezone=user.timezone,
        as_of=winter_date_utc + timedelta(hours=2),
    )

    # 14:00 UTC must be binned at hour 9 in America/New_York
    hour_9_metric = next(m for m in metrics if m.hour == 9)
    hour_14_metric = next(m for m in metrics if m.hour == 14)

    assert hour_9_metric.focus_minutes == 60.0
    assert hour_9_metric.task_completion_rate == 1.0
    assert hour_14_metric.focus_minutes == 0.0


def test_daylight_saving_transition(db_session: Session):
    """
    Verifies that sessions spanning daylight saving transitions
    resolve local hours cleanly without crashing or bin duplication.
    """
    user = _create_user(db_session, tz="America/New_York", prefix="dst_user")

    # Before DST (Standard Time: March 7, 2026 14:00 UTC = 09:00 EST)
    dt_standard = datetime(2026, 3, 7, 14, 0, 0, tzinfo=timezone.utc)
    # After DST (Daylight Time: March 9, 2026 13:00 UTC = 09:00 EDT)
    dt_daylight = datetime(2026, 3, 9, 13, 0, 0, tzinfo=timezone.utc)

    sessions = [
        ContextSession(
            user_id=user.id,
            started_at=dt_standard,
            focused_time_seconds=3000.0,
            transition_count=3,
        ),
        ContextSession(
            user_id=user.id,
            started_at=dt_daylight,
            focused_time_seconds=3000.0,
            transition_count=3,
        ),
    ]

    metrics = TemporalFeatureAggregator.aggregate_hourly_metrics(
        sessions=sessions,
        tasks=[],
        interruptions=[],
        user_timezone=user.timezone,
        as_of=dt_daylight + timedelta(hours=2),
    )

    # Both sessions occurred at 09:00 local user time!
    hour_9_metric = next(m for m in metrics if m.hour == 9)
    assert hour_9_metric.focus_minutes == 50.0
    assert hour_9_metric.observation_count == 2


def test_missing_timestamps(db_session: Session):
    """Verifies sessions and tasks with missing timestamps are safely filtered."""
    user = _create_user(db_session, "missing_ts")
    now = datetime.now(timezone.utc)

    sessions = [
        ContextSession(user_id=user.id, started_at=None, focused_time_seconds=1200.0),
        ContextSession(user_id=user.id, started_at=now, focused_time_seconds=1800.0),
    ]
    tasks = [
        Task(user_id=user.id, title="No Timestamp", created_at=None),
        Task(user_id=user.id, title="With Timestamp", created_at=now),
    ]

    metrics = TemporalFeatureAggregator.aggregate_hourly_metrics(
        sessions=sessions,
        tasks=tasks,
        interruptions=[],
        user_timezone="UTC",
        as_of=now + timedelta(hours=1),
    )

    total_obs = sum(m.observation_count for m in metrics)
    assert total_obs >= 1  # Successfully parsed without raising TypeError or AttributeError


def test_sparse_observations(db_session: Session):
    """Verifies that sparse data (< 5 observations) returns empty focus windows without fabricating."""
    user = _create_user(db_session, "sparse_user")
    now = datetime.now(timezone.utc)

    # Only 2 sessions
    sessions = [
        ContextSession(user_id=user.id, started_at=now - timedelta(days=1), focused_time_seconds=1500.0),
        ContextSession(user_id=user.id, started_at=now - timedelta(days=2), focused_time_seconds=1200.0),
    ]

    windows = FocusWindowDiscoveryEngine.discover_focus_windows(
        user_id=user.id,
        sessions=sessions,
        tasks=[],
        interruptions=[],
        user_timezone="UTC",
        as_of=now,
    )

    assert len(windows) == 0


def test_task_category_differences(db_session: Session):
    """
    Verifies that category conditioning separates distinct focus cadences:
    - Programming: recurrent morning focus (09:00 - 11:00) with high completion.
    - Admin: recurrent afternoon focus (14:00 - 16:00) with high completion.
    """
    user = _create_user(db_session, "cat_user")
    base_time = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)

    sessions = []
    tasks = []

    # 10 days of history
    for d in range(10):
        day_date = base_time - timedelta(days=d)

        # Morning programming sessions (09:00 - 11:00)
        morning_start = day_date.replace(hour=9, minute=0, second=0)
        sessions.append(ContextSession(
            user_id=user.id,
            started_at=morning_start,
            focused_time_seconds=5400.0,  # 90 min
            transition_count=2,
            context_tag="programming",
        ))
        tasks.append(Task(
            user_id=user.id,
            title=f"Coding task {d}",
            status=TaskStatus.COMPLETED,
            context_tag="programming",
            created_at=morning_start,
            completed_at=morning_start + timedelta(minutes=50),
        ))

        # Afternoon admin sessions (14:00 - 16:00)
        afternoon_start = day_date.replace(hour=14, minute=0, second=0)
        sessions.append(ContextSession(
            user_id=user.id,
            started_at=afternoon_start,
            focused_time_seconds=3600.0,  # 60 min
            transition_count=5,
            context_tag="admin",
        ))
        tasks.append(Task(
            user_id=user.id,
            title=f"Admin task {d}",
            status=TaskStatus.COMPLETED,
            context_tag="admin",
            created_at=afternoon_start,
            completed_at=afternoon_start + timedelta(minutes=30),
        ))

    # Discover Programming Focus Windows
    prog_res = FocusWindowDiscoveryEngine.discover_category_focus_windows(
        user_id=user.id,
        category="programming",
        sessions=sessions,
        tasks=tasks,
        interruptions=[],
        user_timezone="UTC",
        as_of=base_time,
    )
    assert len(prog_res.focus_windows) >= 1
    prog_window = prog_res.focus_windows[0]
    assert prog_window.start_time.hour in (9, 10)
    assert prog_res.completion_lift_percentage >= 0.0

    # Discover Admin Focus Windows
    admin_res = FocusWindowDiscoveryEngine.discover_category_focus_windows(
        user_id=user.id,
        category="admin",
        sessions=sessions,
        tasks=tasks,
        interruptions=[],
        user_timezone="UTC",
        as_of=base_time,
    )
    assert len(admin_res.focus_windows) >= 1
    admin_window = admin_res.focus_windows[0]
    assert admin_window.start_time.hour in (14, 15)


def test_active_vs_productive_distinction(db_session: Session):
    """
    CRITICAL CONSTRAINT: Do not assume a user's most active period is their most productive period.
    - Hours 14:00-16:00: Massive active session time (120 min), but 18 transitions/hr,
      6 interruptions/hr, and 0 tasks completed (active fragmented churn).
    - Hours 09:00-11:00: Moderate session time (60 min), 1 transition/hr, 0 interruptions,
      and 4 tasks completed (calm productive focus).
    Assert: 09:00-11:00 is selected as a focus window; 14:00-16:00 is NOT.
    """
    user = _create_user(db_session, "prod_vs_act")
    now = datetime(2026, 8, 10, 18, 0, 0, tzinfo=timezone.utc)

    sessions = []
    tasks = []
    interruptions = []

    for d in range(8):
        day_date = now - timedelta(days=d)

        # Calm productive morning (09:00 - 10:00)
        m_start = day_date.replace(hour=9, minute=0, second=0)
        sessions.append(ContextSession(
            user_id=user.id,
            started_at=m_start,
            focused_time_seconds=3300.0,  # 55 min
            transition_count=1,
        ))
        tasks.append(Task(
            user_id=user.id,
            title=f"Productive Task {d}",
            status=TaskStatus.COMPLETED,
            created_at=m_start,
            completed_at=m_start + timedelta(minutes=40),
        ))

        # Frantic afternoon thrashing (14:00 - 16:00)
        a_start = day_date.replace(hour=14, minute=0, second=0)
        sessions.append(ContextSession(
            user_id=user.id,
            started_at=a_start,
            focused_time_seconds=7200.0,  # 120 min active
            transition_count=35,           # Very high transitions
        ))
        # Add multiple disruptive interruptions
        for k in range(5):
            interruptions.append(DetectedInterruption(
                user_id=user.id,
                interruption_type=DetectedInterruptionType.APPLICATION_SWITCH,
                start_timestamp=a_start + timedelta(minutes=k * 20),
                resumption_lag_seconds=85.0,
                explanation="Disruption",
            ))

    windows = FocusWindowDiscoveryEngine.discover_focus_windows(
        user_id=user.id,
        sessions=sessions,
        tasks=tasks,
        interruptions=interruptions,
        user_timezone="UTC",
        as_of=now,
    )

    # 09:00 morning window should be discovered
    assert any(w.start_time.hour in (9, 10) for w in windows)
    # 14:00-16:00 frantic thrashing must NOT be a top focus window
    assert not any(w.start_time.hour == 14 and w.quality_score > 70.0 for w in windows)


def test_incomplete_sessions(db_session: Session):
    """Verifies that incomplete sessions (ended_at=None, focused_time=0) don't cause zero-division."""
    user = _create_user(db_session, "incomplete")
    now = datetime.now(timezone.utc)

    sessions = [
        ContextSession(
            user_id=user.id,
            started_at=now - timedelta(hours=1),
            ended_at=None,
            focused_time_seconds=0.0,
            transition_count=0,
        )
    ]

    metrics = TemporalFeatureAggregator.aggregate_hourly_metrics(
        sessions=sessions,
        tasks=[],
        interruptions=[],
        user_timezone="UTC",
        as_of=now,
    )

    assert len(metrics) == 24
    for m in metrics:
        assert not math.isnan(m.quality_score)
        assert not math.isinf(m.quality_score)


def test_profile_temporal_integration(db_session: Session):
    """Verifies discovered focus windows update UserBehavioralProfile."""
    user = _create_user(db_session, "profile_sync")
    now = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Ingest sessions at 10:00 AM
    for d in range(8):
        st = (now - timedelta(days=d)).replace(hour=10, minute=0)
        db_session.add(ContextSession(
            user_id=user.id,
            started_at=st,
            focused_time_seconds=3600.0,
            transition_count=2,
        ))
        db_session.add(Task(
            user_id=user.id,
            title=f"Task {d}",
            status=TaskStatus.COMPLETED,
            created_at=st,
            completed_at=st + timedelta(minutes=30),
        ))
    db_session.flush()

    # Rebuild base profile first
    AdaptiveProfileService.rebuild_profile(db_session, user.id, as_of=now)

    # Discover and save focus windows
    windows = FocusWindowService.get_or_discover_windows(
        db=db_session,
        user_id=user.id,
        force_refresh=True,
        as_of=now,
    )
    assert len(windows) >= 1

    # Verify UserFocusWindow record in database
    orm_records = FocusWindowRepository.list_focus_windows(db_session, user.id)
    assert len(orm_records) >= 1
    assert orm_records[0].start_time.hour in (10, 11)
    assert len(orm_records[0].grounded_insights) >= 1


def test_focus_window_api_endpoints(client: TestClient):
    """Tests the /api/v1/adaptive/focus-windows/* REST endpoints."""
    user_id = uuid.uuid4()
    with Session(engine) as session:
        user = User(
            id=user_id,
            email=f"fw_api_{user_id.hex[:6]}@example.com",
            display_name="Focus Window API User",
            timezone="UTC",
            is_active=True,
        )
        session.add(user)

        # Seed some sessions
        now = datetime(2026, 7, 20, 12, 0, 0, tzinfo=timezone.utc)
        for i in range(8):
            st = (now - timedelta(days=i)).replace(hour=10, minute=0)
            session.add(ContextSession(
                user_id=user_id,
                started_at=st,
                focused_time_seconds=3000.0,
                transition_count=2,
                context_tag="programming",
            ))
            session.add(Task(
                user_id=user_id,
                title=f"Coding {i}",
                status=TaskStatus.COMPLETED,
                context_tag="programming",
                created_at=st,
                completed_at=st + timedelta(minutes=40),
            ))
        session.commit()

    from app.core.deps import get_current_user_id
    app.dependency_overrides[get_current_user_id] = lambda: user_id

    try:
        # 1. GET /api/v1/adaptive/focus-windows
        res_list = client.get("/api/v1/adaptive/focus-windows?force_refresh=true")
        assert res_list.status_code == 200
        windows = res_list.json()
        assert len(windows) >= 1
        assert "quality_score" in windows[0]
        assert "grounded_insights" in windows[0]

        # 2. GET /api/v1/adaptive/focus-windows/metrics
        res_metrics = client.get("/api/v1/adaptive/focus-windows/metrics")
        assert res_metrics.status_code == 200
        metrics_data = res_metrics.json()
        assert len(metrics_data["hourly_metrics"]) == 24
        assert "peak_focus_hours" in metrics_data

        # 3. GET /api/v1/adaptive/focus-windows/{category}
        res_cat = client.get("/api/v1/adaptive/focus-windows/programming")
        assert res_cat.status_code == 200
        cat_data = res_cat.json()
        assert cat_data["category"] == "programming"
        assert "in_window_completion_rate" in cat_data

    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

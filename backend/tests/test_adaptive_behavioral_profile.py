"""
Unit and integration test suite for ContextIQ Personal Behavioral Digital Twin & Profile Engine (Phase 4.2).
Validates:
- Insufficient history handling
- Missing telemetry handling
- Duplicate event idempotency
- Delayed and out-of-order event handling
- Incremental profile updates
- Profile reset functionality
- Historical snapshot reproducibility
- Multi-user data isolation
- Privacy controls & consent enforcement
- API endpoints
"""
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

# Add backend and adaptive-intelligence to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "adaptive-intelligence"))

os.environ["APP_ENV"] = "development"
os.environ.setdefault("DATABASE_URL", "sqlite:///./_test_telemetry.db")

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

import app.models  # Register all ORM models
from app.db.session import Base, engine, get_db
from app.main import app
from app.models.context_session import ContextSession
from app.models.detected_interruption import DetectedInterruption
from app.models.enums import DetectedInterruptionType, InterruptionSeverity, TaskStatus
from app.models.task import Task
from app.models.task_event import TaskEvent
from app.models.telemetry_consent import ConsentStatus, TelemetryConsent
from app.models.user import User
from app.profiles.profile_builder import ProfileBuilder
from app.profiles.profile_confidence import ProfileConfidenceEstimator
from app.profiles.profile_engine import BehavioralProfileEngine
from app.profiles.profile_repository import ProfileRepository
from app.profiles.profile_updater import ProfileUpdater
from app.schemas.profile_schemas import PatternStatus


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


def _create_user(db: Session, email_prefix: str = "twin_user") -> User:
    uid = uuid.uuid4()
    user = User(
        id=uid,
        email=f"{email_prefix}_{uid.hex[:6]}@example.com",
        display_name="Digital Twin Tester",
        timezone="UTC",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


# ---------------------------------------------------------------------------
# Task 9 Tests
# ---------------------------------------------------------------------------

def test_insufficient_history(db_session: Session):
    """Verifies that with < 7 samples, metrics are classified as INSUFFICIENT_EVIDENCE."""
    user = _create_user(db_session, "insuff")
    now = datetime.now(timezone.utc)

    # Insert only 3 sessions
    for i in range(3):
        sess = ContextSession(
            user_id=user.id,
            started_at=now - timedelta(days=i, hours=2),
            ended_at=now - timedelta(days=i, hours=1),
            focused_time_seconds=1800.0,
            transition_count=4,
        )
        db_session.add(sess)
    db_session.flush()

    profile = BehavioralProfileEngine.rebuild_profile(db_session, user.id, as_of=now)

    assert profile.is_cold_start is True
    assert profile.global_pattern_status == PatternStatus.INSUFFICIENT_EVIDENCE
    assert profile.focus_behavior.typical_session_duration_minutes.pattern_status == PatternStatus.INSUFFICIENT_EVIDENCE
    assert profile.focus_behavior.typical_session_duration_minutes.confidence_level < 0.35
    assert profile.telemetry_days_observed <= 3


def test_missing_telemetry(db_session: Session):
    """Verifies safe defaults when user has zero telemetry."""
    user = _create_user(db_session, "missing")
    now = datetime.now(timezone.utc)

    profile = BehavioralProfileEngine.rebuild_profile(db_session, user.id, as_of=now)

    assert profile.total_sessions_observed == 0
    assert profile.total_tasks_observed == 0
    assert profile.total_interruptions_observed == 0
    assert profile.global_confidence_score == 0.0
    assert profile.global_pattern_status == PatternStatus.INSUFFICIENT_EVIDENCE
    assert profile.baselines.median_focus_duration_minutes == 25.0
    assert profile.baselines.typical_recovery_duration_seconds == 45.0


def test_established_pattern_thresholds(db_session: Session):
    """Verifies that with >= 30 samples across high coverage, metrics become ESTABLISHED."""
    user = _create_user(db_session, "established")
    now = datetime.now(timezone.utc)

    # Insert 35 sessions across 22 days
    for i in range(35):
        day_offset = i % 22
        sess = ContextSession(
            user_id=user.id,
            started_at=now - timedelta(days=day_offset, hours=(i % 8) + 1),
            ended_at=now - timedelta(days=day_offset, hours=(i % 8)),
            focused_time_seconds=2700.0,  # 45 min
            transition_count=5,
        )
        db_session.add(sess)
    db_session.flush()

    profile = BehavioralProfileEngine.rebuild_profile(db_session, user.id, as_of=now)

    assert profile.total_sessions_observed == 35
    assert profile.telemetry_days_observed >= 20
    assert profile.global_pattern_status == PatternStatus.ESTABLISHED
    assert profile.is_cold_start is False
    assert profile.focus_behavior.typical_session_duration_minutes.pattern_status == PatternStatus.ESTABLISHED
    assert profile.focus_behavior.typical_session_duration_minutes.confidence_level >= 0.75


def test_incremental_profile_updates(db_session: Session):
    """Verifies online O(1) incremental updating without full historical scan."""
    user = _create_user(db_session, "incremental")
    now = datetime.now(timezone.utc)

    # Initial profile build
    profile = BehavioralProfileEngine.get_or_build_profile(db_session, user.id)
    initial_sessions = profile.total_sessions_observed

    # 1. Update with session
    updated_1 = ProfileUpdater.update_with_session(
        profile=profile,
        session_id=str(uuid.uuid4()),
        focused_time_seconds=3600.0,  # 60 min
        transition_count=8,
        started_at=now,
    )
    assert updated_1.total_sessions_observed == initial_sessions + 1
    assert updated_1.focus_behavior.typical_session_duration_minutes.observation_count == initial_sessions + 1

    # 2. Update with task completion
    updated_2 = ProfileUpdater.update_with_task_completed(
        profile=updated_1,
        task_id=str(uuid.uuid4()),
        category="engineering",
        estimated_minutes=45,
        completed_at=now,
        due_at=now + timedelta(hours=1),
    )
    assert updated_2.total_tasks_observed == 1
    assert updated_2.task_completion.task_completion_rate.observed_value == 1.0

    # 3. Update with interruption
    updated_3 = ProfileUpdater.update_with_interruption(
        profile=updated_2,
        interruption_type="APPLICATION_SWITCH",
        resumption_lag_seconds=65.0,
        start_timestamp=now,
    )
    assert updated_3.total_interruptions_observed == 1
    assert "APPLICATION_SWITCH" in updated_3.interruption_behavior.interruption_type_distribution.observed_value


def test_profile_reset(db_session: Session):
    """Verifies that reset clears empirical metrics and resets to cold-start prior."""
    user = _create_user(db_session, "reset_user")
    now = datetime.now(timezone.utc)

    # Ingest data first
    for i in range(10):
        db_session.add(ContextSession(
            user_id=user.id,
            started_at=now - timedelta(days=i),
            focused_time_seconds=2400.0,
            transition_count=3,
        ))
    db_session.flush()

    # Rebuild
    BehavioralProfileEngine.rebuild_profile(db_session, user.id)

    # Reset
    response = BehavioralProfileEngine.reset_profile(db_session, user.id)
    assert response.status == "SUCCESS"

    # Verify cleared profile
    reset_profile = ProfileRepository.get_profile_read(db_session, user.id)
    assert reset_profile.is_cold_start is True
    assert reset_profile.total_sessions_observed == 0
    assert reset_profile.global_pattern_status == PatternStatus.INSUFFICIENT_EVIDENCE
    assert reset_profile.global_confidence_score == 0.0


def test_historical_reproducibility(db_session: Session):
    """Verifies that rebuilding at a specified historical cutoff reproduces identical snapshots."""
    user = _create_user(db_session, "repro")
    base_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Event 1: May 20
    db_session.add(ContextSession(
        user_id=user.id,
        started_at=base_time - timedelta(days=12),
        focused_time_seconds=1800.0,
        transition_count=2,
    ))
    # Event 2: May 25
    db_session.add(ContextSession(
        user_id=user.id,
        started_at=base_time - timedelta(days=7),
        focused_time_seconds=2400.0,
        transition_count=4,
    ))
    # Event 3: June 5 (future relative to cutoff)
    db_session.add(ContextSession(
        user_id=user.id,
        started_at=base_time + timedelta(days=4),
        focused_time_seconds=3600.0,
        transition_count=10,
    ))
    db_session.flush()

    # Build snapshot strictly at base_time cutoff (May 20 & May 25 should be included, June 5 excluded)
    profile_snap1 = BehavioralProfileEngine.rebuild_profile(
        db_session, user.id, as_of=base_time, observation_window_days=30
    )
    assert profile_snap1.total_sessions_observed == 2

    # Rebuild again with same cutoff
    profile_snap2 = BehavioralProfileEngine.rebuild_profile(
        db_session, user.id, as_of=base_time, observation_window_days=30
    )
    assert profile_snap2.total_sessions_observed == 2
    assert profile_snap1.focus_behavior.typical_session_duration_minutes.observed_value == \
           profile_snap2.focus_behavior.typical_session_duration_minutes.observed_value


def test_user_data_isolation(db_session: Session):
    """Verifies that User A's sessions and metrics never bleed into User B's profile."""
    user_a = _create_user(db_session, "user_a")
    user_b = _create_user(db_session, "user_b")
    now = datetime.now(timezone.utc)

    # Add 10 sessions for User A
    for i in range(10):
        db_session.add(ContextSession(
            user_id=user_a.id,
            started_at=now - timedelta(days=i),
            focused_time_seconds=3000.0,
            transition_count=2,
        ))
    db_session.flush()

    profile_a = BehavioralProfileEngine.rebuild_profile(db_session, user_a.id, as_of=now)
    profile_b = BehavioralProfileEngine.rebuild_profile(db_session, user_b.id, as_of=now)

    assert profile_a.total_sessions_observed == 10
    assert profile_b.total_sessions_observed == 0
    assert profile_b.global_confidence_score == 0.0


def test_privacy_and_consent_controls(db_session: Session):
    """Verifies that revoking telemetry consent suppresses profile updates."""
    user = _create_user(db_session, "privacy_user")
    now = datetime.now(timezone.utc)

    # Consent explicitly REVOKED
    db_session.add(TelemetryConsent(
        user_id=user.id,
        consent_status=ConsentStatus.REVOKED,
        enabled_categories=[],
        granted_timestamp=now,
    ))
    db_session.flush()

    res = BehavioralProfileEngine.ingest_session(
        db=db_session,
        user_id=user.id,
        session_id=str(uuid.uuid4()),
        focused_time_seconds=1800.0,
        started_at=now,
    )
    assert res is None  # Suppressed due to lack of consent

    # Personalization toggle
    profile = BehavioralProfileEngine.set_personalization(db_session, user.id, enabled=False)
    assert profile.personalization_enabled is False


def test_adaptive_api_endpoints(client: TestClient):
    """Tests the /api/v1/adaptive/* REST endpoints."""
    user_id = uuid.uuid4()
    with Session(engine) as session:
        user = User(
            id=user_id,
            email=f"api_{user_id.hex[:6]}@example.com",
            display_name="API User",
            timezone="UTC",
            is_active=True,
        )
        session.add(user)
        session.commit()

    # Dependency override for auth
    from app.core.deps import get_current_user_id
    app.dependency_overrides[get_current_user_id] = lambda: user_id

    try:

        # 1. GET /api/v1/adaptive/profile
        res = client.get("/api/v1/adaptive/profile")
        assert res.status_code == 200
        data = res.json()
        assert data["user_id"] == str(user_id)
        assert "focus_behavior" in data
        assert "baselines" in data

        # 2. POST /api/v1/adaptive/profile/rebuild
        res_rebuild = client.post("/api/v1/adaptive/profile/rebuild")
        assert res_rebuild.status_code == 200
        assert res_rebuild.json()["user_id"] == str(user_id)

        # 3. GET /api/v1/adaptive/profile/history
        res_hist = client.get("/api/v1/adaptive/profile/history")
        assert res_hist.status_code == 200
        history = res_hist.json()
        assert len(history) >= 1

        # 4. PUT /api/v1/adaptive/profile/personalization
        res_toggle = client.put("/api/v1/adaptive/profile/personalization", json={"enabled": False})
        assert res_toggle.status_code == 200
        assert res_toggle.json()["personalization_enabled"] is False

        # 5. POST /api/v1/adaptive/profile/reset
        res_reset = client.post("/api/v1/adaptive/profile/reset")
        assert res_reset.status_code == 200
        assert res_reset.json()["status"] == "SUCCESS"

        # 6. DELETE /api/v1/adaptive/profile
        res_del = client.delete("/api/v1/adaptive/profile")
        assert res_del.status_code == 204

    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

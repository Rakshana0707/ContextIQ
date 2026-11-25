"""
Unit and integration test suite for ContextIQ Personalized Intervention Recommendation Engine (Phase 4.5).
Validates:
1. Duplicate recommendations prevention
2. Contradictory recommendations elimination
3. Expired recommendations handling
4. Insufficient evidence guard
5. User dismissal with feedback note
6. Deferred recommendations hiding
7. Personalized ranking adjustment
8. User data isolation
9. REST API endpoints validation
"""
import os
import sys
import uuid
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException
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
from app.models.detected_interruption import DetectedInterruption
from app.models.enums import DetectedInterruptionType, TaskPriority, TaskStatus
from app.models.focus_window import UserFocusWindow
from app.models.task import Task
from app.models.user import User
from app.models.user_intervention import UserIntervention
from app.schemas.intervention_schemas import (
    EstimatedEffort,
    InterventionActionRequest,
    InterventionCategory,
    InterventionGenerateRequest,
    InterventionLifecycleStatus,
    InterventionType,
)
from app.interventions.intervention_catalog import CONTRADICTION_PAIRS, INTERVENTION_METADATA
from app.interventions.intervention_engine import InterventionEngine
from app.interventions.intervention_grounding import InterventionGroundingService
from app.services.adaptive.intervention_service import InterventionService, _normalize_utc


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


def _create_user(db: Session, tz: str = "UTC", prefix: str = "int_user") -> User:
    uid = uuid.uuid4()
    user = User(
        id=uid,
        email=f"{prefix}_{uid.hex[:6]}@example.com",
        display_name="Intervention Tester",
        timezone=tz,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


# ---------------------------------------------------------------------------
# 1. Duplicate Recommendations Prevention
# ---------------------------------------------------------------------------
def test_duplicate_recommendations_prevention(db_session: Session):
    user = _create_user(db_session, prefix="dedup")
    now = datetime(2026, 11, 20, 10, 0, 0, tzinfo=timezone.utc)

    # Add focus window and deep task to trigger SUGGEST_PROTECTED_FOCUS_SESSION
    fw = UserFocusWindow(
        user_id=user.id,
        day_of_week=None,
        start_time=time(9, 0),
        end_time=time(12, 0),
        duration_minutes=180,
        quality_score=85.0,
        is_active=True,
    )
    task = Task(
        user_id=user.id,
        title="Deep Architecture Refactoring",
        status=TaskStatus.PENDING,
        priority=TaskPriority.HIGH,
        estimated_minutes=60,
        created_at=now - timedelta(days=1),
    )
    db_session.add_all([fw, task])
    db_session.flush()

    req = InterventionGenerateRequest(as_of=now, active_hour=10, max_interventions=3)

    # First generation
    batch1 = InterventionService.generate_interventions(db=db_session, user_id=user.id, request=req)
    assert len(batch1) >= 1
    types1 = [b.intervention_type for b in batch1]

    # Second generation under identical context
    batch2 = InterventionService.generate_interventions(db=db_session, user_id=user.id, request=req)
    # Deduplication ensures no duplicate active recommendations of identical signature are persisted
    assert len(batch2) == 0

    # Total in DB should match batch1
    total_db = db_session.query(UserIntervention).filter(UserIntervention.user_id == user.id).all()
    assert len(total_db) == len(batch1)


# ---------------------------------------------------------------------------
# 2. Contradictory Recommendations Elimination
# ---------------------------------------------------------------------------
def test_contradictory_recommendations_elimination():
    user_id = uuid.uuid4()
    now = datetime(2026, 11, 20, 10, 0, 0, tzinfo=timezone.utc)

    # Create dummy focus window (triggers focus session)
    class DummyWindow:
        start_time = time(9, 0)
        end_time = time(12, 0)
        quality_score = 80.0
        confidence_score = 0.90

    # Create dummy tasks
    class DummyTask:
        def __init__(self, tid, title, est=60, status="PENDING"):
            self.id = tid
            self.title = title
            self.estimated_minutes = est
            self.status = status
            self.created_at = now - timedelta(hours=2)

    deep_task = DummyTask(uuid.uuid4(), "Refactor Core Module", est=60)

    # High interruptions triggering SUGGEST_RECOVERY_BUFFER
    class DummyInterruption:
        start_timestamp = now - timedelta(minutes=15)

    interruptions = [DummyInterruption() for _ in range(5)]

    profile_data = {
        "baselines": {
            "baseline_friction_index": 75.0,  # Elevated friction
            "hourly_interruption_frequency": 7.0,
            "typical_recovery_delay_seconds": 90.0,
        }
    }

    # Generate recommendations
    results = InterventionEngine.generate_interventions(
        user_id=user_id,
        tasks=[deep_task],
        focus_windows=[DummyWindow()],
        profile_data=profile_data,
        recent_interruptions=interruptions,
        task_associations=[],
        current_hour=10,
        as_of=now,
        max_interventions=5,
    )

    types_generated = {r.intervention_type for r in results}

    # Verify that contradictory pairs are never concurrently present
    for pair in CONTRADICTION_PAIRS:
        overlap = types_generated.intersection(pair)
        assert len(overlap) <= 1, f"Found contradictory interventions in output: {overlap}"


# ---------------------------------------------------------------------------
# 3. Expired Interventions Handling
# ---------------------------------------------------------------------------
def test_expired_interventions_handling(db_session: Session):
    user = _create_user(db_session, prefix="expire")
    now = datetime.now(timezone.utc)

    # 1. Create an expired intervention (expired 1 hour ago)
    past_int = UserIntervention(
        id=uuid.uuid4(),
        user_id=user.id,
        intervention_type=InterventionType.SUGGEST_PROTECTED_FOCUS_SESSION.value,
        intervention_category=InterventionCategory.FOCUS.value,
        title="Old Stale Recommendation",
        message="Focus session that already expired.",
        trigger_condition="Time elapsed",
        supporting_evidence={"quality": 80},
        expected_outcome="Protects deep work.",
        estimated_effort="LOW",
        relevance_score=75.0,
        confidence=0.85,
        lifecycle_status=InterventionLifecycleStatus.GENERATED.value,
        creation_timestamp=now - timedelta(hours=3),
        expiration_timestamp=now - timedelta(hours=1),
    )

    # 2. Create a fresh intervention (valid for 2 more hours)
    fresh_int = UserIntervention(
        id=uuid.uuid4(),
        user_id=user.id,
        intervention_type=InterventionType.RESUME_PREVIOUS_TASK.value,
        intervention_category=InterventionCategory.RECOVERY.value,
        title="Active Recommendation",
        message="Resume your previous task now.",
        trigger_condition="Inactivity detected",
        supporting_evidence={"inactivity_minutes": 20},
        expected_outcome="Recovers working context.",
        estimated_effort="LOW",
        relevance_score=80.0,
        confidence=0.90,
        lifecycle_status=InterventionLifecycleStatus.GENERATED.value,
        creation_timestamp=now,
        expiration_timestamp=now + timedelta(hours=2),
    )
    db_session.add_all([past_int, fresh_int])
    db_session.commit()

    # Query active interventions
    active = InterventionService.get_interventions(db=db_session, user_id=user.id)

    # Past intervention must NOT be returned in active list
    active_ids = {a.id for a in active}
    assert fresh_int.id in active_ids
    assert past_int.id not in active_ids

    # In database, past_int must now be marked EXPIRED
    db_session.refresh(past_int)
    assert past_int.lifecycle_status == InterventionLifecycleStatus.EXPIRED.value


# ---------------------------------------------------------------------------
# 4. Insufficient Evidence Guard
# ---------------------------------------------------------------------------
def test_insufficient_evidence_guard():
    user_id = uuid.uuid4()
    now = datetime(2026, 11, 20, 10, 0, 0, tzinfo=timezone.utc)

    # Cold start user with no tasks, no focus windows, no profile, no interruptions
    empty_results = InterventionEngine.generate_interventions(
        user_id=user_id,
        tasks=[],
        focus_windows=[],
        profile_data={"overall_pattern_status": "INSUFFICIENT_EVIDENCE"},
        recent_interruptions=[],
        task_associations=[],
        current_hour=10,
        as_of=now,
    )
    # Must safely produce an empty list without hallucinations or crashes
    assert empty_results == []


# ---------------------------------------------------------------------------
# 5. User Dismissal with Feedback Note
# ---------------------------------------------------------------------------
def test_user_dismissal_with_feedback_note(db_session: Session):
    user = _create_user(db_session, prefix="dismiss")
    now = datetime.now(timezone.utc)

    item = UserIntervention(
        id=uuid.uuid4(),
        user_id=user.id,
        intervention_type=InterventionType.REDUCE_APPLICATION_SWITCHING.value,
        intervention_category=InterventionCategory.FOCUS.value,
        title="Window Switching",
        message="High window switching detected.",
        trigger_condition="Thrashing",
        supporting_evidence={"switch_frequency_hourly": 10.0},
        expected_outcome="Preserves working memory.",
        estimated_effort="LOW",
        relevance_score=70.0,
        confidence=0.85,
        lifecycle_status=InterventionLifecycleStatus.GENERATED.value,
        creation_timestamp=now,
        expiration_timestamp=now + timedelta(hours=2),
    )
    db_session.add(item)
    db_session.commit()

    action = InterventionActionRequest(feedback_note="Cross-referencing docs for research, intentional switching.")
    updated = InterventionService.dismiss_intervention(
        db=db_session,
        user_id=user.id,
        intervention_id=item.id,
        action=action,
    )

    assert updated.lifecycle_status == InterventionLifecycleStatus.DISMISSED.value
    assert updated.user_feedback_note == "Cross-referencing docs for research, intentional switching."


# ---------------------------------------------------------------------------
# 6. Deferred Recommendations Hiding
# ---------------------------------------------------------------------------
def test_deferred_recommendations_hiding(db_session: Session):
    user = _create_user(db_session, prefix="defer")
    now = datetime.now(timezone.utc)

    item = UserIntervention(
        id=uuid.uuid4(),
        user_id=user.id,
        intervention_type=InterventionType.BREAK_LARGE_TASK.value,
        intervention_category=InterventionCategory.TASK.value,
        title="Break Task",
        message="Split long task.",
        trigger_condition="Task > 90 min",
        supporting_evidence={"estimated_minutes": 120},
        expected_outcome="Facilitates completion.",
        estimated_effort="MEDIUM",
        relevance_score=75.0,
        confidence=0.85,
        lifecycle_status=InterventionLifecycleStatus.PRESENTED.value,
        creation_timestamp=now,
        expiration_timestamp=now + timedelta(hours=6),
    )
    db_session.add(item)
    db_session.commit()

    # Defer for 45 minutes
    action = InterventionActionRequest(defer_minutes=45, feedback_note="Will split after team sync")
    deferred = InterventionService.defer_intervention(
        db=db_session,
        user_id=user.id,
        intervention_id=item.id,
        action=action,
    )
    assert deferred.lifecycle_status == InterventionLifecycleStatus.DEFERRED.value
    assert _normalize_utc(deferred.deferred_until) > now

    # Normal fetch should hide deferred item
    active_feed = InterventionService.get_interventions(db=db_session, user_id=user.id, include_deferred=False)
    assert item.id not in [a.id for a in active_feed]

    # Explicit fetch with include_deferred=True should show it
    all_feed = InterventionService.get_interventions(db=db_session, user_id=user.id, include_deferred=True)
    assert item.id in [a.id for a in all_feed]


# ---------------------------------------------------------------------------
# 7. Personalized Ranking Adjustment
# ---------------------------------------------------------------------------
def test_personalized_ranking_adjustment():
    user_id = uuid.uuid4()
    now = datetime(2026, 11, 20, 10, 0, 0, tzinfo=timezone.utc)

    class DummyTask:
        def __init__(self, tid, title, est=60, prio="LOW"):
            self.id = tid
            self.title = title
            self.estimated_minutes = est
            self.status = "PENDING"
            self.priority = prio
            self.created_at = now - timedelta(hours=2)
            self.due_at = None
            self.context_tag = None

    class DummyWindow:
        start_time = time(9, 0)
        end_time = time(12, 0)
        quality_score = 80.0
        confidence_score = 0.90

    task = DummyTask(uuid.uuid4(), "Long Draft", est=90)

    # Case A: User historically accepted BREAK_LARGE_TASK 4 times (100% acceptance)
    fb_stats_positive = {
        InterventionType.BREAK_LARGE_TASK.value: {"ACCEPTED": 4, "DISMISSED": 0}
    }
    results_pos = InterventionEngine.generate_interventions(
        user_id=user_id,
        tasks=[task],
        focus_windows=[DummyWindow()],
        profile_data=None,
        recent_interruptions=[],
        task_associations=[],
        current_hour=10,
        historical_feedback_stats=fb_stats_positive,
        as_of=now,
    )
    score_pos = next(r.relevance_score for r in results_pos if r.intervention_type == InterventionType.BREAK_LARGE_TASK.value)

    # Case B: User historically dismissed BREAK_LARGE_TASK 4 times (0% acceptance)
    fb_stats_negative = {
        InterventionType.BREAK_LARGE_TASK.value: {"ACCEPTED": 0, "DISMISSED": 4}
    }
    results_neg = InterventionEngine.generate_interventions(
        user_id=user_id,
        tasks=[task],
        focus_windows=[DummyWindow()],
        profile_data=None,
        recent_interruptions=[],
        task_associations=[],
        current_hour=10,
        historical_feedback_stats=fb_stats_negative,
        as_of=now,
    )
    score_neg = next(r.relevance_score for r in results_neg if r.intervention_type == InterventionType.BREAK_LARGE_TASK.value)

    # Positive personalization must rank higher than negative personalization
    assert score_pos > score_neg
    # But negative personalization is damping (non-fatal), remaining actionable (> 10.0)
    assert score_neg >= 10.0


# ---------------------------------------------------------------------------
# 8. User Data Isolation
# ---------------------------------------------------------------------------
def test_user_data_isolation(db_session: Session):
    user_a = _create_user(db_session, prefix="user_a")
    user_b = _create_user(db_session, prefix="user_b")
    now = datetime.now(timezone.utc)

    item_a = UserIntervention(
        id=uuid.uuid4(),
        user_id=user_a.id,
        intervention_type=InterventionType.SUGGEST_PROTECTED_FOCUS_SESSION.value,
        intervention_category=InterventionCategory.FOCUS.value,
        title="User A Focus",
        message="Private recommendation for User A.",
        trigger_condition="Trigger A",
        supporting_evidence={"private_metric": 42},
        expected_outcome="Outcome A",
        estimated_effort="LOW",
        relevance_score=85.0,
        confidence=0.90,
        lifecycle_status=InterventionLifecycleStatus.GENERATED.value,
        creation_timestamp=now,
        expiration_timestamp=now + timedelta(hours=2),
    )
    db_session.add(item_a)
    db_session.commit()

    # User B fetching interventions must see nothing from User A
    feed_b = InterventionService.get_interventions(db=db_session, user_id=user_b.id)
    assert item_a.id not in [f.id for f in feed_b]

    # User B attempting to accept User A's intervention must raise 404
    with pytest.raises(HTTPException) as exc_info:
        InterventionService.accept_intervention(
            db=db_session,
            user_id=user_b.id,
            intervention_id=item_a.id,
        )
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# 9. REST API Endpoints Validation
# ---------------------------------------------------------------------------
def test_rest_api_endpoints(client: TestClient):
    user_id = uuid.uuid4()
    item_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    with Session(bind=engine) as session:
        user = User(
            id=user_id,
            email=f"api_tester_{user_id.hex[:6]}@example.com",
            display_name="API Tester",
            timezone="UTC",
            is_active=True,
        )
        session.add(user)

        # Pre-seed an active intervention
        intervention = UserIntervention(
            id=item_id,
            user_id=user_id,
            intervention_type=InterventionType.SUGGEST_RECOVERY_BUFFER.value,
            intervention_category=InterventionCategory.RECOVERY.value,
            title="Recovery Buffer",
            message="Behavioral friction is elevated. A 5-minute recovery buffer resets latency.",
            trigger_condition="High friction",
            supporting_evidence={"behavioral_friction_index": 72.0, "consecutive_disruptions": 4},
            expected_outcome="Allows cognitive recovery.",
            estimated_effort="LOW",
            relevance_score=82.0,
            confidence=0.92,
            lifecycle_status=InterventionLifecycleStatus.GENERATED.value,
            creation_timestamp=now,
            expiration_timestamp=now + timedelta(hours=2),
        )
        session.add(intervention)
        session.commit()

    from app.core.deps import get_current_user_id
    app.dependency_overrides[get_current_user_id] = lambda: user_id

    try:
        # 1. GET /api/v1/adaptive/interventions
        res_get = client.get("/api/v1/adaptive/interventions")
        assert res_get.status_code == 200
        data_get = res_get.json()
        assert len(data_get) >= 1
        found_item = next(i for i in data_get if i["id"] == str(item_id))
        # Reading should transition GENERATED to PRESENTED
        assert found_item["lifecycle_status"] == InterventionLifecycleStatus.PRESENTED.value
        assert found_item["intervention_type"] == InterventionType.SUGGEST_RECOVERY_BUFFER.value
        assert "behavioral_friction_index" in found_item["supporting_evidence"]

        # 2. POST /api/v1/adaptive/interventions/generate
        res_gen = client.post("/api/v1/adaptive/interventions/generate", json={"max_interventions": 3})
        assert res_gen.status_code == 200
        assert isinstance(res_gen.json(), list)

        # 3. POST /api/v1/adaptive/interventions/{id}/defer
        res_defer = client.post(
            f"/api/v1/adaptive/interventions/{item_id}/defer",
            json={"defer_minutes": 20, "feedback_note": "Taking buffer later"},
        )
        assert res_defer.status_code == 200
        data_defer = res_defer.json()
        assert data_defer["lifecycle_status"] == InterventionLifecycleStatus.DEFERRED.value
        assert data_defer["user_feedback_note"] == "Taking buffer later"

        # 4. POST /api/v1/adaptive/interventions/{id}/accept
        res_accept = client.post(
            f"/api/v1/adaptive/interventions/{item_id}/accept",
            json={"feedback_note": "Starting buffer now"},
        )
        assert res_accept.status_code == 200
        data_accept = res_accept.json()
        assert data_accept["lifecycle_status"] == InterventionLifecycleStatus.ACCEPTED.value
        assert data_accept["completed_at"] is not None

        # 5. POST /api/v1/adaptive/interventions/{id}/dismiss
        res_dismiss = client.post(
            f"/api/v1/adaptive/interventions/{item_id}/dismiss",
            json={"feedback_note": "Dismissing after completion"},
        )
        assert res_dismiss.status_code == 200
        data_dismiss = res_dismiss.json()
        assert data_dismiss["lifecycle_status"] == InterventionLifecycleStatus.DISMISSED.value

    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

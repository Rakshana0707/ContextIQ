"""
Unit and integration test suite for ContextIQ Adaptive Task Prioritization
and Personalized Scheduling (Phase 4.4).
Validates:
- Urgent deadline escalation (< 4h)
- High-concentration task prioritization in focus windows
- Short chore prioritization during fragmented periods
- Missing duration fallback
- Cold-start & insufficient evidence safety
- Task dependency blocking (parent_task_id)
- Configurable preset weight behavior
- Feedback logging and overrides
- Ranking reproducibility
- REST API endpoints (/api/v1/adaptive/task-ranking*)
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
from app.models.enums import DetectedInterruptionType, TaskPriority, TaskStatus
from app.models.focus_window import UserFocusWindow
from app.models.task import Task
from app.models.task_ranking_feedback import TaskRankingFeedback
from app.models.user import User
from app.prioritization.prioritization_engine import PrioritizationEngine
from app.prioritization.prioritization_features import PrioritizationFeatureExtractor
from app.schemas.task_ranking import (
    RankingPreset,
    RankingWeightConfig,
    TaskRankingFeedbackCreate,
    TaskRankingPreviewRequest,
)
from app.services.adaptive.focus_window_service import FocusWindowService
from app.services.adaptive.ranking_service import AdaptiveRankingService


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


def _create_user(db: Session, tz: str = "UTC", prefix: str = "rank_user") -> User:
    uid = uuid.uuid4()
    user = User(
        id=uid,
        email=f"{prefix}_{uid.hex[:6]}@example.com",
        display_name="Ranking Tester",
        timezone=tz,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


# ---------------------------------------------------------------------------
# Unit & Integration Tests
# ---------------------------------------------------------------------------

def test_urgent_deadlines_escalation(db_session: Session):
    """
    Verifies that a task approaching its deadline (< 4h) receives elevated urgency
    and dominates priority even when explicit priority is MEDIUM.
    """
    user = _create_user(db_session, "urgent_user")
    now = datetime(2026, 10, 10, 10, 0, 0, tzinfo=timezone.utc)

    # Task A: Due in 2 hours (MEDIUM explicit priority)
    task_urgent = Task(
        user_id=user.id,
        title="Submit Grant Report",
        status=TaskStatus.PENDING,
        priority=TaskPriority.MEDIUM,
        due_at=now + timedelta(hours=2),
        estimated_minutes=45,
        created_at=now - timedelta(days=2),
    )

    # Task B: Due in 10 days (HIGH explicit priority)
    task_distant = Task(
        user_id=user.id,
        title="Quarterly Roadmap Review",
        status=TaskStatus.PENDING,
        priority=TaskPriority.HIGH,
        due_at=now + timedelta(days=10),
        estimated_minutes=45,
        created_at=now - timedelta(days=2),
    )
    db_session.add_all([task_urgent, task_distant])
    db_session.flush()

    feat_urgent = PrioritizationFeatureExtractor.extract_task_features(
        db=db_session, task=task_urgent, user_id=user.id, as_of=now
    )
    feat_distant = PrioritizationFeatureExtractor.extract_task_features(
        db=db_session, task=task_distant, user_id=user.id, as_of=now
    )

    assert feat_urgent["deadline_score"] > feat_distant["deadline_score"]
    assert feat_urgent["urgency_score"] > feat_distant["urgency_score"]

    ranked = PrioritizationEngine.rank_tasks(
        tasks_features=[feat_distant, feat_urgent],
        focus_windows=[],
        current_hour=10,
    )

    assert ranked[0].task_id == task_urgent.id
    assert ranked[0].primary_driver == "CRITICAL_DEADLINE"
    assert "Approaching deadline" in ranked[0].grounded_explanation


def test_focus_window_suitability(db_session: Session):
    """
    Verifies that in a verified focus window (e.g. 10:00 - 12:00, Quality 85):
    - High-concentration tasks (programming, 60 min) receive boosted suitability P(t).
    - Short administrative chores (email, 15 min) receive lower suitability so prime time isn't burned.
    """
    user = _create_user(db_session, "fw_suit_user")
    now = datetime(2026, 10, 10, 10, 30, 0, tzinfo=timezone.utc)

    task_deep = Task(
        user_id=user.id,
        title="Implement Cache Engine",
        context_tag="programming",
        status=TaskStatus.PENDING,
        priority=TaskPriority.MEDIUM,
        estimated_minutes=60,
        created_at=now - timedelta(days=1),
    )

    task_chore = Task(
        user_id=user.id,
        title="Reply to Vendor Email",
        context_tag="admin",
        status=TaskStatus.PENDING,
        priority=TaskPriority.MEDIUM,
        estimated_minutes=15,
        created_at=now - timedelta(days=1),
    )
    db_session.add_all([task_deep, task_chore])
    db_session.flush()

    # Create active focus window at 10:00 - 12:00
    fw = UserFocusWindow(
        id=uuid.uuid4(),
        user_id=user.id,
        start_time=time(10, 0),
        end_time=time(12, 0),
        quality_score=85.0,
        task_category="programming",
        confidence_score=0.90,
        is_active=True,
    )

    feats_deep = PrioritizationFeatureExtractor.extract_task_features(
        db=db_session, task=task_deep, user_id=user.id, as_of=now
    )
    feats_chore = PrioritizationFeatureExtractor.extract_task_features(
        db=db_session, task=task_chore, user_id=user.id, as_of=now
    )

    ranked = PrioritizationEngine.rank_tasks(
        tasks_features=[feats_chore, feats_deep],
        focus_windows=[fw],
        current_hour=10,
    )

    top_task = ranked[0]
    assert top_task.task_id == task_deep.id
    assert top_task.score_breakdown.personal_suitability_score > 0.85
    assert top_task.primary_driver == "FOCUS_WINDOW_MATCH"
    assert top_task.recommended_focus_window is not None
    assert top_task.recommended_focus_window.quality_score == 85.0


def test_fragmented_period_chore_priority(db_session: Session):
    """
    Verifies that during a fragmented, high-interruption period:
    - Short administrative chores (15 min) are boosted for quick execution between interruptions.
    - Deep concentration tasks are down-ranked to avoid cognitive interruption fracture.
    """
    user = _create_user(db_session, "frag_user")
    now = datetime(2026, 10, 10, 14, 0, 0, tzinfo=timezone.utc)

    task_deep = Task(
        user_id=user.id,
        title="Design Architecture Spec",
        context_tag="design",
        status=TaskStatus.PENDING,
        priority=TaskPriority.MEDIUM,
        estimated_minutes=90,
        created_at=now - timedelta(days=1),
    )

    task_chore = Task(
        user_id=user.id,
        title="Clear Inbox",
        context_tag="admin",
        status=TaskStatus.PENDING,
        priority=TaskPriority.MEDIUM,
        estimated_minutes=15,
        created_at=now - timedelta(days=1),
    )
    db_session.add_all([task_deep, task_chore])
    db_session.flush()

    profile_data = {
        "baselines": {
            "hourly_interruption_frequency": 4.5,  # Fragmented period (> 3.0)
            "baseline_friction_index": 65.0,
        }
    }

    feats_deep = PrioritizationFeatureExtractor.extract_task_features(
        db=db_session, task=task_deep, user_id=user.id, as_of=now, profile_data=profile_data
    )
    feats_chore = PrioritizationFeatureExtractor.extract_task_features(
        db=db_session, task=task_chore, user_id=user.id, as_of=now, profile_data=profile_data
    )

    ranked = PrioritizationEngine.rank_tasks(
        tasks_features=[feats_deep, feats_chore],
        focus_windows=[],
        current_hour=14,
        profile_data=profile_data,
    )

    assert ranked[0].task_id == task_chore.id
    assert ranked[0].primary_driver == "QUICK_WIN_ADMIN"
    assert ranked[0].score_breakdown.personal_suitability_score >= 0.85
    assert ranked[1].score_breakdown.personal_suitability_score <= 0.35


def test_missing_task_duration_fallback(db_session: Session):
    """Verifies tasks with estimated_minutes=None fallback cleanly to default without errors."""
    user = _create_user(db_session, "missing_dur")
    now = datetime.now(timezone.utc)

    task_no_dur = Task(
        user_id=user.id,
        title="Task without duration",
        status=TaskStatus.PENDING,
        priority=TaskPriority.MEDIUM,
        estimated_minutes=None,
        created_at=now,
    )
    db_session.add(task_no_dur)
    db_session.flush()

    feats = PrioritizationFeatureExtractor.extract_task_features(
        db=db_session, task=task_no_dur, user_id=user.id, as_of=now
    )

    assert feats["estimated_minutes"] == 30  # Default fallback
    assert feats["recovery_buffer_minutes"] == 10

    ranked = PrioritizationEngine.rank_tasks(
        tasks_features=[feats],
        focus_windows=[],
        current_hour=12,
    )
    assert len(ranked) == 1
    assert ranked[0].estimated_minutes == 30


def test_cold_start_insufficient_history(db_session: Session):
    """Verifies that a cold-start user produces valid rankings marked INSUFFICIENT_EVIDENCE."""
    user = _create_user(db_session, "cold_start")
    now = datetime.now(timezone.utc)

    task = Task(
        user_id=user.id,
        title="Brand New User Task",
        status=TaskStatus.PENDING,
        priority=TaskPriority.HIGH,
        created_at=now,
    )
    db_session.add(task)
    db_session.flush()

    feats = PrioritizationFeatureExtractor.extract_task_features(
        db=db_session, task=task, user_id=user.id, as_of=now
    )
    ranked = PrioritizationEngine.rank_tasks(
        tasks_features=[feats],
        focus_windows=[],
        current_hour=10,
    )

    assert len(ranked) == 1
    assert ranked[0].data_sufficiency == "INSUFFICIENT_EVIDENCE"
    assert 0.0 <= ranked[0].composite_score <= 100.0


def test_task_dependency_blocking(db_session: Session):
    """
    Verifies that a child task whose parent is pending is marked is_blocked=True,
    receives scheduling_feasibility_score=0.0, and ranks below actionable tasks.
    """
    user = _create_user(db_session, "dep_user")
    now = datetime.now(timezone.utc)

    parent_task = Task(
        user_id=user.id,
        title="Design Database Schema",
        status=TaskStatus.PENDING,
        priority=TaskPriority.HIGH,
        created_at=now,
    )
    db_session.add(parent_task)
    db_session.flush()

    child_task = Task(
        user_id=user.id,
        title="Run Migration Scripts",
        status=TaskStatus.PENDING,
        priority=TaskPriority.URGENT,  # Urgent, but blocked!
        parent_task_id=parent_task.id,
        created_at=now,
    )
    db_session.add(child_task)
    db_session.flush()

    feats_parent = PrioritizationFeatureExtractor.extract_task_features(
        db=db_session, task=parent_task, user_id=user.id, as_of=now
    )
    feats_child = PrioritizationFeatureExtractor.extract_task_features(
        db=db_session, task=child_task, user_id=user.id, as_of=now
    )

    pending_ids = {parent_task.id, child_task.id}

    ranked = PrioritizationEngine.rank_tasks(
        tasks_features=[feats_child, feats_parent],
        focus_windows=[],
        current_hour=10,
        pending_task_ids=pending_ids,
    )

    # Parent should be rank 1; blocked child should be rank 2
    assert ranked[0].task_id == parent_task.id
    assert ranked[0].is_blocked is False

    assert ranked[1].task_id == child_task.id
    assert ranked[1].is_blocked is True
    assert ranked[1].blocked_by_task_id == parent_task.id
    assert ranked[1].score_breakdown.scheduling_feasibility_score == 0.0
    assert ranked[1].primary_driver == "BLOCKED_DEPENDENCY"


def test_preset_weight_configurations():
    """Verifies that presets (DEADLINE_CRUNCH vs DEEP_WORK) alter weight allocations deterministically."""
    balanced = RankingWeightConfig.for_preset(RankingPreset.BALANCED)
    assert balanced.urgency_weight == 0.30
    assert balanced.personal_suitability_weight == 0.20

    crunch = RankingWeightConfig.for_preset(RankingPreset.DEADLINE_CRUNCH)
    assert crunch.urgency_weight == 0.55
    assert crunch.personal_suitability_weight == 0.10

    deep = RankingWeightConfig.for_preset(RankingPreset.DEEP_WORK)
    assert deep.urgency_weight == 0.15
    assert deep.personal_suitability_weight == 0.40

    norm = deep.normalized()
    total = (
        norm.urgency_weight
        + norm.forgetting_risk_weight
        + norm.personal_suitability_weight
        + norm.context_compatibility_weight
        + norm.scheduling_feasibility_weight
    )
    assert math.isclose(total, 1.0, abs_tol=0.01)


def test_ranking_reproducibility(db_session: Session):
    """Verifies that ranking output is strictly deterministic for identical inputs."""
    user = _create_user(db_session, "repro_user")
    now = datetime(2026, 11, 1, 10, 0, 0, tzinfo=timezone.utc)

    for i in range(5):
        db_session.add(Task(
            user_id=user.id,
            title=f"Reproducible Task {i}",
            priority=TaskPriority.MEDIUM if i % 2 == 0 else TaskPriority.HIGH,
            status=TaskStatus.PENDING,
            estimated_minutes=20 + i * 15,
            created_at=now - timedelta(days=i),
        ))
    db_session.flush()

    res1 = AdaptiveRankingService.get_task_ranking(db=db_session, user_id=user.id, as_of=now)
    res2 = AdaptiveRankingService.get_task_ranking(db=db_session, user_id=user.id, as_of=now)

    assert len(res1.items) == len(res2.items) == 5
    for item1, item2 in zip(res1.items, res2.items):
        assert item1.task_id == item2.task_id
        assert item1.composite_score == item2.composite_score
        assert item1.rank == item2.rank


def test_api_ranking_and_feedback(client: TestClient):
    """Tests the /api/v1/adaptive/task-ranking REST endpoints and feedback recording."""
    user_id = uuid.uuid4()
    task_id = uuid.uuid4()

    with Session(engine) as session:
        user = User(
            id=user_id,
            email=f"rank_api_{user_id.hex[:6]}@example.com",
            display_name="Ranking API Tester",
            timezone="UTC",
            is_active=True,
        )
        session.add(user)

        task = Task(
            id=task_id,
            user_id=user_id,
            title="API Scheduled Task",
            priority=TaskPriority.HIGH,
            status=TaskStatus.PENDING,
            estimated_minutes=40,
            created_at=datetime.now(timezone.utc),
        )
        session.add(task)
        session.commit()

    from app.core.deps import get_current_user_id
    app.dependency_overrides[get_current_user_id] = lambda: user_id

    try:
        # 1. GET /api/v1/adaptive/task-ranking
        res_get = client.get("/api/v1/adaptive/task-ranking")
        assert res_get.status_code == 200
        data_get = res_get.json()
        assert data_get["user_id"] == str(user_id)
        assert len(data_get["items"]) >= 1
        assert "composite_score" in data_get["items"][0]
        assert "score_breakdown" in data_get["items"][0]

        # 2. POST /api/v1/adaptive/task-ranking/preview
        preview_payload = {
            "preset": "DEEP_WORK",
            "include_blocked": True,
        }
        res_prev = client.post("/api/v1/adaptive/task-ranking/preview", json=preview_payload)
        assert res_prev.status_code == 200
        data_prev = res_prev.json()
        assert data_prev["preset_applied"] == "DEEP_WORK"
        assert len(data_prev["items"]) >= 1

        # 3. POST /api/v1/adaptive/task-ranking/feedback
        feedback_payload = {
            "task_id": str(task_id),
            "action": "PINNED",
            "rank_position": 1,
            "composite_score": data_get["items"][0]["composite_score"],
            "feedback_note": "Prioritizing first for morning session",
        }
        res_fb = client.post("/api/v1/adaptive/task-ranking/feedback", json=feedback_payload)
        assert res_fb.status_code == 201
        data_fb = res_fb.json()
        assert data_fb["task_id"] == str(task_id)
        assert data_fb["action"] == "PINNED"

    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

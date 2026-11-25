"""
Test suite for ContextIQ Phase 8.3: Long-Term Behavioral Memory and Pattern Evolution.
Verifies memory models, multi-category coverage, evolution transitions, confidence dynamics,
temporal rollups, user correction, and REST API integration.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker

# SQLite compilation adapter for JSONB in tests
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

from app.core.deps import get_current_user_id
from app.db.session import Base, get_db
from app.main import app
from app.models.behavioral_memory import (
    BehavioralMemory,
    BehavioralTemporalSummary,
    MemoryCategory,
    MemorySourceType,
    MemoryValidityStatus,
    PatternEvolutionType,
    UserBehavioralMemoryPreference,
)
from app.models.behavioral_profile import UserBehavioralProfile
from app.models.focus_window import UserFocusWindow
from app.models.knowledge_graph import Goal
from app.models.user import User
from app.models.user_intervention import UserIntervention
from app.schemas.behavioral_memory import (
    BehavioralMemoryCreate,
    BehavioralMemoryUpdate,
    MemoryCorrectionRequest,
    UserBehavioralMemoryPreferenceUpdate,
)
from app.services.behavioral_memory_service import BehavioralMemoryService


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
        email=f"mem-{uuid.uuid4().hex[:8]}@contextiq.ai",
        display_name="Test Memory User",
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
        email=f"mem2-{uuid.uuid4().hex[:8]}@contextiq.ai",
        display_name="Second Memory User",
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
# Unit & Service Tests
# ---------------------------------------------------------------------------

def test_create_and_retrieve_memory(db_session: Session, test_user: User):
    """Validates explicit memory creation, initial evolution audit trail, and retrieval."""
    payload = BehavioralMemoryCreate(
        category=MemoryCategory.EXPLICIT_USER_INSTRUCTIONS,
        title="No morning meetings",
        description="User explicitly instructed no meetings scheduled prior to 11:00 AM.",
        source_type=MemorySourceType.EXPLICIT_USER_INSTRUCTION,
        confidence=1.0,
        supporting_evidence={"channel": "web_ui"},
    )
    mem = BehavioralMemoryService.create_memory(db_session, test_user.id, payload)
    db_session.commit()

    assert mem.id is not None
    assert mem.user_id == test_user.id
    assert mem.category == MemoryCategory.EXPLICIT_USER_INSTRUCTIONS
    assert mem.source_type == MemorySourceType.EXPLICIT_USER_INSTRUCTION
    assert mem.validity_status == MemoryValidityStatus.ACTIVE
    assert mem.confidence == 1.0
    assert mem.observation_count == 1
    assert len(mem.evolution_history) == 1
    assert mem.evolution_history[0]["evolution_type"] == PatternEvolutionType.EMERGING.value

    fetched = BehavioralMemoryService.get_memory_by_id(db_session, test_user.id, mem.id)
    assert fetched.title == "No morning meetings"


def test_tenancy_isolation(db_session: Session, test_user: User, second_user: User):
    """Ensures cross-user access boundaries prevent reading or mutating other tenants' memories."""
    payload = BehavioralMemoryCreate(
        category=MemoryCategory.FOCUS_PATTERNS,
        title="User 1 Focus Habit",
        description="Private user focus pattern",
    )
    mem = BehavioralMemoryService.create_memory(db_session, test_user.id, payload)
    db_session.commit()

    # User 2 cannot access User 1's memory
    with pytest.raises(Exception):
        BehavioralMemoryService.get_memory_by_id(db_session, second_user.id, mem.id)

    # Listing memories for User 2 returns empty
    user2_mems = BehavioralMemoryService.list_memories(db_session, second_user.id)
    assert len(user2_mems) == 0


def test_memory_categories_coverage(db_session: Session, test_user: User):
    """Verifies that all 10 memory categories can be instantiated and filtered."""
    categories = [
        MemoryCategory.BEHAVIORAL_PREFERENCES,
        MemoryCategory.PRODUCTIVITY_PATTERNS,
        MemoryCategory.FOCUS_PATTERNS,
        MemoryCategory.RECOVERY_PATTERNS,
        MemoryCategory.TASK_MANAGEMENT_PREFERENCES,
        MemoryCategory.CONTEXT_ASSOCIATIONS,
        MemoryCategory.SUCCESSFUL_INTERVENTIONS,
        MemoryCategory.UNSUCCESSFUL_INTERVENTIONS,
        MemoryCategory.LONG_TERM_GOALS,
        MemoryCategory.EXPLICIT_USER_INSTRUCTIONS,
    ]

    for cat in categories:
        mem = BehavioralMemoryService.create_memory(
            db=db_session,
            user_id=test_user.id,
            payload=BehavioralMemoryCreate(
                category=cat,
                title=f"Sample memory for {cat.value}",
                description=f"Description for category {cat.value}",
                source_type=MemorySourceType.MODEL_INFERRED_PATTERN,
                confidence=0.8,
            ),
        )
        assert mem.category == cat

    db_session.commit()
    all_mems = BehavioralMemoryService.list_memories(db_session, test_user.id)
    assert len(all_mems) >= 10

    # Filter by specific category
    focus_mems = BehavioralMemoryService.list_memories(db_session, test_user.id, category=MemoryCategory.FOCUS_PATTERNS)
    assert len(focus_mems) == 1
    assert focus_mems[0].category == MemoryCategory.FOCUS_PATTERNS


def test_pattern_evolution_strengthening(db_session: Session, test_user: User):
    """Tests pattern reinforcement mechanics: confidence increase and status transition."""
    mem = BehavioralMemory(
        user_id=test_user.id,
        category=MemoryCategory.FOCUS_PATTERNS,
        title="Emerging Afternoon Focus",
        description="Initial observations of afternoon focus stretch.",
        source_type=MemorySourceType.MODEL_INFERRED_PATTERN,
        validity_status=MemoryValidityStatus.EMERGING,
        confidence=0.70,
        observation_count=1,
        first_observed_at=datetime.now(timezone.utc),
        last_observed_at=datetime.now(timezone.utc),
        evolution_history=[],
        expiration_policy={"retention_days": 365, "review_after_days": 30, "auto_outdate_dormant_days": 45},
    )
    db_session.add(mem)
    db_session.commit()

    # Reinforce pattern multiple times
    for i in range(2):
        BehavioralMemoryService.reinforce_pattern(
            db_session, mem, supporting_evidence={"session_duration": 48}
        )
    db_session.commit()

    # Should transition to STRENGTHENING at obs=3
    assert mem.observation_count == 3
    assert mem.confidence > 0.70
    assert mem.validity_status == MemoryValidityStatus.STRENGTHENING

    # Reinforce further until ACTIVE (obs >= 5, conf >= 0.75)
    for i in range(3):
        BehavioralMemoryService.reinforce_pattern(
            db_session, mem, supporting_evidence={"session_duration": 55}
        )
    db_session.commit()

    assert mem.observation_count == 6
    assert mem.validity_status == MemoryValidityStatus.ACTIVE
    assert mem.confidence >= 0.75
    assert len(mem.evolution_history) == 5


def test_pattern_evolution_contradiction(db_session: Session, test_user: User):
    """Tests contrary telemetry penalizing confidence and evolving status to WEAKENING / CONTRADICTED."""
    mem = BehavioralMemory(
        user_id=test_user.id,
        category=MemoryCategory.PRODUCTIVITY_PATTERNS,
        title="Late Night Productivity Burst",
        description="Inferred late night coding habit.",
        source_type=MemorySourceType.MODEL_INFERRED_PATTERN,
        validity_status=MemoryValidityStatus.ACTIVE,
        confidence=0.60,
        observation_count=5,
        contradiction_count=0,
        first_observed_at=datetime.now(timezone.utc),
        last_observed_at=datetime.now(timezone.utc),
        evolution_history=[],
        expiration_policy={"retention_days": 180, "review_after_days": 30, "auto_outdate_dormant_days": 45},
    )
    db_session.add(mem)
    db_session.commit()

    # Contradict twice
    BehavioralMemoryService.contradict_pattern(db_session, mem, {"contrary_event": "no_activity_at_night"})
    BehavioralMemoryService.contradict_pattern(db_session, mem, {"contrary_event": "immediate_sleep_pattern"})
    db_session.commit()

    assert mem.contradiction_count == 2
    assert mem.confidence < 0.45
    assert mem.validity_status == MemoryValidityStatus.WEAKENING


def test_explicit_user_directive_resilience(db_session: Session, test_user: User):
    """Ensures explicit user instructions do not get aggressively degraded by single anomalies."""
    mem = BehavioralMemory(
        user_id=test_user.id,
        category=MemoryCategory.EXPLICIT_USER_INSTRUCTIONS,
        title="Prefer Asynchronous Status Updates",
        description="Explicit user instruction for async comms.",
        source_type=MemorySourceType.EXPLICIT_USER_INSTRUCTION,
        validity_status=MemoryValidityStatus.ACTIVE,
        confidence=1.0,
        observation_count=1,
        contradiction_count=0,
        first_observed_at=datetime.now(timezone.utc),
        last_observed_at=datetime.now(timezone.utc),
        evolution_history=[],
        expiration_policy={"retention_days": 730, "review_after_days": 90, "auto_outdate_dormant_days": 365},
    )
    db_session.add(mem)
    db_session.commit()

    # Apply contradiction
    BehavioralMemoryService.contradict_pattern(db_session, mem, {"unexpected_verbal_call": True})
    db_session.commit()

    # Stays ACTIVE, attenuated with smaller penalty (0.15 * 0.4 = 0.06 -> conf ~ 0.94)
    assert mem.validity_status == MemoryValidityStatus.ACTIVE
    assert mem.confidence >= 0.90


def test_evaluate_outdated_patterns(db_session: Session, test_user: User):
    """Verifies that dormant patterns transition to OUTDATED when lacking recent telemetry."""
    old_date = datetime.now(timezone.utc) - timedelta(days=60)
    dormant_mem = BehavioralMemory(
        user_id=test_user.id,
        category=MemoryCategory.PRODUCTIVITY_PATTERNS,
        title="Dormant Task Habit",
        description="No activity observed in 60 days.",
        source_type=MemorySourceType.MODEL_INFERRED_PATTERN,
        validity_status=MemoryValidityStatus.ACTIVE,
        confidence=0.85,
        observation_count=10,
        first_observed_at=old_date,
        last_observed_at=old_date,
        evolution_history=[],
        expiration_policy={"retention_days": 180, "review_after_days": 30, "auto_outdate_dormant_days": 45},
    )
    db_session.add(dormant_mem)
    db_session.commit()

    outdated_list = BehavioralMemoryService.evaluate_outdated_patterns(db_session, test_user.id, dormant_days=45)
    db_session.commit()

    assert len(outdated_list) >= 1
    assert dormant_mem.validity_status == MemoryValidityStatus.OUTDATED
    assert dormant_mem.confidence < 0.85
    assert dormant_mem.evolution_history[-1]["evolution_type"] == PatternEvolutionType.OUTDATED.value


def test_user_correction_flow(db_session: Session, test_user: User):
    """Tests user correction of an inaccurate memory: flags, records notes, and halves confidence."""
    mem = BehavioralMemoryService.create_memory(
        db_session,
        test_user.id,
        BehavioralMemoryCreate(
            category=MemoryCategory.CONTEXT_ASSOCIATIONS,
            title="Prefers Working at Coffee Shop",
            description="Inferred high coffee shop productivity.",
            source_type=MemorySourceType.MODEL_INFERRED_PATTERN,
            confidence=0.84,
        ),
    )
    db_session.commit()

    correction = MemoryCorrectionRequest(
        corrected_description="Only visits coffee shop for socializing, not deep work.",
        user_notes="Inferred incorrectly due to wifi location checkins.",
        is_inaccurate=True,
    )
    updated = BehavioralMemoryService.correct_memory(db_session, test_user.id, mem.id, correction)
    db_session.commit()

    assert updated.is_user_corrected is True
    assert updated.user_correction_notes == "Inferred incorrectly due to wifi location checkins."
    assert updated.validity_status == MemoryValidityStatus.CORRECTED
    assert updated.confidence <= 0.45
    assert updated.description == "Only visits coffee shop for socializing, not deep work."


def test_memory_preferences_and_category_disabling(db_session: Session, test_user: User):
    """Tests user category disabling preventing creation of memories in disabled categories."""
    BehavioralMemoryService.update_preferences(
        db_session,
        test_user.id,
        UserBehavioralMemoryPreferenceUpdate(
            disabled_categories=[MemoryCategory.UNSUCCESSFUL_INTERVENTIONS.value],
            retention_policy_days=180,
        ),
    )
    db_session.commit()

    # Attempting to create a memory in disabled category should raise ValidationError
    with pytest.raises(Exception):
        BehavioralMemoryService.create_memory(
            db_session,
            test_user.id,
            BehavioralMemoryCreate(
                category=MemoryCategory.UNSUCCESSFUL_INTERVENTIONS,
                title="Should Fail",
                description="Category is disabled",
            ),
        )


def test_synthesize_memories_from_behavioral_profile(db_session: Session, test_user: User):
    """Tests synthesis extracting memories from UserBehavioralProfile, FocusWindows, and Goals."""
    # 1. Seed UserBehavioralProfile
    profile = UserBehavioralProfile(
        user_id=test_user.id,
        profile_version="1.0.0",
        is_cold_start=False,
        global_confidence_score=0.88,
        global_pattern_status="ESTABLISHED",
        focus_dimension={
            "typical_session_duration_minutes": {"observed_value": 45.0},
            "focus_stability_score": {"observed_value": 85.0},
        },
        interruption_dimension={
            "interruption_sensitivity_index": {"observed_value": 0.65},
            "recovery_duration_distribution": {"observed_value": {"median_lag_seconds": 120}},
        },
        task_completion_dimension={
            "task_completion_rate": {"observed_value": 0.82},
            "postponement_frequency": {"observed_value": 0.3},
        },
        context_dimension={
            "context_switch_overhead_seconds": {"observed_value": 42.0},
        },
        baselines={
            "median_focus_duration_minutes": 45.0,
            "baseline_behavioral_friction_index": 22.5,
        },
    )

    # 2. Seed UserFocusWindow
    from datetime import time
    focus_win = UserFocusWindow(
        user_id=test_user.id,
        start_time=time(9, 0),
        end_time=time(11, 30),
        duration_minutes=150,
        quality_score=92.0,
        completion_rate=0.89,
        is_active=True,
    )

    # 3. Seed Goal
    goal = Goal(
        user_id=test_user.id,
        title="Deliver Phase 8 Release",
        category="ENGINEERING",
        status="ACTIVE",
        progress_pct=60.0,
    )

    db_session.add_all([profile, focus_win, goal])
    db_session.commit()

    res = BehavioralMemoryService.synthesize_memories_from_behavioral_profile(db_session, test_user.id)
    db_session.commit()

    assert res.created_memories_count >= 4
    assert res.total_active_memories >= 4

    # Verify Focus Pattern exists
    focus_mems = BehavioralMemoryService.list_memories(db_session, test_user.id, category=MemoryCategory.FOCUS_PATTERNS)
    assert len(focus_mems) >= 1

    # Verify Goal memory exists
    goal_mems = BehavioralMemoryService.list_memories(db_session, test_user.id, category=MemoryCategory.LONG_TERM_GOALS)
    assert len(goal_mems) >= 1
    assert "Deliver Phase 8 Release" in goal_mems[0].title


def test_temporal_summary_generation(db_session: Session, test_user: User):
    """Verifies weekly temporal roll-up generation and metrics aggregation."""
    # Seed memories
    mem1 = BehavioralMemoryService.create_memory(
        db_session,
        test_user.id,
        BehavioralMemoryCreate(
            category=MemoryCategory.FOCUS_PATTERNS,
            title="Focus Window 1",
            description="Active morning focus",
            confidence=0.9,
        ),
    )
    mem2 = BehavioralMemoryService.create_memory(
        db_session,
        test_user.id,
        BehavioralMemoryCreate(
            category=MemoryCategory.BEHAVIORAL_PREFERENCES,
            title="Preference 1",
            description="Quiet mode prefered",
            confidence=0.85,
        ),
    )
    db_session.commit()

    summary = BehavioralMemoryService.generate_temporal_summary(
        db=db_session,
        user_id=test_user.id,
        period_type="WEEKLY",
    )
    db_session.commit()

    assert summary.id is not None
    assert summary.period_type == "WEEKLY"
    assert summary.summary_metrics["total_memories"] >= 2
    assert summary.narrative_summary is not None

    summaries = BehavioralMemoryService.get_temporal_summaries(db_session, test_user.id)
    assert len(summaries) >= 1


# ---------------------------------------------------------------------------
# API Endpoint Integration Tests
# ---------------------------------------------------------------------------

def test_api_overview_endpoint(client: TestClient, db_session: Session, test_user: User):
    """Tests GET /api/v1/memory/overview."""
    res = client.get("/api/v1/memory/overview")
    assert res.status_code == 200
    data = res.json()
    assert "total_memories" in data
    assert "active_patterns_count" in data
    assert "category_counts" in data


def test_api_crud_endpoints(client: TestClient, db_session: Session, test_user: User):
    """Tests POST /api/v1/memory, GET /api/v1/memory, PATCH /api/v1/memory/{id}, and DELETE /api/v1/memory/{id}."""
    # Create
    create_payload = {
        "category": "EXPLICIT_USER_INSTRUCTIONS",
        "title": "API Direct Directive",
        "description": "Never schedule over lunch block.",
        "source_type": "EXPLICIT_USER_INSTRUCTION",
        "confidence": 1.0,
    }
    create_res = client.post("/api/v1/memory", json=create_payload)
    assert create_res.status_code == 201
    mem_data = create_res.json()
    mem_id = mem_data["id"]
    assert mem_data["title"] == "API Direct Directive"

    # List
    list_res = client.get("/api/v1/memory")
    assert list_res.status_code == 200
    items = list_res.json()
    assert any(i["id"] == mem_id for i in items)

    # Get Single
    get_res = client.get(f"/api/v1/memory/{mem_id}")
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "API Direct Directive"

    # Patch
    patch_res = client.patch(f"/api/v1/memory/{mem_id}", json={"title": "Updated API Directive"})
    assert patch_res.status_code == 200
    assert patch_res.json()["title"] == "Updated API Directive"

    # User Correction
    correct_res = client.post(
        f"/api/v1/memory/{mem_id}/correct",
        json={"user_notes": "Clarifying lunch window from 12-1pm", "is_inaccurate": False},
    )
    assert correct_res.status_code == 200
    assert correct_res.json()["is_user_corrected"] is True

    # Delete
    del_res = client.delete(f"/api/v1/memory/{mem_id}")
    assert del_res.status_code == 204

    # Verify deleted
    get_again = client.get(f"/api/v1/memory/{mem_id}")
    assert get_again.status_code == 404


def test_api_synthesis_and_preferences(client: TestClient, db_session: Session, test_user: User):
    """Tests POST /api/v1/memory/synthesize and preferences endpoints."""
    # Synthesize
    synth_res = client.post("/api/v1/memory/synthesize")
    assert synth_res.status_code == 200
    synth_data = synth_res.json()
    assert "created_memories_count" in synth_data

    # Preferences
    pref_res = client.get("/api/v1/memory/preferences")
    assert pref_res.status_code == 200
    assert "retention_policy_days" in pref_res.json()

    patch_pref = client.patch("/api/v1/memory/preferences", json={"retention_policy_days": 120})
    assert patch_pref.status_code == 200
    assert patch_pref.json()["retention_policy_days"] == 120

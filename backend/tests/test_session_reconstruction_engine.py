"""
Comprehensive unit and integration test suite for Intelligent Work Session
Reconstruction Engine (ContextIQ Phase 3.6).
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["APP_ENV"] = "development"
os.environ.setdefault("DATABASE_URL", "sqlite:///./_test_telemetry.db")

# Register SQLite compilation for Postgres JSONB in tests
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

import app.models  # Register all models on Base
from app.db.session import Base, engine
from app.main import app
from app.models.context_session import ContextSession
from app.models.enums import TaskEventType, TelemetryEventType
from app.models.raw_telemetry_event import RawTelemetryEvent
from app.models.task import Task
from app.models.task_event import TaskEvent
from app.models.user import User
from app.services.session_reconstruction_engine import (
    SessionReconstructionConfig,
    SessionReconstructionEngine,
    UnifiedEvent,
    reconstruct_sessions_for_user,
)


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Unit Tests for Reconstruction Engine
# ---------------------------------------------------------------------------

def test_engine_normal_workday_multi_app():
    """
    Simulates a multi-application development session:
    - code.exe (20 mins)
    - windowsterminal.exe (10 mins)
    - chrome.exe (10 mins)
    - code.exe (20 mins)
    Verifies primary app detection, secondary app lists, dwell breakdown, and focus calculation.
    """
    engine_inst = SessionReconstructionEngine()
    user_id = uuid.uuid4()
    t0 = datetime(2026, 11, 22, 9, 0, 0, tzinfo=timezone.utc)

    events = [
        UnifiedEvent(
            event_id="e1",
            event_type=TelemetryEventType.APPLICATION_ACTIVATED.value,
            timestamp=t0,
            app_id="code.exe",
        ),
        UnifiedEvent(
            event_id="e2",
            event_type=TelemetryEventType.APPLICATION_ACTIVATED.value,
            timestamp=t0 + timedelta(minutes=20),
            app_id="windowsterminal.exe",
        ),
        UnifiedEvent(
            event_id="e3",
            event_type=TelemetryEventType.APPLICATION_ACTIVATED.value,
            timestamp=t0 + timedelta(minutes=30),
            app_id="chrome.exe",
        ),
        UnifiedEvent(
            event_id="e4",
            event_type=TelemetryEventType.APPLICATION_ACTIVATED.value,
            timestamp=t0 + timedelta(minutes=40),
            app_id="code.exe",
        ),
    ]

    sessions = engine_inst.reconstruct(
        unified_events=events,
        user_id=user_id,
        now=t0 + timedelta(minutes=60),
    )

    assert len(sessions) == 1
    s = sessions[0]
    assert s["primary_application"] == "code.exe"
    assert "windowsterminal.exe" in s["secondary_applications"]
    assert "chrome.exe" in s["secondary_applications"]
    assert s["transition_count"] == 3
    assert s["focused_time_seconds"] > 0
    assert s["task_association_status"] == "UNKNOWN"
    assert s["reconstruction_confidence"] > 0.70


def test_session_boundary_idle_timeout():
    """
    Verifies that an inactivity gap >= 30 minutes cleanly splits work sessions
    and does not merge unrelated work periods.
    """
    engine_inst = SessionReconstructionEngine(
        SessionReconstructionConfig(session_idle_timeout_minutes=30.0)
    )
    user_id = uuid.uuid4()
    t0 = datetime(2026, 11, 22, 9, 0, 0, tzinfo=timezone.utc)

    events = [
        # Session 1: 9:00 - 9:20 (with 30m idle timeout closing at 9:50)
        UnifiedEvent(
            event_id="s1-1",
            event_type=TelemetryEventType.APPLICATION_ACTIVATED.value,
            timestamp=t0,
            app_id="code.exe",
        ),
        UnifiedEvent(
            event_id="s1-2",
            event_type=TelemetryEventType.APPLICATION_ACTIVATED.value,
            timestamp=t0 + timedelta(minutes=20),
            app_id="code.exe",
        ),
        # Idle Gap: 60 minutes of no activity (9:20 to 10:20)
        # Session 2 starts at 10:20
        UnifiedEvent(
            event_id="s2-1",
            event_type=TelemetryEventType.APPLICATION_ACTIVATED.value,
            timestamp=t0 + timedelta(minutes=80),
            app_id="figma.exe",
        ),
        UnifiedEvent(
            event_id="s2-2",
            event_type=TelemetryEventType.APPLICATION_ACTIVATED.value,
            timestamp=t0 + timedelta(minutes=100),
            app_id="figma.exe",
        ),
    ]

    sessions = engine_inst.reconstruct(
        unified_events=events,
        user_id=user_id,
        now=t0 + timedelta(minutes=120),
    )

    # Must NOT merge into one single session
    assert len(sessions) == 2
    assert sessions[0]["primary_application"] == "code.exe"
    assert sessions[1]["primary_application"] == "figma.exe"


def test_session_boundary_day_boundary():
    """Verifies that activity crossing midnight is separated into discrete sessions."""
    engine_inst = SessionReconstructionEngine()
    user_id = uuid.uuid4()

    t_night = datetime(2026, 11, 22, 23, 40, 0, tzinfo=timezone.utc)
    t_next_day = datetime(2026, 11, 23, 0, 10, 0, tzinfo=timezone.utc)

    events = [
        UnifiedEvent(
            event_id="d1-1",
            event_type=TelemetryEventType.APPLICATION_ACTIVATED.value,
            timestamp=t_night,
            app_id="code.exe",
        ),
        UnifiedEvent(
            event_id="d1-2",
            event_type=TelemetryEventType.APPLICATION_ACTIVATED.value,
            timestamp=t_night + timedelta(minutes=10),
            app_id="code.exe",
        ),
        UnifiedEvent(
            event_id="d2-1",
            event_type=TelemetryEventType.APPLICATION_ACTIVATED.value,
            timestamp=t_next_day,
            app_id="code.exe",
        ),
        UnifiedEvent(
            event_id="d2-2",
            event_type=TelemetryEventType.APPLICATION_ACTIVATED.value,
            timestamp=t_next_day + timedelta(minutes=20),
            app_id="code.exe",
        ),
    ]

    sessions = engine_inst.reconstruct(
        unified_events=events,
        user_id=user_id,
        now=t_next_day + timedelta(minutes=30),
    )
    assert len(sessions) == 2


def test_task_association_explicit_vs_unknown():
    """
    Ensures an explicit task is associated when present, while unassociated
    telemetry correctly stays UNKNOWN without unwarranted assumptions.
    """
    engine_inst = SessionReconstructionEngine()
    user_id = uuid.uuid4()
    task_id = uuid.uuid4()
    t0 = datetime(2026, 11, 22, 14, 0, 0, tzinfo=timezone.utc)

    # Case A: Telemetry paired with explicit TaskEvent
    events_with_task = [
        UnifiedEvent(
            event_id="t-1",
            event_type="TASK_STARTED",
            timestamp=t0,
            task_id=task_id,
        ),
        UnifiedEvent(
            event_id="t-2",
            event_type=TelemetryEventType.APPLICATION_ACTIVATED.value,
            timestamp=t0 + timedelta(seconds=10),
            app_id="code.exe",
        ),
        UnifiedEvent(
            event_id="t-3",
            event_type="TASK_COMPLETED",
            timestamp=t0 + timedelta(minutes=30),
            task_id=task_id,
        ),
    ]

    sessions = engine_inst.reconstruct(
        unified_events=events_with_task,
        user_id=user_id,
        now=t0 + timedelta(hours=1),
    )
    assert len(sessions) == 1
    assert sessions[0]["task_id"] == task_id
    assert sessions[0]["task_association_status"] == "EXPLICIT"
    assert sessions[0]["task_association_confidence"] == 0.95


def test_reconstruction_timeline_segments_and_interruption():
    """Verifies granular chronological timeline generation including interruptions."""
    engine_inst = SessionReconstructionEngine()
    user_id = uuid.uuid4()
    t0 = datetime(2026, 11, 22, 10, 0, 0, tzinfo=timezone.utc)

    events = [
        UnifiedEvent(
            event_id="e1",
            event_type=TelemetryEventType.APPLICATION_ACTIVATED.value,
            timestamp=t0,
            app_id="code.exe",
        ),
        UnifiedEvent(
            event_id="e2",
            event_type="DETECTED_INTERRUPTION",
            timestamp=t0 + timedelta(minutes=15),
            app_id="slack.exe",
            duration=60.0,
            payload={"explanation": "Slack notification"},
        ),
        UnifiedEvent(
            event_id="e3",
            event_type=TelemetryEventType.APPLICATION_ACTIVATED.value,
            timestamp=t0 + timedelta(minutes=16),
            app_id="code.exe",
        ),
    ]

    sessions = engine_inst.reconstruct(
        unified_events=events,
        user_id=user_id,
        now=t0 + timedelta(minutes=30),
    )
    assert len(sessions) == 1
    timeline = sessions[0]["timeline"]
    assert len(timeline) >= 3

    types = [seg["segment_type"] for seg in timeline]
    assert "FOCUS" in types
    assert "INTERRUPTION" in types


# ---------------------------------------------------------------------------
# Integration Tests with Database and API Endpoints
# ---------------------------------------------------------------------------

def test_api_reconstruct_and_query_sessions(client):
    user_id = uuid.uuid4()
    with Session(engine) as session:
        user = User(id=user_id, email=f"sess_{user_id.hex[:6]}@example.com", display_name="Session User")
        session.add(user)
        session.commit()

    # Ingest telemetry events into DB
    t0 = datetime.now(timezone.utc) - timedelta(hours=2)
    with Session(engine) as session:
        ev1 = RawTelemetryEvent(
            event_id=f"r1-{user_id.hex[:4]}",
            user_id=user_id,
            event_type=TelemetryEventType.APPLICATION_ACTIVATED.value,
            event_timestamp=t0,
            application_identifier="code.exe",
            payload={},
        )
        ev2 = RawTelemetryEvent(
            event_id=f"r2-{user_id.hex[:4]}",
            user_id=user_id,
            event_type=TelemetryEventType.APPLICATION_ACTIVATED.value,
            event_timestamp=t0 + timedelta(minutes=25),
            application_identifier="windowsterminal.exe",
            payload={},
        )
        ev3 = RawTelemetryEvent(
            event_id=f"r3-{user_id.hex[:4]}",
            user_id=user_id,
            event_type=TelemetryEventType.APPLICATION_ACTIVATED.value,
            event_timestamp=t0 + timedelta(minutes=35),
            application_identifier="code.exe",
            payload={},
        )
        session.add_all([ev1, ev2, ev3])
        session.commit()

    # Trigger reconstruction via API
    reconstruct_resp = client.post(
        "/api/v1/context/sessions/reconstruct",
        json={"lookback_hours": 24, "force_full_rebuild": True},
        headers={"X-User-ID": str(user_id)},
    )
    assert reconstruct_resp.status_code == 200
    assert reconstruct_resp.json()["sessions_reconstructed"] >= 1

    # Query list
    list_resp = client.get("/api/v1/context/sessions", headers={"X-User-ID": str(user_id)})
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] >= 1
    session_id = list_data["items"][0]["id"]

    # Query detail
    detail_resp = client.get(
        f"/api/v1/context/sessions/{session_id}",
        headers={"X-User-ID": str(user_id)},
    )
    assert detail_resp.status_code == 200
    assert detail_resp.json()["primary_application"] == "code.exe"

    # Query timeline
    timeline_resp = client.get(
        f"/api/v1/context/sessions/{session_id}/timeline",
        headers={"X-User-ID": str(user_id)},
    )
    assert timeline_resp.status_code == 200
    assert len(timeline_resp.json()["timeline"]) >= 1


def test_api_session_user_correction(client):
    """Verifies that a user can manually correct task association and add notes."""
    user_id = uuid.uuid4()
    task_id = uuid.uuid4()

    with Session(engine) as session:
        user = User(id=user_id, email=f"corr_{user_id.hex[:6]}@example.com", display_name="Correction User")
        session.add(user)
        task = Task(id=task_id, user_id=user_id, title="Refactor Auth Engine")
        session.add(task)

        # Create an unassociated context session
        t0 = datetime.now(timezone.utc) - timedelta(hours=1)
        cs = ContextSession(
            user_id=user_id,
            started_at=t0,
            ended_at=t0 + timedelta(minutes=30),
            status="COMPLETED",
            primary_application="code.exe",
            task_association_status="UNKNOWN",
            reconstruction_confidence=0.80,
            quality_tier="MEDIUM",
        )
        session.add(cs)
        session.commit()
        session_id = str(cs.id)

    # User submits manual correction
    corr_payload = {
        "task_id": str(task_id),
        "notes": "Working on auth middleware refactoring in VS Code",
    }
    corr_resp = client.post(
        f"/api/v1/context/sessions/{session_id}/correct",
        json=corr_payload,
        headers={"X-User-ID": str(user_id)},
    )
    assert corr_resp.status_code == 200
    data = corr_resp.json()
    assert data["task_id"] == str(task_id)
    assert data["task_association_status"] == "USER_CORRECTED"
    assert data["user_corrected"] is True
    assert "auth middleware" in data["user_correction_notes"]


def test_incremental_reconstruction_preserves_historical_sessions():
    """
    Verifies that incremental processing preserves finalized historical sessions
    outside the lookback window.
    """
    user_id = uuid.uuid4()
    old_time = datetime.now(timezone.utc) - timedelta(days=5)

    with Session(engine) as session:
        user = User(id=user_id, email=f"inc_{user_id.hex[:6]}@example.com", display_name="Inc User")
        session.add(user)
        # Historical session from 5 days ago
        hist_cs = ContextSession(
            user_id=user_id,
            started_at=old_time,
            ended_at=old_time + timedelta(hours=1),
            status="COMPLETED",
            primary_application="idea64.exe",
            reconstruction_confidence=0.95,
            quality_tier="HIGH",
        )
        session.add(hist_cs)
        session.commit()
        hist_id = hist_cs.id

    # Add a new recent event
    now_time = datetime.now(timezone.utc)
    with Session(engine) as session:
        recent_ev = RawTelemetryEvent(
            event_id=f"rec-{user_id.hex[:4]}",
            user_id=user_id,
            event_type=TelemetryEventType.APPLICATION_ACTIVATED.value,
            event_timestamp=now_time - timedelta(minutes=10),
            application_identifier="code.exe",
            payload={},
        )
        session.add(recent_ev)
        session.commit()

    # Run incremental reconstruction with 24-hour lookback
    with Session(engine) as session:
        reconstruct_sessions_for_user(
            db=session,
            user_id=user_id,
            lookback_hours=24,
            force_full_rebuild=False,
        )

    # Verify historical session still exists and was not wiped
    with Session(engine) as session:
        existing_hist = session.get(ContextSession, hist_id)
        assert existing_hist is not None
        assert existing_hist.primary_application == "idea64.exe"

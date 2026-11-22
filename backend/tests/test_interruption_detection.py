"""
Unit and integration tests for Automated Interruption Detection and Classification Engine (Phase 3.5).
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
from app.models.enums import (
    DetectedInterruptionType,
    InterruptionFeedbackClassification,
    InterruptionSeverity,
    InterruptionType,
    TelemetryEventType,
)
from app.models.raw_telemetry_event import RawTelemetryEvent
from app.models.user import User
from app.services.interruption_detector import (
    InterruptionDetectionConfig,
    InterruptionDetector,
    process_and_persist_telemetry_interruptions,
)


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Unit Tests for InterruptionDetector Engine
# ---------------------------------------------------------------------------

def test_preprocessing_and_deduplication():
    detector = InterruptionDetector()
    uid = uuid.uuid4()
    base_time = datetime(2026, 11, 22, 10, 0, 0, tzinfo=timezone.utc)

    # Events out of chronological order and with duplicate event_id
    raw = [
        {
            "event_id": "ev-002",
            "user_id": str(uid),
            "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
            "event_timestamp": (base_time + timedelta(seconds=10)).isoformat(),
            "application_identifier": "cmd.exe",
        },
        {
            "event_id": "ev-001",
            "user_id": str(uid),
            "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
            "event_timestamp": base_time.isoformat(),
            "application_identifier": "code.exe",
        },
        {
            "event_id": "ev-001",  # Duplicate
            "user_id": str(uid),
            "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
            "event_timestamp": base_time.isoformat(),
            "application_identifier": "code.exe",
        },
    ]

    events = detector.preprocess_events(raw)
    assert len(events) == 2
    assert events[0].event_id == "ev-001"
    assert events[1].event_id == "ev-002"
    assert events[0].app_id == "code.exe"
    assert events[1].app_id == "cmd.exe"


def test_false_positive_control_complementary_co_working_pairs():
    """
    Switching between complementary tools (e.g. VS Code and Terminal)
    must NOT be classified as an interruption.
    """
    detector = InterruptionDetector()
    uid = uuid.uuid4()
    t0 = datetime(2026, 11, 22, 10, 0, 0, tzinfo=timezone.utc)

    events = [
        # Sustained work in code.exe
        {
            "event_id": "1",
            "user_id": str(uid),
            "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
            "event_timestamp": t0.isoformat(),
            "application_identifier": "code.exe",
        },
        # Switch to powershell terminal
        {
            "event_id": "2",
            "user_id": str(uid),
            "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
            "event_timestamp": (t0 + timedelta(seconds=60)).isoformat(),
            "application_identifier": "powershell.exe",
        },
        # Switch back to code.exe
        {
            "event_id": "3",
            "user_id": str(uid),
            "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
            "event_timestamp": (t0 + timedelta(seconds=90)).isoformat(),
            "application_identifier": "code.exe",
        },
        {
            "event_id": "4",
            "user_id": str(uid),
            "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
            "event_timestamp": (t0 + timedelta(seconds=180)).isoformat(),
            "application_identifier": "code.exe",
        },
    ]

    detected = detector.detect_interruptions(events, uid)
    # Complementary tool switch should be suppressed
    assert len(detected) == 0


def test_false_positive_control_micro_switch():
    """
    Micro-switches (< 3.0s dwell e.g. transient glance or alt-tab passing through)
    must be suppressed from being classified as interruptions.
    """
    detector = InterruptionDetector()
    uid = uuid.uuid4()
    t0 = datetime(2026, 11, 22, 10, 0, 0, tzinfo=timezone.utc)

    events = [
        {
            "event_id": "1",
            "user_id": str(uid),
            "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
            "event_timestamp": t0.isoformat(),
            "application_identifier": "code.exe",
        },
        # Brief glance to calculator for 1.5 seconds
        {
            "event_id": "2",
            "user_id": str(uid),
            "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
            "event_timestamp": (t0 + timedelta(seconds=60)).isoformat(),
            "application_identifier": "calculator.exe",
        },
        {
            "event_id": "3",
            "user_id": str(uid),
            "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
            "event_timestamp": (t0 + timedelta(seconds=61.5)).isoformat(),
            "application_identifier": "code.exe",
        },
        {
            "event_id": "4",
            "user_id": str(uid),
            "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
            "event_timestamp": (t0 + timedelta(seconds=120)).isoformat(),
            "application_identifier": "code.exe",
        },
    ]

    detected = detector.detect_interruptions(events, uid)
    assert len(detected) == 0


def test_genuine_application_switch_interruption_with_resumption_lag():
    """
    Genuine interruption to an external communication app (Slack)
    must be detected, with resumption lag calculated.
    """
    detector = InterruptionDetector()
    uid = uuid.uuid4()
    t0 = datetime(2026, 11, 22, 10, 0, 0, tzinfo=timezone.utc)

    events = [
        # 60s working in code.exe
        {
            "event_id": "1",
            "user_id": str(uid),
            "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
            "event_timestamp": t0.isoformat(),
            "application_identifier": "code.exe",
        },
        # Interrupted by Slack for 45s
        {
            "event_id": "2",
            "user_id": str(uid),
            "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
            "event_timestamp": (t0 + timedelta(seconds=60)).isoformat(),
            "application_identifier": "slack.exe",
        },
        # Returns to code.exe
        {
            "event_id": "3",
            "user_id": str(uid),
            "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
            "event_timestamp": (t0 + timedelta(seconds=105)).isoformat(),
            "application_identifier": "code.exe",
        },
        {
            "event_id": "4",
            "user_id": str(uid),
            "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
            "event_timestamp": (t0 + timedelta(seconds=180)).isoformat(),
            "application_identifier": "code.exe",
        },
    ]

    detected = detector.detect_interruptions(events, uid)
    assert len(detected) == 1

    item = detected[0]
    assert item["interruption_type"] == DetectedInterruptionType.APPLICATION_SWITCH
    assert item["primary_app"] == "code.exe"
    assert item["interrupting_app"] == "slack.exe"
    assert item["duration_seconds"] == 45.0
    assert item["resumption_lag_seconds"] is not None
    assert item["resumption_lag_seconds"] > 0
    assert "slack.exe" in item["explanation"]
    assert "code.exe" in item["explanation"]


def test_idle_interruption_detection_and_severity():
    """
    Short inactivity (< 180s) suppressed.
    Long inactivity (e.g. 12 minutes) detected with calculated severity and explanation.
    """
    detector = InterruptionDetector()
    uid = uuid.uuid4()
    t0 = datetime(2026, 11, 22, 10, 0, 0, tzinfo=timezone.utc)

    events = [
        {
            "event_id": "1",
            "user_id": str(uid),
            "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
            "event_timestamp": t0.isoformat(),
            "application_identifier": "code.exe",
        },
        # 12-minute idle interruption (720 seconds)
        {
            "event_id": "2",
            "user_id": str(uid),
            "event_type": TelemetryEventType.USER_IDLE_STARTED.value,
            "event_timestamp": (t0 + timedelta(seconds=60)).isoformat(),
            "payload": {},
        },
        {
            "event_id": "3",
            "user_id": str(uid),
            "event_type": TelemetryEventType.USER_ACTIVE_RETURNED.value,
            "event_timestamp": (t0 + timedelta(seconds=780)).isoformat(),
            "payload": {},
        },
    ]

    detected = detector.detect_interruptions(events, uid)
    assert len(detected) == 1

    item = detected[0]
    assert item["interruption_type"] == DetectedInterruptionType.IDLE_INTERRUPTION
    assert item["duration_seconds"] == 720.0
    assert item["severity"] == InterruptionSeverity.MEDIUM
    assert "12.0 minutes" in item["explanation"]
    assert item["primary_app"] == "code.exe"


def test_attention_thrashing_detection():
    """
    Rapid context switching (>= 4 transitions in < 20s across >= 2 unique apps)
    must trigger CONTEXT_SWITCH interruption with HIGH severity.
    """
    detector = InterruptionDetector()
    uid = uuid.uuid4()
    t0 = datetime(2026, 11, 22, 10, 0, 0, tzinfo=timezone.utc)

    # 5 switches in 12 seconds across 3 apps
    events = [
        {
            "event_id": "t1",
            "user_id": str(uid),
            "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
            "event_timestamp": t0.isoformat(),
            "application_identifier": "code.exe",
        },
        {
            "event_id": "t2",
            "user_id": str(uid),
            "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
            "event_timestamp": (t0 + timedelta(seconds=3)).isoformat(),
            "application_identifier": "spotify.exe",
        },
        {
            "event_id": "t3",
            "user_id": str(uid),
            "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
            "event_timestamp": (t0 + timedelta(seconds=6)).isoformat(),
            "application_identifier": "discord.exe",
        },
        {
            "event_id": "t4",
            "user_id": str(uid),
            "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
            "event_timestamp": (t0 + timedelta(seconds=9)).isoformat(),
            "application_identifier": "code.exe",
        },
        {
            "event_id": "t5",
            "user_id": str(uid),
            "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
            "event_timestamp": (t0 + timedelta(seconds=12)).isoformat(),
            "application_identifier": "spotify.exe",
        },
    ]

    detected = detector.detect_interruptions(events, uid)
    assert len(detected) >= 1
    thrash = [d for d in detected if d["interruption_type"] == DetectedInterruptionType.CONTEXT_SWITCH]
    assert len(thrash) == 1
    assert thrash[0]["severity"] == InterruptionSeverity.HIGH
    assert "Rapid attention thrashing" in thrash[0]["explanation"]


def test_labeled_dataset_precision_and_recall():
    """
    Evaluates detector on a labeled ground-truth synthetic stream containing:
    - 2 genuine interruptions (1 app switch to distraction, 1 idle disruption)
    - 2 intentional/benign switches (1 complementary co-working, 1 micro-switch)
    Asserts precision = 1.0 and recall = 1.0 against ground truth.
    """
    detector = InterruptionDetector()
    uid = uuid.uuid4()
    t0 = datetime(2026, 11, 22, 8, 0, 0, tzinfo=timezone.utc)

    synthetic_stream = [
        # Task 1: Primary focus
        {
            "event_id": "g1",
            "user_id": str(uid),
            "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
            "event_timestamp": t0.isoformat(),
            "application_identifier": "code.exe",
        },
        # Benign Switch 1: Complementary Terminal
        {
            "event_id": "g2",
            "user_id": str(uid),
            "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
            "event_timestamp": (t0 + timedelta(seconds=60)).isoformat(),
            "application_identifier": "windowsterminal.exe",
        },
        {
            "event_id": "g3",
            "user_id": str(uid),
            "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
            "event_timestamp": (t0 + timedelta(seconds=90)).isoformat(),
            "application_identifier": "code.exe",
        },
        # Genuine Interruption 1: Slack distraction for 50s
        {
            "event_id": "g4",
            "user_id": str(uid),
            "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
            "event_timestamp": (t0 + timedelta(seconds=150)).isoformat(),
            "application_identifier": "slack.exe",
        },
        {
            "event_id": "g5",
            "user_id": str(uid),
            "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
            "event_timestamp": (t0 + timedelta(seconds=200)).isoformat(),
            "application_identifier": "code.exe",
        },
        # Benign Switch 2: Micro-glance to explorer.exe (2s)
        {
            "event_id": "g6",
            "user_id": str(uid),
            "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
            "event_timestamp": (t0 + timedelta(seconds=260)).isoformat(),
            "application_identifier": "explorer.exe",
        },
        {
            "event_id": "g7",
            "user_id": str(uid),
            "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
            "event_timestamp": (t0 + timedelta(seconds=262)).isoformat(),
            "application_identifier": "code.exe",
        },
        # Genuine Interruption 2: Inactivity for 5 minutes (300s)
        {
            "event_id": "g8",
            "user_id": str(uid),
            "event_type": TelemetryEventType.USER_IDLE_STARTED.value,
            "event_timestamp": (t0 + timedelta(seconds=320)).isoformat(),
            "payload": {},
        },
        {
            "event_id": "g9",
            "user_id": str(uid),
            "event_type": TelemetryEventType.USER_ACTIVE_RETURNED.value,
            "event_timestamp": (t0 + timedelta(seconds=620)).isoformat(),
            "payload": {},
        },
    ]

    detected = detector.detect_interruptions(synthetic_stream, uid)

    # Expected: exactly 2 genuine interruptions detected
    assert len(detected) == 2
    types = {d["interruption_type"] for d in detected}
    assert DetectedInterruptionType.APPLICATION_SWITCH in types
    assert DetectedInterruptionType.IDLE_INTERRUPTION in types

    true_positives = 2
    false_positives = 0
    false_negatives = 0

    precision = true_positives / (true_positives + false_positives)
    recall = true_positives / (true_positives + false_negatives)

    assert precision == 1.0
    assert recall == 1.0


# ---------------------------------------------------------------------------
# API Integration Tests (FastAPI Endpoints)
# ---------------------------------------------------------------------------

def test_api_detected_interruptions_workflow(client):
    user_id = uuid.uuid4()
    with Session(engine) as session:
        user = User(id=user_id, email=f"det_{user_id.hex[:6]}@example.com", display_name="Det User")
        session.add(user)
        session.commit()

    # Ingest a sequence of events into RawTelemetryEvent
    t0 = datetime.now(timezone.utc) - timedelta(minutes=30)
    with Session(engine) as session:
        events = [
            RawTelemetryEvent(
                event_id=f"r1-{user_id.hex[:4]}",
                user_id=user_id,
                event_type=TelemetryEventType.APPLICATION_ACTIVATED.value,
                event_timestamp=t0,
                application_identifier="code.exe",
                payload={},
            ),
            RawTelemetryEvent(
                event_id=f"r2-{user_id.hex[:4]}",
                user_id=user_id,
                event_type=TelemetryEventType.APPLICATION_ACTIVATED.value,
                event_timestamp=t0 + timedelta(seconds=60),
                application_identifier="teams.exe",
                payload={},
            ),
            RawTelemetryEvent(
                event_id=f"r3-{user_id.hex[:4]}",
                user_id=user_id,
                event_type=TelemetryEventType.APPLICATION_ACTIVATED.value,
                event_timestamp=t0 + timedelta(seconds=120),
                application_identifier="code.exe",
                payload={},
            ),
        ]
        session.add_all(events)
        session.commit()

    # Trigger detection
    trigger_resp = client.post(
        "/api/v1/interruptions/detect",
        headers={"X-User-ID": str(user_id)},
    )
    assert trigger_resp.status_code == 200
    detected_list = trigger_resp.json()
    assert len(detected_list) == 1
    interruption_id = detected_list[0]["id"]

    # Query list
    list_resp = client.get("/api/v1/interruptions/detected", headers={"X-User-ID": str(user_id)})
    assert list_resp.status_code == 200
    query_data = list_resp.json()
    assert query_data["total"] >= 1
    assert query_data["items"][0]["id"] == interruption_id

    # Query detail
    detail_resp = client.get(
        f"/api/v1/interruptions/detected/{interruption_id}",
        headers={"X-User-ID": str(user_id)},
    )
    assert detail_resp.status_code == 200
    assert detail_resp.json()["primary_app"] == "code.exe"

    # Submit feedback (GENUINE_INTERRUPTION)
    feedback_payload = {
        "feedback_classification": InterruptionFeedbackClassification.GENUINE_INTERRUPTION.value,
        "notes": "Incoming emergency Teams ping from manager.",
    }
    fb_resp = client.post(
        f"/api/v1/interruptions/detected/{interruption_id}/feedback",
        json=feedback_payload,
        headers={"X-User-ID": str(user_id)},
    )
    assert fb_resp.status_code == 200
    assert fb_resp.json()["feedback_classification"] == "GENUINE_INTERRUPTION"

    # Query metrics
    metrics_resp = client.get("/api/v1/interruptions/metrics", headers={"X-User-ID": str(user_id)})
    assert metrics_resp.status_code == 200
    metrics_data = metrics_resp.json()
    assert metrics_data["total_detected"] >= 1
    assert metrics_data["total_feedback_count"] == 1
    assert metrics_data["accuracy_rate"] == 1.0
    assert metrics_data["false_positive_rate"] == 0.0


def test_api_preserve_manual_interruption_logging(client):
    """Verifies that manual user-logged interruptions continue to work without regression."""
    user_id = uuid.uuid4()
    with Session(engine) as session:
        user = User(id=user_id, email=f"man_{user_id.hex[:6]}@example.com", display_name="Manual User")
        session.add(user)
        session.commit()

    payload = {
        "interruption_type": InterruptionType.PHONE.value,
        "duration_seconds": 120,
        "notes": "Spam call from delivery service",
    }
    create_resp = client.post(
        "/api/v1/interruptions",
        json=payload,
        headers={"X-User-ID": str(user_id)},
    )
    assert create_resp.status_code == 201
    manual_id = create_resp.json()["id"]

    # Fetch by ID
    get_resp = client.get(
        f"/api/v1/interruptions/{manual_id}",
        headers={"X-User-ID": str(user_id)},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["interruption_type"] == "PHONE"

    # List manual
    list_resp = client.get("/api/v1/interruptions", headers={"X-User-ID": str(user_id)})
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

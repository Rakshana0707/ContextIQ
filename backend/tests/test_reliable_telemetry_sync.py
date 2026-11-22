"""Comprehensive integration tests for reliable telemetry ingestion, idempotency, ordering, and status."""
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["APP_ENV"] = "development"
os.environ.setdefault("DATABASE_URL", "sqlite:///./_test_sync.db")

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

# Register SQLite compilation for Postgres JSONB in tests
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

import app.models  # Register all models on Base
from app.db.session import Base, engine
from app.main import app
from app.models.enums import ConsentStatus, TelemetryCategory
from app.models.telemetry_consent import TelemetryConsent, UserPrivacySettings
from app.models.raw_telemetry_event import RawTelemetryEvent
from app.models.user import User


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def active_user(client):
    user_id = uuid.uuid4()
    with Session(engine) as session:
        user = User(
            id=user_id,
            email=f"sync_user_{user_id.hex[:6]}@example.com",
            display_name="Sync User",
        )
        session.add(user)

        # Grant active telemetry consent
        consent = TelemetryConsent(
            user_id=user_id,
            consent_version="1.0.0",
            consent_status=ConsentStatus.GRANTED,
            enabled_categories=[
                TelemetryCategory.APP_TRANSITIONS.value,
                TelemetryCategory.INACTIVITY_DETECTION.value,
                TelemetryCategory.LOCAL_STORAGE.value,
                TelemetryCategory.SERVER_SYNC.value,
            ],
            device_id="device-test-hash-123",
            granted_timestamp=datetime.now(timezone.utc),
            updated_timestamp=datetime.now(timezone.utc),
        )
        session.add(consent)

        # Active settings (not paused)
        settings = UserPrivacySettings(
            user_id=user_id,
            is_paused=False,
            raw_event_retention_days=30,
        )
        session.add(settings)
        session.commit()

    return user_id, "device-test-hash-123"


def test_single_event_ingestion(client, active_user):
    user_id, device_id = active_user
    payload = {
        "event_id": f"single-ev-{uuid.uuid4().hex[:8]}",
        "user_id": str(user_id),
        "device_id": device_id,
        "event_type": "agent_started",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "desktop_agent_windows",
        "schema_version": "1.0.0",
        "application_identifier": "contextiq-agent.exe",
        "payload": {"version": "1.0.0", "startup_mode": "MANUAL"},
    }

    response = client.post(
        "/api/v1/telemetry/events",
        json=payload,
        headers={"X-User-ID": str(user_id), "X-Device-ID": device_id},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["received"] == 1
    assert data["accepted"] == 1
    assert data["duplicates"] == 0
    assert payload["event_id"] in data["synced_event_ids"]


def test_batch_ingestion_and_idempotent_deduplication(client, active_user):
    user_id, device_id = active_user
    t0 = datetime.now(timezone.utc)

    event_a_id = f"idemp-a-{uuid.uuid4().hex[:8]}"
    event_b_id = f"idemp-b-{uuid.uuid4().hex[:8]}"

    batch_payload = {
        "events": [
            {
                "event_id": event_a_id,
                "user_id": str(user_id),
                "device_id": device_id,
                "event_type": "application_activated",
                "event_timestamp": t0.isoformat(),
                "application_identifier": "code.exe",
                "payload": {"process_id": 100},
            },
            {
                "event_id": event_b_id,
                "user_id": str(user_id),
                "device_id": device_id,
                "event_type": "application_deactivated",
                "event_timestamp": (t0 + timedelta(seconds=120)).isoformat(),
                "application_identifier": "code.exe",
                "payload": {"duration_seconds": 120.0},
            },
        ]
    }

    # Pass 1: Initial upload
    resp1 = client.post(
        "/api/v1/telemetry/events/batch",
        json=batch_payload,
        headers={"X-User-ID": str(user_id), "X-Device-ID": device_id},
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["received"] == 2
    assert data1["accepted"] == 2
    assert data1["duplicates"] == 0
    assert len(data1["synced_event_ids"]) == 2

    # Pass 2: Replay identical batch (Idempotency test)
    resp2 = client.post(
        "/api/v1/telemetry/events/batch",
        json=batch_payload,
        headers={"X-User-ID": str(user_id), "X-Device-ID": device_id},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["received"] == 2
    assert data2["accepted"] == 0  # 0 new rows inserted
    assert data2["duplicates"] == 2  # 2 recognized duplicates
    # Crucial: server still acknowledges them so agent marks SYNCED locally!
    assert len(data2["synced_event_ids"]) == 2
    assert set(data2["duplicate_event_ids"]) == {event_a_id, event_b_id}

    # Verify database has exactly 1 row per event_id
    with Session(engine) as session:
        count_a = session.query(RawTelemetryEvent).filter_by(event_id=event_a_id).count()
        count_b = session.query(RawTelemetryEvent).filter_by(event_id=event_b_id).count()
        assert count_a == 1
        assert count_b == 1


def test_rejection_without_consent(client):
    unconsented_user_id = uuid.uuid4()
    with Session(engine) as session:
        user = User(
            id=unconsented_user_id,
            email=f"noconsent_{unconsented_user_id.hex[:6]}@example.com",
            display_name="No Consent User",
        )
        session.add(user)
        session.commit()

    payload = {
        "events": [
            {
                "event_id": f"ev-unauth-{uuid.uuid4().hex[:8]}",
                "user_id": str(unconsented_user_id),
                "event_type": "application_activated",
                "event_timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": {},
            }
        ]
    }

    response = client.post(
        "/api/v1/telemetry/events/batch",
        json=payload,
        headers={"X-User-ID": str(unconsented_user_id)},
    )
    assert response.status_code == 403
    assert "consent is required" in response.json()["detail"].lower()


def test_rejection_when_monitoring_paused(client, active_user):
    user_id, device_id = active_user

    # Pause user collection
    with Session(engine) as session:
        settings = session.query(UserPrivacySettings).filter_by(user_id=user_id).first()
        settings.is_paused = True
        session.commit()

    payload = {
        "events": [
            {
                "event_id": f"ev-paused-{uuid.uuid4().hex[:8]}",
                "user_id": str(user_id),
                "event_type": "application_activated",
                "event_timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": {},
            }
        ]
    }

    response = client.post(
        "/api/v1/telemetry/events/batch",
        json=payload,
        headers={"X-User-ID": str(user_id)},
    )
    assert response.status_code == 403
    assert "paused" in response.json()["detail"].lower()

    # Unpause user for subsequent tests
    with Session(engine) as session:
        settings = session.query(UserPrivacySettings).filter_by(user_id=user_id).first()
        settings.is_paused = False
        session.commit()


def test_out_of_order_events_query_sorting(client, active_user):
    user_id, device_id = active_user
    base_time = datetime(2026, 11, 22, 12, 0, 0, tzinfo=timezone.utc)

    # Ingest in out-of-order sequence: Event 3 (12:30), Event 1 (12:00), Event 2 (12:15)
    t3 = base_time + timedelta(minutes=30)
    t1 = base_time
    t2 = base_time + timedelta(minutes=15)

    ev3_id = f"ooo-3-{uuid.uuid4().hex[:6]}"
    ev1_id = f"ooo-1-{uuid.uuid4().hex[:6]}"
    ev2_id = f"ooo-2-{uuid.uuid4().hex[:6]}"

    batch = {
        "events": [
            {
                "event_id": ev3_id,
                "user_id": str(user_id),
                "device_id": device_id,
                "event_type": "application_activated",
                "event_timestamp": t3.isoformat(),
                "application_identifier": "browser.exe",
                "payload": {"step": 3},
            },
            {
                "event_id": ev1_id,
                "user_id": str(user_id),
                "device_id": device_id,
                "event_type": "application_activated",
                "event_timestamp": t1.isoformat(),
                "application_identifier": "browser.exe",
                "payload": {"step": 1},
            },
            {
                "event_id": ev2_id,
                "user_id": str(user_id),
                "device_id": device_id,
                "event_type": "application_activated",
                "event_timestamp": t2.isoformat(),
                "application_identifier": "browser.exe",
                "payload": {"step": 2},
            },
        ]
    }

    res = client.post(
        "/api/v1/telemetry/events/batch",
        json=batch,
        headers={"X-User-ID": str(user_id), "X-Device-ID": device_id},
    )
    assert res.status_code == 200

    # Query events for user: must return sorted by event_timestamp ASC (t1, then t2, then t3)
    query_res = client.get(
        "/api/v1/telemetry/events",
        params={
            "user_id": str(user_id),
            "application_identifier": "browser.exe",
            "start_time": base_time.isoformat(),
        },
        headers={"X-User-ID": str(user_id)},
    )
    assert query_res.status_code == 200
    items = query_res.json()["items"]
    assert len(items) >= 3

    # Filter to our 3 specific events
    filtered = [i for i in items if i["event_id"] in (ev1_id, ev2_id, ev3_id)]
    assert len(filtered) == 3
    assert filtered[0]["event_id"] == ev1_id
    assert filtered[0]["payload"]["step"] == 1
    assert filtered[1]["event_id"] == ev2_id
    assert filtered[1]["payload"]["step"] == 2
    assert filtered[2]["event_id"] == ev3_id
    assert filtered[2]["payload"]["step"] == 3


def test_agent_status_endpoint(client, active_user):
    user_id, device_id = active_user

    # Post an event first to test status metrics
    client.post(
        "/api/v1/telemetry/events",
        json={
            "event_id": f"status-ev-{uuid.uuid4().hex[:8]}",
            "user_id": str(user_id),
            "device_id": device_id,
            "event_type": "heartbeat",
            "event_timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {"uptime_seconds": 100},
        },
        headers={"X-User-ID": str(user_id), "X-Device-ID": device_id},
    )

    response = client.get(
        "/api/v1/telemetry/agent/status",
        headers={"X-User-ID": str(user_id), "X-Device-ID": device_id},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == str(user_id)
    assert data["device_id"] == device_id
    assert data["consent_status"] == "GRANTED"
    assert data["is_paused"] is False
    assert data["total_events_ingested"] > 0
    assert data["last_event_timestamp"] is not None
    assert data["last_ingestion_timestamp"] is not None
    assert "APP_TRANSITIONS" in data["active_categories"]

"""Comprehensive unit and integration test suite for cross-device synchronization and unified timeline (Phase 5.7)."""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add backend directory and project root to sys.path
backend_dir = Path(__file__).resolve().parents[1]
project_root = backend_dir.parent
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(project_root))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

# Teach SQLite how to compile Postgres JSONB columns
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

os.environ["APP_ENV"] = "development"
os.environ["SECRET_KEY"] = "test-master-secret-for-phase5-encryption"
os.environ["DATABASE_URL"] = "sqlite:///./_test_integrations.db"

from app.db.session import Base, engine
from app.main import app
from app.models.detected_interruption import DetectedInterruption
from app.models.enums import DetectedInterruptionType, InterruptionSeverity, TaskEventType, TaskPriority, TaskStatus
from app.models.external_calendar_event import ExternalCalendarEvent
from app.models.raw_telemetry_event import RawTelemetryEvent
from app.models.task import Task
from app.models.task_event import TaskEvent
from app.models.user import User
from app.models.user_device import UserDevice
from app.schemas.device import DeviceRegisterRequest
from app.schemas.timeline import CrossDeviceSyncRequest
from app.services.device_service import DeviceService
from app.services.timeline_service import TimelineService

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        session.query(RawTelemetryEvent).delete()
        session.query(UserDevice).delete()
        session.query(TaskEvent).delete()
        session.query(DetectedInterruption).delete()
        session.query(ExternalCalendarEvent).delete()
        session.commit()
    yield


@pytest.fixture
def test_user():
    user_id = uuid.uuid4()
    with Session(engine) as session:
        user = User(
            id=user_id,
            email=f"crossdev_{user_id.hex[:6]}@contextiq.ai",
            hashed_password="test_hashed_password",
            display_name="Cross Device Test User",
            is_active=True,
        )
        session.add(user)
        session.commit()
    return user_id


# ============================================================================
# 1. TASK 2: DEVICE REGISTRY & REVOCATION
# ============================================================================

def test_device_registration_and_update(test_user):
    """Registering devices records hardware identity and platform metadata."""
    with Session(engine) as session:
        # Register Windows Desktop
        desktop_req = DeviceRegisterRequest(
            device_id="desktop-hw-hash-12345",
            device_type="DESKTOP",
            platform="WINDOWS",
            device_name="ThinkPad P1 Gen 6",
            application_version="3.6.0",
            device_metadata={"os_build": "22631.3007", "cpu_cores": 16},
        )
        desktop = DeviceService.register_device(session, test_user, desktop_req)
        assert desktop.device_id == "desktop-hw-hash-12345"
        assert desktop.platform == "WINDOWS"
        assert desktop.is_active is True
        assert desktop.connection_status == "ONLINE"

        # Register Mobile Phone
        mobile_req = DeviceRegisterRequest(
            device_id="mobile-phone-pixel9-67890",
            device_type="MOBILE",
            platform="ANDROID",
            device_name="Pixel 9 Pro",
            application_version="5.6.0",
            device_metadata={"manufacturer": "Google", "api_level": 35},
        )
        mobile = DeviceService.register_device(session, test_user, mobile_req)
        assert mobile.device_id == "mobile-phone-pixel9-67890"
        assert mobile.device_type == "MOBILE"

        # List devices
        devices = DeviceService.list_devices(session, test_user)
        assert len(devices) == 2
        device_ids = {d.device_id for d in devices}
        assert "desktop-hw-hash-12345" in device_ids
        assert "mobile-phone-pixel9-67890" in device_ids


def test_device_access_revocation_blocks_subsequent_telemetry(test_user):
    """Revoking device access disables future synchronization and rejects requests with HTTP 403."""
    with Session(engine) as session:
        req = DeviceRegisterRequest(
            device_id="device-to-revoke-999",
            device_type="MOBILE",
            platform="IOS",
            device_name="iPhone 16 Pro",
        )
        DeviceService.register_device(session, test_user, req)

        # Revoke device
        revoked = DeviceService.revoke_device(session, test_user, "device-to-revoke-999")
        assert revoked.is_active is False
        assert revoked.connection_status == "REVOKED"
        assert revoked.revoked_at is not None

        # Attempting to sync from revoked device must be rejected with 403
        sync_req = CrossDeviceSyncRequest(
            device_id="device-to-revoke-999",
            client_timestamp=datetime.now(timezone.utc),
            events=[{"event_id": "ev-blocked-1", "event_type": "APP_FOCUS"}],
        )

        with pytest.raises(Exception) as excinfo:
            TimelineService.sync_device_events(session, test_user, sync_req)
        assert "revoked" in str(excinfo.value).lower()


# ============================================================================
# 2. TASK 4 & 5: CROSS-DEVICE SYNC & TEMPORAL CONSISTENCY
# ============================================================================

def test_cross_device_sync_idempotency_and_clock_skew(test_user):
    """Sync calculates clock skew drift and safely deduplicates identical event IDs."""
    with Session(engine) as session:
        # Pre-register device
        DeviceService.register_device(
            session,
            test_user,
            DeviceRegisterRequest(
                device_id="desktop-sync-device",
                device_type="DESKTOP",
                platform="WINDOWS",
            ),
        )

        now = datetime.now(timezone.utc)
        # Client clock is 3.5 seconds behind server
        client_ts = now - timedelta(seconds=3.5)

        event_payload = {
            "event_id": "unique-sync-event-1",
            "event_type": "APPLICATION_ACTIVATED",
            "application_identifier": "Code.exe",
            "event_timestamp": client_ts.isoformat(),
            "source": "desktop_agent_windows",
        }

        sync_req = CrossDeviceSyncRequest(
            device_id="desktop-sync-device",
            client_timestamp=client_ts,
            events=[event_payload],
        )

        # First ingestion
        resp1 = TimelineService.sync_device_events(session, test_user, sync_req)
        assert resp1.received == 1
        assert resp1.ingested == 1
        assert resp1.dropped_duplicates == 0
        assert resp1.estimated_clock_skew_seconds > 0.0

        # Verify ingested record
        ev_record = session.scalar(
            select(RawTelemetryEvent).where(RawTelemetryEvent.event_id == "unique-sync-event-1")
        )
        assert ev_record is not None
        assert ev_record.application_identifier == "Code.exe"
        # Occurrence timestamp preserves client time
        assert ev_record.event_timestamp is not None
        assert ev_record.ingestion_timestamp is not None

        # Second ingestion with duplicate event_id must drop duplicate cleanly
        resp2 = TimelineService.sync_device_events(session, test_user, sync_req)
        assert resp2.received == 1
        assert resp2.ingested == 0
        assert resp2.dropped_duplicates == 1


# ============================================================================
# 3. TASK 6 & 7: CROSS-DEVICE SESSION RECONSTRUCTION
# ============================================================================

def test_cross_device_session_reconstruction_spans_laptop_and_mobile(test_user):
    """
    Simulates:
      09:00 - Laptop coding activity (DESKTOP)
      09:30 - Mobile notification/interruption (MOBILE)
      09:35 - Laptop resumption (DESKTOP)
    Verifies that the session seamlessly spans devices with transition counts.
    """
    now = datetime.now(timezone.utc)
    base_time = now.replace(hour=9, minute=0, second=0, microsecond=0)

    with Session(engine) as session:
        # Pre-register devices
        DeviceService.register_device(
            session,
            test_user,
            DeviceRegisterRequest(
                device_id="laptop-workstation",
                device_type="DESKTOP",
                platform="WINDOWS",
                device_name="ThinkPad",
            ),
        )
        DeviceService.register_device(
            session,
            test_user,
            DeviceRegisterRequest(
                device_id="mobile-phone",
                device_type="MOBILE",
                platform="ANDROID",
                device_name="Pixel 9",
            ),
        )

        # 1. 09:00 Laptop task activity
        ev1 = RawTelemetryEvent(
            event_id="t-ev-laptop-1",
            user_id=test_user,
            device_id="laptop-workstation",
            event_type="APPLICATION_ACTIVATED",
            application_identifier="devenv.exe",
            event_timestamp=base_time,
            ingestion_timestamp=base_time,
            source="desktop_agent_windows",
            payload={"device_type": "DESKTOP"},
        )
        # 2. 09:20 Mobile distraction / interruption
        ev2 = RawTelemetryEvent(
            event_id="t-ev-mobile-2",
            user_id=test_user,
            device_id="mobile-phone",
            event_type="APPLICATION_ACTIVATED",
            application_identifier="com.slack.mobile",
            event_timestamp=base_time + timedelta(minutes=20),
            ingestion_timestamp=base_time + timedelta(minutes=20),
            source="mobile_android",
            payload={"device_type": "MOBILE"},
        )
        # 3. 09:25 Laptop return
        ev3 = RawTelemetryEvent(
            event_id="t-ev-laptop-3",
            user_id=test_user,
            device_id="laptop-workstation",
            event_type="APPLICATION_ACTIVATED",
            application_identifier="devenv.exe",
            event_timestamp=base_time + timedelta(minutes=25),
            ingestion_timestamp=base_time + timedelta(minutes=25),
            source="desktop_agent_windows",
            payload={"device_type": "DESKTOP"},
        )
        session.add_all([ev1, ev2, ev3])
        session.commit()

        sessions = TimelineService.get_cross_device_sessions(session, test_user, lookback_hours=48)
        assert len(sessions) > 0

        target_session = sessions[0]
        # Must detect cross-device transitions (Laptop -> Mobile -> Laptop = 2 transitions)
        assert target_session.device_transitions_count >= 2
        # Device time breakdown must track both devices
        assert "DESKTOP" in target_session.device_time_breakdown
        assert "MOBILE" in target_session.device_time_breakdown
        assert target_session.cross_device_interruption_seconds > 0.0


# ============================================================================
# 4. TASK 8: REST API ENDPOINTS
# ============================================================================

def test_api_device_registry_and_timeline_lifecycle(test_user):
    """Tests /api/v1/devices and /api/v1/activity/timeline endpoints."""
    headers = {"X-User-Id": str(test_user)}

    # 1. Register Device via API
    reg_resp = client.post(
        "/api/v1/devices/register",
        json={
            "device_id": "api-test-macbook",
            "device_type": "DESKTOP",
            "platform": "MACOS",
            "device_name": "MacBook Air M3",
            "application_version": "1.0.0",
        },
        headers=headers,
    )
    assert reg_resp.status_code == 201
    assert reg_resp.json()["device_name"] == "MacBook Air M3"

    # 2. List Devices via API
    list_resp = client.get("/api/v1/devices", headers=headers)
    assert list_resp.status_code == 200
    assert any(d["device_id"] == "api-test-macbook" for d in list_resp.json())

    # 3. Ingest Batch via Sync Endpoint
    now_iso = datetime.now(timezone.utc).isoformat()
    sync_resp = client.post(
        "/api/v1/activity/sync",
        json={
            "device_id": "api-test-macbook",
            "client_timestamp": now_iso,
            "events": [
                {
                    "event_id": "api-ev-1",
                    "event_type": "APPLICATION_ACTIVATED",
                    "application_identifier": "Terminal",
                    "event_timestamp": now_iso,
                }
            ],
        },
        headers=headers,
    )
    assert sync_resp.status_code == 200
    assert sync_resp.json()["ingested"] == 1

    # 4. Query Unified Timeline via API
    tl_resp = client.get("/api/v1/activity/timeline?device_id=api-test-macbook", headers=headers)
    assert tl_resp.status_code == 200
    events = tl_resp.json()
    assert len(events) >= 1
    assert events[0]["application_identifier"] == "Terminal"
    assert events[0]["device_name"] == "MacBook Air M3"

    # 5. Revoke Device via API
    del_resp = client.delete("/api/v1/devices/api-test-macbook", headers=headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "REVOKED"

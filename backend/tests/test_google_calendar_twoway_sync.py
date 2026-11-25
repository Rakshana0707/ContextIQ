"""Unit and integration test suite for Google Calendar two-way synchronization."""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add backend directory and project root to sys.path
backend_dir = Path(__file__).resolve().parents[1]
project_root = backend_dir.parent
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(project_root))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
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
from app.models.calendar_integration import CalendarCredential, CalendarIntegration, CalendarSyncState
from app.models.external_calendar_event import ExternalCalendarEvent
from app.models.user import User
from app.schemas.google_calendar import GoogleEventCreate, GoogleEventUpdate
from app.services import google_sync_service
from app.services.integration_service import get_token_manager
from integrations.app.core.encryption import TokenVault
from integrations.app.core.token_manager import TokenManager
from integrations.app.providers.google.google_calendar_provider import GoogleCalendarProvider
from integrations.app.schemas.integration_schemas import (
    CalendarDTO,
    CalendarEventDTO,
    ConnectionStatus,
    EventStatus,
    EventTransparency,
    OAuthTokenBundle,
    SyncResult,
)


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def test_user():
    uid = uuid.uuid4()
    with Session(engine) as session:
        u = User(
            id=uid,
            email=f"googleuser_{uid.hex[:6]}@example.com",
            display_name="Google Sync User",
        )
        session.add(u)
        session.commit()
    return uid


@pytest.fixture
def connected_google_integration(test_user):
    token_mgr = get_token_manager()
    bundle = OAuthTokenBundle(
        access_token="ya29.initial_test_access_token",
        refresh_token="1//initial_refresh_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        scope=[
            "https://www.googleapis.com/auth/calendar.events",
            "https://www.googleapis.com/auth/userinfo.email",
        ],
    )
    enc_access, enc_refresh = token_mgr.encrypt_credentials(bundle, user_id=test_user, provider="google_calendar")

    with Session(engine) as session:
        integration = CalendarIntegration(
            user_id=test_user,
            provider="google_calendar",
            provider_account_id="google-sub-9988",
            provider_email="sync.user@gmail.com",
            connection_status=ConnectionStatus.CONNECTED.value,
            granted_scopes=bundle.scope,
            is_active=True,
        )
        session.add(integration)
        session.flush()

        credential = CalendarCredential(
            integration_id=integration.id,
            encrypted_access_token=enc_access,
            encrypted_refresh_token=enc_refresh,
            token_type="Bearer",
            expiration_timestamp=bundle.expires_at,
            credential_version=1,
        )
        session.add(credential)
        session.commit()
        session.refresh(integration)
        return integration.id, test_user


# ============================================================================
# 1. TASK 1: GOOGLE API SETUP & PROVIDER ABSTRACTION
# ============================================================================

def test_google_provider_scopes_and_auth_url():
    provider = GoogleCalendarProvider(client_id="mock-client-id")
    assert "https://www.googleapis.com/auth/calendar.events.readonly" in provider.default_scopes
    assert "https://www.googleapis.com/auth/calendar.events" in provider.write_scopes

    # Minimal scope authorization URL
    auth_url = provider.get_authorization_url(
        redirect_uri="http://localhost:3000/callback",
        state="state-token-123",
        code_challenge="pkce-challenge-abc",
        request_write_access=False,
    )
    assert "accounts.google.com" in auth_url
    assert "calendar.events.readonly" in auth_url
    assert "state=state-token-123" in auth_url
    assert "code_challenge=pkce-challenge-abc" in auth_url

    # Write access requested for two-way sync
    auth_url_write = provider.get_authorization_url(
        redirect_uri="http://localhost:3000/callback",
        state="state-token-123",
        request_write_access=True,
    )
    assert "calendar.events" in auth_url_write


def test_google_provider_authenticate_and_refresh():
    provider = GoogleCalendarProvider(client_id="test-cid", client_secret="test-sec")

    # Mock token exchange
    with patch("httpx.Client.post") as mock_post, patch("httpx.Client.get") as mock_get:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "access_token": "ya29.new_token",
            "refresh_token": "1//refresh_xyz",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "https://www.googleapis.com/auth/calendar.events",
        }
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "email": "user@gmail.com",
            "id": "google-uid-123",
        }

        bundle = provider.authenticate(auth_code="auth-code-123", redirect_uri="http://localhost:3000/callback")
        assert bundle.access_token == "ya29.new_token"
        assert bundle.refresh_token == "1//refresh_xyz"
        assert bundle.provider_email == "user@gmail.com"

        # Test token refresh
        mock_post.return_value.json.return_value = {
            "access_token": "ya29.refreshed_token",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
        refreshed = provider.refresh_credentials("1//refresh_xyz")
        assert refreshed.access_token == "ya29.refreshed_token"
        assert refreshed.refresh_token == "1//refresh_xyz"


# ============================================================================
# 2. TASK 2 & 6: EVENT EXTRACTION, PRIVACY REDACTION & RECURRENCE
# ============================================================================

def test_google_provider_parse_event_and_privacy_redaction():
    provider = GoogleCalendarProvider()

    # Regular public meeting
    item_public = {
        "id": "evt-pub-1",
        "summary": "Team Sync Meeting",
        "description": "Sensitive team project discussions",
        "location": "Room 402",
        "start": {"dateTime": "2026-11-25T10:00:00Z", "timeZone": "America/New_York"},
        "end": {"dateTime": "2026-11-25T11:00:00Z", "timeZone": "America/New_York"},
        "transparency": "opaque",
        "status": "confirmed",
        "visibility": "default",
        "updated": "2026-11-24T12:00:00.000Z",
        "organizer": {"email": "lead@company.com", "self": False},
        "attendees": [{"email": "lead@company.com"}, {"email": "sync.user@gmail.com"}],
    }
    parsed = provider._parse_google_event(item_public, calendar_id="primary")
    assert parsed.title == "Team Sync Meeting"
    assert parsed.description == "Sensitive team project discussions"
    assert parsed.transparency == EventTransparency.OPAQUE
    assert parsed.is_organizer is False
    assert parsed.attendees_count == 2
    assert parsed.timezone == "America/New_York"

    # Private confidential meeting -> description redacted according to Task 2 privacy invariant
    item_private = {
        "id": "evt-priv-1",
        "summary": "Confidential Doctor Appointment",
        "description": "Medical prescription review notes",
        "start": {"dateTime": "2026-11-25T14:00:00Z"},
        "end": {"dateTime": "2026-11-25T15:00:00Z"},
        "transparency": "opaque",
        "visibility": "private",
    }
    parsed_priv = provider._parse_google_event(item_private, calendar_id="primary")
    assert parsed_priv.description is None  # Redacted
    assert parsed_priv.visibility == "private"

    # Recurring event instance (Task 6)
    item_recur_instance = {
        "id": "recur_series_1_20261125T100000Z",
        "recurringEventId": "recur_series_1",
        "summary": "Daily Standup Instance",
        "start": {"dateTime": "2026-11-25T10:00:00Z"},
        "end": {"dateTime": "2026-11-25T10:30:00Z"},
        "originalStartTime": {"dateTime": "2026-11-25T10:00:00Z"},
    }
    parsed_recur = provider._parse_google_event(item_recur_instance, calendar_id="primary")
    assert parsed_recur.is_recurring is True
    assert parsed_recur.recurring_event_id == "recur_series_1"
    assert parsed_recur.original_start_time is not None


# ============================================================================
# 3. TASK 2, 3 & 4: INITIAL & INCREMENTAL TWO-WAY SYNCHRONIZATION
# ============================================================================

def test_initial_and_incremental_synchronization(connected_google_integration):
    integration_id, user_id = connected_google_integration

    now = datetime.now(timezone.utc)
    mock_events = [
        CalendarEventDTO(
            event_id="goog-evt-101",
            calendar_id="primary",
            provider="google_calendar",
            title="Design Review",
            description="Discuss system architecture",
            start_time=now + timedelta(hours=2),
            end_time=now + timedelta(hours=3),
            transparency=EventTransparency.OPAQUE,
            status=EventStatus.CONFIRMED,
            etag="etag-v1",
        ),
        CalendarEventDTO(
            event_id="goog-evt-102",
            calendar_id="primary",
            provider="google_calendar",
            title="Open Office Hours",
            description="Drop in questions",
            start_time=now + timedelta(hours=4),
            end_time=now + timedelta(hours=5),
            transparency=EventTransparency.TRANSPARENT,
            status=EventStatus.CONFIRMED,
            etag="etag-v1",
        ),
    ]

    # Initial Sync
    mock_result_1 = SyncResult(
        success=True,
        new_sync_token="syncToken-alpha-1",
        synced_events=mock_events,
        deleted_event_ids=[],
    )

    with patch.object(GoogleCalendarProvider, "synchronize", return_value=mock_result_1):
        with Session(engine) as session:
            resp = google_sync_service.sync_google_calendar(session, user_id=user_id)
            assert resp.success is True
            assert resp.events_created == 2
            assert resp.events_updated == 0
            assert resp.new_sync_token == "syncToken-alpha-1"

            # Verify persisted in database
            events = google_sync_service.list_events(session, user_id=user_id)
            assert len(events) == 2
            assert any(e.external_event_id == "goog-evt-101" and e.transparency == "OPAQUE" for e in events)
            assert any(e.external_event_id == "goog-evt-102" and e.transparency == "TRANSPARENT" for e in events)

    # Incremental Delta Sync (Task 3): Update evt-101 and cancel evt-102
    updated_evt = CalendarEventDTO(
        event_id="goog-evt-101",
        calendar_id="primary",
        provider="google_calendar",
        title="Design Review (Rescheduled)",
        start_time=now + timedelta(hours=3),
        end_time=now + timedelta(hours=4),
        transparency=EventTransparency.OPAQUE,
        status=EventStatus.CONFIRMED,
        etag="etag-v2",
    )
    mock_result_2 = SyncResult(
        success=True,
        new_sync_token="syncToken-alpha-2",
        synced_events=[updated_evt],
        deleted_event_ids=["goog-evt-102"],
    )

    with patch.object(GoogleCalendarProvider, "synchronize", return_value=mock_result_2):
        with Session(engine) as session:
            resp2 = google_sync_service.sync_google_calendar(session, user_id=user_id)
            assert resp2.success is True
            assert resp2.events_created == 0
            assert resp2.events_updated == 1
            assert resp2.events_deleted == 1
            assert resp2.new_sync_token == "syncToken-alpha-2"

            # Check that evt-101 has new title and evt-102 is CANCELLED
            events = google_sync_service.list_events(session, user_id=user_id)
            assert len(events) == 1
            assert events[0].title == "Design Review (Rescheduled)"


# ============================================================================
# 4. TASK 3: HTTP 410 GONE FULL RESYNC FALLBACK
# ============================================================================

def test_sync_410_gone_fallback(connected_google_integration):
    integration_id, user_id = connected_google_integration
    now = datetime.now(timezone.utc)

    # First call simulates 410 Gone (invalidated sync token), second call returns full resync items
    resync_evt = CalendarEventDTO(
        event_id="goog-evt-fresh-1",
        calendar_id="primary",
        provider="google_calendar",
        title="Full Resync Sprint Planning",
        start_time=now + timedelta(days=1),
        end_time=now + timedelta(days=1, hours=1),
        transparency=EventTransparency.OPAQUE,
    )

    mock_410 = SyncResult(success=True, full_resync_required=True)
    mock_fresh = SyncResult(
        success=True,
        new_sync_token="fresh-sync-token-999",
        synced_events=[resync_evt],
        deleted_event_ids=[],
    )

    with patch.object(GoogleCalendarProvider, "synchronize", side_effect=[mock_410, mock_fresh]) as mock_sync:
        with Session(engine) as session:
            resp = google_sync_service.sync_google_calendar(session, user_id=user_id)
            assert resp.success is True
            assert resp.full_resync_occurred is True
            assert resp.events_created == 1
            assert resp.new_sync_token == "fresh-sync-token-999"
            assert mock_sync.call_count == 2


# ============================================================================
# 5. TASK 4 & 5: TWO-WAY CRUD & OWNERSHIP GUARD
# ============================================================================

def test_create_and_manage_contextiq_focus_block(connected_google_integration):
    integration_id, user_id = connected_google_integration
    now = datetime.now(timezone.utc)

    create_payload = GoogleEventCreate(
        calendar_id="primary",
        title="Deep Focus: Backend Engine Refactoring",
        description="Created by ContextIQ Cognitive Scheduler",
        start_time=now + timedelta(hours=6),
        end_time=now + timedelta(hours=8),
        transparency=EventTransparency.OPAQUE,
    )

    mock_created_dto = CalendarEventDTO(
        event_id="goog-ciq-block-500",
        calendar_id="primary",
        provider="google_calendar",
        title=create_payload.title,
        description=create_payload.description,
        start_time=create_payload.start_time,
        end_time=create_payload.end_time,
        transparency=EventTransparency.OPAQUE,
        etag="etag-ciq-1",
    )

    with patch.object(GoogleCalendarProvider, "create_event", return_value=mock_created_dto) as mock_create:
        with Session(engine) as session:
            evt = google_sync_service.create_event(session, user_id, create_payload)
            assert evt.external_event_id == "goog-ciq-block-500"
            assert evt.is_contextiq_managed is True
            mock_create.assert_called_once()

            # Test updating ContextIQ managed focus block
            update_payload = GoogleEventUpdate(
                title="Deep Focus: Refactoring + Code Review",
                start_time=now + timedelta(hours=6, minutes=30),
            )
            mock_updated_dto = CalendarEventDTO(
                event_id="goog-ciq-block-500",
                calendar_id="primary",
                provider="google_calendar",
                title=update_payload.title,
                start_time=update_payload.start_time,
                end_time=now + timedelta(hours=8),
                transparency=EventTransparency.OPAQUE,
                etag="etag-ciq-2",
            )
            with patch.object(GoogleCalendarProvider, "update_event", return_value=mock_updated_dto):
                updated = google_sync_service.update_event(
                    session, user_id, "goog-ciq-block-500", update_payload
                )
                assert updated.title == "Deep Focus: Refactoring + Code Review"


def test_external_meeting_ownership_guard(connected_google_integration):
    """ContextIQ must reject modifying external team meetings without allow_external_modification."""
    integration_id, user_id = connected_google_integration
    now = datetime.now(timezone.utc)

    # Insert an external meeting directly
    with Session(engine) as session:
        external_evt = ExternalCalendarEvent(
            user_id=user_id,
            integration_id=integration_id,
            calendar_id="primary",
            external_event_id="goog-ext-team-meeting-99",
            title="Company All Hands",
            start_time=now + timedelta(days=2),
            end_time=now + timedelta(days=2, hours=1),
            is_contextiq_managed=False,  # Authored externally
        )
        session.add(external_evt)
        session.commit()

        # Attempt to modify without override must raise PermissionError
        with pytest.raises(PermissionError):
            google_sync_service.update_event(
                session,
                user_id,
                "goog-ext-team-meeting-99",
                GoogleEventUpdate(title="Hacked Title", allow_external_modification=False),
            )

        # Modifying with allow_external_modification=True succeeds
        mock_override_dto = CalendarEventDTO(
            event_id="goog-ext-team-meeting-99",
            calendar_id="primary",
            provider="google_calendar",
            title="Company All Hands (Rescheduled with Permission)",
            start_time=now + timedelta(days=2),
            end_time=now + timedelta(days=2, hours=1),
        )
        with patch.object(GoogleCalendarProvider, "update_event", return_value=mock_override_dto):
            updated = google_sync_service.update_event(
                session,
                user_id,
                "goog-ext-team-meeting-99",
                GoogleEventUpdate(
                    title="Company All Hands (Rescheduled with Permission)",
                    allow_external_modification=True,
                ),
            )
            assert "Rescheduled with Permission" in updated.title


def test_delete_google_event(connected_google_integration):
    integration_id, user_id = connected_google_integration
    now = datetime.now(timezone.utc)

    with Session(engine) as session:
        evt = ExternalCalendarEvent(
            user_id=user_id,
            integration_id=integration_id,
            calendar_id="primary",
            external_event_id="goog-del-target-1",
            title="Meeting to Cancel",
            start_time=now + timedelta(hours=10),
            end_time=now + timedelta(hours=11),
            is_contextiq_managed=True,
        )
        session.add(evt)
        session.commit()

        with patch.object(GoogleCalendarProvider, "delete_event", return_value=True):
            success = google_sync_service.delete_event(session, user_id, "goog-del-target-1")
            assert success is True
            # Check marked CANCELLED locally
            reloaded = session.scalars(
                select(ExternalCalendarEvent).where(ExternalCalendarEvent.external_event_id == "goog-del-target-1")
            ).first()
            assert reloaded.status == EventStatus.CANCELLED.value


# ============================================================================
# 6. TASK 7: FASTAPI REST ENDPOINTS
# ============================================================================

def test_api_trigger_sync(client, connected_google_integration):
    integration_id, user_id = connected_google_integration
    mock_sync_resp = SyncResult(
        success=True,
        new_sync_token="api-sync-tok-1",
        synced_events=[],
        deleted_event_ids=[],
    )

    with patch.object(GoogleCalendarProvider, "synchronize", return_value=mock_sync_resp):
        resp = client.post(
            "/api/v1/integrations/google/sync",
            json={"calendar_id": "primary"},
            headers={"X-User-Id": str(user_id)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["sync_status"] == "SYNCED"


def test_api_list_calendars(client, connected_google_integration):
    integration_id, user_id = connected_google_integration
    mock_cals = [
        CalendarDTO(
            calendar_id="primary",
            name="Personal Calendar",
            is_primary=True,
            access_role="owner",
            time_zone="UTC",
        ),
        CalendarDTO(
            calendar_id="work-cal-id",
            name="Work Calendar",
            is_primary=False,
            access_role="writer",
            time_zone="America/New_York",
        ),
    ]

    with patch.object(GoogleCalendarProvider, "list_calendars", return_value=mock_cals):
        resp = client.get(
            "/api/v1/integrations/google/calendars",
            headers={"X-User-Id": str(user_id)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["name"] == "Personal Calendar"
        assert data[0]["is_primary"] is True


def test_api_events_crud_lifecycle(client, connected_google_integration):
    integration_id, user_id = connected_google_integration
    now = datetime.now(timezone.utc)

    # 1. POST create event
    mock_created = CalendarEventDTO(
        event_id="api-event-uuid-88",
        calendar_id="primary",
        provider="google_calendar",
        title="API Scheduled Focus Window",
        start_time=now + timedelta(hours=1),
        end_time=now + timedelta(hours=2),
        transparency=EventTransparency.OPAQUE,
    )

    with patch.object(GoogleCalendarProvider, "create_event", return_value=mock_created):
        create_resp = client.post(
            "/api/v1/integrations/google/events",
            json={
                "title": "API Scheduled Focus Window",
                "start_time": (now + timedelta(hours=1)).isoformat(),
                "end_time": (now + timedelta(hours=2)).isoformat(),
                "calendar_id": "primary",
            },
            headers={"X-User-Id": str(user_id)},
        )
        assert create_resp.status_code == 201
        evt_data = create_resp.json()
        assert evt_data["title"] == "API Scheduled Focus Window"
        assert evt_data["is_contextiq_managed"] is True
        event_id = evt_data["id"]

    # 2. GET list events
    list_resp = client.get(
        "/api/v1/integrations/google/events?calendar_id=primary",
        headers={"X-User-Id": str(user_id)},
    )
    assert list_resp.status_code == 200
    events_list = list_resp.json()
    assert any(e["id"] == event_id for e in events_list)

    # 3. PATCH update event
    mock_updated = CalendarEventDTO(
        event_id="api-event-uuid-88",
        calendar_id="primary",
        provider="google_calendar",
        title="Updated Focus Window Title",
        start_time=now + timedelta(hours=1),
        end_time=now + timedelta(hours=2),
        transparency=EventTransparency.OPAQUE,
    )
    with patch.object(GoogleCalendarProvider, "update_event", return_value=mock_updated):
        patch_resp = client.patch(
            f"/api/v1/integrations/google/events/{event_id}",
            json={"title": "Updated Focus Window Title"},
            headers={"X-User-Id": str(user_id)},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["title"] == "Updated Focus Window Title"

    # 4. DELETE event
    with patch.object(GoogleCalendarProvider, "delete_event", return_value=True):
        del_resp = client.delete(
            f"/api/v1/integrations/google/events/{event_id}",
            headers={"X-User-Id": str(user_id)},
        )
        assert del_resp.status_code == 200
        assert del_resp.json()["success"] is True


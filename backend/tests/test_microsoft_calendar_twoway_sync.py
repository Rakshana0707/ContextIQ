"""Unit and integration test suite for Microsoft Outlook (Graph API) two-way synchronization."""
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
from app.schemas.microsoft_calendar import MicrosoftEventCreate, MicrosoftEventUpdate
from app.services import microsoft_sync_service
from app.services.integration_service import get_token_manager
from integrations.app.core.encryption import TokenVault
from integrations.app.core.token_manager import TokenManager
from integrations.app.providers.base_calendar_provider import BaseCalendarProvider
from integrations.app.providers.microsoft.microsoft_outlook_provider import MicrosoftOutlookProvider
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
            email=f"msftuser_{uid.hex[:6]}@example.com",
            display_name="Microsoft Sync User",
        )
        session.add(u)
        session.commit()
    return uid


@pytest.fixture
def connected_microsoft_integration(test_user):
    token_mgr = get_token_manager()
    bundle = OAuthTokenBundle(
        access_token="eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.msft_access_token",
        refresh_token="0.AQAAsome_refresh_token_msft",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        scope=[
            "Calendars.ReadWrite",
            "User.Read",
            "offline_access",
        ],
    )
    enc_access, enc_refresh = token_mgr.encrypt_credentials(bundle, user_id=test_user, provider="microsoft_outlook")

    with Session(engine) as session:
        integration = CalendarIntegration(
            user_id=test_user,
            provider="microsoft_outlook",
            provider_account_id="msft-sub-4455",
            provider_email="alex.chen@contoso.com",
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
# 1. TASK 1 & 7: MICROSOFT AUTHENTICATION & PROVIDER ABSTRACTION VALIDATION
# ============================================================================

def test_microsoft_provider_abstraction_and_scopes():
    provider = MicrosoftOutlookProvider(client_id="mock-msft-client-id")
    # Verify inheritance from BaseCalendarProvider (Task 7)
    assert isinstance(provider, BaseCalendarProvider)
    assert provider.provider_id == "microsoft_outlook"
    assert provider.provider_name == "Microsoft Outlook"

    # Minimal delegated scopes (Task 1)
    assert "Calendars.Read" in provider.default_scopes
    assert "User.Read" in provider.default_scopes
    assert "offline_access" in provider.default_scopes

    # Extended write scopes for two-way synchronization
    assert "Calendars.ReadWrite" in provider.write_scopes

    # Authorization URL generation with PKCE
    auth_url = provider.get_authorization_url(
        redirect_uri="http://localhost:3000/callback",
        state="msft-state-999",
        code_challenge="msft-pkce-challenge-xyz",
        request_write_access=True,
    )
    assert "login.microsoftonline.com" in auth_url
    assert "Calendars.ReadWrite" in auth_url
    assert "state=msft-state-999" in auth_url
    assert "code_challenge=msft-pkce-challenge-xyz" in auth_url


def test_microsoft_provider_authenticate_and_refresh():
    provider = MicrosoftOutlookProvider(client_id="cid", client_secret="csec")

    with patch("httpx.Client.post") as mock_post, patch("httpx.Client.get") as mock_get:
        # Mock token exchange
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "access_token": "msft-new-access-tok",
            "refresh_token": "msft-refresh-tok",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "Calendars.ReadWrite User.Read offline_access",
        }
        # Mock /me profile
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "mail": "alex.chen@contoso.com",
            "id": "msft-user-guid-001",
        }

        bundle = provider.authenticate(auth_code="code-msft-1", redirect_uri="http://localhost:3000/callback")
        assert bundle.access_token == "msft-new-access-tok"
        assert bundle.refresh_token == "msft-refresh-tok"
        assert bundle.provider_email == "alex.chen@contoso.com"
        assert bundle.provider_user_id == "msft-user-guid-001"

        # Mock token refresh
        mock_post.return_value.json.return_value = {
            "access_token": "msft-refreshed-tok",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
        refreshed = provider.refresh_credentials("msft-refresh-tok")
        assert refreshed.access_token == "msft-refreshed-tok"
        assert refreshed.refresh_token == "msft-refresh-tok"


# ============================================================================
# 2. TASK 3 & 6: EVENT NORMALIZATION, PRIVACY, RECURRENCE & ONLINE MEETINGS
# ============================================================================

def test_microsoft_event_normalization_and_privacy_redaction():
    provider = MicrosoftOutlookProvider()

    # 1. Standard team meeting with online Teams meeting URL
    item_normal = {
        "id": "msft-evt-normal-1",
        "subject": "Sprint Architecture Review",
        "body": {"contentType": "text", "content": "Reviewing Phase 5.4 Graph APIs"},
        "location": {"displayName": "Teams Meeting"},
        "start": {"dateTime": "2026-11-26T14:00:00Z", "timeZone": "Eastern Standard Time"},
        "end": {"dateTime": "2026-11-26T15:00:00Z", "timeZone": "Eastern Standard Time"},
        "showAs": "busy",
        "sensitivity": "normal",
        "isAllDay": False,
        "isCancelled": False,
        "isOrganizer": False,
        "organizer": {"emailAddress": {"address": "manager@contoso.com"}},
        "attendees": [{"emailAddress": {"address": "manager@contoso.com"}}, {"emailAddress": {"address": "alex@contoso.com"}}],
        "onlineMeeting": {"joinUrl": "https://teams.microsoft.com/l/meetup-join/19..."},
        "@odata.etag": 'W/"etag-msft-1"',
        "lastModifiedDateTime": "2026-11-25T18:00:00Z",
    }
    parsed = provider._parse_microsoft_event(item_normal, calendar_id="primary")
    assert parsed.title == "Sprint Architecture Review"
    assert parsed.description == "Reviewing Phase 5.4 Graph APIs"
    assert parsed.transparency == EventTransparency.OPAQUE
    assert parsed.is_organizer is False
    assert parsed.attendees_count == 2
    assert parsed.html_link == "https://teams.microsoft.com/l/meetup-join/19..."
    assert parsed.timezone == "Eastern Standard Time"
    assert parsed.visibility == "normal"

    # 2. Private event (Task 3: sensitive details redacted)
    item_private = {
        "id": "msft-evt-priv-1",
        "subject": "Private Medical Checkup",
        "body": {"contentType": "text", "content": "Sensitive doctor notes"},
        "start": {"dateTime": "2026-11-26T16:00:00Z"},
        "end": {"dateTime": "2026-11-26T17:00:00Z"},
        "showAs": "busy",
        "sensitivity": "private",
    }
    parsed_priv = provider._parse_microsoft_event(item_private, calendar_id="primary")
    assert parsed_priv.description is None  # Redacted
    assert parsed_priv.visibility == "private"

    # 3. Recurring occurrence (Task 6)
    item_recurrence = {
        "id": "msft-evt-occurrence-1",
        "seriesMasterId": "msft-master-series-99",
        "type": "occurrence",
        "subject": "Daily Standup Occurrence",
        "start": {"dateTime": "2026-11-26T09:00:00Z"},
        "end": {"dateTime": "2026-11-26T09:30:00Z"},
        "showAs": "busy",
    }
    parsed_recur = provider._parse_microsoft_event(item_recurrence, calendar_id="primary")
    assert parsed_recur.is_recurring is True
    assert parsed_recur.recurring_event_id == "msft-master-series-99"


# ============================================================================
# 3. TASK 4: DELTA SYNCHRONIZATION WITH MULTI-PAGE PAGINATION & EXPIRATION
# ============================================================================

def test_microsoft_delta_sync_pagination_and_recovery(connected_microsoft_integration):
    integration_id, user_id = connected_microsoft_integration
    now = datetime.now(timezone.utc)

    # Multi-page pagination simulation: Page 1 with @odata.nextLink -> Page 2 with @odata.deltaLink
    page_1_data = {
        "value": [
            {
                "id": "msft-page1-evt-1",
                "subject": "Page 1 Event",
                "start": {"dateTime": (now + timedelta(hours=1)).isoformat()},
                "end": {"dateTime": (now + timedelta(hours=2)).isoformat()},
                "showAs": "busy",
            }
        ],
        "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/calendarView/delta?$skiptoken=skip123",
    }
    page_2_data = {
        "value": [
            {
                "id": "msft-page2-evt-2",
                "subject": "Page 2 Event",
                "start": {"dateTime": (now + timedelta(hours=3)).isoformat()},
                "end": {"dateTime": (now + timedelta(hours=4)).isoformat()},
                "showAs": "free",
            }
        ],
        "@odata.deltaLink": "https://graph.microsoft.com/v1.0/me/calendarView/delta?$deltatoken=deltaFinal999",
    }

    def mock_get_multi_page(url, headers=None, params=None):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        if "skip123" in url:
            mock_resp.json.return_value = page_2_data
        else:
            mock_resp.json.return_value = page_1_data
        return mock_resp

    provider = MicrosoftOutlookProvider()
    token_bundle = OAuthTokenBundle(
        access_token="dummy", expires_at=now + timedelta(hours=1)
    )

    with patch("httpx.Client.get", side_effect=mock_get_multi_page):
        res = provider.synchronize(sync_token=None, credentials=token_bundle)
        assert res.success is True
        assert len(res.synced_events) == 2
        assert res.new_sync_token == "https://graph.microsoft.com/v1.0/me/calendarView/delta?$deltatoken=deltaFinal999"

    # Delta link expiration (HTTP 410 or resyncRequired) triggers full_resync_required=True
    def mock_get_expired(url, headers=None, params=None):
        mock_resp = MagicMock()
        mock_resp.status_code = 410
        return mock_resp

    with patch("httpx.Client.get", side_effect=mock_get_expired):
        expired_res = provider.synchronize(
            sync_token="https://graph.microsoft.com/v1.0/me/calendarView/delta?expired",
            credentials=token_bundle,
        )
        assert expired_res.success is True
        assert expired_res.full_resync_required is True


# ============================================================================
# 4. TASK 5: TWO-WAY CRUD & OWNERSHIP INVARIANT
# ============================================================================

def test_microsoft_two_way_sync_and_ownership(connected_microsoft_integration):
    integration_id, user_id = connected_microsoft_integration
    now = datetime.now(timezone.utc)

    # 1. ContextIQ focus block creation
    create_payload = MicrosoftEventCreate(
        calendar_id="primary",
        title="Deep Focus: Micro-Delay Optimization",
        description="Scheduled by ContextIQ Intelligence Layer",
        start_time=now + timedelta(hours=5),
        end_time=now + timedelta(hours=7),
        transparency=EventTransparency.OPAQUE,
    )

    mock_created = CalendarEventDTO(
        event_id="msft-ciq-event-777",
        calendar_id="primary",
        provider="microsoft_outlook",
        title=create_payload.title,
        description=create_payload.description,
        start_time=create_payload.start_time,
        end_time=create_payload.end_time,
        transparency=EventTransparency.OPAQUE,
    )

    with patch.object(MicrosoftOutlookProvider, "create_event", return_value=mock_created):
        with Session(engine) as session:
            evt = microsoft_sync_service.create_event(session, user_id, create_payload)
            assert evt.external_event_id == "msft-ciq-event-777"
            assert evt.is_contextiq_managed is True

    # 2. Updating ContextIQ managed event succeeds
    with Session(engine) as session:
        mock_updated = CalendarEventDTO(
            event_id="msft-ciq-event-777",
            calendar_id="primary",
            provider="microsoft_outlook",
            title="Deep Focus: Optimization + Code Review",
            start_time=now + timedelta(hours=5),
            end_time=now + timedelta(hours=7),
            transparency=EventTransparency.OPAQUE,
        )
        with patch.object(MicrosoftOutlookProvider, "update_event", return_value=mock_updated):
            updated = microsoft_sync_service.update_event(
                session,
                user_id,
                "msft-ciq-event-777",
                MicrosoftEventUpdate(title="Deep Focus: Optimization + Code Review"),
            )
            assert updated.title == "Deep Focus: Optimization + Code Review"

    # 3. Ownership Invariant: Modifying external team meeting without override raises PermissionError
    with Session(engine) as session:
        ext_evt = ExternalCalendarEvent(
            user_id=user_id,
            integration_id=integration_id,
            calendar_id="primary",
            external_event_id="msft-ext-allhands-10",
            title="Executive All Hands",
            start_time=now + timedelta(days=3),
            end_time=now + timedelta(days=3, hours=1),
            is_contextiq_managed=False,  # Created externally by meeting organizer
        )
        session.add(ext_evt)
        session.commit()

        # Rejection
        with pytest.raises(PermissionError):
            microsoft_sync_service.update_event(
                session,
                user_id,
                "msft-ext-allhands-10",
                MicrosoftEventUpdate(title="Modified Meeting", allow_external_modification=False),
            )

        # Explicit override permitted
        mock_ext_updated = CalendarEventDTO(
            event_id="msft-ext-allhands-10",
            calendar_id="primary",
            provider="microsoft_outlook",
            title="Executive All Hands (Approved Shift)",
            start_time=now + timedelta(days=3),
            end_time=now + timedelta(days=3, hours=1),
        )
        with patch.object(MicrosoftOutlookProvider, "update_event", return_value=mock_ext_updated):
            ext_updated = microsoft_sync_service.update_event(
                session,
                user_id,
                "msft-ext-allhands-10",
                MicrosoftEventUpdate(title="Executive All Hands (Approved Shift)", allow_external_modification=True),
            )
            assert "Approved Shift" in ext_updated.title


def test_microsoft_delete_event(connected_microsoft_integration):
    integration_id, user_id = connected_microsoft_integration
    now = datetime.now(timezone.utc)

    with Session(engine) as session:
        evt = ExternalCalendarEvent(
            user_id=user_id,
            integration_id=integration_id,
            calendar_id="primary",
            external_event_id="msft-del-target-5",
            title="Focus Block to Delete",
            start_time=now + timedelta(hours=8),
            end_time=now + timedelta(hours=9),
            is_contextiq_managed=True,
        )
        session.add(evt)
        session.commit()

        with patch.object(MicrosoftOutlookProvider, "delete_event", return_value=True):
            success = microsoft_sync_service.delete_event(session, user_id, "msft-del-target-5")
            assert success is True
            reloaded = session.scalars(
                select(ExternalCalendarEvent).where(ExternalCalendarEvent.external_event_id == "msft-del-target-5")
            ).first()
            assert reloaded.status == EventStatus.CANCELLED.value


# ============================================================================
# 5. TASK 8: THROTTLING & RATE-LIMITING
# ============================================================================

def test_microsoft_graph_throttling_handling():
    provider = MicrosoftOutlookProvider()
    token_bundle = OAuthTokenBundle(
        access_token="dummy", expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
    )

    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {"Retry-After": "10"}
        mock_get.return_value = mock_resp

        result = provider.synchronize(sync_token=None, credentials=token_bundle)
        assert result.success is False
        assert "Throttled" in result.error_message
        assert "10s" in result.error_message


# ============================================================================
# 6. TASK 7: FASTAPI REST ENDPOINTS
# ============================================================================

def test_api_microsoft_trigger_sync(client, connected_microsoft_integration):
    integration_id, user_id = connected_microsoft_integration
    mock_sync_res = SyncResult(
        success=True,
        new_sync_token="msft-delta-token-api-1",
        synced_events=[],
        deleted_event_ids=[],
    )

    with patch.object(MicrosoftOutlookProvider, "synchronize", return_value=mock_sync_res):
        resp = client.post(
            "/api/v1/integrations/microsoft/sync",
            json={"calendar_id": "primary"},
            headers={"X-User-Id": str(user_id)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["sync_status"] == "SYNCED"


def test_api_microsoft_list_calendars(client, connected_microsoft_integration):
    integration_id, user_id = connected_microsoft_integration
    mock_cals = [
        CalendarDTO(
            calendar_id="primary",
            name="Outlook Calendar",
            is_primary=True,
            access_role="writer",
            time_zone="UTC",
        ),
        CalendarDTO(
            calendar_id="project-cal-id",
            name="Project Milestones",
            is_primary=False,
            access_role="reader",
            time_zone="UTC",
        ),
    ]

    with patch.object(MicrosoftOutlookProvider, "list_calendars", return_value=mock_cals):
        resp = client.get(
            "/api/v1/integrations/microsoft/calendars",
            headers={"X-User-Id": str(user_id)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["name"] == "Outlook Calendar"
        assert data[0]["is_primary"] is True


def test_api_microsoft_events_crud_lifecycle(client, connected_microsoft_integration):
    integration_id, user_id = connected_microsoft_integration
    now = datetime.now(timezone.utc)

    # 1. POST create event
    mock_created = CalendarEventDTO(
        event_id="msft-api-evt-100",
        calendar_id="primary",
        provider="microsoft_outlook",
        title="Outlook Focus Block via API",
        start_time=now + timedelta(hours=2),
        end_time=now + timedelta(hours=3),
        transparency=EventTransparency.OPAQUE,
    )

    with patch.object(MicrosoftOutlookProvider, "create_event", return_value=mock_created):
        create_resp = client.post(
            "/api/v1/integrations/microsoft/events",
            json={
                "title": "Outlook Focus Block via API",
                "start_time": (now + timedelta(hours=2)).isoformat(),
                "end_time": (now + timedelta(hours=3)).isoformat(),
                "calendar_id": "primary",
            },
            headers={"X-User-Id": str(user_id)},
        )
        assert create_resp.status_code == 201
        evt_data = create_resp.json()
        assert evt_data["title"] == "Outlook Focus Block via API"
        assert evt_data["is_contextiq_managed"] is True
        event_id = evt_data["id"]

    # 2. GET list events
    list_resp = client.get(
        "/api/v1/integrations/microsoft/events?calendar_id=primary",
        headers={"X-User-Id": str(user_id)},
    )
    assert list_resp.status_code == 200
    events_list = list_resp.json()
    assert any(e["id"] == event_id for e in events_list)

    # 3. PATCH update event
    mock_updated = CalendarEventDTO(
        event_id="msft-api-evt-100",
        calendar_id="primary",
        provider="microsoft_outlook",
        title="Updated Outlook Focus Block Title",
        start_time=now + timedelta(hours=2),
        end_time=now + timedelta(hours=3),
        transparency=EventTransparency.OPAQUE,
    )
    with patch.object(MicrosoftOutlookProvider, "update_event", return_value=mock_updated):
        patch_resp = client.patch(
            f"/api/v1/integrations/microsoft/events/{event_id}",
            json={"title": "Updated Outlook Focus Block Title"},
            headers={"X-User-Id": str(user_id)},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["title"] == "Updated Outlook Focus Block Title"

    # 4. DELETE event
    with patch.object(MicrosoftOutlookProvider, "delete_event", return_value=True):
        del_resp = client.delete(
            f"/api/v1/integrations/microsoft/events/{event_id}",
            headers={"X-User-Id": str(user_id)},
        )
        assert del_resp.status_code == 200
        assert del_resp.json()["success"] is True

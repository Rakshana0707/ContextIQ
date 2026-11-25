"""Comprehensive test suite for unified calendar integrations, OAuth management, and encryption."""
from __future__ import annotations

import os
import sys
import time
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
from sqlalchemy import create_engine
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
from app.models.user import User
from integrations.app.core.encryption import TokenEncryptionError, TokenVault, redact_secret
from integrations.app.core.integration_manager import IntegrationManager, OAuthStateError
from integrations.app.core.provider_registry import ProviderRegistry, UnsupportedProviderError
from integrations.app.core.token_manager import TokenManager, TokenSecurityError
from integrations.app.providers.google.google_calendar_provider import GoogleCalendarProvider
from integrations.app.providers.microsoft.microsoft_outlook_provider import MicrosoftOutlookProvider
from integrations.app.schemas.integration_schemas import (
    CalendarEventDTO,
    ConnectionStatus,
    EventStatus,
    EventTransparency,
    OAuthTokenBundle,
    SyncResult,
    SyncStatus,
)


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    # Tables retained in sqlite test file


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def test_users():
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    with Session(engine) as session:
        u_a = User(
            id=user_a,
            email=f"usera_{user_a.hex[:6]}@example.com",
            display_name="User Alpha",
        )
        u_b = User(
            id=user_b,
            email=f"userb_{user_b.hex[:6]}@example.com",
            display_name="User Beta",
        )
        session.add_all([u_a, u_b])
        session.commit()
    return user_a, user_b


# ============================================================================
# 1. TOKEN ENCRYPTION & REDACTION TESTS (TASK 4)
# ============================================================================

def test_token_vault_encryption_decryption():
    vault = TokenVault(master_secret="super-secret-key-12345")
    secret_token = "ya29.a0AfH6SMD_very_secret_oauth_token"
    aad = "user_123:google_calendar"

    encrypted = vault.encrypt(secret_token, associated_data=aad)
    assert isinstance(encrypted, bytes)
    assert len(encrypted) >= 28
    assert secret_token.encode() not in encrypted

    decrypted = vault.decrypt(encrypted, associated_data=aad)
    assert decrypted == secret_token


def test_token_vault_rejects_aad_tampering():
    vault = TokenVault(master_secret="super-secret-key-12345")
    secret_token = "ya29.test_token"
    encrypted = vault.encrypt(secret_token, associated_data="user_1:google_calendar")

    # Attempting decryption under user_2 must fail (anti-token-substitution)
    with pytest.raises(TokenEncryptionError):
        vault.decrypt(encrypted, associated_data="user_2:google_calendar")


def test_token_vault_rejects_corrupted_ciphertext():
    vault = TokenVault(master_secret="super-secret-key-12345")
    encrypted = vault.encrypt("secret_token", associated_data="test")
    # Mutate byte
    corrupted = bytearray(encrypted)
    corrupted[15] ^= 0xFF
    with pytest.raises(TokenEncryptionError):
        vault.decrypt(bytes(corrupted), associated_data="test")


def test_secret_redaction():
    log_msg = "Dispatched request with bearer ya29.a0AfH6SMD123456 and refresh eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig"
    redacted = redact_secret(log_msg)
    assert "ya29." not in redacted
    assert "[REDACTED_SECRET]" in redacted


# ============================================================================
# 2. OAUTH MANAGEMENT & STATE VALIDATION TESTS (TASK 3)
# ============================================================================

def test_pkce_generation():
    verifier, challenge = IntegrationManager.generate_pkce()
    assert len(verifier) >= 43
    assert len(challenge) > 20
    assert verifier != challenge


def test_oauth_state_generation_and_validation():
    token_vault = TokenVault(master_secret="master-secret-1234")
    token_mgr = TokenManager(token_vault)
    manager = IntegrationManager(token_mgr, hmac_secret="state-signing-key")

    uid = uuid.uuid4()
    state = manager.generate_state(
        user_id=uid,
        provider="google_calendar",
        redirect_uri="http://localhost:3000/callback",
        code_verifier="test_code_verifier",
        ttl_seconds=300,
    )

    payload = manager.validate_state(state)
    assert payload["uid"] == str(uid)
    assert payload["p"] == "google_calendar"
    assert payload["r"] == "http://localhost:3000/callback"
    assert payload["cv"] == "test_code_verifier"


def test_oauth_state_tampering_rejected():
    token_vault = TokenVault(master_secret="master-secret-1234")
    token_mgr = TokenManager(token_vault)
    manager = IntegrationManager(token_mgr, hmac_secret="state-signing-key")

    state = manager.generate_state(
        user_id=uuid.uuid4(),
        provider="google_calendar",
        redirect_uri="http://localhost:3000/callback",
    )

    # Corrupt string
    tampered = state[:-4] + "AAAA"
    with pytest.raises(OAuthStateError):
        manager.validate_state(tampered)


def test_oauth_state_expiration_rejected():
    token_vault = TokenVault(master_secret="master-secret-1234")
    token_mgr = TokenManager(token_vault)
    manager = IntegrationManager(token_mgr, hmac_secret="state-signing-key")

    state = manager.generate_state(
        user_id=uuid.uuid4(),
        provider="google_calendar",
        redirect_uri="http://localhost:3000/callback",
        ttl_seconds=-10,  # Expired in past
    )
    with pytest.raises(OAuthStateError, match="expired"):
        manager.validate_state(state)


# ============================================================================
# 3. PROVIDER ABSTRACTION & REGISTRY TESTS (TASK 2)
# ============================================================================

def test_provider_registry():
    providers = ProviderRegistry.list_providers()
    assert "google_calendar" in providers
    assert "microsoft_outlook" in providers

    google_p = ProviderRegistry.get_provider("google_calendar")
    assert isinstance(google_p, GoogleCalendarProvider)

    ms_p = ProviderRegistry.get_provider("microsoft_outlook")
    assert isinstance(ms_p, MicrosoftOutlookProvider)

    with pytest.raises(UnsupportedProviderError):
        ProviderRegistry.get_provider("invalid_provider")


def test_google_provider_scopes():
    google_p = GoogleCalendarProvider()
    assert "https://www.googleapis.com/auth/calendar.events.readonly" in google_p.default_scopes
    assert "https://www.googleapis.com/auth/calendar.events" in google_p.write_scopes

    auth_url_read = google_p.get_authorization_url(
        redirect_uri="http://localhost:3000/callback",
        state="test_state",
        code_challenge="test_challenge",
        request_write_access=False,
    )
    assert "calendar.events.readonly" in auth_url_read
    assert "calendar.events " not in auth_url_read
    assert "code_challenge=test_challenge" in auth_url_read

    auth_url_write = google_p.get_authorization_url(
        redirect_uri="http://localhost:3000/callback",
        state="test_state",
        code_challenge="test_challenge",
        request_write_access=True,
    )
    assert "calendar.events" in auth_url_write


def test_microsoft_provider_scopes():
    ms_p = MicrosoftOutlookProvider()
    assert "Calendars.Read" in ms_p.default_scopes
    assert "Calendars.ReadWrite" in ms_p.write_scopes

    auth_url = ms_p.get_authorization_url(
        redirect_uri="http://localhost:3000/callback",
        state="test_state",
        code_challenge="test_challenge",
    )
    assert "Calendars.Read" in auth_url
    assert "code_challenge=test_challenge" in auth_url


# ============================================================================
# 4. TOKEN LIFECYCLE & AUTO-REFRESH TESTS (TASK 4 & TASK 8)
# ============================================================================

def test_token_auto_refresh_on_expiration():
    vault = TokenVault(master_secret="test-secret-12345")
    token_mgr = TokenManager(vault)
    uid = uuid.uuid4()
    provider = "google_calendar"

    # Token expired 10 minutes ago
    expired_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    bundle = OAuthTokenBundle(
        access_token="expired_access_token",
        refresh_token="valid_refresh_token",
        expires_at=expired_at,
        scope=["calendar.events.readonly"],
    )
    enc_access, enc_refresh = token_mgr.encrypt_credentials(bundle, uid, provider)

    # Mock provider refresh call
    new_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    mock_bundle = OAuthTokenBundle(
        access_token="freshly_refreshed_access_token",
        refresh_token="rotated_refresh_token",
        expires_at=new_expires_at,
        scope=["calendar.events.readonly"],
    )

    with patch.object(GoogleCalendarProvider, "refresh_credentials", return_value=mock_bundle):
        valid_bundle, was_refreshed, new_enc_acc, new_enc_ref = token_mgr.ensure_valid_token(
            encrypted_access_token=enc_access,
            encrypted_refresh_token=enc_refresh,
            expiration_timestamp=expired_at,
            user_id=uid,
            provider=provider,
            scopes=["calendar.events.readonly"],
        )

        assert was_refreshed is True
        assert valid_bundle.access_token == "freshly_refreshed_access_token"
        assert valid_bundle.refresh_token == "rotated_refresh_token"
        assert new_enc_acc is not None
        assert new_enc_ref is not None


# ============================================================================
# 5. REST API ENDPOINTS & USER ISOLATION TESTS (TASK 6 & TASK 9)
# ============================================================================

def test_connect_endpoint_generates_auth_params(client, test_users):
    user_a, _ = test_users
    resp = client.post(
        "/api/v1/integrations/google_calendar/connect",
        headers={"X-User-Id": str(user_a)},
        json={"redirect_uri": "http://localhost:3000/settings/integrations/callback"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "google_calendar"
    assert "accounts.google.com" in data["authorization_url"]
    assert "state=" in data["authorization_url"]
    assert data["state"]
    assert data["code_verifier"]


def test_callback_and_list_integrations_flow(client, test_users):
    user_a, user_b = test_users

    # 1. Initiate connect for User A
    connect_resp = client.post(
        "/api/v1/integrations/google_calendar/connect",
        headers={"X-User-Id": str(user_a)},
        json={"redirect_uri": "http://localhost:3000/callback"},
    )
    state = connect_resp.json()["state"]

    # 2. Mock Google token exchange and userinfo
    mock_token_bundle = OAuthTokenBundle(
        access_token="mock_access_ya29",
        refresh_token="mock_refresh_1234",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        scope=["https://www.googleapis.com/auth/calendar.events.readonly"],
        provider_user_id="google_sub_999",
        provider_email="user_a@gmail.com",
    )

    with patch.object(GoogleCalendarProvider, "authenticate", return_value=mock_token_bundle), \
         patch.object(GoogleCalendarProvider, "synchronize", return_value=SyncResult(success=True, new_sync_token="sync_v1")):

        cb_resp = client.get(
            "/api/v1/integrations/google_calendar/callback",
            params={"code": "valid_auth_code", "state": state},
        )
        assert cb_resp.status_code == 200
        int_data = cb_resp.json()
        integration_id = int_data["id"]
        assert int_data["provider"] == "google_calendar"
        assert int_data["provider_email"] == "user_a@gmail.com"
        assert int_data["connection_status"] == "CONNECTED"

        # Verify no token credentials leaked in response
        assert "access_token" not in int_data
        assert "encrypted_access_token" not in int_data

        # 3. List integrations for User A
        list_resp = client.get(
            "/api/v1/integrations",
            headers={"X-User-Id": str(user_a)},
        )
        assert list_resp.status_code == 200
        items = list_resp.json()
        assert len(items) >= 1
        assert any(i["id"] == integration_id for i in items)

        # 4. Check Status
        status_resp = client.get(
            f"/api/v1/integrations/{integration_id}/status",
            headers={"X-User-Id": str(user_a)},
        )
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["is_active"] is True
        assert status_data["has_valid_token"] is True
        assert status_data["expires_in_seconds"] > 3000

        # 5. USER ISOLATION CHECK: User B must not see or access User A's integration
        list_resp_b = client.get(
            "/api/v1/integrations",
            headers={"X-User-Id": str(user_b)},
        )
        assert list_resp_b.status_code == 200
        assert not any(i["id"] == integration_id for i in list_resp_b.json())

        status_resp_b = client.get(
            f"/api/v1/integrations/{integration_id}/status",
            headers={"X-User-Id": str(user_b)},
        )
        assert status_resp_b.status_code == 404

        disconnect_resp_b = client.post(
            f"/api/v1/integrations/{integration_id}/disconnect",
            headers={"X-User-Id": str(user_b)},
        )
        assert disconnect_resp_b.status_code == 404

        # 6. User A Disconnects
        with patch.object(GoogleCalendarProvider, "disconnect", return_value=True):
            disc_resp = client.post(
                f"/api/v1/integrations/{integration_id}/disconnect",
                headers={"X-User-Id": str(user_a)},
            )
            assert disc_resp.status_code == 200

            # Verify status is now REVOKED
            status_after = client.get(
                f"/api/v1/integrations/{integration_id}/status",
                headers={"X-User-Id": str(user_a)},
            )
            assert status_after.json()["connection_status"] == "REVOKED"
            assert status_after.json()["is_active"] is False


def test_sync_recovery_on_410_gone():
    google_p = GoogleCalendarProvider()
    mock_resp = MagicMock()
    mock_resp.status_code = 410

    bundle = OAuthTokenBundle(
        access_token="mock_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    with patch("httpx.Client.get", return_value=mock_resp):
        result = google_p.synchronize(
            sync_token="expired_sync_token",
            credentials=bundle,
        )
        assert result.success is True
        assert result.full_resync_required is True

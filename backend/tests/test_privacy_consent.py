import os
import sys
from pathlib import Path
import uuid
from datetime import datetime, timezone

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

# Ensure test DB environment
os.environ["APP_ENV"] = "development"
os.environ.setdefault("DATABASE_URL", "sqlite:///./_test_privacy.db")

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

# Teach SQLite how to compile Postgres JSONB columns
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

from app.db.session import Base, engine, get_db
from sqlalchemy.orm import Session
from app.main import app
from app.models.enums import ConsentStatus, TelemetryCategory
from app.models.user import User
from app.services.agent_privacy_guard import AgentPrivacyGuard, DEFAULT_GLOBAL_DENYLIST


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    # Cleanup test db tables if desired


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def user_a(client):
    user_id = uuid.uuid4()
    with Session(engine) as session:
        user = User(
            id=user_id,
            email=f"user_a_{user_id.hex[:6]}@example.com",
            display_name="User A",
        )
        session.add(user)
        session.commit()
    return user_id


@pytest.fixture
def user_b(client):
    user_id = uuid.uuid4()
    with Session(engine) as session:
        user = User(
            id=user_id,
            email=f"user_b_{user_id.hex[:6]}@example.com",
            display_name="User B",
        )
        session.add(user)
        session.commit()
    return user_id


# --- 1. Consent Architecture & Default Disabled State ---

def test_consent_default_absent(client, user_a):
    """Verify that by default, a newly created user has zero granted consent."""
    res = client.get("/api/v1/privacy/consent", headers={"X-User-Id": str(user_a)})
    assert res.status_code == 200
    assert res.json() is None


def test_grant_consent_explicit(client, user_a):
    """User explicitly grants consent for selected telemetry categories."""
    payload = {
        "consent_version": "1.0.0",
        "enabled_categories": [
            "APP_TRANSITIONS",
            "INACTIVITY_DETECTION",
            "SESSION_RECONSTRUCTION",
            "LOCAL_STORAGE",
            "SERVER_SYNC",
        ],
        "device_id": "device_win_pc_01",
    }
    res = client.post("/api/v1/privacy/consent", json=payload, headers={"X-User-Id": str(user_a)})
    assert res.status_code == 201
    data = res.json()
    assert data["consent_status"] == "GRANTED"
    assert data["consent_version"] == "1.0.0"
    assert len(data["enabled_categories"]) == 5
    assert "APP_TRANSITIONS" in data["enabled_categories"]
    assert data["user_id"] == str(user_a)

    # Verify active consent endpoint reflects this
    active_res = client.get("/api/v1/privacy/consent", headers={"X-User-Id": str(user_a)})
    assert active_res.status_code == 200
    assert active_res.json()["id"] == data["id"]


# --- 2. Consent Revocation & Auditable History ---

def test_revoke_consent_and_audit_history(client, user_a):
    """Revoking consent marks active consent as revoked and maintains immutable audit history."""
    # 1. First grant initial consent
    grant_payload = {
        "consent_version": "1.0.0",
        "enabled_categories": ["APP_TRANSITIONS", "SERVER_SYNC"],
        "device_id": "device_win_pc_01",
    }
    client.post("/api/v1/privacy/consent", json=grant_payload, headers={"X-User-Id": str(user_a)})

    # 2. Revoke consent
    revoke_payload = {
        "device_id": "device_win_pc_01",
        "reason": "User requested full monitoring halt",
    }
    res = client.post("/api/v1/privacy/consent/revoke", json=revoke_payload, headers={"X-User-Id": str(user_a)})
    assert res.status_code == 200
    data = res.json()
    assert data["consent_status"] == "REVOKED"
    assert data["revoked_timestamp"] is not None

    # Verify active consent is now None
    active_res = client.get("/api/v1/privacy/consent", headers={"X-User-Id": str(user_a)})
    assert active_res.status_code == 200
    assert active_res.json() is None

    # Verify audit history preserves both grant and revoke records
    history_res = client.get("/api/v1/privacy/consent/history", headers={"X-User-Id": str(user_a)})
    assert history_res.status_code == 200
    history = history_res.json()
    assert len(history) >= 2
    statuses = [item["consent_status"] for item in history]
    assert "GRANTED" in statuses
    assert "REVOKED" in statuses


# --- 3. Privacy Settings & Instant Pause / Resume Controls ---

def test_privacy_settings_pause_and_resume(client, user_a):
    """User can pause monitoring immediately with a designated duration budget."""
    # 1. Fetch initial settings
    res = client.get("/api/v1/privacy/settings", headers={"X-User-Id": str(user_a)})
    assert res.status_code == 200
    assert res.json()["raw_event_retention_days"] == 30

    # 2. Pause monitoring for 60 minutes
    update_res = client.patch(
        "/api/v1/privacy/settings",
        json={"is_paused": True, "pause_duration_minutes": 60, "raw_event_retention_days": 14},
        headers={"X-User-Id": str(user_a)},
    )
    assert update_res.status_code == 200
    data = update_res.json()
    assert data["is_paused"] is True
    assert data["paused_until"] is not None
    assert data["raw_event_retention_days"] == 14

    # 3. Resume monitoring manually
    resume_res = client.patch(
        "/api/v1/privacy/settings",
        json={"is_paused": False},
        headers={"X-User-Id": str(user_a)},
    )
    assert resume_res.status_code == 200
    assert resume_res.json()["is_paused"] is False
    assert resume_res.json()["paused_until"] is None


# --- 4. Application Exclusions Management ---

def test_app_exclusions_crud(client, user_a):
    """Users can add, list, and remove excluded applications."""
    # Add exclusion
    payload = {"application_identifier": "1password.exe", "description": "Password Manager"}
    res = client.post("/api/v1/privacy/exclusions", json=payload, headers={"X-User-Id": str(user_a)})
    assert res.status_code == 201
    exclusion_id = res.json()["id"]
    assert res.json()["application_identifier"] == "1password.exe"

    # Reject duplicate
    dup_res = client.post("/api/v1/privacy/exclusions", json=payload, headers={"X-User-Id": str(user_a)})
    assert dup_res.status_code == 409

    # List exclusions
    list_res = client.get("/api/v1/privacy/exclusions", headers={"X-User-Id": str(user_a)})
    assert list_res.status_code == 200
    apps = [e["application_identifier"] for e in list_res.json()]
    assert "1password.exe" in apps

    # Remove exclusion
    del_res = client.delete(f"/api/v1/privacy/exclusions/{exclusion_id}", headers={"X-User-Id": str(user_a)})
    assert del_res.status_code == 204

    # Verify deletion
    list_after = client.get("/api/v1/privacy/exclusions", headers={"X-User-Id": str(user_a)})
    assert len(list_after.json()) == 0


# --- 5. User-Scoped Security & Isolation ---

def test_user_isolation(client, user_a, user_b):
    """User B cannot access or delete User A's application exclusions or consent."""
    # User A adds exclusion
    res_a = client.post(
        "/api/v1/privacy/exclusions",
        json={"application_identifier": "whatsapp.exe", "description": "Personal messaging"},
        headers={"X-User-Id": str(user_a)},
    )
    assert res_a.status_code == 201
    exclusion_id_a = res_a.json()["id"]

    # User B lists exclusions (should not see User A's)
    res_b = client.get("/api/v1/privacy/exclusions", headers={"X-User-Id": str(user_b)})
    assert res_b.status_code == 200
    assert len(res_b.json()) == 0

    # User B attempts to delete User A's exclusion -> 404
    del_b = client.delete(f"/api/v1/privacy/exclusions/{exclusion_id_a}", headers={"X-User-Id": str(user_b)})
    assert del_b.status_code == 404


# --- 6. GDPR Article 17 Data Purge (Right to Erasure) ---

def test_data_purge_confirmation(client, user_a):
    """Purge request requires exact confirmation phrase 'DELETE MY DATA'."""
    # Invalid confirmation
    bad_res = client.post(
        "/api/v1/privacy/data/purge",
        json={"purge_raw_telemetry": True, "confirmation_phrase": "delete please"},
        headers={"X-User-Id": str(user_a)},
    )
    assert bad_res.status_code == 400

    # Valid confirmation
    good_res = client.post(
        "/api/v1/privacy/data/purge",
        json={"purge_raw_telemetry": True, "purge_context_sessions": True, "confirmation_phrase": "DELETE MY DATA"},
        headers={"X-User-Id": str(user_a)},
    )
    assert good_res.status_code == 200
    assert good_res.json()["status"] == "success"


# --- 7. Agent Privacy Guard: Offline Enforcement ---

def test_agent_privacy_guard_offline():
    """Verify pure client-side privacy guard behavior without backend connection."""
    # 1. No consent -> refuse collection
    guard_no_consent = AgentPrivacyGuard(consent_status=None)
    assert guard_no_consent.is_consent_valid() is False
    assert guard_no_consent.can_collect_category("APP_TRANSITIONS") is False
    assert guard_no_consent.filter_and_sanitize_event(
        "APP_FOCUS_GAINED", "APP_TRANSITIONS", "code.exe", "ContextIQ - VSCode"
    ) is None

    # 2. Granted consent with selective categories
    guard_active = AgentPrivacyGuard(
        consent_status="GRANTED",
        enabled_categories=["APP_TRANSITIONS", "SESSION_RECONSTRUCTION"],
        user_exclusions={"slack.exe"},
    )
    assert guard_active.is_consent_valid() is True
    assert guard_active.can_collect_category("APP_TRANSITIONS") is True
    # Non-consented category is blocked
    assert guard_active.can_collect_category("INACTIVITY_DETECTION") is False

    # 3. Excluded app handling: zero identity, zero duration, zero content
    excluded_event = guard_active.filter_and_sanitize_event(
        event_type="APP_FOCUS_GAINED",
        category="APP_TRANSITIONS",
        process_name="slack.exe",
        raw_title="Confidential Slack Chat with Client",
        duration_seconds=45.2,
    )
    assert excluded_event is not None
    assert excluded_event["is_excluded"] is True
    assert excluded_event["application_identifier"] == "EXCLUDED_PRIVATE"
    assert excluded_event["sanitized_title"] == "[PRIVATE]"
    assert excluded_event["duration_seconds"] is None

    # 4. Global denylist check (e.g. 1Password)
    denylist_event = guard_active.filter_and_sanitize_event(
        event_type="APP_FOCUS_GAINED",
        category="APP_TRANSITIONS",
        process_name="1password.exe",
        raw_title="1Password Master Vault Unlock",
    )
    assert denylist_event["is_excluded"] is True
    assert denylist_event["application_identifier"] == "EXCLUDED_PRIVATE"

    # 5. Title redaction for safe apps
    clean_event = guard_active.filter_and_sanitize_event(
        event_type="APP_FOCUS_GAINED",
        category="APP_TRANSITIONS",
        process_name="code.exe",
        raw_title="C:\\Users\\John\\Documents\\SecretProject\\main.py — Visual Studio Code",
        duration_seconds=12.5,
    )
    assert clean_event["is_excluded"] is False
    assert clean_event["application_identifier"] == "code.exe"
    # Full path should be stripped
    assert "C:\\Users" not in clean_event["sanitized_title"]
    assert "main.py" in clean_event["sanitized_title"]

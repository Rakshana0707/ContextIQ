"""
Comprehensive Test Suite for Phase 7.9: Security, Privacy, and Deployment Hardening.
Validates:
1. JWT authentication, expiration enforcement, and invalid signature rejection.
2. Secure logout and token revocation blacklist (prevents replay of logged-out tokens).
3. Cross-user isolation and Object-Level Authorization (IDOR protection across tasks and privacy).
4. Role-based administrative access control (require_admin dependency).
5. Production security headers injection (CSP, HSTS, X-Frame-Options, X-Content-Type-Options).
6. Request payload size limit enforcement (rejects > 5MB with 413 Payload Too Large).
7. Client rate limiting and 429 Too Many Requests with Retry-After header.
8. Surveillance payload rejection (keystrokes, screenshots, clipboard strictly blocked).
9. GDPR Article 20 Data Portability export package generation.
10. GDPR Article 17 Cascading Account Erasure and complete data wipeout.
11. Production secrets guard and dev-secret detection.
12. Backup script SHA-256 integrity verification.
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.core.deps import TokenBlacklist, get_current_user, get_db, require_admin
from app.core.security_middleware import rate_limiter
from app.main import app
from app.models.automation_rule import AutomationRule
from app.models.calendar_integration import CalendarIntegration
from app.models.context_session import ContextSession
from app.models.raw_telemetry_event import RawTelemetryEvent
from app.models.safety_models import EmergencyStopEvent, WorkflowAuditEvent
from app.models.task import Task
from app.models.telemetry_consent import TelemetryConsent, UserAppExclusion, UserPrivacySettings
from app.models.user import User
from app.models.workflow_models import WorkflowExecutionPlan
from app.schemas.privacy import ConsentGrantRequest
from app.services.agent_privacy_guard import AgentPrivacyGuard
from app.services.privacy_service import (
    grant_consent,
    validate_no_surveillance_payload,
)
from scripts.backup_restore import calculate_sha256, verify

TEST_DB_URL = "sqlite:///:memory:"


@pytest.fixture
def db_session():
    from app.db.session import Base
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    TokenBlacklist.reset()
    rate_limiter.reset()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        TokenBlacklist.reset()
        rate_limiter.reset()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def user_a(db_session) -> User:
    u = User(
        id=uuid.UUID("a1111111-1111-1111-1111-111111111111"),
        email="user_a@contextiq.io",
        display_name="User Alpha",
        is_active=True,
        is_admin=False,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def user_b(db_session) -> User:
    u = User(
        id=uuid.UUID("b2222222-2222-2222-2222-222222222222"),
        email="user_b@contextiq.io",
        display_name="User Bravo",
        is_active=True,
        is_admin=False,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def admin_user(db_session) -> User:
    u = User(
        id=uuid.UUID("c9999999-9999-9999-9999-999999999999"),
        email="admin@contextiq.io",
        display_name="Admin Security User",
        is_active=True,
        is_admin=True,
        role_persona="admin",
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


def make_token(user_id: uuid.UUID, expires_minutes: int = 60) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expires_minutes)
    to_encode = {"sub": str(user_id), "iat": now, "exp": expire}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")


class TestAuthenticationAndAuthorization:
    def test_jwt_expiration_enforced(self, client, user_a):
        # Generate an already expired token (-10 minutes)
        expired_token = make_token(user_a.id, expires_minutes=-10)
        res = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {expired_token}"})
        assert res.status_code == 401
        assert "Invalid authentication credentials" in res.json()["detail"]

    def test_invalid_signature_rejected(self, client, user_a):
        # Sign token with wrong secret
        now = datetime.now(timezone.utc)
        payload = {"sub": str(user_a.id), "exp": now + timedelta(hours=1)}
        fake_token = jwt.encode(payload, "wrong-untrusted-secret-key-123", algorithm="HS256")
        res = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {fake_token}"})
        assert res.status_code == 401

    def test_secure_logout_and_token_revocation(self, client, user_a):
        token = make_token(user_a.id)

        # 1. Verify token works before logout
        res_before = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
        assert res_before.status_code == 200
        assert res_before.json()["email"] == user_a.email

        # 2. Call logout endpoint
        logout_res = client.post("/api/v1/users/logout", headers={"Authorization": f"Bearer {token}"})
        assert logout_res.status_code == 200
        assert "revoked" in logout_res.json()["message"]

        # 3. Attempting to use revoked token must now be rejected
        res_after = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
        assert res_after.status_code == 401
        assert "revoked" in res_after.json()["detail"]

    def test_cross_user_isolation_and_idor_protection(self, client, db_session, user_a, user_b):
        # Create a task owned exclusively by User A
        task_a = Task(
            id=uuid.uuid4(),
            user_id=user_a.id,
            title="Confidential Financial Analysis for User A",
            status="PENDING",
            priority="HIGH",
        )
        db_session.add(task_a)
        db_session.commit()

        token_b = make_token(user_b.id)

        # User B attempts to access User A's task -> Must be 404
        get_res = client.get(
            f"/api/v1/tasks/{task_a.id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert get_res.status_code == 404

        # User B attempts to delete User A's task -> Must be 404
        del_res = client.delete(
            f"/api/v1/tasks/{task_a.id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert del_res.status_code == 404

        # Verify task still exists in DB unmodified
        assert db_session.get(Task, task_a.id) is not None

    def test_role_based_administrative_access(self, user_a, admin_user):
        # Regular user fails admin check
        with pytest.raises(Exception) as excinfo:
            require_admin(current_user=user_a)
        assert "403" in str(excinfo.value) or "Administrative" in str(excinfo.value)

        # Admin user succeeds
        admin_verified = require_admin(current_user=admin_user)
        assert admin_verified.id == admin_user.id


class TestAPISecurityAndMiddleware:
    def test_security_headers_injected(self, client):
        res = client.get("/health/live")
        assert res.status_code == 200

        headers = res.headers
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["X-XSS-Protection"] == "1; mode=block"
        assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "default-src 'self'" in headers["Content-Security-Policy"]
        assert "camera=()" in headers["Permissions-Policy"]

    def test_request_payload_size_limit(self, client):
        # Send request claiming Content-Length > 5MB
        headers = {"Content-Length": str(6 * 1024 * 1024)}  # 6 MB
        res = client.post("/health/live", headers=headers)
        assert res.status_code == 413
        assert "payload too large" in res.json().get("error", "").lower() or "5mb" in res.json().get("detail", "").lower()

    def test_rate_limiting_enforcement(self, client):
        rate_limiter.reset()
        rate_limiter.set_limit(5)  # Limit to 5 requests for fast test

        # First 5 requests succeed
        for _ in range(5):
            res = client.get("/api/v1/privacy/consent")
            assert res.status_code in (200, 401, 404)  # Valid API handling, not throttled

        # 6th request triggers rate limiter
        throttled_res = client.get("/api/v1/privacy/consent")
        assert throttled_res.status_code == 429
        assert "Retry-After" in throttled_res.headers
        assert throttled_res.headers["Retry-After"] == "60"

        # Exempt health probes must never be throttled
        health_res = client.get("/health/live")
        assert health_res.status_code == 200

        rate_limiter.reset()
        rate_limiter.set_limit(180)


class TestPrivacyAndSurveillanceGuardrails:
    def test_prohibited_surveillance_payload_rejection(self):
        # Validate that keystrokes, screenshots, and clipboard are strictly rejected
        with pytest.raises(Exception) as excinfo:
            validate_no_surveillance_payload({"keystrokes": "abcde123", "duration": 10})
        assert "Prohibited surveillance payload rejected" in str(excinfo.value)

        with pytest.raises(Exception) as excinfo:
            validate_no_surveillance_payload({"screenshot": "base64_data...", "window": "browser"})
        assert "screenshot" in str(excinfo.value)

        with pytest.raises(Exception) as excinfo:
            validate_no_surveillance_payload({"clipboard_text": "copied password"})
        assert "clipboard" in str(excinfo.value)

        # Benign productivity telemetry passes
        validate_no_surveillance_payload({"window_focus_duration": 45.2, "app": "code.exe"})

    def test_agent_privacy_guard_surveillance_blackout(self):
        guard = AgentPrivacyGuard(
            consent_status="GRANTED",
            enabled_categories=["APP_TRANSITIONS"],
            is_paused=False,
        )

        # If title or process reveals surveillance/keylog payload, event is dropped
        event = guard.filter_and_sanitize_event(
            event_type="app_switched",
            category="APP_TRANSITIONS",
            process_name="keylogger.exe",
            raw_title="Keystroke Recorder Buffer",
        )
        assert event is None

        # Standard clean event is recorded with title minimization
        clean_event = guard.filter_and_sanitize_event(
            event_type="app_switched",
            category="APP_TRANSITIONS",
            process_name="pycharm.exe",
            raw_title="ContextIQ - C:\\Users\\Shiv\\repo\\main.py?token=secret123",
        )
        assert clean_event is not None
        assert clean_event["application_identifier"] == "pycharm.exe"
        assert "secret123" not in clean_event["sanitized_title"]

    def test_gdpr_data_export(self, client, db_session, user_a):
        # Seed user tasks and consent
        t = Task(
            id=uuid.uuid4(),
            user_id=user_a.id,
            title="User A Private Task",
            status="PENDING",
            priority="HIGH",
        )
        db_session.add(t)
        grant_consent(
            db_session,
            user_a.id,
            ConsentGrantRequest(consent_version="1.0.0", enabled_categories=["APP_TRANSITIONS"]),
        )
        db_session.commit()

        token = make_token(user_a.id)
        res = client.get("/api/v1/privacy/data/export", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()

        assert data["gdpr_article"] == "Article 20 (Right to Data Portability)"
        assert data["user_profile"]["email"] == user_a.email
        assert len(data["tasks"]) >= 1
        assert len(data["consent_audit_history"]) >= 1
        assert "privacy_settings" in data

    def test_gdpr_account_deletion_cascading(self, client, db_session, user_a):
        # Seed data across multiple tables for User A
        task = Task(id=uuid.uuid4(), user_id=user_a.id, title="Task to wipe")
        db_session.add(task)
        grant_consent(
            db_session,
            user_a.id,
            ConsentGrantRequest(consent_version="1.0.0", enabled_categories=["APP_TRANSITIONS"]),
        )
        db_session.commit()

        token = make_token(user_a.id)

        # Rejection when confirmation phrase is missing/incorrect
        bad_req = client.post(
            "/api/v1/privacy/account/delete",
            json={"confirmation_phrase": "just delete please"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert bad_req.status_code == 400

        # Valid deletion request
        good_req = client.post(
            "/api/v1/privacy/account/delete",
            json={"confirmation_phrase": "DELETE MY ENTIRE ACCOUNT"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert good_req.status_code == 200
        assert good_req.json()["status"] == "DELETED"

        # Verify User and related rows are eradicated
        assert db_session.get(User, user_a.id) is None
        assert db_session.scalar(select(Task).where(Task.user_id == user_a.id)) is None
        assert db_session.scalar(select(TelemetryConsent).where(TelemetryConsent.user_id == user_a.id)) is None


class TestProductionConfigurationAndBackupIntegrity:
    def test_production_secret_guard(self):
        settings = Settings(
            APP_ENV="production",
            SECRET_KEY="dev-secret-change-me",
            CORS_ORIGINS=["https://app.contextiq.io"],
        )
        warnings = settings.validate_runtime()
        assert any("SECRET_KEY is still the development default" in w for w in warnings)

    def test_backup_and_checksum_verification(self, tmp_path):
        import gzip
        # Create a valid sample gzip archive
        test_file = tmp_path / "test_backup.sql.gz"
        with gzip.open(test_file, "wb") as f_gz:
            f_gz.write(b"Simulated GZIP backup stream for ContextIQ database")

        digest = calculate_sha256(test_file)
        checksum_file = tmp_path / "test_backup.sql.gz.sha256"
        checksum_file.write_text(f"{digest}  test_backup.sql.gz\n")

        # Integrity verification passes
        assert verify(test_file) is True

        # Tampered file fails verification
        tampered_file = tmp_path / "tampered.sql.gz"
        with gzip.open(tampered_file, "wb") as f_gz:
            f_gz.write(b"Tampered payload")
        tampered_checksum = tmp_path / "tampered.sql.gz.sha256"
        tampered_checksum.write_text(f"{digest}  tampered.sql.gz\n")

        assert verify(tampered_file) is False

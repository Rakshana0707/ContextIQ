"""
Unit and integration test suite for ContextIQ Intelligent Notification and Cognitive Load Management (Phase 4.8).
Validates:
1. Quiet hours suppression
2. Focus session protection (deferral of non-critical alerts)
3. Critical deadline alert bypass (< 2h deadline delivers immediately)
4. Duplicate notification suppression within deduplication window
5. Expired notification handling
6. Hourly and daily notification limits
7. User timezone changes and quiet hour evaluation
8. User preference overrides (explicit category opt-out)
9. Fatigue score calculation and consecutive dismissal penalty
10. REST API endpoints (/notifications, /preferences, /acknowledge, /dismiss, /metrics)
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "adaptive-intelligence"))

os.environ["APP_ENV"] = "development"
os.environ.setdefault("DATABASE_URL", "sqlite:///./_test_telemetry.db")


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


import app.models
from app.db.session import Base, engine
from app.main import app
from app.models.notification_models import (
    NotificationFatigueRecord,
    UserNotification,
    UserNotificationPreference,
)
from app.models.user import User
from app.notifications.delivery_policy import DeliveryPolicyResolver
from app.notifications.eligibility_evaluator import EligibilityEvaluator, _get_local_hour
from app.notifications.fatigue_tracker import NotificationFatigueTracker
from app.schemas.notification_schemas import (
    DeliveryChannel,
    DeliveryStrategy,
    NotificationCategory,
    NotificationCreateRequest,
    NotificationDismissRequest,
    NotificationPreferenceUpdate,
    NotificationPriority,
)
from app.services.adaptive.notification_service import NotificationService


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client():
    return TestClient(app)


def _create_user(db: Session, prefix: str = "notif_user", tz: str = "UTC") -> User:
    uid = uuid.uuid4()
    user = User(
        id=uid,
        email=f"{prefix}_{uid.hex[:6]}@example.com",
        display_name="Notification Tester",
        timezone=tz,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


# ---------------------------------------------------------------------------
# 1. Quiet Hours Suppression
# ---------------------------------------------------------------------------
def test_quiet_hours_suppression(db_session: Session):
    user = _create_user(db_session, prefix="quiet", tz="UTC")
    # 23:00 UTC falls inside default quiet hours (22:00 to 08:00)
    as_of = datetime(2026, 11, 22, 23, 15, 0, tzinfo=timezone.utc)

    req = NotificationCreateRequest(
        category=NotificationCategory.RECOVERY_SUGGESTION,
        priority=NotificationPriority.MEDIUM,
        title="Take a recovery buffer",
        message="You have been context switching frequently.",
    )

    notif = NotificationService.schedule_notification(
        db=db_session,
        user_id=user.id,
        request=req,
        as_of=as_of,
    )

    assert notif.delivery_strategy == DeliveryStrategy.SUPPRESSED_QUIET_PERIOD.value
    assert notif.is_delivered is False
    assert "quiet hours" in notif.metadata_payload.get("delivery_rationale", "").lower()


# ---------------------------------------------------------------------------
# 2. Focus Session Protection
# ---------------------------------------------------------------------------
def test_focus_session_suppression(db_session: Session):
    user = _create_user(db_session, prefix="focus", tz="UTC")
    # 14:00 UTC is outside quiet hours
    as_of = datetime(2026, 11, 22, 14, 0, 0, tzinfo=timezone.utc)

    req = NotificationCreateRequest(
        category=NotificationCategory.FOCUS_SESSION_SUGGESTION,
        priority=NotificationPriority.MEDIUM,
        title="Schedule Deep Work",
        message="A focus window is opening soon.",
    )

    # Active focus session with 40 min remaining
    notif = NotificationService.schedule_notification(
        db=db_session,
        user_id=user.id,
        request=req,
        as_of=as_of,
        is_in_active_focus_session=True,
        focus_remaining_minutes=40,
    )

    assert notif.delivery_strategy == DeliveryStrategy.DEFERRED.value
    assert notif.is_delivered is False
    assert notif.is_deferred is True
    assert notif.deferred_until is not None
    from app.notifications.eligibility_evaluator import _normalize_utc
    assert _normalize_utc(notif.deferred_until) == as_of + timedelta(minutes=40)
    assert "focus session" in notif.metadata_payload.get("delivery_rationale", "").lower()


# ---------------------------------------------------------------------------
# 3. Critical Deadline Alert Bypass
# ---------------------------------------------------------------------------
def test_critical_alert_bypass(db_session: Session):
    user = _create_user(db_session, prefix="crit", tz="UTC")
    # Inside quiet hours AND during active focus session
    as_of = datetime(2026, 11, 22, 23, 30, 0, tzinfo=timezone.utc)
    imminent_deadline = as_of + timedelta(minutes=45)  # 45 min remaining (< 2h)

    req = NotificationCreateRequest(
        category=NotificationCategory.CRITICAL_DEADLINE_REMINDER,
        priority=NotificationPriority.CRITICAL,
        title="Urgent Deadline Approaching",
        message="Critical milestone due in 45 minutes.",
        deadline_at=imminent_deadline,
        is_critical_urgency=True,
    )

    notif = NotificationService.schedule_notification(
        db=db_session,
        user_id=user.id,
        request=req,
        as_of=as_of,
        is_in_active_focus_session=True,
    )

    # Critical alert MUST bypass both quiet hours and focus session block!
    assert notif.delivery_strategy == DeliveryStrategy.IMMEDIATE.value
    assert notif.is_delivered is True
    assert notif.delivered_at is not None


# ---------------------------------------------------------------------------
# 4. Duplicate Notification Suppression
# ---------------------------------------------------------------------------
def test_duplicate_notification_suppression(db_session: Session):
    user = _create_user(db_session, prefix="dup", tz="UTC")
    as_of = datetime(2026, 11, 22, 11, 0, 0, tzinfo=timezone.utc)

    req = NotificationCreateRequest(
        category=NotificationCategory.CONTEXTUAL_REMINDER,
        priority=NotificationPriority.LOW,
        title="Prepare meeting notes",
        message="Review meeting materials before start.",
    )

    # First dispatch delivers immediately
    notif_1 = NotificationService.schedule_notification(
        db=db_session, user_id=user.id, request=req, as_of=as_of
    )
    assert notif_1.delivery_strategy == DeliveryStrategy.IMMEDIATE.value

    # Second duplicate dispatch 10 minutes later (< 30 min window) is suppressed
    notif_2 = NotificationService.schedule_notification(
        db=db_session, user_id=user.id, request=req, as_of=as_of + timedelta(minutes=10)
    )
    assert notif_2.delivery_strategy == DeliveryStrategy.SUPPRESSED_DUPLICATE.value
    assert notif_2.is_delivered is False


# ---------------------------------------------------------------------------
# 5. Expired Notification Handling
# ---------------------------------------------------------------------------
def test_expired_notification_handling(db_session: Session):
    user = _create_user(db_session, prefix="exp", tz="UTC")
    as_of = datetime(2026, 11, 22, 15, 0, 0, tzinfo=timezone.utc)
    expired_at = as_of - timedelta(minutes=10)  # Expired 10 min ago

    req = NotificationCreateRequest(
        category=NotificationCategory.RECOVERY_SUGGESTION,
        priority=NotificationPriority.MEDIUM,
        title="Micro-break expired",
        message="Window for micro-break passed.",
        expires_at=expired_at,
    )

    notif = NotificationService.schedule_notification(
        db=db_session, user_id=user.id, request=req, as_of=as_of
    )
    assert notif.delivery_strategy == DeliveryStrategy.EXPIRED.value
    assert notif.is_delivered is False


# ---------------------------------------------------------------------------
# 6. Hourly and Daily Notification Limits
# ---------------------------------------------------------------------------
def test_notification_limits(db_session: Session):
    user = _create_user(db_session, prefix="limits", tz="UTC")
    as_of = datetime(2026, 11, 22, 10, 0, 0, tzinfo=timezone.utc)

    # Set custom limit of 2 per hour
    NotificationService.update_preferences(
        db=db_session,
        user_id=user.id,
        update_data=NotificationPreferenceUpdate(max_notifications_per_hour=2),
    )

    # Dispatch 1
    req1 = NotificationCreateRequest(
        category=NotificationCategory.HIGH_FORGETTING_RISK_ALERT,
        priority=NotificationPriority.HIGH,
        title="Risk 1",
        message="Alert 1",
    )
    n1 = NotificationService.schedule_notification(db=db_session, user_id=user.id, request=req1, as_of=as_of)
    assert n1.delivery_strategy == DeliveryStrategy.IMMEDIATE.value

    # Dispatch 2
    req2 = NotificationCreateRequest(
        category=NotificationCategory.RECOVERY_SUGGESTION,
        priority=NotificationPriority.MEDIUM,
        title="Risk 2",
        message="Alert 2",
    )
    n2 = NotificationService.schedule_notification(
        db=db_session, user_id=user.id, request=req2, as_of=as_of + timedelta(minutes=5)
    )
    assert n2.delivery_strategy == DeliveryStrategy.IMMEDIATE.value

    # Dispatch 3 in same hour -> Hits rate limit -> DEFERRED
    req3 = NotificationCreateRequest(
        category=NotificationCategory.FOCUS_SESSION_SUGGESTION,
        priority=NotificationPriority.MEDIUM,
        title="Risk 3",
        message="Alert 3",
    )
    n3 = NotificationService.schedule_notification(
        db=db_session, user_id=user.id, request=req3, as_of=as_of + timedelta(minutes=10)
    )
    assert n3.delivery_strategy == DeliveryStrategy.DEFERRED.value
    assert "limit reached" in n3.metadata_payload.get("delivery_rationale", "").lower()


# ---------------------------------------------------------------------------
# 7. Timezone Changes and Quiet Hours Evaluation
# ---------------------------------------------------------------------------
def test_timezone_changes(db_session: Session):
    # 02:00 UTC is daytime (11:00 AM) in Tokyo (Asia/Tokyo = UTC+9)
    # But 02:00 UTC is night (2:00 AM) in UTC
    user_tokyo = _create_user(db_session, prefix="tokyo", tz="Asia/Tokyo")
    as_of = datetime(2026, 11, 22, 2, 0, 0, tzinfo=timezone.utc)

    req = NotificationCreateRequest(
        category=NotificationCategory.DAILY_BEHAVIORAL_SUMMARY,
        priority=NotificationPriority.LOW,
        title="Daily Summary",
        message="Summary of focus work.",
    )

    # For Tokyo user, 02:00 UTC is 11:00 AM local -> NOT in quiet hours -> IMMEDIATE
    notif_tokyo = NotificationService.schedule_notification(
        db=db_session, user_id=user_tokyo.id, request=req, as_of=as_of
    )
    assert notif_tokyo.delivery_strategy == DeliveryStrategy.IMMEDIATE.value

    # For UTC user, 02:00 UTC is 02:00 AM local -> IN quiet hours -> SUPPRESSED_QUIET_PERIOD
    user_utc = _create_user(db_session, prefix="utc_user", tz="UTC")
    notif_utc = NotificationService.schedule_notification(
        db=db_session, user_id=user_utc.id, request=req, as_of=as_of
    )
    assert notif_utc.delivery_strategy == DeliveryStrategy.SUPPRESSED_QUIET_PERIOD.value


# ---------------------------------------------------------------------------
# 8. User Preference Overrides (User Sovereignty)
# ---------------------------------------------------------------------------
def test_user_preference_overrides(db_session: Session):
    user = _create_user(db_session, prefix="override", tz="UTC")
    as_of = datetime(2026, 11, 22, 12, 0, 0, tzinfo=timezone.utc)

    # User explicitly disables RECOVERY_SUGGESTION
    NotificationService.update_preferences(
        db=db_session,
        user_id=user.id,
        update_data=NotificationPreferenceUpdate(
            enabled_categories={NotificationCategory.RECOVERY_SUGGESTION.value: False}
        ),
    )

    req = NotificationCreateRequest(
        category=NotificationCategory.RECOVERY_SUGGESTION,
        priority=NotificationPriority.HIGH,
        title="Take a break",
        message="Urgent recovery suggested.",
    )

    notif = NotificationService.schedule_notification(
        db=db_session, user_id=user.id, request=req, as_of=as_of
    )

    # Must be completely suppressed to NO_NOTIFICATION (User Sovereignty respected)
    assert notif.delivery_strategy == DeliveryStrategy.NO_NOTIFICATION.value
    assert notif.is_delivered is False
    assert "disabled in user preferences" in notif.metadata_payload.get("delivery_rationale", "")


# ---------------------------------------------------------------------------
# 9. Fatigue Score Calculation & Dismissal Penalty
# ---------------------------------------------------------------------------
def test_fatigue_score_calculation(db_session: Session):
    user = _create_user(db_session, prefix="fatigue", tz="UTC")
    as_of = datetime(2026, 11, 22, 12, 0, 0, tzinfo=timezone.utc)

    # Create 3 notifications and dismiss them consecutively
    for i in range(3):
        req = NotificationCreateRequest(
            category=NotificationCategory.CONTEXTUAL_REMINDER,
            priority=NotificationPriority.LOW,
            title=f"Nudge {i}",
            message=f"Message {i}",
        )
        notif = NotificationService.schedule_notification(
            db=db_session, user_id=user.id, request=req, as_of=as_of + timedelta(minutes=i * 35)
        )
        NotificationService.dismiss_notification(
            db=db_session,
            user_id=user.id,
            notification_id=notif.id,
            reason="Not useful right now",
            annoyance_level=4,
        )

    metrics = NotificationService.get_metrics(db=db_session, user_id=user.id)
    assert metrics.consecutive_dismissals == 3
    assert metrics.total_dismissed_7d == 3
    assert metrics.fatigue_score >= 0.60
    assert metrics.fatigue_level in ("HIGH", "CRITICAL")
    assert "Notification fatigue score represents user interaction frequency" in metrics.disclaimer


# ---------------------------------------------------------------------------
# 10. REST API Endpoints Verification
# ---------------------------------------------------------------------------
def test_rest_api_endpoints(client: TestClient):
    with Session(bind=engine) as session:
        user = _create_user(session, prefix="api_test")
        user_id = user.id
        session.commit()

    from app.core.deps import get_current_user_id
    app.dependency_overrides[get_current_user_id] = lambda: user_id

    try:
        # 1. GET /api/v1/adaptive/notifications/preferences
        res_pref = client.get("/api/v1/adaptive/notifications/preferences")
        assert res_pref.status_code == 200
        pref_data = res_pref.json()
        assert pref_data["quiet_hours_start"] == 22
        assert pref_data["quiet_hours_end"] == 8

        # 2. POST /api/v1/adaptive/notifications/preferences
        update_payload = {
            "quiet_hours_start": 23,
            "quiet_hours_end": 7,
            "max_notifications_per_hour": 5,
        }
        res_up = client.post("/api/v1/adaptive/notifications/preferences", json=update_payload)
        assert res_up.status_code == 200
        assert res_up.json()["quiet_hours_start"] == 23
        assert res_up.json()["max_notifications_per_hour"] == 5

        # 3. POST /api/v1/adaptive/notifications
        create_payload = {
            "category": "HIGH_FORGETTING_RISK_ALERT",
            "priority": "HIGH",
            "title": "Review API Specs",
            "message": "Forgetting risk is high on task #42",
        }
        res_create = client.post("/api/v1/adaptive/notifications", json=create_payload)
        assert res_create.status_code == 201
        notif_data = res_create.json()
        assert "id" in notif_data
        notif_id = notif_data["id"]

        # 4. GET /api/v1/adaptive/notifications
        res_list = client.get("/api/v1/adaptive/notifications")
        assert res_list.status_code == 200
        list_data = res_list.json()
        assert len(list_data) >= 1
        assert any(n["id"] == notif_id for n in list_data)

        # 5. POST /api/v1/adaptive/notifications/{id}/acknowledge
        res_ack = client.post(f"/api/v1/adaptive/notifications/{notif_id}/acknowledge")
        assert res_ack.status_code == 200
        assert res_ack.json()["is_read"] is True

        # 6. Create another notification to dismiss
        res_create2 = client.post(
            "/api/v1/adaptive/notifications",
            json={
                "category": "RECOVERY_SUGGESTION",
                "priority": "LOW",
                "title": "Stretch break",
                "message": "Time to stretch.",
            },
        )
        notif2_id = res_create2.json()["id"]

        # 7. POST /api/v1/adaptive/notifications/{id}/dismiss
        res_dis = client.post(
            f"/api/v1/adaptive/notifications/{notif2_id}/dismiss",
            json={"reason": "Busy right now", "annoyance_level": 2},
        )
        assert res_dis.status_code == 200
        assert res_dis.json()["is_dismissed"] is True

        # 8. GET /api/v1/adaptive/notifications/metrics
        res_met = client.get("/api/v1/adaptive/notifications/metrics")
        assert res_met.status_code == 200
        met_data = res_met.json()
        assert met_data["total_presented_7d"] >= 2
        assert "fatigue_score" in met_data
        assert "fatigue_level" in met_data

    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

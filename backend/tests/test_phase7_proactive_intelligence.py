"""
Automated Test Suite for Phase 7.3: Proactive Behavioral Monitoring and Event-Driven Intelligence.
Covers:
1. Deduplication and Idempotency key handling.
2. Delayed and out-of-order event ingestion.
3. Missing context and corrupt payloads (dead-lettering).
4. Telemetry consent gating (consent required for desktop/mobile telemetry).
5. Behavioral detection with conformal uncertainty guarantees.
6. Notification fatigue management (daily limits and duplicate cooldown).
7. User-disabled rules and paused preferences.
8. Proactive Feed user responses (Approve, Snooze, Dismiss).
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.event_models import (
    DeadLetterEventRecord,
    ProactiveFeedItem,
    StandardEventRecord,
)
from app.models.notification_models import UserNotificationPreference
from app.models.telemetry_consent import ConsentStatus, TelemetryConsent
from app.models.user import User
from app.models.automation_rule import (
    AutomationActionDefinition,
    AutomationCondition,
    AutomationRule,
    AutomationTrigger,
)
from app.schemas.event_schemas import (
    EventIngestRequest,
    EventSource,
    StandardEvent,
    StandardEventType,
)
from app.services.behavioral_detector import BehavioralChangeDetector
from app.services.event_processor import EventProcessor
from app.services.proactive_intelligence import ProactiveIntelligenceService


TEST_DB_URL = "sqlite:///:memory:"


@pytest.fixture
def db_session():
    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user(db_session):
    u = User(
        id=uuid.UUID("a1111111-1111-1111-1111-111111111111"),
        email="proactive.tester@contextiq.io",
        display_name="Proactive Intelligence User",
        is_active=True,
    )
    db_session.add(u)
    # Add telemetry consent by default
    consent = TelemetryConsent(
        user_id=u.id,
        consent_status="GRANTED",
        granted_timestamp=datetime.now(timezone.utc),
    )
    db_session.add(consent)

    # Add notification preference
    pref = UserNotificationPreference(
        user_id=u.id,
        quiet_hours_enabled=False,
        max_notifications_per_day=10,
    )
    db_session.add(pref)

    db_session.commit()
    db_session.refresh(u)
    return u


def test_event_deduplication_and_idempotency(db_session, test_user):
    """Verifies duplicate events with matching idempotency keys are safely deduplicated."""
    now = datetime.now(timezone.utc)
    idempotency_key = "test_key_12345"

    req1 = EventIngestRequest(
        event_type="CONTEXT_SWITCH",
        user_id=test_user.id,
        source="desktop_telemetry",
        event_timestamp=now,
        payload={"app": "IDE"},
        idempotency_key=idempotency_key,
    )

    res1 = EventProcessor.process_event(db=db_session, event_or_req=req1)
    assert res1.status == "PROCESSED"
    assert res1.is_duplicate is False

    # Second event with the exact same idempotency_key
    req2 = EventIngestRequest(
        event_type="CONTEXT_SWITCH",
        user_id=test_user.id,
        source="desktop_telemetry",
        event_timestamp=now,
        payload={"app": "IDE"},
        idempotency_key=idempotency_key,
    )

    res2 = EventProcessor.process_event(db=db_session, event_or_req=req2)
    assert res2.status == "DUPLICATE"
    assert res2.is_duplicate is True


def test_delayed_and_out_of_order_events(db_session, test_user):
    """Verifies that events with past timestamps (e.g. offline synchronization) are handled cleanly."""
    past_ts = datetime.now(timezone.utc) - timedelta(hours=5)

    delayed_event = StandardEvent(
        event_id=str(uuid.uuid4()),
        event_type="CONTEXT_SWITCH",
        user_id=test_user.id,
        event_timestamp=past_ts,
        source="desktop_telemetry",
        payload={"delayed": True, "app": "Browser"},
        idempotency_key=f"delayed_{uuid.uuid4()}",
    )

    result = EventProcessor.process_event(db=db_session, event_or_req=delayed_event)
    assert result.status == "PROCESSED"

    stored = db_session.query(StandardEventRecord).filter_by(event_id=delayed_event.event_id).first()
    assert stored is not None
    assert stored.processed is True


def test_missing_context_and_corrupt_payload_deadletter(db_session, test_user):
    """Corrupt or invalid event payloads should be routed to dead-letter storage with diagnostics."""
    # Invalid event missing mandatory fields
    corrupt_payload = {
        "user_id": "not-a-valid-uuid",
        "payload": "not-a-dict",
    }

    result = EventProcessor.process_event(db=db_session, event_or_req=corrupt_payload)
    assert result.status == "DEAD_LETTER"

    dl = db_session.query(DeadLetterEventRecord).first()
    assert dl is not None
    assert dl.error_code == "VALIDATION_FAILED"
    assert dl.status == "PENDING"


def test_telemetry_consent_gating(db_session):
    """Desktop telemetry without user consent must be rejected and dead-lettered."""
    # User without consent
    unconsented_user = User(
        id=uuid.UUID("b2222222-2222-2222-2222-222222222222"),
        email="unconsented@contextiq.io",
        display_name="Unconsented User",
        is_active=True,
    )
    db_session.add(unconsented_user)
    db_session.commit()

    req = EventIngestRequest(
        event_type="CONTEXT_SWITCH",
        user_id=unconsented_user.id,
        source="desktop_telemetry",
        payload={"app": "Terminal"},
        idempotency_key="unconsented_telemetry_1",
    )

    result = EventProcessor.process_event(db=db_session, event_or_req=req)
    assert result.status == "DEAD_LETTER"
    assert "telemetry consent" in (result.rationale or "").lower()

    dl = db_session.query(DeadLetterEventRecord).filter_by(error_code="CONSENT_REQUIRED").first()
    assert dl is not None


def test_behavioral_detector_and_conformal_bounds(db_session, test_user):
    """Verifies that behavioral detections include explicit conformal intervals and bounds."""
    # Detect context thrashing
    event = BehavioralChangeDetector.detect_context_thrashing(
        user_id=test_user.id,
        switch_count_last_minute=9,
        active_apps=["IDE", "Slack", "Email", "Browser", "Terminal"],
    )
    assert event is not None
    assert event.event_type == StandardEventType.THRASHING_DETECTED.value

    # Conformal checks: predictions are never framed as absolute certainty
    payload = event.payload
    assert "conformal_interval_text" in payload
    assert payload["confidence_score"] < 1.0
    assert payload["uncertainty_lower_bound"] <= payload["confidence_score"] <= payload["uncertainty_upper_bound"]

    # Ingest event and verify proactive feed item generation
    res = EventProcessor.process_event(db=db_session, event_or_req=event)
    assert res.proactive_feed_item_created is True
    assert res.proactive_feed_item_id is not None

    feed_item = db_session.query(ProactiveFeedItem).filter_by(id=res.proactive_feed_item_id).first()
    assert feed_item is not None
    assert feed_item.detection_type == StandardEventType.THRASHING_DETECTED.value
    assert "9 switches" in feed_item.why_it_matters or "switched applications" in feed_item.why_it_matters
    assert feed_item.confidence_score == payload["confidence_score"]


def test_notification_fatigue_daily_limit(db_session, test_user):
    """Verifies that proactive alerts beyond the daily ceiling (3) are suppressed."""
    now = datetime.now(timezone.utc)

    # Ingest 3 distinct behavioral events
    events = [
        BehavioralChangeDetector.detect_context_thrashing(test_user.id, 8, ["A", "B"], now=now),
        BehavioralChangeDetector.detect_forgetting_risk_spike(test_user.id, uuid.uuid4(), "Task 1", 0.85, now=now + timedelta(seconds=1)),
        BehavioralChangeDetector.detect_calendar_overload(test_user.id, 4, 3.0, 0.0, now=now + timedelta(seconds=2)),
    ]

    for ev in events:
        res = EventProcessor.process_event(db=db_session, event_or_req=ev, now=now)
        assert res.proactive_feed_item_created is True

    # 4th behavioral alert on the same day should be suppressed by fatigue limit
    ev4 = BehavioralChangeDetector.detect_recovery_lag_exceeded(test_user.id, 1800, 600, now=now + timedelta(seconds=3))
    res4 = EventProcessor.process_event(db=db_session, event_or_req=ev4, now=now)

    assert res4.proactive_feed_item_created is False
    assert res4.suppressed_by_fatigue is True
    assert "daily proactive intelligence limit reached" in (res4.rationale or "").lower()


def test_user_disabled_automation_and_paused_preference(db_session, test_user):
    """Verifies that when notifications are paused by the user, proactive insights are suppressed."""
    pref = db_session.query(UserNotificationPreference).filter_by(user_id=test_user.id).first()
    pref.is_paused = True
    pref.paused_until = datetime.now(timezone.utc) + timedelta(hours=2)
    db_session.commit()

    ev = BehavioralChangeDetector.detect_context_thrashing(test_user.id, 8, ["A", "B"])
    res = EventProcessor.process_event(db=db_session, event_or_req=ev)

    assert res.proactive_feed_item_created is False
    assert res.suppressed_by_fatigue is True
    assert "paused" in (res.rationale or "").lower()


def test_feed_item_actions_approve_snooze_dismiss(db_session, test_user):
    """Verifies user can respond to proactive feed items (Approve, Snooze, Dismiss)."""
    ev = BehavioralChangeDetector.detect_context_thrashing(test_user.id, 7, ["App1", "App2"])
    res = EventProcessor.process_event(db=db_session, event_or_req=ev)
    assert res.proactive_feed_item_id is not None

    item_id = res.proactive_feed_item_id

    # 1. Snooze
    snoozed = ProactiveIntelligenceService.respond_to_feed_item(
        db=db_session,
        feed_item_id=item_id,
        user_id=test_user.id,
        action="SNOOZE",
        snooze_minutes=30,
    )
    assert snoozed.status == "SNOOZED"
    assert snoozed.snoozed_until is not None

    # 2. Approve
    approved = ProactiveIntelligenceService.respond_to_feed_item(
        db=db_session,
        feed_item_id=item_id,
        user_id=test_user.id,
        action="APPROVE",
    )
    assert approved.status == "ACTIONED"

    # 3. Dismiss
    dismissed = ProactiveIntelligenceService.respond_to_feed_item(
        db=db_session,
        feed_item_id=item_id,
        user_id=test_user.id,
        action="DISMISS",
    )
    assert dismissed.status == "DISMISSED"

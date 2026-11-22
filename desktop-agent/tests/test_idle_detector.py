"""Tests for aggregate idle time and inactivity detection."""
from datetime import datetime, timezone, timedelta
import pytest
from app.collectors.idle_detector import IdleDetector
from app.events.event_builder import EventBuilder


class MockIdleProvider:
    def __init__(self, idle_seconds: float = 0.0):
        self.idle_seconds = idle_seconds

    def get_idle_duration_seconds(self) -> float:
        return self.idle_seconds


@pytest.fixture
def builder():
    return EventBuilder(user_id="user-123", device_id="dev-456")


def test_active_user_under_threshold(builder):
    provider = MockIdleProvider(idle_seconds=15.0)
    detector = IdleDetector(event_builder=builder, idle_threshold_seconds=120.0, provider=provider)

    events = detector.check_idle_state(current_app_id="code.exe")
    assert len(events) == 0
    assert detector.is_idle is False


def test_crossing_idle_threshold_triggers_user_idle_started(builder):
    provider = MockIdleProvider(idle_seconds=125.0)
    detector = IdleDetector(event_builder=builder, idle_threshold_seconds=120.0, provider=provider)

    t0 = datetime(2026, 11, 22, 10, 0, 0, tzinfo=timezone.utc)
    events = detector.check_idle_state(current_app_id="code.exe", check_time_utc=t0)

    assert len(events) == 1
    event = events[0]
    assert event["event_type"] == "user_idle_started"
    assert event["application_identifier"] == "code.exe"
    assert event["payload"]["idle_threshold_seconds"] == 120.0
    assert event["payload"]["last_active_application"] == "code.exe"
    assert detector.is_idle is True


def test_continuous_idle_produces_no_duplicate_events(builder):
    provider = MockIdleProvider(idle_seconds=130.0)
    detector = IdleDetector(event_builder=builder, idle_threshold_seconds=120.0, provider=provider)

    detector.check_idle_state(current_app_id="code.exe")
    assert detector.is_idle is True

    # User remains idle (e.g. 150s idle)
    provider.idle_seconds = 150.0
    events = detector.check_idle_state(current_app_id="code.exe")
    assert len(events) == 0
    assert detector.is_idle is True


def test_return_from_inactivity_triggers_user_active_returned(builder):
    provider = MockIdleProvider(idle_seconds=120.0)
    detector = IdleDetector(event_builder=builder, idle_threshold_seconds=120.0, provider=provider)

    # 1. Start idle at t0
    t0 = datetime(2026, 11, 22, 10, 0, 0, tzinfo=timezone.utc)
    detector.check_idle_state(current_app_id="code.exe", check_time_utc=t0)
    assert detector.is_idle is True

    # 2. User moves mouse / interacts at t1 (10 minutes later = 600s)
    # Windows idle duration immediately drops to 0.5s (< threshold)
    t1 = t0 + timedelta(seconds=600)
    provider.idle_seconds = 0.5

    events = detector.check_idle_state(current_app_id="code.exe", check_time_utc=t1)
    assert len(events) == 1

    event = events[0]
    assert event["event_type"] == "user_active_returned"
    assert event["application_identifier"] == "code.exe"
    assert event["payload"]["total_idle_duration_seconds"] == 600.0
    assert event["payload"]["resuming_into_application"] == "code.exe"
    assert detector.is_idle is False

"""Tests for application activity tracking and transition detection."""
import pytest
from app.collectors.application_activity import ApplicationActivityTracker
from app.collectors.foreground_window import ForegroundAppInfo
from app.events.event_builder import EventBuilder


@pytest.fixture
def builder():
    return EventBuilder(user_id="user-123", device_id="dev-456")


def test_initial_application_activation(builder):
    tracker = ApplicationActivityTracker(event_builder=builder)

    sample1 = ForegroundAppInfo(process_id=100, executable_name="code.exe", application_identifier="code.exe")
    events = tracker.process_foreground_sample(sample1, sample_time_monotonic=10.0)

    assert len(events) == 1
    assert events[0]["event_type"] == "application_activated"
    assert events[0]["application_identifier"] == "code.exe"
    assert events[0]["previous_application_identifier"] is None
    assert events[0]["payload"]["process_id"] == 100
    assert events[0]["payload"]["is_rapid_switch"] is False


def test_repeated_sample_on_same_app_generates_no_duplicates(builder):
    tracker = ApplicationActivityTracker(event_builder=builder)

    sample1 = ForegroundAppInfo(process_id=100, executable_name="code.exe", application_identifier="code.exe")
    events1 = tracker.process_foreground_sample(sample1, sample_time_monotonic=10.0)
    assert len(events1) == 1

    # Second sample on same app and PID
    events2 = tracker.process_foreground_sample(sample1, sample_time_monotonic=10.5)
    assert len(events2) == 0


def test_application_transition_duration_and_activation(builder):
    tracker = ApplicationActivityTracker(event_builder=builder)

    # 1. Start in Code.exe at monotonic 100.0
    app_a = ForegroundAppInfo(process_id=100, executable_name="code.exe", application_identifier="code.exe")
    tracker.process_foreground_sample(app_a, sample_time_monotonic=100.0)

    # 2. Transition to Slack.exe at monotonic 145.5 (45.5 seconds later)
    app_b = ForegroundAppInfo(process_id=200, executable_name="slack.exe", application_identifier="slack.exe")
    events = tracker.process_foreground_sample(app_b, sample_time_monotonic=145.5)

    assert len(events) == 2

    # First event: deactivated Code.exe
    deact = events[0]
    assert deact["event_type"] == "application_deactivated"
    assert deact["application_identifier"] == "code.exe"
    assert deact["payload"]["duration_seconds"] == 45.5
    assert deact["payload"]["process_id"] == 100

    # Second event: activated Slack.exe
    act = events[1]
    assert act["event_type"] == "application_activated"
    assert act["application_identifier"] == "slack.exe"
    assert act["previous_application_identifier"] == "code.exe"
    assert act["payload"]["process_id"] == 200
    assert act["payload"]["is_rapid_switch"] is False


def test_rapid_application_switch_detection(builder):
    tracker = ApplicationActivityTracker(event_builder=builder, rapid_switch_threshold_seconds=0.3)

    app_a = ForegroundAppInfo(process_id=100, executable_name="code.exe", application_identifier="code.exe")
    tracker.process_foreground_sample(app_a, sample_time_monotonic=10.0)

    # Switch to Slack only 0.15s later (< 0.3s)
    app_b = ForegroundAppInfo(process_id=200, executable_name="slack.exe", application_identifier="slack.exe")
    events = tracker.process_foreground_sample(app_b, sample_time_monotonic=10.15)

    assert len(events) == 2
    assert events[1]["event_type"] == "application_activated"
    assert events[1]["payload"]["is_rapid_switch"] is True


def test_flush_current_activity_on_shutdown(builder):
    tracker = ApplicationActivityTracker(event_builder=builder)

    app_a = ForegroundAppInfo(process_id=100, executable_name="code.exe", application_identifier="code.exe")
    tracker.process_foreground_sample(app_a, sample_time_monotonic=50.0)

    # Flush on shutdown at monotonic 62.0
    deact_event = tracker.flush_current_activity(transition_trigger="AGENT_SHUTDOWN", sample_time_monotonic=62.0)

    assert deact_event is not None
    assert deact_event["event_type"] == "application_deactivated"
    assert deact_event["application_identifier"] == "code.exe"
    assert deact_event["payload"]["duration_seconds"] == 12.0
    assert deact_event["payload"]["transition_trigger"] == "AGENT_SHUTDOWN"

    # Subsequent flush should return None since state is cleared
    assert tracker.flush_current_activity() is None

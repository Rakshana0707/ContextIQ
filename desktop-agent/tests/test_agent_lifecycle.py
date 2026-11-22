"""Tests for DesktopAgent end-to-end lifecycle and sampling steps."""
import pytest
from app.agent import DesktopAgent
from app.config import AgentConfig


class MockWin32Provider:
    """Mock for Win32 foreground API."""
    def __init__(self, hwnd: int = 101, pid: int = 1000, image_path: str = "C:\\Apps\\code.exe"):
        self.hwnd = hwnd
        self.pid = pid
        self.image_path = image_path

    def get_foreground_window(self) -> int:
        return self.hwnd

    def get_window_thread_process_id(self, hwnd: int) -> int:
        return self.pid if hwnd == self.hwnd else 0

    def get_process_image_path(self, pid: int) -> str | None:
        return self.image_path if pid == self.pid else None

    def get_window_text(self, hwnd: int) -> str | None:
        return None


class MockIdleProvider:
    """Mock for idle time API."""
    def __init__(self, idle_seconds: float = 5.0):
        self.idle_seconds = idle_seconds

    def get_idle_duration_seconds(self) -> float:
        return self.idle_seconds


@pytest.fixture
def agent_setup(tmp_path):
    db_file = tmp_path / "lifecycle_agent.db"
    config = AgentConfig(
        db_path=str(db_file),
        user_id="user-lifecycle-test",
        idle_threshold_seconds=120.0,
        polling_interval_seconds=0.1,
        heartbeat_interval_seconds=999.0,  # disable during step tests
    )

    win32_mock = MockWin32Provider(
        hwnd=101,
        pid=1000,
        image_path="C:\\Apps\\code.exe",
    )
    idle_mock = MockIdleProvider(idle_seconds=5.0)

    agent = DesktopAgent(
        config=config,
        win32_provider=win32_mock,
        idle_provider=idle_mock,
    )
    return agent, win32_mock, idle_mock


def test_agent_refuses_collection_without_consent(agent_setup):
    agent, win32_mock, idle_mock = agent_setup

    # Consent not granted initially
    events = agent.step()
    assert len(events) == 0

    stats = agent.local_db.get_stats()
    assert stats["total_events"] == 0


def test_agent_end_to_end_collection_and_exclusions(agent_setup):
    agent, win32_mock, idle_mock = agent_setup

    # Explicitly grant consent
    agent.consent_checker.grant_consent()

    # Step 1: In Code.exe
    step1_events = agent.step()
    assert len(step1_events) == 1
    assert step1_events[0]["event_type"] == "application_activated"
    assert step1_events[0]["application_identifier"] == "code.exe"

    # Step 2: Switch to Slack.exe
    win32_mock.hwnd = 202
    win32_mock.pid = 2000
    win32_mock.image_path = "C:\\Apps\\slack.exe"

    step2_events = agent.step()
    assert len(step2_events) == 2
    assert step2_events[0]["event_type"] == "application_deactivated"
    assert step2_events[0]["application_identifier"] == "code.exe"
    assert step2_events[1]["event_type"] == "application_activated"
    assert step2_events[1]["application_identifier"] == "slack.exe"

    # Step 3: Switch to a password manager (KeePass.exe - on global denylist)
    win32_mock.hwnd = 303
    win32_mock.pid = 3000
    win32_mock.image_path = "C:\\Tools\\KeePass.exe"

    step3_events = agent.step()
    # Should deactivate Slack.exe, but SUPPRESS KeePass.exe activation!
    assert len(step3_events) == 1
    assert step3_events[0]["event_type"] == "application_deactivated"
    assert step3_events[0]["application_identifier"] == "slack.exe"

    # Verify all events persisted in local DB
    stats = agent.local_db.get_stats()
    assert stats["total_events"] == 4
    assert stats["pending_events"] == 4


def test_agent_zero_buffering_when_monitoring_paused(agent_setup):
    agent, win32_mock, idle_mock = agent_setup
    agent.consent_checker.grant_consent()

    # Initial activation in Code.exe
    agent.step()
    initial_stats = agent.local_db.get_stats()
    assert initial_stats["total_events"] == 1

    # Pause monitoring
    agent.consent_checker.pause()

    # User switches to Chrome while paused
    win32_mock.hwnd = 404
    win32_mock.pid = 4000
    win32_mock.image_path = "C:\\Apps\\chrome.exe"

    paused_events = agent.step()
    # Must generate 0 events!
    assert len(paused_events) == 0

    # Local buffer must NOT secretly increase
    paused_stats = agent.local_db.get_stats()
    assert paused_stats["total_events"] == initial_stats["total_events"]

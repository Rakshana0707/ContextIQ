"""Tests for foreground window metadata collector."""
import pytest
from app.collectors.foreground_window import ForegroundWindowCollector, NativeWin32Provider


class MockWin32Provider:
    """Deterministic mock for Win32 API interactions."""

    def __init__(
        self,
        hwnd: int = 1001,
        pid: int = 4321,
        image_path: str = "C:\\Program Files\\Microsoft VS Code\\Code.exe",
        window_title: str = "workspace - Visual Studio Code",
    ):
        self.hwnd = hwnd
        self.pid = pid
        self.image_path = image_path
        self.window_title = window_title

    def get_foreground_window(self) -> int:
        return self.hwnd

    def get_window_thread_process_id(self, hwnd: int) -> int:
        return self.pid if hwnd == self.hwnd else 0

    def get_process_image_path(self, pid: int) -> str | None:
        return self.image_path if pid == self.pid else None

    def get_window_text(self, hwnd: int) -> str | None:
        return self.window_title if hwnd == self.hwnd else None


def test_foreground_collector_normal_app():
    provider = MockWin32Provider(
        hwnd=1001,
        pid=5555,
        image_path="C:\\Users\\User\\AppData\\Local\\Programs\\Slack\\slack.exe",
        window_title="General - Slack",
    )
    # Strict default: capture_window_titles is False
    collector = ForegroundWindowCollector(provider=provider, capture_window_titles=False)
    info = collector.get_foreground_app()

    assert info.process_id == 5555
    assert info.executable_name == "slack.exe"
    assert info.application_identifier == "slack.exe"
    assert info.hwnd == 1001
    # Privacy invariant: window_title is None by default
    assert info.window_title is None


def test_foreground_collector_desktop_null_hwnd():
    provider = MockWin32Provider(hwnd=0)
    collector = ForegroundWindowCollector(provider=provider)
    info = collector.get_foreground_app()

    assert info.process_id is None
    assert info.executable_name == "desktop"
    assert info.application_identifier == "desktop"
    assert info.hwnd == 0
    assert info.window_title is None


def test_foreground_collector_unqueryable_process():
    # Simulate system or protected process where OpenProcess / QueryFullProcessImageName fails
    class UnqueryableProvider(MockWin32Provider):
        def get_process_image_path(self, pid: int) -> str | None:
            return None

    provider = UnqueryableProvider(hwnd=2002, pid=4)
    collector = ForegroundWindowCollector(provider=provider)
    info = collector.get_foreground_app()

    assert info.process_id == 4
    assert info.executable_name == "unknown.exe"
    assert info.application_identifier == "unknown.exe"
    assert info.window_title is None


def test_foreground_collector_title_capture_when_explicitly_consented():
    provider = MockWin32Provider(
        hwnd=3003,
        pid=1234,
        image_path="C:\\Windows\\notepad.exe",
        window_title="Untitled - Notepad",
    )
    collector = ForegroundWindowCollector(provider=provider, capture_window_titles=True)
    info = collector.get_foreground_app()

    assert info.executable_name == "notepad.exe"
    assert info.window_title == "Untitled - Notepad"

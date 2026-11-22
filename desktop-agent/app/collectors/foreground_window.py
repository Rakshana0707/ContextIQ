"""Foreground window and process metadata collector using Win32 APIs."""
import ctypes
import logging
import os
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)

# Win32 Process Access Rights
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


@dataclass
class ForegroundAppInfo:
    """Snapshot metadata of the active foreground application."""
    process_id: int | None
    executable_name: str
    application_identifier: str
    hwnd: int | None = None
    window_title: str | None = None  # None by default (privacy invariant)


class NativeWin32Provider(Protocol):
    """Protocol for Win32 API interactions to support unit test mocking."""
    def get_foreground_window(self) -> int: ...
    def get_window_thread_process_id(self, hwnd: int) -> int: ...
    def get_process_image_path(self, pid: int) -> str | None: ...
    def get_window_text(self, hwnd: int) -> str | None: ...


class WindowsNativeProvider:
    """Actual Win32 implementation using ctypes."""

    def __init__(self) -> None:
        if platform.system() == "Windows":
            self.user32 = ctypes.windll.user32
            self.kernel32 = ctypes.windll.kernel32
        else:
            self.user32 = None
            self.kernel32 = None

    def get_foreground_window(self) -> int:
        if not self.user32:
            return 0
        return self.user32.GetForegroundWindow()

    def get_window_thread_process_id(self, hwnd: int) -> int:
        if not self.user32 or not hwnd:
            return 0
        pid = ctypes.c_ulong()
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value

    def get_process_image_path(self, pid: int) -> str | None:
        if not self.kernel32 or not pid:
            return None
        h_process = self.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h_process:
            return None
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = ctypes.c_ulong(1024)
            success = self.kernel32.QueryFullProcessImageNameW(h_process, 0, buf, ctypes.byref(size))
            if success:
                return buf.value
            return None
        finally:
            self.kernel32.CloseHandle(h_process)

    def get_window_text(self, hwnd: int) -> str | None:
        if not self.user32 or not hwnd:
            return None
        length = self.user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return None
        buf = ctypes.create_unicode_buffer(length + 1)
        self.user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value


class ForegroundWindowCollector:
    """Collects foreground application metadata with strict privacy preservation."""

    def __init__(
        self,
        provider: NativeWin32Provider | None = None,
        capture_window_titles: bool = False,
    ):
        self.provider = provider or WindowsNativeProvider()
        self.capture_window_titles = capture_window_titles

    def get_foreground_app(self) -> ForegroundAppInfo:
        """Query currently active foreground window and process.

        Guarantees:
        - Never raises uncaught exceptions on permissions or process closure.
        - Window titles are strictly None unless explicitly enabled.
        """
        try:
            hwnd = self.provider.get_foreground_window()
            if not hwnd:
                return ForegroundAppInfo(
                    process_id=None,
                    executable_name="desktop",
                    application_identifier="desktop",
                    hwnd=0,
                    window_title=None,
                )

            pid = self.provider.get_window_thread_process_id(hwnd)
            if not pid:
                return ForegroundAppInfo(
                    process_id=None,
                    executable_name="system",
                    application_identifier="system",
                    hwnd=hwnd,
                    window_title=None,
                )

            image_path = self.provider.get_process_image_path(pid)
            if image_path:
                exe_name = Path(image_path).name.lower()
            else:
                exe_name = "unknown.exe"

            # Application identifier defaults to normalized executable name
            app_id = exe_name

            # Window title is strictly omitted by default
            title: str | None = None
            if self.capture_window_titles:
                title = self.provider.get_window_text(hwnd)

            return ForegroundAppInfo(
                process_id=pid,
                executable_name=exe_name,
                application_identifier=app_id,
                hwnd=hwnd,
                window_title=title,
            )
        except Exception as e:
            logger.debug("Error retrieving foreground application: %s", e)
            return ForegroundAppInfo(
                process_id=None,
                executable_name="unknown.exe",
                application_identifier="unknown.exe",
                hwnd=None,
                window_title=None,
            )

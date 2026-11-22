"""Idle and inactivity detection using aggregate Windows GetLastInputInfo."""
import ctypes
import logging
import platform
import time
from datetime import datetime, timezone
from typing import Any, Protocol

from app.events.event_builder import EventBuilder

logger = logging.getLogger(__name__)


class LASTINPUTINFO(ctypes.Structure):
    """Win32 LASTINPUTINFO structure."""
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("dwTime", ctypes.c_uint),
    ]


class IdleTimeProvider(Protocol):
    """Protocol for abstracting idle-time queries."""
    def get_idle_duration_seconds(self) -> float: ...


class WindowsIdleProvider:
    """Win32 native implementation of idle time retrieval."""

    def __init__(self) -> None:
        if platform.system() == "Windows":
            self.user32 = ctypes.windll.user32
            self.kernel32 = ctypes.windll.kernel32
        else:
            self.user32 = None
            self.kernel32 = None

    def get_idle_duration_seconds(self) -> float:
        if not self.user32 or not self.kernel32:
            return 0.0

        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)

        if not self.user32.GetLastInputInfo(ctypes.byref(lii)):
            return 0.0

        # Query system tick count in milliseconds
        try:
            current_ticks = self.kernel32.GetTickCount64()
        except AttributeError:
            current_ticks = self.kernel32.GetTickCount()

        # Handle 32-bit tick wrap-around if necessary
        dw_time = lii.dwTime
        if current_ticks < dw_time:
            # 32-bit overflow handling
            elapsed_ms = (0xFFFFFFFF - dw_time) + current_ticks
        else:
            elapsed_ms = current_ticks - dw_time

        return max(0.0, float(elapsed_ms) / 1000.0)


class IdleDetector:
    """Detects continuous user inactivity and returns using aggregate idle time.

    Strictly complies with the Anti-Surveillance Manifesto:
    - Zero keyboard key codes collected.
    - Zero mouse coordinates or click targets collected.
    - Only aggregate elapsed idle seconds from OS timer.
    """

    def __init__(
        self,
        event_builder: EventBuilder,
        idle_threshold_seconds: float = 120.0,
        provider: IdleTimeProvider | None = None,
    ):
        self.event_builder = event_builder
        self.idle_threshold_seconds = idle_threshold_seconds
        self.provider = provider or WindowsIdleProvider()

        # State machine
        self.is_idle: bool = False
        self.idle_start_utc: datetime | None = None
        self.last_known_app: str | None = None

    def check_idle_state(
        self,
        current_app_id: str | None = None,
        check_time_utc: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Sample idle status and emit events when crossing the idle threshold.

        Returns:
            list[dict]: Zero or one event (`user_idle_started` or `user_active_returned`).
        """
        now_utc = check_time_utc or datetime.now(timezone.utc)
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)

        idle_seconds = self.provider.get_idle_duration_seconds()

        events: list[dict[str, Any]] = []

        if not self.is_idle:
            # User was active; check if they crossed the idle threshold
            if idle_seconds >= self.idle_threshold_seconds:
                self.is_idle = True
                self.idle_start_utc = now_utc
                self.last_known_app = current_app_id

                event = self.event_builder.build_user_idle_started(
                    idle_threshold_seconds=self.idle_threshold_seconds,
                    last_active_app=current_app_id,
                )
                event["event_timestamp"] = now_utc.isoformat()
                events.append(event)
        else:
            # User was idle; check if user input resumed
            # (idle_seconds drops well below the threshold upon user interaction)
            if idle_seconds < self.idle_threshold_seconds:
                total_duration = 0.0
                if self.idle_start_utc is not None:
                    total_duration = max(0.0, (now_utc - self.idle_start_utc).total_seconds())
                else:
                    total_duration = self.idle_threshold_seconds

                self.is_idle = False
                self.idle_start_utc = None

                event = self.event_builder.build_user_active_returned(
                    total_idle_duration_seconds=total_duration,
                    resuming_app=current_app_id,
                )
                event["event_timestamp"] = now_utc.isoformat()
                events.append(event)

        return events

    def reset(self) -> None:
        """Reset idle state machine."""
        self.is_idle = False
        self.idle_start_utc = None
        self.last_known_app = None

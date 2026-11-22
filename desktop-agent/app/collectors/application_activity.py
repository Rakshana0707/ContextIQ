"""Application activity tracker for activation intervals and transitions."""
import logging
import time
from datetime import datetime, timezone
from typing import Any

from app.collectors.foreground_window import ForegroundAppInfo
from app.events.event_builder import EventBuilder

logger = logging.getLogger(__name__)


class ApplicationActivityTracker:
    """Tracks continuous application focus intervals and emits activation events."""

    def __init__(
        self,
        event_builder: EventBuilder,
        rapid_switch_threshold_seconds: float = 0.2,
    ):
        self.event_builder = event_builder
        self.rapid_switch_threshold = rapid_switch_threshold_seconds

        # Internal transition state
        self.current_app_id: str | None = None
        self.current_pid: int | None = None
        self.current_hwnd: int | None = None
        self.activation_time_monotonic: float | None = None
        self.activation_timestamp_utc: datetime | None = None
        self.previous_app_id: str | None = None

    def process_foreground_sample(
        self,
        app_info: ForegroundAppInfo,
        sample_time_monotonic: float | None = None,
        sample_time_utc: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Process a foreground sample and emit events on application transitions.

        Returns:
            list[dict]: Zero, one, or two events (e.g. [deactivated, activated]).
        """
        now_mono = sample_time_monotonic if sample_time_monotonic is not None else time.monotonic()
        now_utc = sample_time_utc or datetime.now(timezone.utc)
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)

        target_app = app_info.application_identifier or "unknown.exe"
        target_pid = app_info.process_id

        # Check if the active application has changed
        is_same_app = (
            self.current_app_id is not None
            and self.current_app_id == target_app
            and (self.current_pid == target_pid or target_pid is None or self.current_pid is None)
        )

        if is_same_app:
            # Repeated sample on the same running foreground app; no transition
            return []

        events: list[dict[str, Any]] = []

        # 1. If an application was previously active, emit application_deactivated
        is_rapid = False
        if self.current_app_id is not None and self.activation_time_monotonic is not None:
            duration = max(0.0, now_mono - self.activation_time_monotonic)
            is_rapid = duration < self.rapid_switch_threshold

            deactivated_event = self.event_builder.build_application_deactivated(
                app_id=self.current_app_id,
                duration_seconds=duration,
                process_id=self.current_pid,
                transition_trigger="FOCUS_SWITCH",
            )
            deactivated_event["event_timestamp"] = now_utc.isoformat()
            events.append(deactivated_event)

        # 2. Emit application_activated for the new foreground application
        activated_event = self.event_builder.build_application_activated(
            app_id=target_app,
            previous_app_id=self.current_app_id,
            process_id=target_pid,
            is_rapid_switch=is_rapid,
        )
        activated_event["event_timestamp"] = now_utc.isoformat()
        events.append(activated_event)

        # 3. Update internal state
        self.previous_app_id = self.current_app_id
        self.current_app_id = target_app
        self.current_pid = target_pid
        self.current_hwnd = app_info.hwnd
        self.activation_time_monotonic = now_mono
        self.activation_timestamp_utc = now_utc

        return events

    def flush_current_activity(
        self,
        transition_trigger: str = "AGENT_SHUTDOWN",
        sample_time_monotonic: float | None = None,
        sample_time_utc: datetime | None = None,
    ) -> dict[str, Any] | None:
        """Deactivate the current active application cleanly (e.g. on pause or shutdown)."""
        if self.current_app_id is None or self.activation_time_monotonic is None:
            return None

        now_mono = sample_time_monotonic if sample_time_monotonic is not None else time.monotonic()
        now_utc = sample_time_utc or datetime.now(timezone.utc)
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)

        duration = max(0.0, now_mono - self.activation_time_monotonic)
        event = self.event_builder.build_application_deactivated(
            app_id=self.current_app_id,
            duration_seconds=duration,
            process_id=self.current_pid,
            transition_trigger=transition_trigger,
        )
        event["event_timestamp"] = now_utc.isoformat()

        # Reset active tracker state
        self.previous_app_id = self.current_app_id
        self.current_app_id = None
        self.current_pid = None
        self.current_hwnd = None
        self.activation_time_monotonic = None
        self.activation_timestamp_utc = None

        return event

    def reset(self) -> None:
        """Reset internal state without generating deactivation event."""
        self.current_app_id = None
        self.current_pid = None
        self.current_hwnd = None
        self.activation_time_monotonic = None
        self.activation_timestamp_utc = None
        self.previous_app_id = None

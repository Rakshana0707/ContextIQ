"""Event builder and canonical envelope constructor for desktop activity telemetry."""
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any


def generate_event_id() -> str:
    """Generate a time-ordered UUID string (UUIDv7 style if possible, or UUIDv4)."""
    # 48-bit timestamp ms + random bits formatted as standard UUID string
    try:
        # Check if Python 3.14+ has uuid.uuid7 or fallback
        if hasattr(uuid, "uuid7"):
            return str(uuid.uuid7())  # type: ignore
    except Exception:
        pass

    # Construct timestamp-ordered UUID (UUIDv7 compatible format)
    ms = int(time.time() * 1000)
    rand_a = os.urandom(2).hex()
    rand_b = os.urandom(8).hex()
    # 018d9f4a-9b12-78a0-9832-7e92b8d00123
    ms_hex = f"{ms:012x}"
    return f"{ms_hex[:8]}-{ms_hex[8:]}-7{rand_a[:3]}-a{rand_a[3:]}{rand_b[:2]}-{rand_b[2:]}"


class EventBuilder:
    """Constructs self-describing, privacy-checked telemetry events."""

    def __init__(self, user_id: str, device_id: str, source: str = "desktop_agent_windows"):
        self.user_id = user_id
        self.device_id = device_id
        self.source = source
        self.schema_version = "1.0.0"

    def build_event(
        self,
        event_type: str,
        application_identifier: str | None = None,
        previous_application_identifier: str | None = None,
        current_application_identifier: str | None = None,
        payload: dict[str, Any] | None = None,
        correlation_id: str | None = None,
        session_id: str | None = None,
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """Construct canonical telemetry event dictionary."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        elif timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        return {
            "event_id": generate_event_id(),
            "user_id": self.user_id,
            "device_id": self.device_id,
            "event_type": event_type,
            "event_timestamp": timestamp.isoformat(),
            "source": self.source,
            "schema_version": self.schema_version,
            "session_id": session_id,
            "correlation_id": correlation_id,
            "application_identifier": application_identifier,
            "previous_application_identifier": previous_application_identifier,
            "current_application_identifier": current_application_identifier,
            "payload": payload or {},
        }

    def build_application_activated(
        self,
        app_id: str,
        previous_app_id: str | None,
        process_id: int | None = None,
        is_rapid_switch: bool = False,
    ) -> dict[str, Any]:
        """Convenience method for application_activated event."""
        payload: dict[str, Any] = {
            "process_id": process_id,
            "is_rapid_switch": is_rapid_switch,
        }
        return self.build_event(
            event_type="application_activated",
            application_identifier=app_id,
            previous_application_identifier=previous_app_id,
            current_application_identifier=app_id,
            payload=payload,
        )

    def build_application_deactivated(
        self,
        app_id: str,
        duration_seconds: float,
        process_id: int | None = None,
        transition_trigger: str = "FOCUS_LOST",
    ) -> dict[str, Any]:
        """Convenience method for application_deactivated event."""
        payload: dict[str, Any] = {
            "process_id": process_id,
            "duration_seconds": round(max(0.0, duration_seconds), 4),
            "transition_trigger": transition_trigger,
        }
        return self.build_event(
            event_type="application_deactivated",
            application_identifier=app_id,
            current_application_identifier=None,
            payload=payload,
        )

    def build_user_idle_started(
        self,
        idle_threshold_seconds: float,
        last_active_app: str | None = None,
    ) -> dict[str, Any]:
        """Convenience method for user_idle_started event."""
        payload: dict[str, Any] = {
            "idle_threshold_seconds": idle_threshold_seconds,
            "last_active_application": last_active_app,
        }
        return self.build_event(
            event_type="user_idle_started",
            application_identifier=last_active_app,
            payload=payload,
        )

    def build_user_active_returned(
        self,
        total_idle_duration_seconds: float,
        resuming_app: str | None = None,
    ) -> dict[str, Any]:
        """Convenience method for user_active_returned event."""
        payload: dict[str, Any] = {
            "total_idle_duration_seconds": round(max(0.0, total_idle_duration_seconds), 4),
            "resuming_into_application": resuming_app,
        }
        return self.build_event(
            event_type="user_active_returned",
            application_identifier=resuming_app,
            payload=payload,
        )

    def build_heartbeat(
        self,
        uptime_seconds: float,
        cpu_percent: float,
        memory_mb: float,
        buffer_pending_count: int,
        buffer_total_count: int,
    ) -> dict[str, Any]:
        """Convenience method for heartbeat event."""
        payload: dict[str, Any] = {
            "uptime_seconds": round(uptime_seconds, 1),
            "cpu_percent": round(cpu_percent, 2),
            "memory_mb": round(memory_mb, 2),
            "buffer_pending_count": buffer_pending_count,
            "buffer_total_count": buffer_total_count,
        }
        return self.build_event(
            event_type="heartbeat",
            payload=payload,
        )

    def build_agent_started(self, version: str = "1.0.0", startup_mode: str = "MANUAL") -> dict[str, Any]:
        """Convenience method for agent_started event."""
        payload = {
            "version": version,
            "startup_mode": startup_mode,
        }
        return self.build_event(
            event_type="agent_started",
            payload=payload,
        )

    def build_agent_stopped(self, uptime_seconds: float, reason: str = "CLEAN_SHUTDOWN") -> dict[str, Any]:
        """Convenience method for agent_stopped event."""
        payload = {
            "uptime_seconds": round(max(0.0, uptime_seconds), 2),
            "reason": reason,
        }
        return self.build_event(
            event_type="agent_stopped",
            payload=payload,
        )

    def build_telemetry_paused(self, duration_seconds: float | None = None, reason: str = "USER_REQUEST") -> dict[str, Any]:
        """Convenience method for telemetry_paused event."""
        payload = {
            "duration_seconds": duration_seconds,
            "reason": reason,
        }
        return self.build_event(
            event_type="telemetry_paused",
            payload=payload,
        )

    def build_telemetry_resumed(self, total_paused_seconds: float | None = None) -> dict[str, Any]:
        """Convenience method for telemetry_resumed event."""
        payload = {
            "total_paused_seconds": total_paused_seconds,
        }
        return self.build_event(
            event_type="telemetry_resumed",
            payload=payload,
        )

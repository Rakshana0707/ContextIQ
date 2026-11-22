"""Local privacy and consent checker ensuring strictly opt-in and zero secret buffering."""
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_CATEGORIES = {
    "app_transitions",
    "inactivity_detection",
    "session_reconstruction",
    "behavioral_analytics",
    "local_storage",
    "server_sync",
}


class ConsentChecker:
    """Evaluates whether activity collection is currently permitted.

    Guarantees:
    - Opt-in by default: Collection refused if consent is missing or revoked.
    - Zero-buffering: If paused, stops collecting and generating events entirely.
    """

    def __init__(
        self,
        is_telemetry_enabled: bool = False,
        is_paused: bool = False,
        paused_until: datetime | None = None,
        enabled_categories: set[str] | None = None,
    ):
        self.is_telemetry_enabled = is_telemetry_enabled
        self.is_paused = is_paused
        self.paused_until = paused_until
        self.enabled_categories = enabled_categories if enabled_categories is not None else set(DEFAULT_CATEGORIES)

    def is_collection_allowed(self, category: str | None = None) -> bool:
        """Verify whether collection is currently permitted.

        Checks:
        1. Is overall telemetry enabled? (Opt-in invariant)
        2. Is collection currently paused? (Quick-pause timer)
        3. If a category is requested, is that category consented?
        """
        # 1. Base opt-in check
        if not self.is_telemetry_enabled:
            return False

        # 2. Pause check
        if self.is_paused:
            now = datetime.now(timezone.utc)
            if self.paused_until is not None:
                # Ensure timezone aware
                p_until = self.paused_until
                if p_until.tzinfo is None:
                    p_until = p_until.replace(tzinfo=timezone.utc)

                if now >= p_until:
                    # Timer expired; auto-resume
                    logger.info("Pause duration expired; auto-resuming collection")
                    self.is_paused = False
                    self.paused_until = None
                else:
                    return False
            else:
                return False

        # 3. Category check
        if category and category not in self.enabled_categories:
            return False

        return True

    def pause(self, duration_seconds: float | None = None) -> None:
        """Pause collection immediately.

        When paused, the agent will stop creating events and NOT buffer secretly.
        """
        self.is_paused = True
        if duration_seconds is not None and duration_seconds > 0:
            self.paused_until = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)
        else:
            self.paused_until = None
        logger.info("Telemetry collection PAUSED (paused_until=%s)", self.paused_until)

    def resume(self) -> None:
        """Resume collection immediately."""
        self.is_paused = False
        self.paused_until = None
        logger.info("Telemetry collection RESUMED")

    def grant_consent(self, categories: list[str] | set[str] | None = None) -> None:
        """Grant consent explicitly."""
        self.is_telemetry_enabled = True
        self.is_paused = False
        self.paused_until = None
        if categories:
            self.enabled_categories = set(categories)
        else:
            self.enabled_categories = set(DEFAULT_CATEGORIES)
        logger.info("Telemetry consent GRANTED for categories: %s", self.enabled_categories)

    def revoke_consent(self) -> None:
        """Revoke consent immediately. All collection halts."""
        self.is_telemetry_enabled = False
        self.is_paused = False
        self.paused_until = None
        logger.info("Telemetry consent REVOKED; all monitoring terminated")

    def update_from_backend(self, settings_data: dict[str, Any], consent_data: dict[str, Any] | None) -> None:
        """Synchronize local checker state with server privacy settings."""
        if consent_data and consent_data.get("consent_status") == "GRANTED":
            self.is_telemetry_enabled = True
            cats = consent_data.get("enabled_categories", [])
            if cats:
                self.enabled_categories = set(cats)
        else:
            self.is_telemetry_enabled = False

        self.is_paused = bool(settings_data.get("is_paused", False))
        p_until = settings_data.get("paused_until")
        if p_until:
            try:
                dt = datetime.fromisoformat(p_until.replace("Z", "+00:00"))
                self.paused_until = dt
            except Exception:
                self.paused_until = None
        else:
            self.paused_until = None

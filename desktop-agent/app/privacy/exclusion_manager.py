"""Application exclusion manager for process blacklisting and denylist filtering."""
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Global Security Denylist (Anti-surveillance baseline)
GLOBAL_SECURITY_DENYLIST: set[str] = {
    "1password.exe",
    "keepass.exe",
    "keepassxc.exe",
    "bitwarden.exe",
    "lastpass.exe",
    "dashlane.exe",
    "credentialmanager.exe",
    "taskmgr.exe",
    "regedit.exe",
    "mstsc.exe",
}


class ExclusionManager:
    """Manages global and user-configured process exclusions."""

    def __init__(self, initial_exclusions: list[str] | set[str] | None = None):
        self._user_exclusions: set[str] = set()
        if initial_exclusions:
            for item in initial_exclusions:
                self._user_exclusions.add(item.lower().strip())

    def is_excluded(self, app_identifier: str | None) -> bool:
        """Return True if application is blacklisted by global denylist or user exclusion."""
        if not app_identifier:
            return False

        clean_id = app_identifier.lower().strip()

        # 1. Global security denylist check
        if clean_id in GLOBAL_SECURITY_DENYLIST:
            return True

        # 2. User exclusions check (exact executable name or substring)
        if clean_id in self._user_exclusions:
            return True

        for excl in self._user_exclusions:
            if excl and excl in clean_id:
                return True

        return False

    def add_exclusion(self, app_identifier: str) -> None:
        """Add application to user exclusion list."""
        clean_id = app_identifier.lower().strip()
        self._user_exclusions.add(clean_id)
        logger.info("Added user application exclusion: %s", clean_id)

    def remove_exclusion(self, app_identifier: str) -> None:
        """Remove application from user exclusion list."""
        clean_id = app_identifier.lower().strip()
        self._user_exclusions.discard(clean_id)
        logger.info("Removed user application exclusion: %s", clean_id)

    def update_from_backend(self, exclusions_data: list[dict[str, Any]] | list[str]) -> None:
        """Update exclusions list from backend API response."""
        new_set: set[str] = set()
        for item in exclusions_data:
            if isinstance(item, dict):
                app_id = item.get("application_identifier", "")
            else:
                app_id = str(item)
            if app_id:
                new_set.add(app_id.lower().strip())
        self._user_exclusions = new_set
        logger.debug("Updated user exclusions (%d rules)", len(self._user_exclusions))

    def get_all_exclusions(self) -> set[str]:
        """Return combined global and user exclusion identifiers."""
        return set(GLOBAL_SECURITY_DENYLIST) | set(self._user_exclusions)

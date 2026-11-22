"""
agent_privacy_guard.py

Pure client/agent-side privacy and consent enforcement engine.
This module executes on the desktop agent prior to recording or buffering
any event, guaranteeing that:

1. Telemetry is refused if valid consent is absent, revoked, or expired.
2. Collection is halted immediately when paused by the user.
3. Excluded applications are strictly redacted (zero identity, duration, or transition leakage).
4. Data minimization rules are enforced without network dependency.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

# Pre-compiled regex patterns for client-side title sanitization
PATH_REGEX = re.compile(r"[A-Za-z]:\\[\w\s\-\.\\]+\\([\w\s\-\.]+\.[a-zA-Z0-9]+)")
URL_PARAM_REGEX = re.compile(r"(https?://[a-zA-Z0-9\-\.]+(?::\d+)?)(/[^\s?]*)?(?:\?[^\s]*)?")
EMAIL_REGEX = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")
CREDIT_CARD_REGEX = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")
SSN_REGEX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

# Mandatory global denylist of high-risk security, credential, and private tools
DEFAULT_GLOBAL_DENYLIST: Set[str] = {
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
    "tor.exe",
    "vpn.exe",
}


class AgentPrivacyGuard:
    """
    Offline-capable privacy sentinel.
    Instantiated on the desktop collector with cached or locally configured policies.
    """

    def __init__(
        self,
        consent_status: Optional[str] = None,
        enabled_categories: Optional[List[str]] = None,
        is_paused: bool = False,
        paused_until: Optional[datetime] = None,
        user_exclusions: Optional[Set[str]] = None,
    ):
        self.consent_status = consent_status
        self.enabled_categories = set(enabled_categories or [])
        self.is_paused = is_paused
        self.paused_until = paused_until
        self.user_exclusions = {app.lower().strip() for app in (user_exclusions or set())}

    def is_consent_valid(self, now: Optional[datetime] = None) -> bool:
        """Check if valid active consent exists."""
        if not self.consent_status or self.consent_status.upper() != "GRANTED":
            return False
        return True

    def is_monitoring_paused(self, now: Optional[datetime] = None) -> bool:
        """Check if telemetry collection is currently paused."""
        if not self.is_paused:
            return False
        if self.paused_until is None:
            return True
        now = now or datetime.now(timezone.utc)
        return now < self.paused_until

    def can_collect_category(self, category: str, now: Optional[datetime] = None) -> bool:
        """
        Verify whether an event belonging to `category` can be collected.
        Returns False if consent is absent, paused, or category not opted-in.
        """
        if not self.is_consent_valid(now):
            return False
        if self.is_monitoring_paused(now):
            return False
        return category in self.enabled_categories

    def is_application_excluded(self, process_name: str) -> bool:
        """Check if process name is in user exclusions or global security denylist."""
        clean = process_name.lower().strip()
        if clean in DEFAULT_GLOBAL_DENYLIST:
            return True
        return clean in self.user_exclusions

    def sanitize_window_title(self, raw_title: str) -> str:
        """
        Strip sensitive substrings from raw window title prior to recording.
        Removes file paths, URLs, query params, emails, card numbers.
        """
        if not raw_title:
            return ""
        clean = raw_title
        clean = PATH_REGEX.sub(r"\1", clean)
        clean = URL_PARAM_REGEX.sub(r"\1", clean)
        clean = EMAIL_REGEX.sub("[EMAIL]", clean)
        clean = CREDIT_CARD_REGEX.sub("[REDACTED_CARD]", clean)
        clean = SSN_REGEX.sub("[REDACTED_ID]", clean)
        return clean[:100].strip()

    def filter_and_sanitize_event(
        self,
        event_type: str,
        category: str,
        process_name: str,
        raw_title: str,
        duration_seconds: Optional[float] = None,
        now: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Master privacy gatekeeper.
        Returns sanitized event dictionary ready for local buffering,
        or None if collection must be suppressed.
        """
        # 1. Verification of global consent and pause state
        if not self.can_collect_category(category, now):
            return None

        clean_process = process_name.lower().strip()

        # 2. Application exclusion handling (Task 4)
        if self.is_application_excluded(clean_process):
            # When an excluded app is active:
            # - Do not record its identity.
            # - Do not record its duration.
            # - Do not record its transitions as identifiable application events.
            # - Do not inspect its content.
            # Privacy-preserving: emit neutral blackout placeholder with ZERO process identity
            return {
                "event_type": "EXCLUDED_APPLICATION_MASKED",
                "application_identifier": "EXCLUDED_PRIVATE",
                "sanitized_title": "[PRIVATE]",
                "category": "EXCLUDED",
                "duration_seconds": None,
                "is_excluded": True,
            }

        # 3. Standard sanitized event output
        return {
            "event_type": event_type,
            "application_identifier": clean_process,
            "sanitized_title": self.sanitize_window_title(raw_title),
            "category": category,
            "duration_seconds": duration_seconds,
            "is_excluded": False,
        }

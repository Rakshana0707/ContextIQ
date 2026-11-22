"""Tests for consent verification, pause state, and process exclusions."""
from datetime import datetime, timezone, timedelta
import pytest
from app.privacy.consent_checker import ConsentChecker
from app.privacy.exclusion_manager import ExclusionManager, GLOBAL_SECURITY_DENYLIST


def test_consent_default_disabled():
    checker = ConsentChecker()
    # Opt-in invariant: collection is False by default
    assert checker.is_collection_allowed() is False
    assert checker.is_collection_allowed("app_transitions") is False


def test_grant_and_revoke_consent():
    checker = ConsentChecker()
    checker.grant_consent(categories=["app_transitions", "local_storage"])

    assert checker.is_collection_allowed() is True
    assert checker.is_collection_allowed("app_transitions") is True
    assert checker.is_collection_allowed("local_storage") is True
    # Non-consented category is rejected
    assert checker.is_collection_allowed("server_sync") is False

    # Revoke consent
    checker.revoke_consent()
    assert checker.is_collection_allowed() is False
    assert checker.is_collection_allowed("app_transitions") is False


def test_quick_pause_and_timer_expiration():
    checker = ConsentChecker(is_telemetry_enabled=True)
    assert checker.is_collection_allowed() is True

    # Pause for 60 seconds
    checker.pause(duration_seconds=60)
    assert checker.is_collection_allowed() is False

    # Simulate timer expiration: set paused_until to past
    checker.paused_until = datetime.now(timezone.utc) - timedelta(seconds=10)
    assert checker.is_collection_allowed() is True
    assert checker.is_paused is False


def test_manual_resume():
    checker = ConsentChecker(is_telemetry_enabled=True)
    checker.pause()
    assert checker.is_collection_allowed() is False

    checker.resume()
    assert checker.is_collection_allowed() is True


def test_global_security_denylist_exclusions():
    manager = ExclusionManager()

    # Password managers and system utilities must be blocked
    for app in ["1password.exe", "KeePass.exe", "bitwarden.exe", "taskmgr.exe", "regedit.exe"]:
        assert manager.is_excluded(app) is True

    # Normal productivity tools must be allowed
    for app in ["code.exe", "slack.exe", "chrome.exe", "notepad.exe"]:
        assert manager.is_excluded(app) is False


def test_user_defined_app_exclusions():
    manager = ExclusionManager()
    assert manager.is_excluded("whatsapp.exe") is False

    manager.add_exclusion("whatsapp.exe")
    assert manager.is_excluded("whatsapp.exe") is True
    assert manager.is_excluded("WhatsApp.exe") is True  # Case insensitive

    manager.remove_exclusion("whatsapp.exe")
    assert manager.is_excluded("whatsapp.exe") is False

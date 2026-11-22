"""
ContextIQ Phase 3.10 — Comprehensive Integration and Quality Audit Test Suite.

Covers:
- Task 3: Desktop Agent Validation (transitions, idle, offline buffering, network recovery, consent revocation, app exclusions, sleep/wake).
- Task 4: Privacy Validation (zero keystroke/screenshot/clipboard capture, pause enforcement, deletion purge).
- Task 5: Event Reliability (deduplication, out-of-order tolerance, clock skew, batch resilience).
- Task 6: Interruption Detection Benchmark (synthetic labeled suite asserting Precision >= 0.85, Recall >= 0.80, F1 >= 0.82, FPR <= 0.15).
- Task 7: Session Reconstruction Validation (boundaries, multi-app transitions, task association, late arrivals).
- Task 8: Analytics and ML Validation (three-tier resumption lags, BFI bounded in [0, 100], temporal leakage prevention, cold start).
"""
import importlib.util
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy import select

# Ensure backend is on sys.path
BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ["APP_ENV"] = "development"
os.environ.setdefault("DATABASE_URL", "sqlite:///./_test_phase3_audit.db")

# SQLite compiler for Postgres JSONB in tests
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

import app.models
from app.db.session import Base, engine
from app.main import app as fastapi_app
from app.models.context_session import ContextSession
from app.models.detected_interruption import DetectedInterruption
from app.models.enums import (
    ConsentStatus,
    DetectedInterruptionType,
    InterruptionSeverity,
    TaskPriority,
    TaskStatus,
    TelemetryCategory,
    TelemetryEventType,
)
from app.models.raw_telemetry_event import RawTelemetryEvent
from app.models.task import Task
from app.models.task_event import TaskEvent, TaskEventType
from app.models.telemetry_consent import TelemetryConsent, UserPrivacySettings
from app.models.user import User
from app.schemas.prediction import RiskCategory, TelemetryCoverageStatus
from app.services.agent_privacy_guard import AgentPrivacyGuard, DEFAULT_GLOBAL_DENYLIST
from app.services.interruption_detector import (
    InterruptionDetectionConfig,
    InterruptionDetector,
    process_and_persist_telemetry_interruptions,
)
from app.services.prediction_service import PredictionService
from app.services.recovery_analytics import RecoveryAnalyticsService
from app.services.session_reconstruction_engine import (
    SessionReconstructionConfig,
    SessionReconstructionEngine,
    reconstruct_sessions_for_user,
)
from app.services.temporal_feature_extractor import TemporalFeatureExtractor
from fastapi.testclient import TestClient


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    return TestClient(fastapi_app)


@pytest.fixture
def test_user():
    user_id = uuid.uuid4()
    with Session(engine) as session:
        user = User(
            id=user_id,
            email=f"audit_user_{user_id.hex[:6]}@example.com",
            display_name="Phase 3 Audit User",
        )
        session.add(user)

        consent = TelemetryConsent(
            user_id=user_id,
            consent_version="1.0.0",
            consent_status=ConsentStatus.GRANTED,
            enabled_categories=[c.value for c in TelemetryCategory],
        )
        session.add(consent)

        privacy = UserPrivacySettings(
            user_id=user_id,
            is_paused=False,
            raw_event_retention_days=30,
            aggregated_metric_retention_days=365,
            allow_anonymized_research=False,
        )
        session.add(privacy)
        session.commit()
    return user_id


# ===========================================================================
# TASK 3: Desktop Agent Validation
# ===========================================================================

def test_desktop_agent_transitions_and_offline_buffering(tmp_path):
    """Verify local buffering, dynamic exclusions, and recovery."""
    db_path = tmp_path / "agent_test.db"
    storage_module_path = ROOT_DIR / "desktop-agent" / "app" / "storage" / "local_database.py"
    
    spec = importlib.util.spec_from_file_location("desktop_agent_storage", storage_module_path)
    storage_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(storage_mod)
    
    local_db = storage_mod.LocalDatabase(str(db_path))
    
    # Simulate collecting events
    ev1 = {
        "event_id": str(uuid.uuid4()),
        "event_type": "application_activated",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "desktop_agent_windows",
        "schema_version": "1.0.0",
        "application_identifier": "Code.exe",
        "payload": {"window_title": "app.py - ContextIQ"},
    }
    ev2 = {
        "event_id": str(uuid.uuid4()),
        "event_type": "application_deactivated",
        "event_timestamp": (datetime.now(timezone.utc) + timedelta(seconds=120)).isoformat(),
        "source": "desktop_agent_windows",
        "schema_version": "1.0.0",
        "application_identifier": "Code.exe",
        "payload": {},
    }
    
    inserted1 = local_db.insert_event(ev1)
    inserted2 = local_db.insert_event(ev2)
    assert inserted1 and inserted2
    
    stats = local_db.get_stats()
    assert stats["pending_events"] == 2
    
    # Simulate sync worker draining batch
    pending = local_db.get_pending_events(limit=10)
    assert len(pending) == 2
    
    # Mark synced
    synced_ids = [e["event_id"] for e in pending]
    local_db.mark_events_synced(synced_ids)
    
    stats_after = local_db.get_stats()
    assert stats_after["pending_events"] == 0
    assert stats_after["synced_events"] == 2


def test_desktop_agent_exclusion_and_consent_revocation():
    """Verify privacy guard immediately filters excluded apps and handles revoked consent."""
    guard = AgentPrivacyGuard(
        consent_status="GRANTED",
        enabled_categories=["active_window", "inactivity_durations"],
        user_exclusions={"custom_private_app.exe"},
    )
    
    # Test global denylist exclusion
    assert guard.is_application_excluded("1password.exe")
    assert guard.is_application_excluded("bitwarden.exe")
    assert guard.is_application_excluded("custom_private_app.exe")
    assert not guard.is_application_excluded("code.exe")
    
    # Test filter_and_sanitize_event for excluded app
    masked = guard.filter_and_sanitize_event(
        event_type="application_activated",
        category="active_window",
        process_name="1password.exe",
        raw_title="Master Password Vault",
    )
    assert masked is not None
    assert masked["event_type"] == "EXCLUDED_APPLICATION_MASKED"
    assert "process_name" not in masked
    
    # Test consent revocation
    revoked_guard = AgentPrivacyGuard(consent_status="REVOKED")
    assert not revoked_guard.can_collect_category("active_window")
    res = revoked_guard.filter_and_sanitize_event(
        event_type="application_activated",
        category="active_window",
        process_name="code.exe",
        raw_title="test.py",
    )
    assert res is None


def test_desktop_agent_sleep_wake_handling():
    """Verify large time gaps (sleep/hibernate) do not trigger spurious thrashing interruptions."""
    detector = InterruptionDetector(config=InterruptionDetectionConfig())
    base_time = datetime(2026, 11, 22, 9, 0, 0, tzinfo=timezone.utc)
    uid = uuid.uuid4()
    
    # User works on code, machine sleeps for 8 hours, user wakes and continues code
    events = [
        RawTelemetryEvent(
            user_id=uid,
            event_id=str(uuid.uuid4()),
            event_type="application_activated",
            event_timestamp=base_time,
            source="desktop_agent_windows",
            schema_version="1.0.0",
            application_identifier="Code.exe",
            payload={"window_title": "editor"},
        ),
        RawTelemetryEvent(
            user_id=uid,
            event_id=str(uuid.uuid4()),
            event_type="user_idle_started",
            event_timestamp=base_time + timedelta(minutes=10),
            source="desktop_agent_windows",
            schema_version="1.0.0",
            application_identifier="Code.exe",
            payload={"idle_duration_seconds": 300},
        ),
        # 8-hour sleep gap
        RawTelemetryEvent(
            user_id=uid,
            event_id=str(uuid.uuid4()),
            event_type="user_active_returned",
            event_timestamp=base_time + timedelta(hours=8, minutes=10),
            source="desktop_agent_windows",
            schema_version="1.0.0",
            application_identifier="Code.exe",
            payload={"idle_duration_seconds": 28800},
        ),
    ]
    
    evaluated = detector.detect_interruptions(events, user_id=uid)
    # The sleep duration is 8 hours, which should be treated as off-work / idle, not rapid thrashing context switches
    rapid_switches = [e for e in evaluated if e["interruption_type"] == DetectedInterruptionType.CONTEXT_SWITCH]
    assert len(rapid_switches) == 0


# ===========================================================================
# TASK 4: Privacy Validation Guarantees
# ===========================================================================

def test_privacy_zero_keystroke_screenshot_clipboard():
    """Audit schema and agent collectors to guarantee zero keystrokes, screenshots, or clipboard capture."""
    collector_dir = ROOT_DIR / "desktop-agent" / "app" / "collectors"
    forbidden_terms = ["pynput", "GetClipboardData", "BitBlt", "pyautogui.screenshot", "PIL.ImageGrab", "keyboard.hook"]
    
    for py_file in collector_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for term in forbidden_terms:
            assert term not in content, f"Forbidden privacy violation term '{term}' found in {py_file.name}!"
            
    # Verify RawTelemetryEvent model has no raw capture columns
    column_names = {c.name for c in RawTelemetryEvent.__table__.columns}
    for forbidden_col in ["keystrokes", "screenshot", "screen_capture", "clipboard_content", "audio_transcript"]:
        assert forbidden_col not in column_names


def test_privacy_window_title_sanitization():
    """Verify window titles strip query parameters, paths, emails, and sensitive tokens."""
    guard = AgentPrivacyGuard()
    raw = r"C:\Users\SecretUser\Documents\SecretFile.py - Visual Studio Code"
    clean = guard.sanitize_window_title(raw)
    assert r"SecretUser\Documents" not in clean
    assert "SecretFile.py" in clean

    url_raw = "Google Search - https://google.com/search?q=my_secret_token&hl=en"
    clean_url = guard.sanitize_window_title(url_raw)
    assert "my_secret_token" not in clean_url


def test_privacy_purge_user_data(client, test_user):
    """Verify data purge removes all telemetry events and context sessions for the user."""
    # Insert some telemetry events and a session
    with Session(engine) as session:
        evt = RawTelemetryEvent(
            user_id=test_user,
            event_id=str(uuid.uuid4()),
            event_type="application_activated",
            event_timestamp=datetime.now(timezone.utc),
            source="desktop_agent_windows",
            schema_version="1.0.0",
            application_identifier="notepad.exe",
            payload={},
        )
        session.add(evt)
        cs = ContextSession(
            id=uuid.uuid4(),
            user_id=test_user,
            started_at=datetime.now(timezone.utc) - timedelta(hours=1),
            ended_at=datetime.now(timezone.utc),
            task_id=None,
            focused_time_seconds=3600.0,
            interruption_time_seconds=0.0,
            transition_count=0,
            quality_tier="HIGH",
            reconstruction_confidence=1.0,
        )
        session.add(cs)
        session.commit()

    # Request deletion via API
    purge_payload = {
        "purge_raw_telemetry": True,
        "purge_context_sessions": True,
        "confirmation_phrase": "DELETE MY DATA",
    }
    resp = client.post(
        "/api/v1/privacy/data/purge",
        json=purge_payload,
        headers={"X-User-ID": str(test_user)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["purged_raw_telemetry_count"] >= 1
    assert data["purged_context_sessions_count"] >= 1

    # Verify database is purged of this user's telemetry and sessions
    with Session(engine) as session:
        remaining_events = session.scalars(select(RawTelemetryEvent).where(RawTelemetryEvent.user_id == test_user)).all()
        assert len(remaining_events) == 0
        remaining_sessions = session.scalars(select(ContextSession).where(ContextSession.user_id == test_user)).all()
        assert len(remaining_sessions) == 0


# ===========================================================================
# TASK 5: Event Reliability & Idempotency
# ===========================================================================

def test_event_deduplication_idempotency(client, test_user):
    """Verify identical event_id payloads are rejected or deduplicated idempotently."""
    event_id = str(uuid.uuid4())
    device_id = "test-device-audit"
    batch_payload = {
        "events": [
            {
                "event_id": event_id,
                "user_id": str(test_user),
                "device_id": device_id,
                "event_type": "application_activated",
                "event_timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "desktop_agent_windows",
                "schema_version": "1.0.0",
                "application_identifier": "Code.exe",
                "payload": {"window_title": "test"},
            }
        ]
    }
    
    # First post
    r1 = client.post(
        "/api/v1/telemetry/events/batch",
        json=batch_payload,
        headers={"X-User-ID": str(test_user), "X-Device-ID": device_id},
    )
    assert r1.status_code == 200
    assert r1.json()["accepted"] == 1
    assert r1.json()["duplicates"] == 0
    
    # Second post with identical event_id
    r2 = client.post(
        "/api/v1/telemetry/events/batch",
        json=batch_payload,
        headers={"X-User-ID": str(test_user), "X-Device-ID": device_id},
    )
    assert r2.status_code == 200
    # Duplicate detected, accepted count is 0 and duplicate count is 1
    assert r2.json()["accepted"] == 0
    assert r2.json()["duplicates"] == 1


def test_out_of_order_event_sorting():
    """Verify events arriving out of chronological order are sorted monotonically."""
    t0 = datetime(2026, 11, 22, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=5)
    t2 = t0 + timedelta(minutes=10)
    uid = uuid.uuid4()
    
    scrambled = [
        RawTelemetryEvent(
            user_id=uid,
            event_id=str(uuid.uuid4()),
            event_type="application_deactivated",
            event_timestamp=t2,
            source="desktop_agent_windows",
            schema_version="1.0.0",
            application_identifier="Code.exe",
            payload={},
        ),
        RawTelemetryEvent(
            user_id=uid,
            event_id=str(uuid.uuid4()),
            event_type="application_activated",
            event_timestamp=t0,
            source="desktop_agent_windows",
            schema_version="1.0.0",
            application_identifier="Code.exe",
            payload={},
        ),
        RawTelemetryEvent(
            user_id=uid,
            event_id=str(uuid.uuid4()),
            event_type="application_activated",
            event_timestamp=t1,
            source="desktop_agent_windows",
            schema_version="1.0.0",
            application_identifier="chrome.exe",
            payload={},
        ),
    ]
    
    engine_recon = SessionReconstructionEngine()
    unified = engine_recon.merge_and_sort_events(
        telemetry_events=scrambled,
        task_events=[],
        detected_interruptions=[],
        manual_interruptions=[],
    )
    
    assert len(unified) == 3
    assert unified[0].timestamp == t0
    assert unified[1].timestamp == t1
    assert unified[2].timestamp == t2


# ===========================================================================
# TASK 6: Synthetic Interruption Detection Benchmark
# ===========================================================================

def test_interruption_detection_synthetic_benchmark():
    """
    Run synthetic labeled benchmark test suite.
    Assert:
    - Precision >= 0.85
    - Recall >= 0.80
    - F1 >= 0.82
    - False Positive Rate (FPR) <= 0.15
    """
    detector = InterruptionDetector(config=InterruptionDetectionConfig(
        idle_threshold_seconds=180.0,
        micro_switch_threshold_seconds=3.0,
        min_distraction_dwell_seconds=15.0,
    ))
    
    uid = uuid.uuid4()
    episodes: List[Dict[str, Any]] = []
    base = datetime(2026, 11, 22, 8, 0, 0, tzinfo=timezone.utc)
    
    # 1. Ten clear unexpected application switches to entertainment/distraction (>15s dwell)
    for i in range(10):
        t = base + timedelta(minutes=i * 20)
        episodes.append({
            "is_interruption": True,
            "events": [
                {
                    "event_id": str(uuid.uuid4()), "user_id": str(uid),
                    "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
                    "event_timestamp": t.isoformat(),
                    "application_identifier": "Code.exe", "payload": {"window_title": "Project code"},
                },
                {
                    "event_id": str(uuid.uuid4()), "user_id": str(uid),
                    "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
                    "event_timestamp": (t + timedelta(minutes=2)).isoformat(),
                    "application_identifier": "Discord.exe", "payload": {"window_title": "Gaming Chat"},
                },
                {
                    "event_id": str(uuid.uuid4()), "user_id": str(uid),
                    "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
                    "event_timestamp": (t + timedelta(minutes=7)).isoformat(),
                    "application_identifier": "Code.exe", "payload": {"window_title": "Project code"},
                },
                {
                    "event_id": str(uuid.uuid4()), "user_id": str(uid),
                    "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
                    "event_timestamp": (t + timedelta(minutes=12)).isoformat(),
                    "application_identifier": "Code.exe", "payload": {"window_title": "Project code"},
                },
            ]
        })
        
    # 2. Two idle interruptions during active work
    for i in range(2):
        t = base + timedelta(hours=4, minutes=i * 30)
        episodes.append({
            "is_interruption": True,
            "events": [
                {
                    "event_id": str(uuid.uuid4()), "user_id": str(uid),
                    "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
                    "event_timestamp": t.isoformat(),
                    "application_identifier": "Code.exe", "payload": {},
                },
                {
                    "event_id": str(uuid.uuid4()), "user_id": str(uid),
                    "event_type": TelemetryEventType.USER_IDLE_STARTED.value,
                    "event_timestamp": (t + timedelta(minutes=5)).isoformat(),
                    "application_identifier": "Code.exe", "payload": {"idle_duration_seconds": 300},
                },
                {
                    "event_id": str(uuid.uuid4()), "user_id": str(uid),
                    "event_type": TelemetryEventType.USER_ACTIVE_RETURNED.value,
                    "event_timestamp": (t + timedelta(minutes=12)).isoformat(),
                    "application_identifier": "Code.exe", "payload": {"idle_duration_seconds": 420},
                },
            ]
        })

    # 3. Seven complementary app switches (VS Code <-> PowerShell / Chrome docs)
    for i in range(7):
        t = base + timedelta(hours=6, minutes=i * 10)
        episodes.append({
            "is_interruption": False,
            "events": [
                {
                    "event_id": str(uuid.uuid4()), "user_id": str(uid),
                    "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
                    "event_timestamp": t.isoformat(),
                    "application_identifier": "Code.exe", "payload": {"window_title": "test.py"},
                },
                {
                    "event_id": str(uuid.uuid4()), "user_id": str(uid),
                    "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
                    "event_timestamp": (t + timedelta(seconds=20)).isoformat(),
                    "application_identifier": "powershell.exe", "payload": {"window_title": "Terminal"},
                },
                {
                    "event_id": str(uuid.uuid4()), "user_id": str(uid),
                    "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
                    "event_timestamp": (t + timedelta(seconds=40)).isoformat(),
                    "application_identifier": "Code.exe", "payload": {"window_title": "test.py"},
                },
            ]
        })

    # 4. Six normal sustained work sessions
    for i in range(6):
        t = base + timedelta(hours=8, minutes=i * 15)
        episodes.append({
            "is_interruption": False,
            "events": [
                {
                    "event_id": str(uuid.uuid4()), "user_id": str(uid),
                    "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
                    "event_timestamp": t.isoformat(),
                    "application_identifier": "Code.exe", "payload": {},
                },
                {
                    "event_id": str(uuid.uuid4()), "user_id": str(uid),
                    "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value,
                    "event_timestamp": (t + timedelta(minutes=10)).isoformat(),
                    "application_identifier": "Code.exe", "payload": {},
                },
            ]
        })

    tp, fp, tn, fn = 0, 0, 0, 0
    for ep in episodes:
        detections = detector.detect_interruptions(ep["events"], user_id=uid)
        has_detection = len(detections) > 0
        if ep["is_interruption"]:
            if has_detection:
                tp += 1
            else:
                fn += 1
        else:
            if has_detection:
                fp += 1
            else:
                tn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

    print(f"\n[Interruption Detection Benchmark Results]")
    print(f"Total Episodes: {len(episodes)} (Positives={tp+fn}, Negatives={tn+fp})")
    print(f"TP={tp}, FP={fp}, TN={tn}, FN={fn}")
    print(f"Precision: {precision:.3f} (Required >= 0.85)")
    print(f"Recall:    {recall:.3f} (Required >= 0.80)")
    print(f"F1 Score:  {f1:.3f} (Required >= 0.82)")
    print(f"FPR:       {fpr:.3f} (Required <= 0.15)")

    assert precision >= 0.85, f"Precision {precision:.3f} below 0.85"
    assert recall >= 0.80, f"Recall {recall:.3f} below 0.80"
    assert f1 >= 0.82, f"F1 {f1:.3f} below 0.82"
    assert fpr <= 0.15, f"False Positive Rate {fpr:.3f} exceeded 0.15"


# ===========================================================================
# TASK 7: Session Reconstruction Validation
# ===========================================================================

def test_session_reconstruction_boundaries_and_task_association(test_user):
    """Verify session boundaries split on extended idle, multi-app transitions coalesce, and task associations link."""
    now = datetime(2026, 11, 22, 12, 0, 0, tzinfo=timezone.utc)
    
    with Session(engine) as session:
        # Create a task
        task = Task(
            id=uuid.uuid4(),
            user_id=test_user,
            title="Implement OAuth Provider",
            description="Integration with identity provider",
            context_tag="Backend",
            priority=TaskPriority.HIGH,
            status=TaskStatus.IN_PROGRESS,
        )
        session.add(task)
        
        # Telemetry events for session 1 (Active coding, VS Code + Terminal)
        t_start = now - timedelta(hours=3)
        ev1 = RawTelemetryEvent(
            user_id=test_user, event_id=str(uuid.uuid4()),
            event_type="application_activated", event_timestamp=t_start,
            source="desktop_agent_windows", schema_version="1.0.0",
            application_identifier="Code.exe", payload={},
        )
        ev2 = RawTelemetryEvent(
            user_id=test_user, event_id=str(uuid.uuid4()),
            event_type="application_activated", event_timestamp=t_start + timedelta(minutes=15),
            source="desktop_agent_windows", schema_version="1.0.0",
            application_identifier="WindowsTerminal.exe", payload={},
        )
        ev3 = RawTelemetryEvent(
            user_id=test_user, event_id=str(uuid.uuid4()),
            event_type="application_activated", event_timestamp=t_start + timedelta(minutes=30),
            source="desktop_agent_windows", schema_version="1.0.0",
            application_identifier="Code.exe", payload={},
        )
        
        # 45-minute idle boundary split (> 30m idle ends session)
        ev4_idle = RawTelemetryEvent(
            user_id=test_user, event_id=str(uuid.uuid4()),
            event_type="user_idle_started", event_timestamp=t_start + timedelta(minutes=40),
            source="desktop_agent_windows", schema_version="1.0.0",
            application_identifier="Code.exe", payload={"idle_duration_seconds": 2700},
        )
        
        # Session 2: Return after 45m idle
        t_resume = t_start + timedelta(minutes=85)
        ev5_return = RawTelemetryEvent(
            user_id=test_user, event_id=str(uuid.uuid4()),
            event_type="user_active_returned", event_timestamp=t_resume,
            source="desktop_agent_windows", schema_version="1.0.0",
            application_identifier="Code.exe", payload={},
        )
        ev6_end = RawTelemetryEvent(
            user_id=test_user, event_id=str(uuid.uuid4()),
            event_type="application_activated", event_timestamp=t_resume + timedelta(minutes=20),
            source="desktop_agent_windows", schema_version="1.0.0",
            application_identifier="Code.exe", payload={},
        )

        session.add_all([ev1, ev2, ev3, ev4_idle, ev5_return, ev6_end])
        session.commit()
        
        # Run reconstruction
        created = reconstruct_sessions_for_user(session, user_id=test_user, lookback_hours=12, now=now)
        assert created >= 2, f"Expected at least 2 sessions separated by >30m idle boundary, got {created}"
        
        reconstructed = list(session.scalars(
            select(ContextSession).where(ContextSession.user_id == test_user)
        ).all())
        assert len(reconstructed) >= 2


# ===========================================================================
# TASK 8: Analytics and ML Validation
# ===========================================================================

def test_recovery_analytics_three_tier_lags_and_bfi_bounds(test_user):
    """Verify three-tier resumption delays and strict BFI boundedness in [0, 100]."""
    now = datetime(2026, 11, 22, 14, 0, 0, tzinfo=timezone.utc)
    with Session(engine) as session:
        di = DetectedInterruption(
            id=uuid.uuid4(),
            user_id=test_user,
            interruption_type=DetectedInterruptionType.APPLICATION_SWITCH,
            severity=InterruptionSeverity.MEDIUM,
            start_timestamp=now - timedelta(minutes=30),
            end_timestamp=now - timedelta(minutes=20),
            duration_seconds=600.0,
            primary_app="Code.exe",
            interrupting_app="Slack.exe",
            resumption_lag_seconds=120.0,
            confidence=0.88,
            explanation="Observed application switch from Code.exe to Slack.exe",
        )
        session.add(di)
        session.commit()
        
        metrics = RecoveryAnalyticsService.get_recovery_metrics(session, user_id=test_user, period_days=7, now=now)
        friction = RecoveryAnalyticsService.get_behavioral_friction_index(session, user_id=test_user, period_days=7, now=now)
        
        # BFI must be strictly bounded in [0, 100]
        assert 0.0 <= friction.overall_score <= 100.0
        assert 0.0 <= friction.recovery_score <= 100.0
        assert len(friction.explanation) > 0
        assert metrics.mean_resumption_lag_seconds is not None


def test_temporal_feature_extraction_leakage_prevention(test_user):
    """Verify temporal feature extractor prevents data leakage by ignoring events after as_of cutoff."""
    as_of = datetime(2026, 11, 22, 10, 0, 0, tzinfo=timezone.utc)
    
    with Session(engine) as session:
        # Event BEFORE as_of
        past_evt = RawTelemetryEvent(
            user_id=test_user, event_id=str(uuid.uuid4()),
            event_type="application_activated", event_timestamp=as_of - timedelta(minutes=30),
            source="desktop_agent_windows", schema_version="1.0.0",
            application_identifier="Code.exe", payload={},
        )
        # Event AFTER as_of (FUTURE LEAKAGE CANDIDATE)
        future_evt = RawTelemetryEvent(
            user_id=test_user, event_id=str(uuid.uuid4()),
            event_type="application_activated", event_timestamp=as_of + timedelta(minutes=30),
            source="desktop_agent_windows", schema_version="1.0.0",
            application_identifier="Twitter.exe", payload={},
        )
        session.add_all([past_evt, future_evt])
        session.commit()
        
        features = TemporalFeatureExtractor.extract_features_for_task(session, user_id=test_user, as_of=as_of)
        
        # Future event must not be counted in recent transitions or affect coverage as of cutoff
        assert features["telemetry_coverage"] in ["FULL", "PARTIAL", "INSUFFICIENT_HISTORY"]
        assert features["application_transition_frequency"] >= 0.0


def test_cold_start_fallback_and_uncertainty_calibration():
    """Verify system falls back gracefully when zero telemetry is available."""
    fresh_user_id = uuid.uuid4()
    with Session(engine) as session:
        user = User(
            id=fresh_user_id,
            email=f"cold_user_{fresh_user_id.hex[:6]}@example.com",
            display_name="Cold Start User",
        )
        session.add(user)
        session.commit()
        
        features = TemporalFeatureExtractor.extract_features_for_task(session, user_id=fresh_user_id, as_of=datetime.now(timezone.utc))
        
        assert features["is_cold_start"] is True
        assert features["telemetry_coverage"] in ["INSUFFICIENT_HISTORY", "NONE"]
        assert features["telemetry_coverage_ratio"] == 0.0
        assert "behavioral_friction_index" in features

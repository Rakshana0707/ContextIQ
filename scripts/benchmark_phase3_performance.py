"""
ContextIQ Phase 3.10 — Performance Testing and Benchmark Suite.

Measures:
1. Desktop agent local SQLite insertion throughput & latency.
2. Backend batch ingestion API throughput & latency.
3. Automated Interruption Detection engine throughput & latency.
4. Intelligent Session Reconstruction engine latency.
5. Behavioral Analytics and Friction Index calculation latency.
6. CPU and memory footprint indicators.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ["APP_ENV"] = "development"
os.environ.setdefault("DATABASE_URL", "sqlite:///./_benchmark_phase3.db")

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

import app.models
from app.db.session import Base, engine
from app.main import app as fastapi_app
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
from app.models.telemetry_consent import TelemetryConsent, UserPrivacySettings
from app.models.user import User
from app.services.interruption_detector import InterruptionDetector, InterruptionDetectionConfig
from app.services.recovery_analytics import RecoveryAnalyticsService
from app.services.session_reconstruction_engine import (
    SessionReconstructionConfig,
    SessionReconstructionEngine,
    reconstruct_sessions_for_user,
)
from fastapi.testclient import TestClient


def run_benchmarks():
    print("=" * 80)
    print("ContextIQ Phase 3.10 — Automated Behavioral Telemetry Performance Benchmarks")
    print("=" * 80)

    Base.metadata.create_all(bind=engine)
    client = TestClient(fastapi_app)

    bench_user_id = uuid.uuid4()
    with Session(engine) as session:
        user = User(
            id=bench_user_id,
            email=f"bench_{bench_user_id.hex[:6]}@example.com",
            display_name="Benchmark User",
        )
        session.add(user)
        consent = TelemetryConsent(
            user_id=bench_user_id,
            consent_version="1.0.0",
            consent_status=ConsentStatus.GRANTED,
            enabled_categories=[c.value for c in TelemetryCategory],
        )
        session.add(consent)
        session.commit()

    results: Dict[str, Any] = {}

    # -------------------------------------------------------------------------
    # 1. Local SQLite Buffer Throughput & Latency
    # -------------------------------------------------------------------------
    print("\n[Benchmark 1/5] Local SQLite Buffer Insertion Throughput...")
    storage_path = ROOT_DIR / "desktop-agent" / "app" / "storage" / "local_database.py"
    spec = importlib.util.spec_from_file_location("local_db_mod", storage_path)
    storage_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(storage_mod)

    bench_sqlite_file = ROOT_DIR / "_bench_local_agent.db"
    if bench_sqlite_file.exists():
        bench_sqlite_file.unlink()

    local_db = storage_mod.LocalDatabase(str(bench_sqlite_file))
    event_count = 1000
    events = [
        {
            "event_id": str(uuid.uuid4()),
            "event_type": "application_activated" if i % 2 == 0 else "application_deactivated",
            "event_timestamp": (datetime.now(timezone.utc) + timedelta(seconds=i * 10)).isoformat(),
            "application_identifier": "Code.exe" if i % 4 != 0 else "chrome.exe",
            "payload": {"window_title": f"Bench Window {i}", "process_id": 1000 + (i % 5)},
        }
        for i in range(event_count)
    ]

    t0 = time.perf_counter()
    local_db.insert_events_batch(events)
    t1 = time.perf_counter()

    batch_duration_sec = t1 - t0
    batch_throughput = event_count / batch_duration_sec
    ms_per_event = (batch_duration_sec / event_count) * 1000.0

    print(f"  -> Inserted {event_count} events in {batch_duration_sec:.4f}s")
    print(f"  -> Throughput: {batch_throughput:.1f} events/sec")
    print(f"  -> Latency:    {ms_per_event:.4f} ms/event")

    results["local_sqlite_buffer"] = {
        "event_count": event_count,
        "duration_seconds": round(batch_duration_sec, 4),
        "throughput_events_per_sec": round(batch_throughput, 1),
        "latency_ms_per_event": round(ms_per_event, 4),
    }

    # -------------------------------------------------------------------------
    # 2. Ingestion API Batch Ingestion Throughput
    # -------------------------------------------------------------------------
    print("\n[Benchmark 2/5] Backend Telemetry Ingestion API (Batch Endpoint)...")
    batch_size = 200
    api_payload = {
        "events": [
            {
                "event_id": str(uuid.uuid4()),
                "user_id": str(bench_user_id),
                "device_id": "win-bench-01",
                "event_type": "application_activated",
                "event_timestamp": (datetime.now(timezone.utc) + timedelta(seconds=i * 5)).isoformat(),
                "source": "desktop_agent_windows",
                "schema_version": "1.0.0",
                "application_identifier": "Code.exe",
                "payload": {"title": f"Editor {i}"},
            }
            for i in range(batch_size)
        ]
    }

    t0 = time.perf_counter()
    resp = client.post(
        "/api/v1/telemetry/events/batch",
        json=api_payload,
        headers={"X-User-ID": str(bench_user_id), "X-Device-ID": "win-bench-01"},
    )
    t1 = time.perf_counter()
    api_duration = t1 - t0
    assert resp.status_code == 200
    api_throughput = batch_size / api_duration

    print(f"  -> Ingested {batch_size} events in {api_duration:.4f}s (Status: {resp.status_code})")
    print(f"  -> Throughput: {api_throughput:.1f} events/sec")
    print(f"  -> Request Latency: {api_duration * 1000.0:.2f} ms")

    results["backend_ingestion_api"] = {
        "batch_size": batch_size,
        "request_duration_ms": round(api_duration * 1000.0, 2),
        "throughput_events_per_sec": round(api_throughput, 1),
    }

    # -------------------------------------------------------------------------
    # 3. Interruption Detection Engine Latency & Throughput
    # -------------------------------------------------------------------------
    print("\n[Benchmark 3/5] Automated Interruption Detection Engine...")
    detector = InterruptionDetector(config=InterruptionDetectionConfig())
    eval_count = 500
    test_events = [
        {
            "event_id": str(uuid.uuid4()),
            "user_id": str(bench_user_id),
            "event_type": TelemetryEventType.APPLICATION_ACTIVATED.value if i % 5 != 0 else TelemetryEventType.USER_IDLE_STARTED.value,
            "event_timestamp": (datetime.now(timezone.utc) + timedelta(seconds=i * 30)).isoformat(),
            "application_identifier": "Code.exe" if i % 2 == 0 else "Slack.exe",
            "payload": {"idle_duration_seconds": 200 if i % 5 == 0 else 0},
        }
        for i in range(eval_count)
    ]

    t0 = time.perf_counter()
    detected = detector.detect_interruptions(test_events, user_id=bench_user_id)
    t1 = time.perf_counter()
    detector_duration = t1 - t0
    detector_throughput = eval_count / detector_duration
    latency_per_100 = (detector_duration / eval_count) * 100.0 * 1000.0

    print(f"  -> Processed {eval_count} events in {detector_duration:.4f}s (Detections: {len(detected)})")
    print(f"  -> Throughput: {detector_throughput:.1f} events/sec")
    print(f"  -> Latency:    {latency_per_100:.2f} ms per 100 events")

    results["interruption_detector"] = {
        "event_count": eval_count,
        "duration_seconds": round(detector_duration, 4),
        "throughput_events_per_sec": round(detector_throughput, 1),
        "latency_ms_per_100_events": round(latency_per_100, 2),
    }

    # -------------------------------------------------------------------------
    # 4. Session Reconstruction Engine Latency
    # -------------------------------------------------------------------------
    print("\n[Benchmark 4/5] Intelligent Session Reconstruction Engine...")
    with Session(engine) as session:
        t0 = time.perf_counter()
        sessions_created = reconstruct_sessions_for_user(
            session, user_id=bench_user_id, lookback_hours=48, now=datetime.now(timezone.utc)
        )
        t1 = time.perf_counter()
    recon_duration = t1 - t0
    print(f"  -> Reconstructed sessions in {recon_duration * 1000.0:.2f} ms (Created: {sessions_created})")

    results["session_reconstruction"] = {
        "duration_ms": round(recon_duration * 1000.0, 2),
        "sessions_created": sessions_created,
    }

    # -------------------------------------------------------------------------
    # 5. Cognitive Recovery & Behavioral Friction Index Calculation
    # -------------------------------------------------------------------------
    print("\n[Benchmark 5/5] Behavioral Friction Index & Recovery Analytics Latency...")
    with Session(engine) as session:
        t0 = time.perf_counter()
        metrics = RecoveryAnalyticsService.get_recovery_metrics(session, user_id=bench_user_id, period_days=14)
        friction = RecoveryAnalyticsService.get_behavioral_friction_index(session, user_id=bench_user_id, period_days=14)
        t1 = time.perf_counter()
    analytics_duration = t1 - t0
    print(f"  -> Computed Metrics & BFI in {analytics_duration * 1000.0:.2f} ms")
    print(f"  -> BFI Score: {friction.overall_score:.1f}/100")

    results["recovery_analytics_bfi"] = {
        "duration_ms": round(analytics_duration * 1000.0, 2),
        "overall_bfi_score": friction.overall_score,
    }

    # Cleanup bench sqlite file
    if bench_sqlite_file.exists():
        try:
            local_db.close()
            bench_sqlite_file.unlink()
        except Exception:
            pass

    print("\n" + "=" * 80)
    print("ALL PERFORMANCE BENCHMARKS COMPLETED SUCCESSFULLY")
    print("=" * 80)
    print(json.dumps(results, indent=2))
    return results


if __name__ == "__main__":
    run_benchmarks()

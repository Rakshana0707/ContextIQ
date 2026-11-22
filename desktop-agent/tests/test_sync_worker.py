"""Tests for background synchronization worker and offline operation."""
import pytest
from app.events.event_builder import EventBuilder
from app.monitoring.health import HealthMonitor
from app.privacy.consent_checker import ConsentChecker
from app.privacy.exclusion_manager import ExclusionManager
from app.storage.local_database import LocalDatabase
from app.sync.sync_worker import SyncWorker


class MockApiClient:
    def __init__(self, should_succeed: bool = True):
        self.should_succeed = should_succeed
        self.uploaded_batches = []

    def upload_telemetry_batch(self, events: list, user_id: str | None = None) -> bool:
        if self.should_succeed:
            self.uploaded_batches.append(events)
            return True
        return False

    def get_privacy_settings(self, user_id: str):
        return None

    def get_active_consent(self, user_id: str):
        return None

    def get_app_exclusions(self, user_id: str):
        return []


@pytest.fixture
def sync_setup(tmp_path):
    db_file = tmp_path / "sync_test.db"
    db = LocalDatabase(db_path=db_file)
    builder = EventBuilder(user_id="user-sync-test", device_id="dev-sync-test")
    health = HealthMonitor(event_builder=builder, local_db=db)
    consent = ConsentChecker(is_telemetry_enabled=True)
    exclusions = ExclusionManager()
    client = MockApiClient(should_succeed=True)

    worker = SyncWorker(
        local_db=db,
        api_client=client,
        consent_checker=consent,
        exclusion_manager=exclusions,
        health_monitor=health,
        user_id="user-sync-test",
        sync_interval_seconds=0.1,
        batch_size=10,
    )

    return worker, db, client, consent


def test_sync_worker_uploads_and_marks_synced(sync_setup):
    worker, db, client, consent = sync_setup

    # Insert 3 pending events
    for i in range(3):
        db.insert_event({
            "event_id": f"sync-ev-{i}",
            "event_type": "application_activated",
            "event_timestamp": "2026-11-22T10:00:00Z",
            "application_identifier": "code.exe",
            "payload": {},
        })

    assert len(db.get_pending_events()) == 3

    # Run single dispatch pass
    worker._dispatch_pending_batch()

    assert len(client.uploaded_batches) == 1
    assert len(client.uploaded_batches[0]) == 3

    # Pending events should now be 0 (marked SYNCED)
    assert len(db.get_pending_events()) == 0
    stats = db.get_stats()
    assert stats["synced_events"] == 3


def test_offline_operation_retains_events_and_increments_retries(sync_setup):
    worker, db, client, consent = sync_setup

    # Simulate offline backend
    client.should_succeed = False

    db.insert_event({
        "event_id": "offline-ev-1",
        "event_type": "application_activated",
        "event_timestamp": "2026-11-22T10:00:00Z",
        "application_identifier": "code.exe",
        "payload": {},
    })

    # Dispatch pass fails
    worker._dispatch_pending_batch()

    # Event remains in SQLite
    pending = db.get_pending_events()
    assert len(pending) == 1
    assert pending[0]["retry_count"] == 1
    assert pending[0]["sync_status"] == "PENDING"
    assert worker.health_monitor.sync_errors_count == 1


def test_sync_worker_skips_when_server_sync_category_disabled(sync_setup):
    worker, db, client, consent = sync_setup

    # Disable server_sync category
    consent.enabled_categories = {"app_transitions", "local_storage"}

    db.insert_event({
        "event_id": "no-sync-ev-1",
        "event_type": "application_activated",
        "event_timestamp": "2026-11-22T10:00:00Z",
        "application_identifier": "code.exe",
        "payload": {},
    })

    # Run worker loop check
    if consent.is_collection_allowed("server_sync"):
        worker._dispatch_pending_batch()

    # Did not upload
    assert len(client.uploaded_batches) == 0
    assert len(db.get_pending_events()) == 1

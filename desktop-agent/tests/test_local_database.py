"""Tests for SQLite WAL persistent local storage buffer."""
import pytest
from app.storage.local_database import LocalDatabase


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_buffer.db"
    db = LocalDatabase(db_path=db_file)
    yield db
    db.close()


def test_insert_and_retrieve_pending_event(temp_db):
    event = {
        "event_id": "018d9f4a-0001-7000-a000-000000000001",
        "event_type": "application_activated",
        "event_timestamp": "2026-11-22T10:00:00Z",
        "application_identifier": "code.exe",
        "payload": {"process_id": 1234},
    }

    inserted = temp_db.insert_event(event)
    assert inserted is True

    pending = temp_db.get_pending_events(limit=10)
    assert len(pending) == 1
    assert pending[0]["event_id"] == "018d9f4a-0001-7000-a000-000000000001"
    assert pending[0]["event_type"] == "application_activated"
    assert pending[0]["application_identifier"] == "code.exe"
    assert pending[0]["payload"]["process_id"] == 1234
    assert pending[0]["sync_status"] == "PENDING"
    assert pending[0]["retry_count"] == 0


def test_duplicate_event_prevention(temp_db):
    event = {
        "event_id": "duplicate-id-123",
        "event_type": "application_activated",
        "event_timestamp": "2026-11-22T10:00:00Z",
        "application_identifier": "code.exe",
        "payload": {},
    }

    # First insertion succeeds
    first_res = temp_db.insert_event(event)
    assert first_res is True

    # Duplicate insertion is ignored
    second_res = temp_db.insert_event(event)
    assert second_res is False

    stats = temp_db.get_stats()
    assert stats["total_events"] == 1


def test_mark_synced_and_purge(temp_db):
    events = [
        {
            "event_id": f"event-{i}",
            "event_type": "application_activated",
            "event_timestamp": "2026-11-01T10:00:00Z",  # Past date for purge test
            "application_identifier": "code.exe",
            "payload": {},
        }
        for i in range(5)
    ]
    temp_db.insert_events_batch(events)

    pending = temp_db.get_pending_events(limit=10)
    assert len(pending) == 5

    # Mark 3 events as synced
    synced_ids = ["event-0", "event-1", "event-2"]
    temp_db.mark_events_synced(synced_ids)

    # Only remaining 2 are pending
    remaining_pending = temp_db.get_pending_events(limit=10)
    assert len(remaining_pending) == 2

    # Purge synced events older than 7 days
    purged_count = temp_db.purge_synced_events(older_than_days=7)
    assert purged_count == 3

    stats = temp_db.get_stats()
    assert stats["total_events"] == 2
    assert stats["pending_events"] == 2


def test_retry_count_and_failed_status(temp_db):
    event = {
        "event_id": "fail-event-1",
        "event_type": "application_activated",
        "event_timestamp": "2026-11-22T10:00:00Z",
        "application_identifier": "code.exe",
        "payload": {},
    }
    temp_db.insert_event(event)

    # Fail 4 times (max_retries=5)
    for _ in range(4):
        temp_db.mark_events_failed(["fail-event-1"], max_retries=5)

    pending = temp_db.get_pending_events(max_retries=5)
    assert len(pending) == 1
    assert pending[0]["retry_count"] == 4
    assert pending[0]["sync_status"] == "PENDING"

    # 5th failure exceeds max_retries -> marks FAILED
    temp_db.mark_events_failed(["fail-event-1"], max_retries=5)

    pending_after = temp_db.get_pending_events(max_retries=5)
    assert len(pending_after) == 0

    stats = temp_db.get_stats()
    assert stats["failed_events"] == 1


def test_events_survive_agent_restart(tmp_path):
    db_file = tmp_path / "restart_test.db"

    # Session 1: insert events and close
    db1 = LocalDatabase(db_path=db_file)
    db1.insert_event({
        "event_id": "persist-1",
        "event_type": "application_activated",
        "event_timestamp": "2026-11-22T10:00:00Z",
        "application_identifier": "slack.exe",
        "payload": {},
    })
    db1.close()

    # Session 2: reopen same file
    db2 = LocalDatabase(db_path=db_file)
    pending = db2.get_pending_events()
    assert len(pending) == 1
    assert pending[0]["event_id"] == "persist-1"
    assert pending[0]["application_identifier"] == "slack.exe"
    db2.close()

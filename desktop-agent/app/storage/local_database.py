"""Persistent local SQLite buffer storage for desktop telemetry events."""
import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class LocalDatabase:
    """Thread-safe SQLite persistent buffer using Write-Ahead Logging (WAL)."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self.db_path),
                timeout=30.0,
                check_same_thread=False,
            )
            self._conn.row_factory = sqlite3.Row
            # Enable WAL mode and normal synchronous for fast, durable writes
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA synchronous=NORMAL;")
        return self._conn

    def _init_db(self) -> None:
        """Create necessary tables and indexes if they do not exist."""
        with self._lock:
            conn = self._get_connection()
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS telemetry_events (
                        event_id TEXT PRIMARY KEY,
                        event_type TEXT NOT NULL,
                        event_timestamp TEXT NOT NULL,
                        application_identifier TEXT,
                        payload TEXT NOT NULL,
                        sync_status TEXT NOT NULL DEFAULT 'PENDING',
                        retry_count INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL
                    );
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_telemetry_events_sync
                    ON telemetry_events (sync_status, retry_count, event_timestamp);
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_telemetry_events_timestamp
                    ON telemetry_events (event_timestamp);
                """)

    def insert_event(self, event: dict[str, Any]) -> bool:
        """Insert a single event.

        Uses INSERT OR IGNORE to guarantee idempotency across retries or replays.
        Returns True if inserted, False if ignored (duplicate).
        """
        now_str = datetime.now(timezone.utc).isoformat()
        event_id = event.get("event_id")
        if not event_id:
            raise ValueError("Event must contain an 'event_id'")

        payload_str = json.dumps(event.get("payload", {}))
        with self._lock:
            conn = self._get_connection()
            with conn:
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO telemetry_events (
                        event_id, event_type, event_timestamp, application_identifier,
                        payload, sync_status, retry_count, created_at
                    ) VALUES (?, ?, ?, ?, ?, 'PENDING', 0, ?)
                    """,
                    (
                        event_id,
                        event.get("event_type", "UNKNOWN"),
                        event.get("event_timestamp", now_str),
                        event.get("application_identifier"),
                        payload_str,
                        now_str,
                    ),
                )
                return cursor.rowcount > 0

    def insert_events_batch(self, events: list[dict[str, Any]]) -> int:
        """Insert a batch of events inside a single transaction."""
        if not events:
            return 0
        now_str = datetime.now(timezone.utc).isoformat()
        records = [
            (
                e["event_id"],
                e.get("event_type", "UNKNOWN"),
                e.get("event_timestamp", now_str),
                e.get("application_identifier"),
                json.dumps(e.get("payload", {})),
                now_str,
            )
            for e in events
            if "event_id" in e
        ]
        with self._lock:
            conn = self._get_connection()
            with conn:
                cursor = conn.executemany(
                    """
                    INSERT OR IGNORE INTO telemetry_events (
                        event_id, event_type, event_timestamp, application_identifier,
                        payload, sync_status, retry_count, created_at
                    ) VALUES (?, ?, ?, ?, ?, 'PENDING', 0, ?)
                    """,
                    records,
                )
                return cursor.rowcount

    def get_pending_events(self, limit: int = 50, max_retries: int = 5) -> list[dict[str, Any]]:
        """Retrieve pending events up to limit that have not exceeded max_retries."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute(
                """
                SELECT event_id, event_type, event_timestamp, application_identifier,
                       payload, sync_status, retry_count, created_at
                FROM telemetry_events
                WHERE sync_status = 'PENDING' AND retry_count < ?
                ORDER BY event_timestamp ASC
                LIMIT ?
                """,
                (max_retries, limit),
            )
            rows = cursor.fetchall()
            results = []
            for row in rows:
                try:
                    payload = json.loads(row["payload"])
                except Exception:
                    payload = {}
                results.append({
                    "event_id": row["event_id"],
                    "event_type": row["event_type"],
                    "event_timestamp": row["event_timestamp"],
                    "application_identifier": row["application_identifier"],
                    "payload": payload,
                    "sync_status": row["sync_status"],
                    "retry_count": row["retry_count"],
                    "created_at": row["created_at"],
                })
            return results

    def mark_events_synced(self, event_ids: list[str]) -> None:
        """Mark events as successfully synced to server."""
        if not event_ids:
            return
        placeholders = ",".join("?" for _ in event_ids)
        with self._lock:
            conn = self._get_connection()
            with conn:
                conn.execute(
                    f"UPDATE telemetry_events SET sync_status = 'SYNCED' WHERE event_id IN ({placeholders})",
                    event_ids,
                )

    def mark_events_failed(self, event_ids: list[str], max_retries: int = 5) -> None:
        """Increment retry count. If max_retries reached, set sync_status = 'FAILED'."""
        if not event_ids:
            return
        placeholders = ",".join("?" for _ in event_ids)
        with self._lock:
            conn = self._get_connection()
            with conn:
                conn.execute(
                    f"""
                    UPDATE telemetry_events
                    SET retry_count = retry_count + 1,
                        sync_status = CASE WHEN retry_count + 1 >= ? THEN 'FAILED' ELSE 'PENDING' END
                    WHERE event_id IN ({placeholders})
                    """,
                    [max_retries, *event_ids],
                )

    def purge_synced_events(self, older_than_days: int = 7) -> int:
        """Delete synced events older than threshold to control disk growth."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
        with self._lock:
            conn = self._get_connection()
            with conn:
                cursor = conn.execute(
                    "DELETE FROM telemetry_events WHERE sync_status = 'SYNCED' AND event_timestamp < ?",
                    (cutoff,),
                )
                return cursor.rowcount

    def purge_all_events(self) -> int:
        """Eradicate all local events (e.g. on GDPR right to erasure)."""
        with self._lock:
            conn = self._get_connection()
            with conn:
                cursor = conn.execute("DELETE FROM telemetry_events")
                return cursor.rowcount

    def get_stats(self) -> dict[str, Any]:
        """Return operational telemetry buffer stats."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN sync_status = 'PENDING' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN sync_status = 'SYNCED' THEN 1 ELSE 0 END) as synced,
                    SUM(CASE WHEN sync_status = 'FAILED' THEN 1 ELSE 0 END) as failed
                FROM telemetry_events
            """)
            row = cursor.fetchone()
            total = row["total"] or 0
            pending = row["pending"] or 0
            synced = row["synced"] or 0
            failed = row["failed"] or 0

            db_size = 0
            if self.db_path.exists():
                db_size = self.db_path.stat().st_size

            return {
                "total_events": total,
                "pending_events": pending,
                "synced_events": synced,
                "failed_events": failed,
                "db_size_bytes": db_size,
            }

    def close(self) -> None:
        """Safely close database connection."""
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception as e:
                    logger.debug("Error closing local database: %s", e)
                finally:
                    self._conn = None

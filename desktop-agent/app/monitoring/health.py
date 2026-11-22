"""Process health, resource utilization, and heartbeat monitor."""
import logging
import os
import time
from typing import Any

from app.events.event_builder import EventBuilder
from app.storage.local_database import LocalDatabase

logger = logging.getLogger(__name__)

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class HealthMonitor:
    """Tracks desktop agent process metrics and generates heartbeats."""

    def __init__(self, event_builder: EventBuilder, local_db: LocalDatabase):
        self.event_builder = event_builder
        self.local_db = local_db
        self.start_time_monotonic = time.monotonic()
        self.sync_errors_count = 0
        self.last_heartbeat_time = time.monotonic()

        self._process = None
        if HAS_PSUTIL:
            try:
                self._process = psutil.Process(os.getpid())
                # First call to initialize cpu_percent baseline
                self._process.cpu_percent(interval=None)
            except Exception as e:
                logger.debug("Failed to initialize psutil process: %s", e)

    def record_sync_error(self) -> None:
        """Increment count of synchronization failures."""
        self.sync_errors_count += 1

    def reset_sync_errors(self) -> None:
        """Reset sync error count upon successful synchronization."""
        self.sync_errors_count = 0

    def get_metrics(self) -> dict[str, Any]:
        """Collect current system and buffer metrics."""
        uptime = time.monotonic() - self.start_time_monotonic

        cpu_percent = 0.0
        memory_mb = 0.0

        if self._process is not None:
            try:
                cpu_percent = self._process.cpu_percent(interval=None)
                memory_mb = self._process.memory_info().rss / (1024.0 * 1024.0)
            except Exception as e:
                logger.debug("Error querying process resource metrics: %s", e)

        db_stats = self.local_db.get_stats()

        return {
            "uptime_seconds": round(uptime, 2),
            "cpu_percent": round(cpu_percent, 2),
            "memory_mb": round(memory_mb, 2),
            "sync_errors_count": self.sync_errors_count,
            "buffer_total_events": db_stats.get("total_events", 0),
            "buffer_pending_events": db_stats.get("pending_events", 0),
            "buffer_synced_events": db_stats.get("synced_events", 0),
            "buffer_failed_events": db_stats.get("failed_events", 0),
            "buffer_disk_bytes": db_stats.get("db_size_bytes", 0),
        }

    def create_heartbeat_event(self) -> dict[str, Any]:
        """Construct heartbeat telemetry event."""
        metrics = self.get_metrics()
        self.last_heartbeat_time = time.monotonic()
        return self.event_builder.build_heartbeat(
            uptime_seconds=metrics["uptime_seconds"],
            cpu_percent=metrics["cpu_percent"],
            memory_mb=metrics["memory_mb"],
            buffer_pending_count=metrics["buffer_pending_events"],
            buffer_total_count=metrics["buffer_total_events"],
        )

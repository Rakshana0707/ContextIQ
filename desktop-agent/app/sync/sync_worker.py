"""Background synchronization worker for dispatching buffered events to server."""
import logging
import random
import threading
import time
from typing import Any, Optional

from app.monitoring.health import HealthMonitor
from app.privacy.consent_checker import ConsentChecker
from app.privacy.exclusion_manager import ExclusionManager
from app.storage.local_database import LocalDatabase
from app.sync.api_client import ContextIQApiClient

logger = logging.getLogger(__name__)


class SyncWorker:
    """Dispatches locally buffered events to ContextIQ backend with retry backoff."""

    def __init__(
        self,
        local_db: LocalDatabase,
        api_client: ContextIQApiClient,
        consent_checker: ConsentChecker,
        exclusion_manager: ExclusionManager,
        health_monitor: HealthMonitor,
        user_id: str,
        device_id: Optional[str] = None,
        sync_interval_seconds: float = 10.0,
        batch_size: int = 50,
        max_retries: int = 5,
    ):
        self.local_db = local_db
        self.api_client = api_client
        self.consent_checker = consent_checker
        self.exclusion_manager = exclusion_manager
        self.health_monitor = health_monitor
        self.user_id = user_id
        self.device_id = device_id
        self.sync_interval = sync_interval_seconds
        self.batch_size = batch_size
        self.max_retries = max_retries

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._backoff_seconds = 0.0
        self._last_policy_refresh_time = 0.0

        # Operational metrics (Task 8)
        self.last_successful_sync: Optional[float] = None
        self.last_sync_latency_ms: float = 0.0
        self.total_events_synced: int = 0

    def start(self) -> None:
        """Start synchronization worker thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="SyncWorkerThread", daemon=True)
        self._thread.start()
        logger.info(
            "SyncWorker started (interval=%.1fs, batch_size=%d, user=%s)",
            self.sync_interval,
            self.batch_size,
            self.user_id,
        )

    def stop(self, timeout: float = 5.0) -> None:
        """Signal worker thread to stop and wait for completion."""
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            logger.info("SyncWorker stopped")

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                # 1. Periodically refresh privacy settings & exclusions from server
                self._maybe_refresh_policies()

                # 2. Check if server synchronization is permitted
                if self.consent_checker.is_collection_allowed("server_sync"):
                    self._dispatch_pending_batch()
                else:
                    logger.debug("Server sync category not consented or collection paused; skipping sync pass")

            except Exception as e:
                logger.error("Unexpected error in SyncWorker loop: %s", e, exc_info=True)

            # Sleep interval with backoff handling
            sleep_time = self.sync_interval + self._backoff_seconds
            self._stop_event.wait(timeout=sleep_time)

    def _dispatch_pending_batch(self) -> None:
        """Retrieve pending events and upload to server with partial failure recovery."""
        pending = self.local_db.get_pending_events(limit=self.batch_size, max_retries=self.max_retries)
        if not pending:
            # Nothing to sync; reset backoff
            self._backoff_seconds = 0.0
            return

        event_ids = [e["event_id"] for e in pending]
        logger.debug("Dispatching batch of %d events (IDs: %d items)", len(pending), len(event_ids))

        # Call API client (preserves original event timestamps and privacy invariants)
        result = self.api_client.upload_telemetry_batch(
            events=pending,
            user_id=self.user_id,
            device_id=self.device_id,
        )

        if result.success:
            # Mark successfully acknowledged events
            if result.synced_ids:
                self.local_db.mark_events_synced(result.synced_ids)
                self.total_events_synced += len(result.synced_ids)

            # Handle partial batch failure
            if result.failed_ids:
                logger.warning(
                    "Partial batch failure: %d events rejected by server", len(result.failed_ids)
                )
                self.local_db.mark_events_failed(result.failed_ids, max_retries=self.max_retries)

            self.health_monitor.reset_sync_errors()
            self._backoff_seconds = 0.0
            self.last_successful_sync = time.time()
            self.last_sync_latency_ms = result.latency_ms

            logger.info(
                "Sync succeeded: %d acknowledged (%d duplicates) in %.2fms",
                len(result.synced_ids),
                len(result.duplicate_ids),
                result.latency_ms,
            )
        else:
            # Full failure (e.g. network outage or server 5xx)
            self.local_db.mark_events_failed(event_ids, max_retries=self.max_retries)
            self.health_monitor.record_sync_error()

            # Exponential backoff with jitter (capped at 60s)
            self._backoff_seconds = min(60.0, max(2.0, self._backoff_seconds * 2 + random.uniform(0.5, 2.0)))
            logger.warning(
                "Sync failed (%s); retry backoff set to %.2fs",
                result.error_message or "Network error",
                self._backoff_seconds,
            )

    def _maybe_refresh_policies(self) -> None:
        """Refresh privacy settings & app exclusions every 60 seconds."""
        now = time.monotonic()
        if now - self._last_policy_refresh_time < 60.0:
            return

        self._last_policy_refresh_time = now
        try:
            settings = self.api_client.get_privacy_settings(self.user_id)
            consent = self.api_client.get_active_consent(self.user_id)
            if settings is not None:
                self.consent_checker.update_from_backend(settings, consent)

            exclusions = self.api_client.get_app_exclusions(self.user_id)
            if exclusions:
                self.exclusion_manager.update_from_backend(exclusions)
        except Exception as e:
            logger.debug("Failed refreshing policies from server: %s", e)

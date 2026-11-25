"""Synchronization scheduler with rate limiting, error recovery, and exponential backoff."""
from __future__ import annotations

import logging
import math
import random
import time
from typing import Callable, Optional
from uuid import UUID

from integrations.app.core.provider_registry import ProviderRegistry
from integrations.app.core.token_manager import TokenManager
from integrations.app.schemas.integration_schemas import OAuthTokenBundle, SyncResult
from integrations.app.synchronization.sync_state import CalendarSyncTracker

logger = logging.getLogger(__name__)


class SyncScheduler:
    """Orchestrates periodic and on-demand synchronization runs with exponential backoff."""

    def __init__(
        self,
        token_manager: TokenManager,
        base_backoff_seconds: float = 2.0,
        max_backoff_seconds: float = 300.0,
    ):
        self.token_manager = token_manager
        self.base_backoff = base_backoff_seconds
        self.max_backoff = max_backoff_seconds

    def compute_backoff_delay(self, failure_count: int) -> float:
        """Compute exponential backoff with jitter."""
        if failure_count <= 0:
            return 0.0
        backoff = min(self.max_backoff, self.base_backoff * (2 ** (failure_count - 1)))
        jitter = random.uniform(0.8, 1.2)
        return round(backoff * jitter, 2)

    def execute_sync(
        self,
        provider: str,
        credentials: OAuthTokenBundle,
        sync_tracker: CalendarSyncTracker,
        on_events_synced: Optional[Callable[[list], None]] = None,
    ) -> SyncResult:
        """Perform a synchronization cycle using the appropriate provider adapter."""
        sync_tracker.mark_in_progress()
        start_time = time.monotonic()

        try:
            adapter = ProviderRegistry.get_provider(provider)
            result = adapter.synchronize(
                sync_token=sync_tracker.sync_token,
                credentials=credentials,
                calendar_id=sync_tracker.calendar_id,
            )
            elapsed_ms = (time.monotonic() - start_time) * 1000.0
            result.sync_duration_ms = round(elapsed_ms, 2)

            if result.full_resync_required:
                logger.info("Delta sync required full resynchronization for integration %s", sync_tracker.integration_id)
                sync_tracker.reset_for_resync()
                # Run full sync immediately
                result = adapter.synchronize(
                    sync_token=None,
                    credentials=credentials,
                    calendar_id=sync_tracker.calendar_id,
                )
                result.sync_duration_ms = round((time.monotonic() - start_time) * 1000.0, 2)

            if result.success:
                sync_tracker.mark_success(
                    new_sync_token=result.new_sync_token,
                    event_count=len(result.synced_events),
                )
                if on_events_synced and result.synced_events:
                    on_events_synced(result.synced_events)
            else:
                sync_tracker.mark_failure(result.error_message or "Unknown sync failure")

            return result

        except Exception as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000.0
            error_msg = str(e)
            logger.error("Sync execution failed for %s: %s", sync_tracker.integration_id, error_msg)
            sync_tracker.mark_failure(error_msg)
            return SyncResult(
                success=False,
                error_message=error_msg,
                sync_duration_ms=round(elapsed_ms, 2),
            )

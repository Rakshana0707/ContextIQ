"""Synchronization state tracking and transition management."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from integrations.app.schemas.integration_schemas import SyncStatus


@dataclass
class CalendarSyncTracker:
    """In-memory or operational representation of calendar synchronization state."""
    integration_id: UUID
    calendar_id: str = "primary"
    sync_token: Optional[str] = None
    last_sync_timestamp: Optional[datetime] = None
    sync_status: SyncStatus = SyncStatus.INITIALIZING
    error_message: Optional[str] = None
    synced_event_count: int = 0
    consecutive_failures: int = 0

    def mark_in_progress(self) -> None:
        self.sync_status = SyncStatus.IN_PROGRESS
        self.error_message = None

    def mark_success(self, new_sync_token: Optional[str], event_count: int) -> None:
        self.sync_status = SyncStatus.SYNCED
        if new_sync_token:
            self.sync_token = new_sync_token
        self.last_sync_timestamp = datetime.now(timezone.utc)
        self.synced_event_count += event_count
        self.consecutive_failures = 0
        self.error_message = None

    def mark_failure(self, error: str) -> None:
        self.sync_status = SyncStatus.FAILED
        self.error_message = error
        self.consecutive_failures += 1

    def reset_for_resync(self) -> None:
        self.sync_token = None
        self.sync_status = SyncStatus.INITIALIZING
        self.error_message = None

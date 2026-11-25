"""Conflict management for calendar events adhering to non-destructive invariants."""
from __future__ import annotations

import logging
from enum import Enum
from typing import Optional, Tuple

from integrations.app.schemas.integration_schemas import CalendarEventDTO

logger = logging.getLogger(__name__)


class ConflictResolutionAction(str, Enum):
    APPLY_REMOTE = "APPLY_REMOTE"      # Remote external event overwrites local cache
    PRESERVE_LOCAL = "PRESERVE_LOCAL"  # Local modification takes precedence (only for ContextIQ managed)
    FLAG_DISPUTE = "FLAG_DISPUTE"      # Human review required


class ConflictManager:
    """Evaluates concurrent calendar changes according to data ownership rules.

    Rules:
    1. External user events are authoritative: ContextIQ never overwrites them.
    2. ContextIQ-managed focus blocks can be moved by the user in external calendar;
       ContextIQ adapts to the user's manual change.
    """

    @staticmethod
    def resolve_event_conflict(
        local_event: Optional[CalendarEventDTO],
        remote_event: CalendarEventDTO,
        is_contextiq_managed: bool = False,
    ) -> Tuple[ConflictResolutionAction, CalendarEventDTO]:
        """Determine resolution strategy when an event is updated concurrently."""
        if not local_event:
            return ConflictResolutionAction.APPLY_REMOTE, remote_event

        # If it's an external user meeting, remote calendar is authoritative
        if not is_contextiq_managed:
            return ConflictResolutionAction.APPLY_REMOTE, remote_event

        # For ContextIQ-managed focus blocks, if the user moved the time in their external calendar,
        # we respect the user's external decision and adapt the internal focus window.
        if (local_event.start_time != remote_event.start_time) or (local_event.end_time != remote_event.end_time):
            logger.info(
                "User moved ContextIQ focus block '%s' in external calendar to %s-%s. Adapting internal schedule.",
                remote_event.title,
                remote_event.start_time,
                remote_event.end_time,
            )
            return ConflictResolutionAction.APPLY_REMOTE, remote_event

        return ConflictResolutionAction.APPLY_REMOTE, remote_event

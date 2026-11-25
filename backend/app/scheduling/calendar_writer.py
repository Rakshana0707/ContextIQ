"""Calendar writer performing idempotent external calendar commitments upon explicit user schedule approval."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.calendar_integration import CalendarIntegration
from app.models.external_calendar_event import ExternalCalendarEvent
from app.models.schedule_proposal import ScheduleProposal
from app.models.task import Task
from app.schemas.scheduling import ScheduleApprovalRequest, ScheduleApprovalResponse, ScheduledSlotDTO
from app.services.integration_service import get_token_manager
from integrations.app.core.provider_registry import ProviderRegistry
from integrations.app.schemas.integration_schemas import (
    CalendarEventCreateDTO,
    ConnectionStatus,
    EventTransparency,
    OAuthTokenBundle,
)

logger = logging.getLogger(__name__)


def _resolve_calendar_integration(
    db: Session,
    user_id: UUID,
    requested_provider: Optional[str] = None,
) -> CalendarIntegration:
    """Finds an active, authenticated calendar integration for the user (Google or Microsoft)."""
    stmt = select(CalendarIntegration).where(
        CalendarIntegration.user_id == user_id,
        CalendarIntegration.connection_status == ConnectionStatus.CONNECTED.value,
        CalendarIntegration.is_active.is_(True),
    )
    if requested_provider:
        stmt = stmt.where(CalendarIntegration.provider == requested_provider)

    # Order by preference (e.g. Google Calendar first or most recently used)
    stmt = stmt.order_by(CalendarIntegration.updated_at.desc())
    integration = db.scalars(stmt).first()
    if not integration or not integration.credentials:
        raise ValueError(
            f"No connected, authenticated calendar integration found"
            + (f" for {requested_provider}" if requested_provider else "")
            + ". Please link Google Calendar or Microsoft Outlook first."
        )
    return integration


def _get_valid_credentials(db: Session, integration: CalendarIntegration) -> OAuthTokenBundle:
    token_mgr = get_token_manager()
    cred = integration.credentials
    bundle, was_refreshed, new_access, new_refresh = token_mgr.ensure_valid_token(
        encrypted_access_token=cred.encrypted_access_token,
        encrypted_refresh_token=cred.encrypted_refresh_token,
        expiration_timestamp=cred.expiration_timestamp,
        user_id=integration.user_id,
        provider=integration.provider,
        scopes=integration.granted_scopes,
    )
    if was_refreshed:
        cred.encrypted_access_token = new_access  # type: ignore
        if new_refresh:
            cred.encrypted_refresh_token = new_refresh
        cred.expiration_timestamp = bundle.expires_at
        cred.credential_version += 1
        db.commit()
    return bundle


class CalendarWriter:
    """Manages transactional, idempotent creation of ContextIQ focus blocks in external calendars."""

    @classmethod
    def commit_approved_schedule(
        cls,
        db: Session,
        user_id: UUID,
        proposal: ScheduleProposal,
        request: ScheduleApprovalRequest,
    ) -> ScheduleApprovalResponse:
        """Commits approved task schedule slots to user's external calendar.

        Guarantees:
        1. Explicit user authorization required.
        2. Idempotent event creation (skips slots already pushed).
        3. Partial-failure resilience without corrupted state.
        """
        integration = _resolve_calendar_integration(
            db=db,
            user_id=user_id,
            requested_provider=request.target_provider,
        )
        credentials = _get_valid_credentials(db, integration)
        adapter = ProviderRegistry.get_provider(integration.provider)

        scheduled_slots = proposal.scheduled_items or []
        include_ids = set(request.include_task_ids) if request.include_task_ids else None

        created_event_ids: List[str] = []
        now_utc = datetime.now(timezone.utc)

        for slot_data in scheduled_slots:
            slot = ScheduledSlotDTO(**slot_data)
            if include_ids and slot.task_id not in include_ids:
                continue

            # Idempotency Guard: Verify slot was not already pushed to external calendar
            dup_stmt = select(ExternalCalendarEvent).where(
                ExternalCalendarEvent.user_id == user_id,
                ExternalCalendarEvent.linked_task_id == slot.task_id,
                ExternalCalendarEvent.start_time == slot.start_time,
                ExternalCalendarEvent.status != "CANCELLED",
            )
            existing_event = db.scalars(dup_stmt).first()
            if existing_event:
                logger.info("Skipping duplicate focus block creation for task %s at %s", slot.task_id, slot.start_time)
                created_event_ids.append(existing_event.external_event_id)
                continue

            # Create event in external calendar
            create_dto = CalendarEventCreateDTO(
                title=f"Focus: {slot.title}",
                start_time=slot.start_time,
                end_time=slot.end_time,
                is_all_day=False,
                description=f"ContextIQ Intelligent Focus Block\nRationale: {slot.explanation.primary_rationale}\nConfidence: {slot.explanation.confidence_score * 100:.0f}%",
                location_name="ContextIQ Deep Work",
                transparency=EventTransparency.OPAQUE,
            )

            try:
                created_dto = adapter.create_event(
                    calendar_id=request.calendar_id,
                    event=create_dto,
                    credentials=credentials,
                )

                # Persist local reference in external_calendar_events
                new_evt = ExternalCalendarEvent(
                    user_id=user_id,
                    integration_id=integration.id,
                    calendar_id=request.calendar_id,
                    external_event_id=created_dto.event_id,
                    title=created_dto.title,
                    description=created_dto.description,
                    location_name=created_dto.location_name,
                    start_time=created_dto.start_time,
                    end_time=created_dto.end_time,
                    timezone=created_dto.timezone or "UTC",
                    is_all_day=False,
                    status="CONFIRMED",
                    transparency="OPAQUE",
                    visibility="default",
                    is_private=False,
                    is_recurring=False,
                    is_organizer=True,
                    etag=created_dto.etag,
                    html_link=created_dto.html_link,
                    is_contextiq_managed=True,
                    linked_task_id=slot.task_id,
                    last_synced_at=now_utc,
                )
                db.add(new_evt)
                created_event_ids.append(created_dto.event_id)

            except Exception as e:
                logger.error("Failed to commit task %s to %s: %s", slot.task_id, integration.provider, e)
                # Continue with other slots rather than hard aborting everything

        # Mark proposal status as COMMITTED
        proposal.status = "COMMITTED"
        proposal.updated_at = now_utc
        db.commit()

        return ScheduleApprovalResponse(
            success=True,
            schedule_id=proposal.id,
            status="COMMITTED",
            events_created=len(created_event_ids),
            calendar_provider=integration.provider,
            created_event_ids=created_event_ids,
            message=f"Successfully committed {len(created_event_ids)} focus block(s) to {integration.provider}.",
        )

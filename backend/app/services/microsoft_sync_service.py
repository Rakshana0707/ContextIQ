"""Service implementing Microsoft Outlook (Microsoft Graph) two-way synchronization, conflict resolution, and event operations."""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.models.calendar_integration import CalendarIntegration, CalendarSyncState
from app.models.external_calendar_event import ExternalCalendarEvent
from app.schemas.microsoft_calendar import (
    MicrosoftCalendarDTO,
    MicrosoftEventCreate,
    MicrosoftEventRead,
    MicrosoftEventUpdate,
    MicrosoftSyncResponse,
)
from app.services.integration_service import get_token_manager
from integrations.app.core.provider_registry import ProviderRegistry
from integrations.app.schemas.integration_schemas import (
    CalendarEventCreateDTO,
    CalendarEventDTO,
    CalendarEventUpdateDTO,
    ConnectionStatus,
    EventStatus,
    EventTransparency,
    OAuthTokenBundle,
    SyncStatus,
)

logger = logging.getLogger(__name__)


def _get_active_microsoft_integration(db: Session, user_id: UUID) -> CalendarIntegration:
    """Retrieve the user's active, connected Microsoft Outlook integration."""
    stmt = select(CalendarIntegration).where(
        CalendarIntegration.user_id == user_id,
        CalendarIntegration.provider == "microsoft_outlook",
        CalendarIntegration.connection_status == ConnectionStatus.CONNECTED.value,
        CalendarIntegration.is_active.is_(True),
    )
    integration = db.scalars(stmt).first()
    if not integration or not integration.credentials:
        raise ValueError("No active, authenticated Microsoft Outlook integration found for this user.")
    return integration


def _get_valid_credentials(db: Session, integration: CalendarIntegration) -> OAuthTokenBundle:
    """Ensure OAuth credentials are valid and fresh, rotating in the database if refreshed."""
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


def sync_microsoft_calendar(
    db: Session,
    user_id: UUID,
    calendar_id: str = "primary",
    force_full: bool = False,
) -> MicrosoftSyncResponse:
    """Execute two-way synchronization for the user's Microsoft Outlook Calendar.

    Supports multi-page delta queries via @odata.nextLink and @odata.deltaLink,
    invalid delta token recovery, and automatic preservation of external meetings vs ContextIQ focus blocks.
    """
    t0 = time.time()
    try:
        integration = _get_active_microsoft_integration(db, user_id)
    except ValueError as e:
        return MicrosoftSyncResponse(
            success=False,
            integration_id=uuid.uuid4(),
            sync_status=SyncStatus.FAILED.value,
            events_created=0,
            events_updated=0,
            events_deleted=0,
            duration_ms=0.0,
            error_message=str(e),
        )

    try:
        credentials = _get_valid_credentials(db, integration)
    except Exception as e:
        logger.error("Failed to acquire valid tokens for Microsoft sync: %s", e)
        return MicrosoftSyncResponse(
            success=False,
            integration_id=integration.id,
            sync_status=SyncStatus.FAILED.value,
            events_created=0,
            events_updated=0,
            events_deleted=0,
            duration_ms=(time.time() - t0) * 1000,
            error_message=f"Authentication error: {e}",
        )

    # Resolve or create sync state tracking record
    stmt = select(CalendarSyncState).where(
        CalendarSyncState.integration_id == integration.id,
        CalendarSyncState.calendar_id == calendar_id,
    )
    sync_state = db.scalars(stmt).first()
    if not sync_state:
        sync_state = CalendarSyncState(
            integration_id=integration.id,
            calendar_id=calendar_id,
            sync_status=SyncStatus.INITIALIZING.value,
        )
        db.add(sync_state)
        db.flush()

    sync_state.sync_status = SyncStatus.IN_PROGRESS.value
    db.commit()

    provider_adapter = ProviderRegistry.get_provider("microsoft_outlook")
    sync_token = None if force_full else sync_state.sync_token
    full_resync_occurred = force_full

    sync_result = provider_adapter.synchronize(
        sync_token=sync_token,
        credentials=credentials,
        calendar_id=calendar_id,
    )

    # Handle delta link invalidation (HTTP 410 / resyncRequired)
    if sync_result.full_resync_required:
        logger.info("Microsoft delta link invalidated. Performing full resynchronization.")
        full_resync_occurred = True
        sync_result = provider_adapter.synchronize(
            sync_token=None,
            credentials=credentials,
            calendar_id=calendar_id,
        )

    if not sync_result.success:
        sync_state.sync_status = SyncStatus.FAILED.value
        sync_state.error_message = sync_result.error_message
        db.commit()
        return MicrosoftSyncResponse(
            success=False,
            integration_id=integration.id,
            sync_status=SyncStatus.FAILED.value,
            events_created=0,
            events_updated=0,
            events_deleted=0,
            duration_ms=(time.time() - t0) * 1000,
            error_message=sync_result.error_message or "Synchronization failed",
        )

    created_count = 0
    updated_count = 0
    deleted_count = 0
    now_utc = datetime.now(timezone.utc)

    # 1. Process removed / deleted events
    if sync_result.deleted_event_ids:
        del_stmt = select(ExternalCalendarEvent).where(
            ExternalCalendarEvent.integration_id == integration.id,
            ExternalCalendarEvent.external_event_id.in_(sync_result.deleted_event_ids),
        )
        existing_deleted = db.scalars(del_stmt).all()
        for evt in existing_deleted:
            evt.status = EventStatus.CANCELLED.value
            evt.last_synced_at = now_utc
            deleted_count += 1

    # 2. Process upserted events
    for dto in sync_result.synced_events:
        evt_stmt = select(ExternalCalendarEvent).where(
            ExternalCalendarEvent.integration_id == integration.id,
            ExternalCalendarEvent.external_event_id == dto.event_id,
        )
        existing = db.scalars(evt_stmt).first()

        if existing is None:
            # Create new record
            new_evt = ExternalCalendarEvent(
                user_id=user_id,
                integration_id=integration.id,
                calendar_id=calendar_id,
                external_event_id=dto.event_id,
                title=dto.title,
                description=dto.description,
                location_name=dto.location_name,
                start_time=dto.start_time,
                end_time=dto.end_time,
                timezone=dto.timezone or "UTC",
                is_all_day=dto.is_all_day,
                status=dto.status.value if hasattr(dto.status, "value") else str(dto.status),
                transparency=dto.transparency.value if hasattr(dto.transparency, "value") else str(dto.transparency),
                visibility=dto.visibility or "normal",
                is_private=(dto.visibility in ("private", "confidential")),
                is_recurring=dto.is_recurring,
                recurring_event_id=dto.recurring_event_id,
                original_start_time=dto.original_start_time,
                is_organizer=dto.is_organizer,
                organizer_email=dto.organizer_email,
                attendees_count=dto.attendees_count,
                etag=dto.etag,
                html_link=dto.html_link,
                external_updated_at=dto.updated_at_provider,
                is_contextiq_managed=False,  # External meeting authored in Outlook
                last_synced_at=now_utc,
            )
            db.add(new_evt)
            created_count += 1
        else:
            # Update existing record
            # Respect User Agency: If ContextIQ focus block was rescheduled externally in Outlook, adapt cleanly
            # If external meeting, Microsoft Graph is authoritative (EXTERNAL_WINS)
            existing.title = dto.title
            existing.description = dto.description
            existing.location_name = dto.location_name
            existing.start_time = dto.start_time
            existing.end_time = dto.end_time
            existing.timezone = dto.timezone or existing.timezone
            existing.is_all_day = dto.is_all_day
            existing.status = dto.status.value if hasattr(dto.status, "value") else str(dto.status)
            existing.transparency = dto.transparency.value if hasattr(dto.transparency, "value") else str(dto.transparency)
            existing.visibility = dto.visibility or existing.visibility
            existing.is_private = (dto.visibility in ("private", "confidential"))
            existing.is_recurring = dto.is_recurring
            existing.recurring_event_id = dto.recurring_event_id
            existing.original_start_time = dto.original_start_time
            existing.is_organizer = dto.is_organizer
            existing.organizer_email = dto.organizer_email
            existing.attendees_count = dto.attendees_count
            existing.etag = dto.etag
            existing.html_link = dto.html_link
            existing.external_updated_at = dto.updated_at_provider
            existing.last_synced_at = now_utc
            updated_count += 1

    # Update sync state record
    if sync_result.new_sync_token:
        sync_state.sync_token = sync_result.new_sync_token
    sync_state.last_sync_timestamp = now_utc
    sync_state.sync_status = SyncStatus.SYNCED.value
    sync_state.error_message = None
    db.commit()

    duration = (time.time() - t0) * 1000
    return MicrosoftSyncResponse(
        success=True,
        integration_id=integration.id,
        sync_status=SyncStatus.SYNCED.value,
        events_created=created_count,
        events_updated=updated_count,
        events_deleted=deleted_count,
        new_sync_token=sync_state.sync_token,
        full_resync_occurred=full_resync_occurred,
        duration_ms=round(duration, 2),
    )


def list_calendars(db: Session, user_id: UUID) -> List[MicrosoftCalendarDTO]:
    """Retrieve list of user calendars from Microsoft Graph API."""
    integration = _get_active_microsoft_integration(db, user_id)
    credentials = _get_valid_credentials(db, integration)
    adapter = ProviderRegistry.get_provider("microsoft_outlook")
    calendars = adapter.list_calendars(credentials)
    return [
        MicrosoftCalendarDTO(
            calendar_id=cal.calendar_id,
            name=cal.name,
            is_primary=cal.is_primary,
            access_role=cal.access_role,
            description=cal.description,
            time_zone=cal.time_zone,
        )
        for cal in calendars
    ]


def list_events(
    db: Session,
    user_id: UUID,
    calendar_id: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    transparency: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> List[ExternalCalendarEvent]:
    """Query synchronized Microsoft Outlook events from the local database."""
    stmt = (
        select(ExternalCalendarEvent)
        .join(CalendarIntegration, ExternalCalendarEvent.integration_id == CalendarIntegration.id)
        .where(
            ExternalCalendarEvent.user_id == user_id,
            CalendarIntegration.provider == "microsoft_outlook",
            ExternalCalendarEvent.status != EventStatus.CANCELLED.value,
        )
    )
    if calendar_id:
        stmt = stmt.where(ExternalCalendarEvent.calendar_id == calendar_id)
    if start_time:
        stmt = stmt.where(ExternalCalendarEvent.end_time >= start_time)
    if end_time:
        stmt = stmt.where(ExternalCalendarEvent.start_time <= end_time)
    if transparency:
        stmt = stmt.where(ExternalCalendarEvent.transparency == transparency)
    if status:
        stmt = stmt.where(ExternalCalendarEvent.status == status)

    stmt = stmt.order_by(ExternalCalendarEvent.start_time.asc()).limit(limit)
    return list(db.scalars(stmt).all())


def create_event(
    db: Session,
    user_id: UUID,
    payload: MicrosoftEventCreate,
) -> ExternalCalendarEvent:
    """Create a new event in Microsoft Outlook (e.g. ContextIQ scheduled focus block).

    Guarantees two-way push and stores local reference with is_contextiq_managed=True.
    """
    integration = _get_active_microsoft_integration(db, user_id)
    credentials = _get_valid_credentials(db, integration)
    adapter = ProviderRegistry.get_provider("microsoft_outlook")

    create_dto = CalendarEventCreateDTO(
        title=payload.title,
        start_time=payload.start_time,
        end_time=payload.end_time,
        is_all_day=payload.is_all_day,
        description=payload.description,
        location_name=payload.location_name,
        transparency=payload.transparency,
    )

    created_dto = adapter.create_event(
        calendar_id=payload.calendar_id,
        event=create_dto,
        credentials=credentials,
    )

    now_utc = datetime.now(timezone.utc)
    new_evt = ExternalCalendarEvent(
        user_id=user_id,
        integration_id=integration.id,
        calendar_id=payload.calendar_id,
        external_event_id=created_dto.event_id,
        title=created_dto.title,
        description=created_dto.description,
        location_name=created_dto.location_name,
        start_time=created_dto.start_time,
        end_time=created_dto.end_time,
        timezone=created_dto.timezone or payload.timezone or "UTC",
        is_all_day=created_dto.is_all_day,
        status=created_dto.status.value if hasattr(created_dto.status, "value") else str(created_dto.status),
        transparency=created_dto.transparency.value if hasattr(created_dto.transparency, "value") else str(created_dto.transparency),
        visibility=created_dto.visibility or "normal",
        is_private=(created_dto.visibility in ("private", "confidential")),
        is_recurring=created_dto.is_recurring,
        recurring_event_id=created_dto.recurring_event_id,
        is_organizer=True,
        etag=created_dto.etag,
        html_link=created_dto.html_link,
        is_contextiq_managed=True,
        linked_task_id=payload.linked_task_id,
        last_synced_at=now_utc,
    )
    db.add(new_evt)
    db.commit()
    db.refresh(new_evt)
    return new_evt


def update_event(
    db: Session,
    user_id: UUID,
    event_id: str,
    payload: MicrosoftEventUpdate,
) -> ExternalCalendarEvent:
    """Update an existing event in Microsoft Outlook and synchronize the local database record.

    Enforces ownership invariants: external meetings cannot be modified without
    explicit `allow_external_modification=True` permission.
    """
    stmt = (
        select(ExternalCalendarEvent)
        .join(CalendarIntegration, ExternalCalendarEvent.integration_id == CalendarIntegration.id)
        .where(
            ExternalCalendarEvent.user_id == user_id,
            CalendarIntegration.provider == "microsoft_outlook",
            or_(
                ExternalCalendarEvent.external_event_id == event_id,
                ExternalCalendarEvent.id == UUID(event_id) if _is_valid_uuid(event_id) else False,
            ),
        )
    )
    event = db.scalars(stmt).first()
    if not event:
        raise ValueError(f"Microsoft Outlook calendar event {event_id} not found.")

    # Guard external meetings: ContextIQ must not clobber meetings authored by other people
    if not event.is_contextiq_managed and not payload.allow_external_modification:
        raise PermissionError(
            "Cannot modify externally authored Microsoft calendar meeting without explicit allow_external_modification flag."
        )

    integration = _get_active_microsoft_integration(db, user_id)
    credentials = _get_valid_credentials(db, integration)
    adapter = ProviderRegistry.get_provider("microsoft_outlook")

    update_dto = CalendarEventUpdateDTO(
        title=payload.title,
        start_time=payload.start_time,
        end_time=payload.end_time,
        is_all_day=payload.is_all_day,
        description=payload.description,
        location_name=payload.location_name,
        transparency=payload.transparency,
    )

    updated_dto = adapter.update_event(
        calendar_id=event.calendar_id,
        event_id=event.external_event_id,
        updates=update_dto,
        credentials=credentials,
    )

    # Apply changes locally
    if payload.title is not None:
        event.title = updated_dto.title
    if payload.description is not None:
        event.description = updated_dto.description
    if payload.location_name is not None:
        event.location_name = updated_dto.location_name
    if payload.start_time is not None:
        event.start_time = updated_dto.start_time
    if payload.end_time is not None:
        event.end_time = updated_dto.end_time
    if payload.is_all_day is not None:
        event.is_all_day = updated_dto.is_all_day
    if payload.transparency is not None:
        event.transparency = updated_dto.transparency.value if hasattr(updated_dto.transparency, "value") else str(updated_dto.transparency)

    event.etag = updated_dto.etag
    event.last_synced_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(event)
    return event


def delete_event(
    db: Session,
    user_id: UUID,
    event_id: str,
) -> bool:
    """Delete an event from Microsoft Outlook and mark it cancelled locally."""
    stmt = (
        select(ExternalCalendarEvent)
        .join(CalendarIntegration, ExternalCalendarEvent.integration_id == CalendarIntegration.id)
        .where(
            ExternalCalendarEvent.user_id == user_id,
            CalendarIntegration.provider == "microsoft_outlook",
            or_(
                ExternalCalendarEvent.external_event_id == event_id,
                ExternalCalendarEvent.id == UUID(event_id) if _is_valid_uuid(event_id) else False,
            ),
        )
    )
    event = db.scalars(stmt).first()
    if not event:
        return False

    integration = _get_active_microsoft_integration(db, user_id)
    credentials = _get_valid_credentials(db, integration)
    adapter = ProviderRegistry.get_provider("microsoft_outlook")

    success = adapter.delete_event(
        calendar_id=event.calendar_id,
        event_id=event.external_event_id,
        credentials=credentials,
    )

    if success:
        event.status = EventStatus.CANCELLED.value
        event.last_synced_at = datetime.now(timezone.utc)
        db.commit()
        return True
    return False


def _is_valid_uuid(val: str) -> bool:
    try:
        UUID(val)
        return True
    except (ValueError, TypeError):
        return False

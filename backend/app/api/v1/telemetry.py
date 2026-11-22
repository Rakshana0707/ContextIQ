"""Telemetry ingestion and query REST endpoints."""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Union
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enums import ConsentStatus
from app.models.raw_telemetry_event import RawTelemetryEvent
from app.schemas.telemetry import (
    AgentStatusResponse,
    TelemetryBatchIn,
    TelemetryBatchResponse,
    TelemetryEventIn,
    TelemetryEventsQueryResponse,
    TelemetryEventRead,
)
from app.services.privacy_service import get_active_consent, get_or_create_privacy_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


def _verify_user_telemetry_authorization(
    db: Session,
    user_id_raw: str,
    device_id: Optional[str] = None,
) -> uuid.UUID:
    """Validate user identity, active consent, and pause state."""
    try:
        user_uuid = uuid.UUID(str(user_id_raw))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid user authorization identifier: {user_id_raw}",
        )

    # 1. Active consent check (Opt-in invariant)
    active_consent = get_active_consent(db, user_uuid)
    if not active_consent or active_consent.consent_status != ConsentStatus.GRANTED:
        logger.warning("Telemetry ingestion rejected: No active consent for user %s", user_uuid)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active telemetry consent is required before ingesting activity events",
        )

    # 2. Check privacy settings and pause timer
    settings = get_or_create_privacy_settings(db, user_uuid)
    if settings.is_paused:
        now = datetime.now(timezone.utc)
        if settings.paused_until:
            p_until = settings.paused_until
            if p_until.tzinfo is None:
                p_until = p_until.replace(tzinfo=timezone.utc)
            if now < p_until:
                logger.info("Rejecting telemetry batch: Collection paused until %s for user %s", p_until, user_uuid)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Activity collection is currently paused for this user",
                )
            else:
                # Timer expired; auto-resume on backend
                settings.is_paused = False
                settings.paused_until = None
                db.commit()
        else:
            logger.info("Rejecting telemetry batch: Collection manually paused for user %s", user_uuid)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Activity collection is currently paused for this user",
            )

    return user_uuid


def _process_events_batch(
    db: Session,
    events: list[TelemetryEventIn],
    user_uuid: uuid.UUID,
    device_id: Optional[str] = None,
) -> TelemetryBatchResponse:
    """Idempotently process and persist incoming telemetry events."""
    if not events:
        return TelemetryBatchResponse(
            received=0, accepted=0, duplicates=0, failed=0, status="ok"
        )

    incoming_ids = [e.event_id for e in events]

    # Check for already ingested IDs to guarantee idempotency
    stmt = select(RawTelemetryEvent.event_id).where(RawTelemetryEvent.event_id.in_(incoming_ids))
    existing_ids = set(db.scalars(stmt).all())

    new_records: list[RawTelemetryEvent] = []
    accepted_ids: list[str] = []
    duplicate_ids: list[str] = []

    for ev in events:
        if ev.event_id in existing_ids:
            duplicate_ids.append(ev.event_id)
            continue

        # Normalization
        ev_user_id = user_uuid
        ev_device = ev.device_id or device_id

        # Parse session / correlation UUIDs if provided
        s_id = None
        if ev.session_id:
            try:
                s_id = uuid.UUID(str(ev.session_id))
            except (ValueError, TypeError):
                pass

        c_id = None
        if ev.correlation_id:
            try:
                c_id = uuid.UUID(str(ev.correlation_id))
            except (ValueError, TypeError):
                pass

        record = RawTelemetryEvent(
            event_id=ev.event_id,
            user_id=ev_user_id,
            device_id=ev_device,
            event_type=ev.event_type,
            event_timestamp=ev.event_timestamp,
            ingestion_timestamp=datetime.now(timezone.utc),
            source=ev.source,
            schema_version=ev.schema_version,
            session_id=s_id,
            correlation_id=c_id,
            application_identifier=ev.application_identifier,
            previous_application_identifier=ev.previous_application_identifier,
            current_application_identifier=ev.current_application_identifier,
            payload=ev.payload or {},
        )
        new_records.append(record)
        accepted_ids.append(ev.event_id)

    if new_records:
        db.add_all(new_records)
        db.commit()

    # Both accepted and duplicate IDs are successfully acknowledged
    all_acknowledged = accepted_ids + duplicate_ids

    logger.info(
        "Ingested batch: %d received, %d accepted, %d duplicate for user %s",
        len(events),
        len(accepted_ids),
        len(duplicate_ids),
        user_uuid,
    )

    return TelemetryBatchResponse(
        received=len(events),
        accepted=len(accepted_ids),
        duplicates=len(duplicate_ids),
        failed=0,
        synced_event_ids=all_acknowledged,
        duplicate_event_ids=duplicate_ids,
        failed_event_ids=[],
        status="ok",
    )


@router.post("/events", response_model=TelemetryBatchResponse, status_code=status.HTTP_200_OK)
def ingest_telemetry_events(
    batch: Union[TelemetryBatchIn, TelemetryEventIn],
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    x_device_id: Optional[str] = Header(None, alias="X-Device-ID"),
    db: Session = Depends(get_db),
) -> TelemetryBatchResponse:
    """Ingest single or batched behavioral telemetry events from desktop agents."""
    if isinstance(batch, TelemetryEventIn):
        events = [batch]
    else:
        events = batch.events

    if not events:
        return TelemetryBatchResponse(received=0, accepted=0, duplicates=0, status="ok")

    # Authorize user
    user_id_raw = x_user_id or str(events[0].user_id)
    device_id = x_device_id or events[0].device_id
    user_uuid = _verify_user_telemetry_authorization(db, user_id_raw, device_id)

    return _process_events_batch(db, events, user_uuid, device_id)


@router.post("/events/batch", response_model=TelemetryBatchResponse, status_code=status.HTTP_200_OK)
def ingest_telemetry_events_batch(
    batch: TelemetryBatchIn,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    x_device_id: Optional[str] = Header(None, alias="X-Device-ID"),
    db: Session = Depends(get_db),
) -> TelemetryBatchResponse:
    """Dedicated batch ingestion endpoint with granular server acknowledgements."""
    events = batch.events
    if not events:
        return TelemetryBatchResponse(received=0, accepted=0, duplicates=0, status="ok")

    user_id_raw = x_user_id or str(events[0].user_id)
    device_id = x_device_id or events[0].device_id
    user_uuid = _verify_user_telemetry_authorization(db, user_id_raw, device_id)

    return _process_events_batch(db, events, user_uuid, device_id)


@router.get("/agent/status", response_model=AgentStatusResponse)
def get_agent_status(
    user_id: Optional[uuid.UUID] = None,
    device_id: Optional[str] = None,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    x_device_id: Optional[str] = Header(None, alias="X-Device-ID"),
    db: Session = Depends(get_db),
) -> AgentStatusResponse:
    """Query synchronization health, active consent, and ingestion status."""
    resolved_user_str = str(user_id) if user_id else x_user_id
    if not resolved_user_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User identifier required via parameter or X-User-ID header",
        )

    try:
        user_uuid = uuid.UUID(resolved_user_str)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user UUID format")

    resolved_device = device_id or x_device_id

    consent = get_active_consent(db, user_uuid)
    settings = get_or_create_privacy_settings(db, user_uuid)

    consent_status_str = consent.consent_status.value if consent else "REVOKED"
    active_categories = list(consent.enabled_categories) if consent else []

    # Query last event and total counts
    stmt = (
        select(RawTelemetryEvent)
        .where(RawTelemetryEvent.user_id == user_uuid)
        .order_by(RawTelemetryEvent.event_timestamp.desc())
    )
    if resolved_device:
        stmt = stmt.where(RawTelemetryEvent.device_id == resolved_device)

    latest_event = db.scalars(stmt).first()

    count_stmt = select(func.count(RawTelemetryEvent.event_id)).where(RawTelemetryEvent.user_id == user_uuid)
    if resolved_device:
        count_stmt = count_stmt.where(RawTelemetryEvent.device_id == resolved_device)
    total_events = db.scalar(count_stmt) or 0

    return AgentStatusResponse(
        user_id=str(user_uuid),
        device_id=resolved_device,
        consent_status=consent_status_str,
        is_paused=settings.is_paused,
        paused_until=settings.paused_until,
        last_event_timestamp=latest_event.event_timestamp if latest_event else None,
        last_ingestion_timestamp=latest_event.ingestion_timestamp if latest_event else None,
        total_events_ingested=total_events,
        active_categories=active_categories,
    )


@router.get("/events", response_model=TelemetryEventsQueryResponse)
def query_telemetry_events(
    user_id: Optional[uuid.UUID] = None,
    device_id: Optional[str] = None,
    event_type: Optional[str] = None,
    application_identifier: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    db: Session = Depends(get_db),
) -> TelemetryEventsQueryResponse:
    """Retrieve chronologically ordered raw telemetry events for analytics engines."""
    resolved_user_str = str(user_id) if user_id else x_user_id
    if not resolved_user_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User identifier required via parameter or X-User-ID header",
        )

    try:
        user_uuid = uuid.UUID(resolved_user_str)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user UUID format")

    stmt = select(RawTelemetryEvent).where(RawTelemetryEvent.user_id == user_uuid)

    if device_id:
        stmt = stmt.where(RawTelemetryEvent.device_id == device_id)
    if event_type:
        stmt = stmt.where(RawTelemetryEvent.event_type == event_type)
    if application_identifier:
        stmt = stmt.where(RawTelemetryEvent.application_identifier == application_identifier)
    if start_time:
        stmt = stmt.where(RawTelemetryEvent.event_timestamp >= start_time)
    if end_time:
        stmt = stmt.where(RawTelemetryEvent.event_timestamp <= end_time)

    # Count total matching rows
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_count = db.scalar(count_stmt) or 0

    # Guarantee chronological ordering (occurrence time)
    stmt = stmt.order_by(RawTelemetryEvent.event_timestamp.asc()).limit(limit).offset(offset)
    records = db.scalars(stmt).all()

    items = [TelemetryEventRead.model_validate(r) for r in records]

    return TelemetryEventsQueryResponse(
        items=items,
        total=total_count,
        limit=limit,
        offset=offset,
    )

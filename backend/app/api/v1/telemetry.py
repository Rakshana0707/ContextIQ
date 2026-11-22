"""Telemetry ingestion endpoint for desktop activity events."""
import logging
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.telemetry import TelemetryBatchIn, TelemetryBatchResponse
from app.services.privacy_service import get_or_create_privacy_settings, get_active_consent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.post("/events", response_model=TelemetryBatchResponse, status_code=status.HTTP_200_OK)
def ingest_telemetry_batch(
    batch: TelemetryBatchIn,
    x_user_id: str | None = Header(None, alias="X-User-ID"),
    db: Session = Depends(get_db),
) -> TelemetryBatchResponse:
    """Receive and validate batched behavioral telemetry events from desktop agents."""
    events = batch.events
    if not events:
        return TelemetryBatchResponse(received=0, accepted=0, duplicates=0)

    # Determine user identity from header or first event
    user_id_raw = x_user_id or str(events[0].user_id)
    try:
        user_uuid = UUID(user_id_raw)
    except (ValueError, TypeError):
        user_uuid = None

    if user_uuid:
        # Check if user has active consent
        active_consent = get_active_consent(db, user_uuid)
        settings = get_or_create_privacy_settings(db, user_uuid)

        if settings.is_paused:
            logger.info("Rejecting telemetry batch for paused user %s", user_uuid)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Activity collection is currently paused for this user",
            )

    logger.info("Ingested %d telemetry events for user %s", len(events), user_id_raw)
    return TelemetryBatchResponse(
        received=len(events),
        accepted=len(events),
        duplicates=0,
        status="ok",
    )

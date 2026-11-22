import uuid
from datetime import datetime
from typing import List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_id
from app.db.session import get_db
from app.models.enums import DetectedInterruptionType, InterruptionSeverity
from app.models.raw_telemetry_event import RawTelemetryEvent
from app.schemas.interruption import (
    DetectedInterruptionFeedbackCreate,
    DetectedInterruptionFeedbackRead,
    DetectedInterruptionRead,
    DetectedInterruptionsQueryResponse,
    InterruptionCreate,
    InterruptionDetectionBatchTrigger,
    InterruptionDetectionMetricsResponse,
    InterruptionRead,
)
from app.services import interruption_detector, interruption_service

router = APIRouter(prefix="/interruptions", tags=["interruptions"])


# ---------------------------------------------------------------------------
# Automated Interruption Detection Endpoints (Phase 3.5)
# Note: Defined before /{interruption_id} to prevent path parameter collision
# ---------------------------------------------------------------------------

@router.get("/metrics", response_model=InterruptionDetectionMetricsResponse)
def get_interruption_metrics(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Calculates behavioral interruption metrics and feedback validation rates."""
    return interruption_detector.compute_interruption_metrics(db, user_id)


@router.get("/detected", response_model=DetectedInterruptionsQueryResponse)
def list_detected_interruptions(
    interruption_type: Optional[DetectedInterruptionType] = Query(default=None),
    severity: Optional[InterruptionSeverity] = Query(default=None),
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    min_confidence: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Returns paginated, filterable automated interruption events for the user."""
    items, total = interruption_detector.query_detected_interruptions(
        db=db,
        user_id=user_id,
        interruption_type=interruption_type,
        severity=severity,
        start_time=start_time,
        end_time=end_time,
        min_confidence=min_confidence,
        limit=limit,
        offset=offset,
    )
    return DetectedInterruptionsQueryResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/detect", response_model=List[DetectedInterruptionRead])
def trigger_detection(
    payload: Optional[InterruptionDetectionBatchTrigger] = None,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Triggers automated interruption detection over recently ingested
    raw telemetry events for the user and returns any newly detected interruptions.
    """
    trigger_opts = payload or InterruptionDetectionBatchTrigger()
    stmt = (
        select(RawTelemetryEvent)
        .where(RawTelemetryEvent.user_id == user_id)
        .order_by(desc(RawTelemetryEvent.event_timestamp))
        .limit(trigger_opts.limit)
    )
    events = list(db.scalars(stmt).all())
    # Sort chronological for processing
    events.reverse()

    persisted = interruption_detector.process_and_persist_telemetry_interruptions(
        db=db,
        user_id=user_id,
        raw_events=events,
    )
    return persisted


@router.get("/detected/{interruption_id}", response_model=DetectedInterruptionRead)
def get_detected_interruption_detail(
    interruption_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Retrieves single detected interruption details with user feedback history."""
    item = interruption_detector.get_detected_interruption_by_id(db, user_id, interruption_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Detected interruption not found",
        )
    return item


@router.post("/detected/{interruption_id}/feedback", response_model=DetectedInterruptionFeedbackRead)
@router.post("/{interruption_id}/feedback", response_model=DetectedInterruptionFeedbackRead)
def submit_interruption_feedback_endpoint(
    interruption_id: uuid.UUID,
    payload: DetectedInterruptionFeedbackCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Submits ground-truth manual feedback for a detected interruption."""
    try:
        return interruption_detector.submit_interruption_feedback(
            db=db,
            user_id=user_id,
            interruption_id=interruption_id,
            payload=payload,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ---------------------------------------------------------------------------
# Manual Interruption Endpoints (Phase 1 Baseline Preserved)
# ---------------------------------------------------------------------------

@router.post("", response_model=InterruptionRead, status_code=status.HTTP_201_CREATED)
def create_interruption(
    payload: InterruptionCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return interruption_service.create_interruption(db, user_id, payload)


@router.get("", response_model=list[InterruptionRead])
def list_interruptions(
    task_id: uuid.UUID | None = Query(default=None),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return interruption_service.list_interruptions(db, user_id, task_id)


@router.get("/{interruption_id}", response_model=Union[DetectedInterruptionRead, InterruptionRead])
def get_interruption(
    interruption_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Fetches interruption by ID. Checks manual interruptions first;
    if not found, checks detected interruptions.
    """
    try:
        return interruption_service.get_interruption(db, user_id, interruption_id)
    except HTTPException:
        detected = interruption_detector.get_detected_interruption_by_id(db, user_id, interruption_id)
        if detected:
            return detected
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interruption not found",
        )


@router.delete("/{interruption_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_interruption(
    interruption_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    interruption_service.delete_interruption(db, user_id, interruption_id)

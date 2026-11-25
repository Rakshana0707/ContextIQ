"""
FastAPI router for Proactive Behavioral Intelligence and Event Ingestion (Phase 7.3).
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_id
from app.db.session import get_db
from app.models.event_models import DeadLetterEventRecord
from app.schemas.event_schemas import (
    DeadLetterRecordSchema,
    EventIngestRequest,
    EventProcessingResult,
    ProactiveActionRequest,
    ProactiveFeedItemSchema,
    StandardEvent,
)
from app.services.behavioral_detector import BehavioralChangeDetector
from app.services.event_processor import EventProcessor
from app.services.proactive_intelligence import ProactiveIntelligenceService

router = APIRouter(prefix="/proactive", tags=["proactive-intelligence"])


@router.post("/events/ingest", response_model=EventProcessingResult, status_code=status.HTTP_200_OK)
def ingest_event(
    payload: EventIngestRequest,
    db: Session = Depends(get_db),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> EventProcessingResult:
    """
    Ingests an operational event or behavioral telemetry record into the
    ContextIQ standardized event stream. Evaluates rules and generates
    proactive feed items when appropriate.
    """
    # Enforce current user ID if not explicitly administrative
    payload.user_id = current_user_id
    result = EventProcessor.process_event(db=db, event_or_req=payload)
    return result


@router.get("/feed", response_model=List[ProactiveFeedItemSchema])
def get_proactive_feed(
    status_filter: Optional[str] = Query(default=None, description="ACTIVE, SNOOZED, DISMISSED, ACTIONED or null for all"),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> List[ProactiveFeedItemSchema]:
    """Retrieves proactive intelligence feed items for current user."""
    items = ProactiveIntelligenceService.get_user_feed(
        db=db,
        user_id=current_user_id,
        status=status_filter,
        limit=limit,
    )
    return [ProactiveFeedItemSchema.model_validate(item) for item in items]


@router.post("/feed/{item_id}/action", response_model=ProactiveFeedItemSchema)
def respond_to_feed_item(
    item_id: uuid.UUID,
    action_req: ProactiveActionRequest,
    db: Session = Depends(get_db),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> ProactiveFeedItemSchema:
    """
    Accepts user decision on proactive intelligence item:
    APPROVE (action proposal), SNOOZE (defer for N minutes), or DISMISS.
    """
    updated_item = ProactiveIntelligenceService.respond_to_feed_item(
        db=db,
        feed_item_id=item_id,
        user_id=current_user_id,
        action=action_req.action,
        snooze_minutes=action_req.snooze_minutes or 60,
    )
    if not updated_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proactive feed item '{item_id}' not found.",
        )
    return ProactiveFeedItemSchema.model_validate(updated_item)


@router.get("/dead-letter", response_model=List[DeadLetterRecordSchema])
def list_dead_letter_events(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> List[DeadLetterRecordSchema]:
    """Returns dead-letter queue records for current user (or administrative audit)."""
    records = db.execute(
        select(DeadLetterEventRecord)
        .where(
            (DeadLetterEventRecord.user_id == current_user_id) | (DeadLetterEventRecord.user_id.is_(None))
        )
        .order_by(DeadLetterEventRecord.created_at.desc())
        .limit(limit)
    ).scalars().all()

    return [DeadLetterRecordSchema.model_validate(r) for r in records]


@router.post("/simulate-detection", response_model=EventProcessingResult)
def simulate_behavioral_detection(
    detection_type: str = Query(..., description="THRASHING, FORGETTING_RISK, RECOVERY_LAG, CALENDAR_OVERLOAD, BFI_SPIKE"),
    db: Session = Depends(get_db),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> EventProcessingResult:
    """
    Triggers simulated behavioral pattern detection for end-to-end testing and demonstrations.
    """
    event: Optional[StandardEvent] = None
    if detection_type.upper() in ("THRASHING", "THRASHING_DETECTED"):
        event = BehavioralChangeDetector.detect_context_thrashing(
            user_id=current_user_id,
            switch_count_last_minute=8,
            active_apps=["IDE", "Slack", "Browser", "Email", "Terminal"],
        )
    elif detection_type.upper() in ("FORGETTING_RISK", "FORGETTING_RISK_SPIKE"):
        event = BehavioralChangeDetector.detect_forgetting_risk_spike(
            user_id=current_user_id,
            task_id=uuid.uuid4(),
            task_title="Review Q4 Behavioral Analytics",
            predicted_lapse_probability=0.82,
            hours_since_interruption=3.5,
        )
    elif detection_type.upper() in ("RECOVERY_LAG", "RECOVERY_LAG_EXCEEDED"):
        event = BehavioralChangeDetector.detect_recovery_lag_exceeded(
            user_id=current_user_id,
            actual_recovery_duration_seconds=1500,
            expected_recovery_seconds=600,
        )
    elif detection_type.upper() in ("CALENDAR_OVERLOAD"):
        event = BehavioralChangeDetector.detect_calendar_overload(
            user_id=current_user_id,
            consecutive_events_count=4,
            total_dense_hours=3.5,
            buffer_minutes_between=0.0,
        )
    elif detection_type.upper() in ("BFI_SPIKE"):
        event = BehavioralChangeDetector.detect_bfi_spike(
            user_id=current_user_id,
            baseline_bfi=0.35,
            current_bfi=0.68,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown detection type '{detection_type}'.",
        )

    if not event:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Detection criteria did not meet threshold for triggering an event.",
        )

    # Ingest event directly
    return EventProcessor.process_event(db=db, event_or_req=event)

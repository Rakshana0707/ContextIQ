"""FastAPI router for unified behavioral timeline and cross-device session reconstruction (Phase 5.7)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.timeline import (
    CrossDeviceSessionRead,
    CrossDeviceSyncRequest,
    CrossDeviceSyncResponse,
    UnifiedTimelineEventDTO,
)
from app.services.timeline_service import TimelineService

router = APIRouter(prefix="/activity", tags=["activity"])


@router.post("/sync", response_model=CrossDeviceSyncResponse, status_code=status.HTTP_200_OK, summary="Sync Cross-Device Events")
def sync_cross_device_events(
    payload: CrossDeviceSyncRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Ingests batch events from an authorized desktop or mobile client.
    Enforces idempotency, calculates clock-skew drift, and updates device last-seen status.
    """
    return TimelineService.sync_device_events(db=db, user_id=user_id, request=payload)


@router.get("/timeline", response_model=List[UnifiedTimelineEventDTO], summary="Get Unified Behavioral Timeline")
def get_unified_timeline(
    device_id: Optional[str] = Query(None, description="Filter by device hardware identifier"),
    device_type: Optional[str] = Query(None, description="Filter by device type (DESKTOP, MOBILE, WEB, CALENDAR)"),
    start_time: Optional[datetime] = Query(None, description="Start timestamp filter (ISO 8601)"),
    end_time: Optional[datetime] = Query(None, description="End timestamp filter (ISO 8601)"),
    task_id: Optional[uuid.UUID] = Query(None, description="Filter by associated task ID"),
    application: Optional[str] = Query(None, description="Filter by application name"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    limit: int = Query(50, ge=1, le=200, description="Max events to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Returns a unified, chronologically ordered stream of behavioral events across all user devices.
    """
    return TimelineService.get_unified_timeline(
        db=db,
        user_id=user_id,
        device_id=device_id,
        device_type=device_type,
        start_time=start_time,
        end_time=end_time,
        task_id=task_id,
        application=application,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )


@router.get("/cross-device-sessions", response_model=List[CrossDeviceSessionRead], summary="Get Cross-Device Reconstructed Sessions")
def get_cross_device_sessions(
    lookback_hours: int = Query(24, ge=1, le=168, description="Lookback hours for session reconstruction"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Synthesizes and returns multi-device work sessions spanning desktop, mobile, and web.
    """
    return TimelineService.get_cross_device_sessions(
        db=db,
        user_id=user_id,
        lookback_hours=lookback_hours,
    )

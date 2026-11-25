"""REST API router for Google Calendar two-way synchronization and event operations."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.google_calendar import (
    GoogleCalendarDTO,
    GoogleEventCreate,
    GoogleEventRead,
    GoogleEventUpdate,
    GoogleSyncResponse,
)
from app.services import google_sync_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/google", tags=["google_calendar"])


class SyncGoogleRequest(BaseModel):
    calendar_id: str = "primary"
    force_full: bool = False


@router.post("/sync", response_model=GoogleSyncResponse)
def trigger_google_sync(
    payload: Optional[SyncGoogleRequest] = None,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Trigger delta or full synchronization with Google Calendar."""
    calendar_id = payload.calendar_id if payload else "primary"
    force_full = payload.force_full if payload else False
    return google_sync_service.sync_google_calendar(
        db=db,
        user_id=user_id,
        calendar_id=calendar_id,
        force_full=force_full,
    )


@router.get("/calendars", response_model=List[GoogleCalendarDTO])
def get_user_google_calendars(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """List Google Calendars available in the connected user account."""
    try:
        return google_sync_service.list_calendars(db, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Failed to list Google calendars: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/events", response_model=List[GoogleEventRead])
def list_synchronized_events(
    calendar_id: Optional[str] = Query(None, description="Filter by calendar ID"),
    start_time: Optional[datetime] = Query(None, description="Start time lower bound"),
    end_time: Optional[datetime] = Query(None, description="End time upper bound"),
    transparency: Optional[str] = Query(None, description="OPAQUE (busy) or TRANSPARENT (free)"),
    status: Optional[str] = Query(None, description="CONFIRMED, TENTATIVE, or CANCELLED"),
    limit: int = Query(100, ge=1, le=500),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Query synchronized Google Calendar events from the local database."""
    events = google_sync_service.list_events(
        db=db,
        user_id=user_id,
        calendar_id=calendar_id,
        start_time=start_time,
        end_time=end_time,
        transparency=transparency,
        status=status,
        limit=limit,
    )
    return events


@router.post("/events", response_model=GoogleEventRead, status_code=status.HTTP_201_CREATED)
def create_google_event(
    payload: GoogleEventCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Create a new event in Google Calendar (e.g. ContextIQ scheduled focus block)."""
    try:
        return google_sync_service.create_event(db, user_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Failed to create Google event: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.patch("/events/{event_id}", response_model=GoogleEventRead)
def update_google_event(
    event_id: str,
    payload: GoogleEventUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Update an existing Google Calendar event and synchronize the change."""
    try:
        return google_sync_service.update_event(db, user_id, event_id, payload)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Failed to update Google event %s: %s", event_id, exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.delete("/events/{event_id}")
def delete_google_event(
    event_id: str,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Delete an event from Google Calendar and mark it cancelled locally."""
    try:
        success = google_sync_service.delete_event(db, user_id, event_id)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Event {event_id} not found.")
        return {"success": True, "event_id": event_id}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to delete Google event %s: %s", event_id, exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

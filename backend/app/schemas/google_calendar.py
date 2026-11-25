"""Pydantic schemas for Google Calendar two-way synchronization endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from integrations.app.schemas.integration_schemas import EventStatus, EventTransparency


class GoogleSyncResponse(BaseModel):
    """Result of a Google Calendar synchronization run."""
    success: bool
    integration_id: uuid.UUID
    sync_status: str
    events_created: int
    events_updated: int
    events_deleted: int
    new_sync_token: Optional[str] = None
    full_resync_occurred: bool = False
    duration_ms: float
    error_message: Optional[str] = None


class GoogleCalendarDTO(BaseModel):
    """Information about a Google Calendar resource."""
    calendar_id: str
    name: str
    is_primary: bool
    access_role: str
    description: Optional[str] = None
    time_zone: Optional[str] = None


class GoogleEventRead(BaseModel):
    """Structured representation of a synchronized Google Calendar event."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    integration_id: uuid.UUID
    calendar_id: str
    external_event_id: str
    title: str
    description: Optional[str] = None
    location_name: Optional[str] = None
    start_time: datetime
    end_time: datetime
    timezone: str
    is_all_day: bool
    status: str
    transparency: str
    visibility: str
    is_private: bool
    is_recurring: bool
    recurring_event_id: Optional[str] = None
    is_organizer: bool
    organizer_email: Optional[str] = None
    attendees_count: int
    etag: Optional[str] = None
    html_link: Optional[str] = None
    is_contextiq_managed: bool
    linked_task_id: Optional[uuid.UUID] = None
    last_synced_at: datetime
    created_at: datetime
    updated_at: datetime


class GoogleEventCreate(BaseModel):
    """Payload to create an event in Google Calendar (e.g. ContextIQ focus block)."""
    calendar_id: str = "primary"
    title: str = Field(..., max_length=512)
    description: Optional[str] = None
    location_name: Optional[str] = None
    start_time: datetime
    end_time: datetime
    timezone: str = "UTC"
    is_all_day: bool = False
    transparency: EventTransparency = EventTransparency.OPAQUE
    linked_task_id: Optional[uuid.UUID] = None


class GoogleEventUpdate(BaseModel):
    """Payload to update an event in Google Calendar."""
    title: Optional[str] = Field(None, max_length=512)
    description: Optional[str] = None
    location_name: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    timezone: Optional[str] = None
    is_all_day: Optional[bool] = None
    transparency: Optional[EventTransparency] = None
    allow_external_modification: bool = False  # Guard against accidental external event overwrite

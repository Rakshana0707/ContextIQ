"""Pydantic schemas and Data Transfer Objects (DTOs) for external calendar integrations."""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ConnectionStatus(str, Enum):
    CONNECTED = "CONNECTED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    ERROR = "ERROR"


class SyncStatus(str, Enum):
    INITIALIZING = "INITIALIZING"
    SYNCED = "SYNCED"
    IN_PROGRESS = "IN_PROGRESS"
    FAILED = "FAILED"


class EventStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    TENTATIVE = "TENTATIVE"
    CANCELLED = "CANCELLED"


class EventTransparency(str, Enum):
    OPAQUE = "OPAQUE"            # Blocks focus time (busy)
    TRANSPARENT = "TRANSPARENT"  # Does not block focus time (free)


class OAuthTokenBundle(BaseModel):
    """Encapsulation of OAuth token credentials."""
    model_config = ConfigDict(frozen=True)

    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_at: datetime
    scope: List[str] = Field(default_factory=list)
    id_token: Optional[str] = None
    provider_user_id: Optional[str] = None
    provider_email: Optional[str] = None


class CalendarDTO(BaseModel):
    """Normalized representation of an external calendar container."""
    calendar_id: str
    name: str
    is_primary: bool = False
    access_role: str = "reader"
    description: Optional[str] = None
    time_zone: Optional[str] = None


class CalendarEventDTO(BaseModel):
    """Normalized external calendar event DTO."""
    event_id: str
    calendar_id: str = "primary"
    provider: str
    title: str
    start_time: datetime
    end_time: datetime
    is_all_day: bool = False
    description: Optional[str] = None
    location_name: Optional[str] = None
    status: EventStatus = EventStatus.CONFIRMED
    transparency: EventTransparency = EventTransparency.OPAQUE
    organizer_email: Optional[str] = None
    attendees_count: int = 0
    is_organizer: bool = True
    html_link: Optional[str] = None
    etag: Optional[str] = None
    timezone: Optional[str] = None
    visibility: Optional[str] = "default"
    recurring_event_id: Optional[str] = None
    is_recurring: bool = False
    original_start_time: Optional[datetime] = None
    updated_at_provider: Optional[datetime] = None
    raw_payload: Dict[str, Any] = Field(default_factory=dict)


class CalendarEventCreateDTO(BaseModel):
    """Payload to create an event in an external calendar."""
    title: str
    start_time: datetime
    end_time: datetime
    is_all_day: bool = False
    description: Optional[str] = None
    location_name: Optional[str] = None
    transparency: EventTransparency = EventTransparency.OPAQUE


class CalendarEventUpdateDTO(BaseModel):
    """Payload to update an event in an external calendar."""
    title: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    is_all_day: Optional[bool] = None
    description: Optional[str] = None
    location_name: Optional[str] = None
    transparency: Optional[EventTransparency] = None


class SyncResult(BaseModel):
    """Result of an initial or incremental synchronization operation."""
    success: bool
    new_sync_token: Optional[str] = None
    synced_events: List[CalendarEventDTO] = Field(default_factory=list)
    deleted_event_ids: List[str] = Field(default_factory=list)
    full_resync_required: bool = False
    sync_duration_ms: float = 0.0
    error_message: Optional[str] = None


# --- API Request & Response Schemas ---

class ConnectRequest(BaseModel):
    """Request to initiate OAuth connection."""
    redirect_uri: Optional[str] = None
    request_write_access: bool = False  # Default minimal read-only scope


class ConnectResponse(BaseModel):
    """Response containing authorization URL and PKCE/state data."""
    provider: str
    authorization_url: str
    state: str
    code_verifier: Optional[str] = None


class IntegrationResponse(BaseModel):
    """Public integration metadata (never contains raw or encrypted credentials)."""
    id: uuid.UUID
    user_id: uuid.UUID
    provider: str
    provider_account_id: Optional[str] = None
    provider_email: Optional[str] = None
    connection_status: ConnectionStatus
    granted_scopes: List[str] = Field(default_factory=list)
    last_synced_at: Optional[datetime] = None
    sync_status: SyncStatus = SyncStatus.INITIALIZING
    created_at: datetime
    updated_at: datetime


class IntegrationStatusResponse(BaseModel):
    """Detailed health and synchronization status of an integration."""
    id: uuid.UUID
    provider: str
    connection_status: ConnectionStatus
    is_active: bool
    has_valid_token: bool
    expires_in_seconds: Optional[int] = None
    last_synced_at: Optional[datetime] = None
    sync_status: SyncStatus
    error_message: Optional[str] = None


class CalendarListResponse(BaseModel):
    """List of user calendars across connected integrations."""
    integration_id: uuid.UUID
    provider: str
    calendars: List[CalendarDTO]

"""Pydantic v2 schemas for telemetry ingestion, querying, and agent status."""
import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class TelemetryEventIn(BaseModel):
    """Raw telemetry event payload received from desktop agent."""
    event_id: str = Field(min_length=8, max_length=64, description="Globally unique time-ordered identifier (UUIDv7/UUIDv4)")
    user_id: uuid.UUID | str = Field(description="User identifier")
    device_id: Optional[str] = Field(default=None, max_length=128, description="Device hardware hash")
    event_type: str = Field(min_length=1, max_length=64, description="Behavioral event type (e.g. application_activated)")
    event_timestamp: datetime = Field(description="Occurrence timestamp in UTC recorded on client clock")
    source: str = Field(default="desktop_agent_windows", max_length=64, description="Platform source identifier")
    schema_version: str = Field(default="1.0.0", max_length=32, description="Event contract schema version")

    session_id: Optional[uuid.UUID | str] = Field(default=None, description="Optional work session identifier")
    correlation_id: Optional[uuid.UUID | str] = Field(default=None, description="Optional correlated event identifier")

    application_identifier: Optional[str] = Field(default=None, max_length=255, description="Primary executable identifier")
    previous_application_identifier: Optional[str] = Field(default=None, max_length=255, description="Relinquished application")
    current_application_identifier: Optional[str] = Field(default=None, max_length=255, description="Active application")

    payload: dict[str, Any] = Field(default_factory=dict, description="Event-specific metadata")


class TelemetryEventRead(BaseModel):
    """Telemetry event representation for client responses."""
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    user_id: uuid.UUID
    device_id: Optional[str] = None
    event_type: str
    event_timestamp: datetime
    ingestion_timestamp: datetime
    source: str
    schema_version: str
    session_id: Optional[uuid.UUID] = None
    correlation_id: Optional[uuid.UUID] = None
    application_identifier: Optional[str] = None
    previous_application_identifier: Optional[str] = None
    current_application_identifier: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class TelemetryBatchIn(BaseModel):
    """Batch ingestion request envelope."""
    events: list[TelemetryEventIn] = Field(
        min_length=1,
        max_length=500,
        description="Batched telemetry events (up to 500 per request)",
    )


class TelemetryBatchResponse(BaseModel):
    """Detailed server acknowledgement for batch synchronization."""
    received: int = Field(description="Total events received in request")
    accepted: int = Field(description="Newly inserted events in database")
    duplicates: int = Field(default=0, description="Ignored duplicate events")
    failed: int = Field(default=0, description="Events rejected or failed")
    synced_event_ids: list[str] = Field(default_factory=list, description="IDs acknowledged by server (accepted + duplicate)")
    duplicate_event_ids: list[str] = Field(default_factory=list, description="IDs already existing in database")
    failed_event_ids: list[str] = Field(default_factory=list, description="IDs that failed processing")
    status: str = Field(default="ok", description="Batch processing status")


class AgentStatusResponse(BaseModel):
    """Agent health, connection, and sync diagnostic status."""
    user_id: str
    device_id: Optional[str] = None
    consent_status: str
    is_paused: bool
    paused_until: Optional[datetime] = None
    last_event_timestamp: Optional[datetime] = None
    last_ingestion_timestamp: Optional[datetime] = None
    total_events_ingested: int = 0
    active_categories: list[str] = Field(default_factory=list)


class TelemetryEventsQueryResponse(BaseModel):
    """Paginated telemetry events response."""
    items: list[TelemetryEventRead]
    total: int
    limit: int
    offset: int

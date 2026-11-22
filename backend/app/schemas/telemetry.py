"""Telemetry event ingestion schemas for ContextIQ backend."""
from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field


class TelemetryEventIn(BaseModel):
    """Raw telemetry event payload received from desktop agent."""
    event_id: str = Field(description="Unique event ID (UUIDv7 or UUIDv4)")
    user_id: UUID | str = Field(description="User identifier")
    device_id: str | None = Field(default=None, description="Device hash")
    event_type: str = Field(description="Classification of behavioral event")
    event_timestamp: datetime | str = Field(description="Event timestamp in UTC")
    source: str = Field(default="desktop_agent_windows")
    schema_version: str = Field(default="1.0.0")
    session_id: UUID | str | None = Field(default=None)
    correlation_id: UUID | str | None = Field(default=None)
    application_identifier: str | None = Field(default=None)
    previous_application_identifier: str | None = Field(default=None)
    current_application_identifier: str | None = Field(default=None)
    payload: dict[str, Any] = Field(default_factory=dict)


class TelemetryBatchIn(BaseModel):
    """Batch ingestion request envelope."""
    events: list[TelemetryEventIn] = Field(description="List of telemetry events")


class TelemetryBatchResponse(BaseModel):
    """Batch ingestion response."""
    received: int
    accepted: int
    duplicates: int
    status: str = "ok"

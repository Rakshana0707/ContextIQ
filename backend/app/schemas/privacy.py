import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.enums import ConsentStatus, TelemetryCategory
from app.schemas.base import ORMBase


# --- Telemetry Consent Schemas ---

class ConsentGrantRequest(BaseModel):
    consent_version: str = Field(default="1.0.0", max_length=32)
    enabled_categories: list[TelemetryCategory] = Field(
        ...,
        description="Explicitly enabled telemetry collection categories",
        min_length=1,
    )
    device_id: Optional[str] = Field(default=None, max_length=128)


class ConsentRevokeRequest(BaseModel):
    device_id: Optional[str] = Field(default=None, max_length=128)
    reason: Optional[str] = Field(default=None, max_length=256)


class ConsentRead(ORMBase):
    id: uuid.UUID
    user_id: uuid.UUID
    consent_version: str
    enabled_categories: list[str]
    granted_timestamp: datetime
    updated_timestamp: datetime
    revoked_timestamp: Optional[datetime] = None
    device_id: Optional[str] = None
    consent_status: ConsentStatus
    created_at: datetime


# --- Privacy Settings Schemas ---

class PrivacySettingsRead(ORMBase):
    user_id: uuid.UUID
    is_paused: bool
    paused_until: Optional[datetime] = None
    raw_event_retention_days: int
    aggregated_metric_retention_days: int
    allow_anonymized_research: bool
    updated_at: datetime


class PrivacySettingsUpdate(BaseModel):
    is_paused: Optional[bool] = None
    pause_duration_minutes: Optional[int] = Field(
        default=None, ge=1, le=43200, description="Pause duration in minutes (e.g. 60 for 1 hour)"
    )
    raw_event_retention_days: Optional[int] = Field(default=None, ge=1, le=365)
    aggregated_metric_retention_days: Optional[int] = Field(default=None, ge=30, le=3650)
    allow_anonymized_research: Optional[bool] = None


# --- App Exclusion Schemas ---

class AppExclusionCreate(BaseModel):
    application_identifier: str = Field(..., max_length=128, description="Executable name, e.g. '1password.exe'")
    description: Optional[str] = Field(default=None, max_length=256)


class AppExclusionRead(ORMBase):
    id: uuid.UUID
    user_id: uuid.UUID
    application_identifier: str
    description: Optional[str] = None
    created_at: datetime


# --- Data Purge (Right to Erasure) Schemas ---

class DataPurgeRequest(BaseModel):
    purge_raw_telemetry: bool = Field(default=True, description="Delete granular timestamped focus events")
    purge_context_sessions: bool = Field(default=False, description="Delete derived context sessions")
    purge_local_buffer_token: Optional[str] = Field(default=None, description="Device-specific purge token")
    confirmation_phrase: str = Field(..., description="Must equal 'DELETE MY DATA'")


class DataPurgeResponse(BaseModel):
    status: str = "success"
    message: str
    purged_raw_telemetry_count: int
    purged_context_sessions_count: int
    purged_at: datetime


# --- Telemetry Metadata Summary ---

class TelemetryMetadataSummary(BaseModel):
    total_raw_events: int
    total_context_sessions: int
    oldest_event_at: Optional[datetime] = None
    newest_event_at: Optional[datetime] = None
    active_monitoring_status: str  # "ACTIVE", "PAUSED", "DISABLED"
    active_categories_count: int
    excluded_apps_count: int
    retention_days_raw: int

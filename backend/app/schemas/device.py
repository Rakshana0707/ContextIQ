"""Pydantic schemas for device registry and hardware authorization (Phase 5.7)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class DeviceRegisterRequest(BaseModel):
    """Payload to register or update an authorized device."""
    device_id: str = Field(..., max_length=128, description="Persistent unique device hardware identifier")
    device_type: str = Field("DESKTOP", max_length=32, description="DESKTOP | MOBILE | TABLET | WEB")
    platform: str = Field("WINDOWS", max_length=32, description="WINDOWS | ANDROID | IOS | MACOS | LINUX | WEB")
    device_name: str = Field("Workstation", max_length=255, description="Human-readable device name")
    application_version: str = Field("1.0.0", max_length=64, description="Installed client software version")
    device_metadata: Dict[str, Any] = Field(default_factory=dict, description="Hardware specs, OS build, screen resolution")


class DeviceUpdateRequest(BaseModel):
    device_name: Optional[str] = None
    application_version: Optional[str] = None
    device_metadata: Optional[Dict[str, Any]] = None


class DeviceRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    device_id: str
    device_type: str
    platform: str
    device_name: str
    application_version: str
    registration_timestamp: datetime
    last_seen_timestamp: datetime
    connection_status: str
    synchronization_status: str
    device_metadata: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool
    revoked_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeviceRevokeResponse(BaseModel):
    device_id: str
    status: str = "REVOKED"
    message: str = "Device access revoked successfully. Telemetry synchronization disabled."
    revoked_at: datetime

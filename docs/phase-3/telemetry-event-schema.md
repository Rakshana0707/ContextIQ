# Phase 3: Telemetry Event Schema Specification

## 1. Overview & Event Modeling Principles

The ContextIQ Telemetry Event Contract defines the standardized schema for all desktop activity and disruption signals. To support high-throughput ingestion, zero-data-loss buffering, and cross-platform future expansion, the contract enforces the following engineering invariants:

1. **Self-Describing Envelope**: Every event carries a standardized header containing temporal, device, user, and correlation provenance.
2. **Strict Privacy Hygiene**: Application metadata is restricted to binary process names and high-level sanitized categories. Free-text window titles are strictly redacted on the client prior to serialization.
3. **Monotonic & Chronological Order**: Events use UUIDv7 (timestamp-ordered UUID) for `event_id`, guaranteeing chronological sorting even under distributed or out-of-order ingestion.
4. **Idempotency Guarantee**: `event_id` serves as the primary deduplication key across both client buffer and server storage (`ON CONFLICT (event_id) DO NOTHING`).
5. **Schema Versioning**: Every event explicitly specifies `schema_version = "1.0.0"`, facilitating backward-compatible schema evolutions.

---

## 2. Canonical Telemetry Event Envelope

Every telemetry event transmitted by the agent adheres to the following base contract:

```json
{
  "event_id": "018d9f4a-9b12-78a0-9832-7e92b8d00123",
  "user_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "device_id": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "event_type": "APP_FOCUS_GAINED",
  "event_timestamp": "2026-11-21T10:15:30.125482Z",
  "ingestion_timestamp": "2026-11-21T10:15:45.002150Z",
  "source": "desktop_agent_windows",
  "schema_version": "1.0.0",
  "session_id": "a4d87f5e-1832-4911-9a72-73108c903aef",
  "correlation_id": "c1f8872e-0931-4a11-b012-e31a10052c11",
  "application_identifier": "code.exe",
  "previous_application_identifier": "slack.exe",
  "current_application_identifier": "code.exe",
  "payload": { ... }
}
```

### Data Dictionary — Envelope Fields

| Field Name | Type | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `event_id` | `UUIDv7` | Yes | Globally unique, time-ordered identifier for the event. | `"018d9f4a-9b12-78a0-9832-7e92b8d00123"` |
| `user_id` | `UUIDv4` | Yes | Foreign key identifier of the authenticated user. | `"9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"` |
| `device_id` | `string` | Yes | SHA-256 hash of machine motherboard UUID + OS installation ID. Never exposes raw hardware serials. | `"e3b0c44298fc1c14..."` |
| `event_type` | `Enum` | Yes | High-level event classification (see section 3). | `"APP_FOCUS_GAINED"` |
| `event_timestamp` | `datetime (UTC)` | Yes | High-precision ISO-8601 UTC timestamp of occurrence recorded by client OS clock. | `"2026-11-21T10:15:30.125482Z"` |
| `ingestion_timestamp` | `datetime (UTC)` | Nullable | Server-assigned timestamp upon receipt at the ingestion boundary. | `"2026-11-21T10:15:45.002150Z"` |
| `source` | `string` | Yes | Source identifier and platform tag. | `"desktop_agent_windows"` |
| `schema_version` | `string` | Yes | Semantic version string of the event schema. | `"1.0.0"` |
| `session_id` | `UUID` | Nullable | Active desktop work session identifier, if reconstructed or assigned. | `"a4d87f5e-1832-4911-9a72-73108c903aef"` |
| `correlation_id` | `UUID` | Nullable | Shared identifier connecting paired events (e.g. `APP_FOCUS_LOST` to `APP_FOCUS_GAINED`, or `USER_IDLE_START` to `USER_IDLE_END`). | `"c1f8872e-0931-4a11-b012-e31a10052c11"` |
| `application_identifier` | `string` | Yes | Executable process name of the active foreground application. | `"code.exe"` |
| `previous_application_identifier` | `string` | Nullable | Process name of the window relinquishing focus. | `"slack.exe"` |
| `current_application_identifier` | `string` | Nullable | Process name of the window receiving focus (matches `application_identifier`). | `"code.exe"` |
| `payload` | `JSON Object` | Yes | Event-specific metadata attributes. | `{ ... }` |

---

## 3. Supported Event Types & Detailed Payloads

### 3.1 `APP_FOCUS_GAINED`
Emitted immediately when a top-level window becomes active in the foreground.

```json
{
  "event_type": "APP_FOCUS_GAINED",
  "application_identifier": "code.exe",
  "previous_application_identifier": "slack.exe",
  "current_application_identifier": "code.exe",
  "payload": {
    "process_id": 14220,
    "category": "DEVELOPMENT",
    "window_class": "Chrome_WidgetWin_1",
    "sanitized_title": "workspace-contextiq — Visual Studio Code",
    "is_full_screen": false,
    "monitor_index": 1,
    "transition_trigger": "USER_CLICK"
  }
}
```

### 3.2 `APP_FOCUS_LOST`
Emitted when a previously active window loses focus. Contains duration telemetry for the focus interval.

```json
{
  "event_type": "APP_FOCUS_LOST",
  "application_identifier": "slack.exe",
  "payload": {
    "process_id": 8940,
    "category": "COMMUNICATION",
    "focus_duration_seconds": 18.452,
    "active_typing_detected": false
  }
}
```

### 3.3 `USER_IDLE_START`
Emitted when `GetLastInputInfo` indicates continuous inactivity exceeding the idle threshold (default: 180 seconds).

```json
{
  "event_type": "USER_IDLE_START",
  "application_identifier": "code.exe",
  "payload": {
    "idle_threshold_seconds": 180,
    "last_active_timestamp": "2026-11-21T10:12:30.125Z",
    "last_active_application": "code.exe",
    "last_active_category": "DEVELOPMENT"
  }
}
```

### 3.4 `USER_IDLE_END`
Emitted on the first user input tick following an idle interval. Marks the start of potential **Resumption Lag**.

```json
{
  "event_type": "USER_IDLE_END",
  "application_identifier": "code.exe",
  "correlation_id": "c1f8872e-0931-4a11-b012-e31a10052c11",
  "payload": {
    "total_idle_duration_seconds": 642.5,
    "wake_input_type": "MOUSE_MOVE",
    "resuming_into_application": "code.exe",
    "is_same_as_last_active": true
  }
}
```

### 3.5 `SYSTEM_LOCK` & `SYSTEM_UNLOCK`
Emitted via Windows Session Notifications when the workstation is locked (`Win+L`, screensaver timeout) or unlocked.

```json
{
  "event_type": "SYSTEM_LOCK",
  "payload": {
    "lock_trigger": "MANUAL_LOCK",
    "active_app_prior_to_lock": "code.exe"
  }
}
```

### 3.6 `HEARTBEAT`
Emitted every 60 seconds by the agent to report liveness, buffer status, and resource usage.

```json
{
  "event_type": "HEARTBEAT",
  "payload": {
    "agent_version": "1.0.0",
    "uptime_seconds": 28800,
    "buffer_unflushed_count": 0,
    "buffer_disk_bytes": 1048576,
    "agent_cpu_percent": 0.2,
    "agent_memory_mb": 24.6,
    "active_privacy_mode": "STANDARD"
  }
}
```

### 3.7 `AGENT_LIFECYCLE`
Emitted on agent startup, graceful shutdown, pause, or resume from tray.

```json
{
  "event_type": "AGENT_LIFECYCLE",
  "payload": {
    "action": "PAUSED_BY_USER",
    "reason": "USER_REQUESTED_INCOGNITO",
    "duration_budget_minutes": 60
  }
}
```

---

## 4. Pydantic Models & Validation Code

Below are the canonical Pydantic v2 schemas used across the desktop agent and backend ingestion services:

```python
"""
telemetry_schemas.py — ContextIQ Telemetry Schema Definitions
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class TelemetryEventType(str, Enum):
    APP_FOCUS_GAINED = "APP_FOCUS_GAINED"
    APP_FOCUS_LOST = "APP_FOCUS_LOST"
    USER_IDLE_START = "USER_IDLE_START"
    USER_IDLE_END = "USER_IDLE_END"
    SYSTEM_LOCK = "SYSTEM_LOCK"
    SYSTEM_UNLOCK = "SYSTEM_UNLOCK"
    HEARTBEAT = "HEARTBEAT"
    AGENT_LIFECYCLE = "AGENT_LIFECYCLE"


class ActivityCategory(str, Enum):
    DEVELOPMENT = "DEVELOPMENT"
    COMMUNICATION = "COMMUNICATION"
    DOCUMENTATION = "DOCUMENTATION"
    BROWSING = "BROWSING"
    UTILITY = "UTILITY"
    DISTRACTION = "DISTRACTION"
    UNKNOWN = "UNKNOWN"


class TelemetryEvent(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    event_id: UUID = Field(..., description="UUIDv7 time-ordered event identifier")
    user_id: UUID = Field(..., description="User foreign key UUID")
    device_id: str = Field(..., max_length=64, description="Hashed hardware identifier")
    event_type: TelemetryEventType
    event_timestamp: datetime
    ingestion_timestamp: Optional[datetime] = None
    source: str = Field(default="desktop_agent_windows", max_length=32)
    schema_version: str = Field(default="1.0.0", max_length=16)
    
    session_id: Optional[UUID] = None
    correlation_id: Optional[UUID] = None
    
    application_identifier: str = Field(..., max_length=128, description="Process name (e.g., code.exe)")
    previous_application_identifier: Optional[str] = Field(None, max_length=128)
    current_application_identifier: Optional[str] = Field(None, max_length=128)
    
    payload: Dict[str, Any] = Field(default_factory=dict)


class TelemetryBatchRequest(BaseModel):
    agent_version: str = Field(..., example="1.0.0")
    device_id: str
    sent_at: datetime
    events: list[TelemetryEvent] = Field(..., max_length=500)


class TelemetryBatchResponse(BaseModel):
    status: str = "success"
    received_count: int
    inserted_count: int
    duplicate_count: int
    server_time: datetime
```

---

## 5. PostgreSQL Storage Engine Schema & Partitioning

To store high-volume telemetry events efficiently while preserving query performance for session reconstruction, `raw_telemetry_events` is partitioned by month:

```sql
-- PostgreSQL Migration: raw_telemetry_events table with range partitioning
CREATE TABLE raw_telemetry_events (
    event_id UUID NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_id VARCHAR(64) NOT NULL,
    event_type VARCHAR(32) NOT NULL,
    event_timestamp TIMESTAMPTZ NOT NULL,
    ingestion_timestamp TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    source VARCHAR(32) NOT NULL,
    schema_version VARCHAR(16) NOT NULL,
    session_id UUID,
    correlation_id UUID,
    application_identifier VARCHAR(128) NOT NULL,
    previous_application_identifier VARCHAR(128),
    current_application_identifier VARCHAR(128),
    payload JSONB,
    PRIMARY KEY (event_id, event_timestamp)
) PARTITION BY RANGE (event_timestamp);

-- Efficient multi-column indexes for session reconstruction
CREATE INDEX ix_telemetry_user_time ON raw_telemetry_events (user_id, event_timestamp DESC);
CREATE INDEX ix_telemetry_correlation ON raw_telemetry_events (correlation_id) WHERE correlation_id IS NOT NULL;
CREATE INDEX ix_telemetry_app ON raw_telemetry_events (user_id, application_identifier, event_timestamp DESC);

-- Initial 2026 Partitions
CREATE TABLE raw_telemetry_events_2026_11 PARTITION OF raw_telemetry_events
    FOR VALUES FROM ('2026-11-01 00:00:00+00') TO ('2026-12-01 00:00:00+00');
CREATE TABLE raw_telemetry_events_2026_12 PARTITION OF raw_telemetry_events
    FOR VALUES FROM ('2026-12-01 00:00:00+00') TO ('2027-01-01 00:00:00+00');
```

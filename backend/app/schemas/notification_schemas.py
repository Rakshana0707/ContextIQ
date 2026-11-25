"""
Pydantic v2 schemas for ContextIQ Intelligent Notification and Cognitive Load Management (Phase 4.8).
Defines schemas for notifications, user preferences, quiet hour rules, dismissal feedback,
and cognitive fatigue metrics.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


class NotificationCategory(str, Enum):
    CRITICAL_DEADLINE_REMINDER = "CRITICAL_DEADLINE_REMINDER"
    HIGH_FORGETTING_RISK_ALERT = "HIGH_FORGETTING_RISK_ALERT"
    RECOVERY_SUGGESTION = "RECOVERY_SUGGESTION"
    FOCUS_SESSION_SUGGESTION = "FOCUS_SESSION_SUGGESTION"
    CONTEXTUAL_REMINDER = "CONTEXTUAL_REMINDER"
    DAILY_BEHAVIORAL_SUMMARY = "DAILY_BEHAVIORAL_SUMMARY"


class NotificationPriority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    BACKGROUND = "BACKGROUND"


class DeliveryStrategy(str, Enum):
    IMMEDIATE = "IMMEDIATE"
    DEFERRED = "DEFERRED"
    BATCHED_SUMMARY = "BATCHED_SUMMARY"
    SUPPRESSED_QUIET_PERIOD = "SUPPRESSED_QUIET_PERIOD"
    EXPIRED = "EXPIRED"
    SUPPRESSED_DUPLICATE = "SUPPRESSED_DUPLICATE"
    NO_NOTIFICATION = "NO_NOTIFICATION"


class DeliveryChannel(str, Enum):
    WEB_IN_APP_TOAST = "WEB_IN_APP_TOAST"
    IN_APP_NOTIFICATION_CENTER = "IN_APP_NOTIFICATION_CENTER"
    DESKTOP_AGENT_NOTIFICATION = "DESKTOP_AGENT_NOTIFICATION"


class SummaryFrequency(str, Enum):
    DAILY = "DAILY"
    TWICE_DAILY = "TWICE_DAILY"
    OFF = "OFF"


class NotificationRead(ORMBase):
    id: uuid.UUID
    user_id: uuid.UUID
    intervention_id: Optional[uuid.UUID] = None
    category: str
    priority: str
    title: str
    message: str
    delivery_channel: str
    delivery_strategy: str
    is_delivered: bool
    delivered_at: Optional[datetime] = None
    is_read: bool
    read_at: Optional[datetime] = None
    is_dismissed: bool
    dismissed_at: Optional[datetime] = None
    is_deferred: bool
    deferred_until: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    metadata_payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class NotificationCreateRequest(BaseModel):
    category: NotificationCategory
    priority: NotificationPriority = NotificationPriority.MEDIUM
    title: str = Field(..., max_length=255)
    message: str
    intervention_id: Optional[uuid.UUID] = None
    preferred_channel: Optional[DeliveryChannel] = None
    expires_at: Optional[datetime] = None
    deadline_at: Optional[datetime] = None
    is_critical_urgency: bool = False
    metadata_payload: Dict[str, Any] = Field(default_factory=dict)


class NotificationPreferenceRead(ORMBase):
    id: uuid.UUID
    user_id: uuid.UUID
    enabled_categories: Dict[str, bool]
    quiet_hours_start: int
    quiet_hours_end: int
    quiet_hours_enabled: bool
    max_notifications_per_hour: int
    max_notifications_per_day: int
    summary_frequency: str
    is_paused: bool
    paused_until: Optional[datetime] = None
    desktop_agent_enabled: bool
    sound_enabled: bool
    updated_at: datetime


class NotificationPreferenceUpdate(BaseModel):
    enabled_categories: Optional[Dict[str, bool]] = None
    quiet_hours_start: Optional[int] = Field(None, ge=0, le=23)
    quiet_hours_end: Optional[int] = Field(None, ge=0, le=23)
    quiet_hours_enabled: Optional[bool] = None
    max_notifications_per_hour: Optional[int] = Field(None, ge=1, le=20)
    max_notifications_per_day: Optional[int] = Field(None, ge=1, le=100)
    summary_frequency: Optional[SummaryFrequency] = None
    is_paused: Optional[bool] = None
    pause_duration_minutes: Optional[int] = Field(None, ge=5, le=1440)
    desktop_agent_enabled: Optional[bool] = None
    sound_enabled: Optional[bool] = None


class NotificationAcknowledgeResponse(BaseModel):
    id: uuid.UUID
    is_read: bool
    acknowledged_at: datetime
    message: str = "Notification acknowledged."


class NotificationDismissRequest(BaseModel):
    reason: Optional[str] = None
    annoyance_level: Optional[int] = Field(None, ge=1, le=5)  # 1 (not annoyed) to 5 (highly annoyed)


class NotificationDismissResponse(BaseModel):
    id: uuid.UUID
    is_dismissed: bool
    dismissed_at: datetime
    updated_fatigue_score: float
    message: str = "Notification dismissed."


class NotificationMetricsResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    user_id: uuid.UUID
    fatigue_score: float
    fatigue_level: str  # LOW, MODERATE, HIGH, CRITICAL
    total_presented_7d: int
    total_accepted_7d: int
    total_dismissed_7d: int
    total_deferred_7d: int
    acceptance_rate_7d: float
    consecutive_dismissals: int
    active_quiet_hours: bool
    is_paused: bool
    paused_until: Optional[datetime] = None
    notifications_delivered_today: int
    notifications_delivered_current_hour: int
    channel_distribution: Dict[str, int] = Field(default_factory=dict)
    category_distribution: Dict[str, int] = Field(default_factory=dict)
    disclaimer: str = (
        "Notification fatigue score represents user interaction frequency and dismissal patterns. "
        "It is strictly an operational metric and not a clinical or psychological diagnosis."
    )

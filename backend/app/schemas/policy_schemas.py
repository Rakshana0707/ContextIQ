"""
Pydantic schemas and enums for Phase 7.6 Permission, Consent, and Policy Enforcement.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class PermissionScope(str, Enum):
    TASKS_READ = "tasks:read"
    TASKS_WRITE = "tasks:write"
    CALENDAR_READ = "calendar:read"
    CALENDAR_EVENTS_CREATE = "calendar:events:create"
    CALENDAR_EVENTS_MODIFY = "calendar:events:modify"
    NOTIFICATIONS_SEND = "notifications:send"
    TELEMETRY_DESKTOP_COLLECT = "telemetry:desktop:collect"
    LOCATION_READ = "location:read"
    AUTOMATION_SCHEDULE_RUN = "automation:schedule:run"
    WORKFLOWS_EXECUTE = "workflows:execute"


class ActionRiskTier(str, Enum):
    INFORMATIONAL = "INFORMATIONAL"                           # Tier 0: Read-only, no state mutation
    RECOMMENDATION_ONLY = "RECOMMENDATION_ONLY"               # Tier 0: Proposal/hint generated
    REVERSIBLE_INTERNAL_MODIFICATION = "REVERSIBLE_INTERNAL_MODIFICATION"  # Tier 1: Internal, fully reversible
    EXTERNAL_MODIFICATION = "EXTERNAL_MODIFICATION"           # Tier 2: Modifies external calendar/notifications
    CONSEQUENTIAL_EXTERNAL_ACTION = "CONSEQUENTIAL_EXTERNAL_ACTION"        # Tier 3: High impact, irreversible or shifts calendar


class ConsentStatusEnum(str, Enum):
    GRANTED = "GRANTED"
    REVOKED = "REVOKED"
    SUSPENDED = "SUSPENDED"
    EXPIRED = "EXPIRED"


class ConsentSource(str, Enum):
    USER_EXPLICIT = "USER_EXPLICIT"
    SYSTEM_DEFAULT = "SYSTEM_DEFAULT"
    OAUTH_DELEGATION = "OAUTH_DELEGATION"
    ADMIN_POLICY = "ADMIN_POLICY"


class PolicyConsentGrantRequest(BaseModel):
    scope: PermissionScope
    device_id: Optional[str] = None
    integration_id: Optional[str] = None
    consent_version: str = "1.0.0"
    source: ConsentSource = ConsentSource.USER_EXPLICIT
    policy_metadata: Optional[Dict[str, Any]] = None


class PolicyConsentRevokeRequest(BaseModel):
    scope: PermissionScope
    reason: Optional[str] = None


class PolicyConsentResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    scope: str
    consent_status: str
    consent_version: str
    granted_timestamp: datetime
    revoked_timestamp: Optional[datetime] = None
    source: str
    device_id: Optional[str] = None
    integration_id: Optional[str] = None
    revocation_reason: Optional[str] = None
    policy_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PolicyEvaluationRequest(BaseModel):
    action_identifier: str
    parameters: Optional[Dict[str, Any]] = None
    workflow_plan_id: Optional[uuid.UUID] = None
    step_key: Optional[str] = None


class PolicyEvaluationResult(BaseModel):
    allowed: bool
    risk_tier: ActionRiskTier
    requires_approval: bool
    denial_reason: Optional[str] = None
    scope_required: Optional[PermissionScope] = None
    details: Optional[Dict[str, Any]] = None


class PolicyAuditTrailResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    action_identifier: str
    scope_checked: Optional[str] = None
    decision: str
    risk_tier: str
    reason: Optional[str] = None
    context_snapshot: Optional[Dict[str, Any]] = None
    evaluated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserPolicyOverviewResponse(BaseModel):
    user_id: uuid.UUID
    permissions: List[PolicyConsentResponse]
    active_scopes: List[str]
    risk_tier_rules: Dict[str, Any]
    quiet_hours_active: bool

"""
Pydantic schemas and enums for Phase 7.7 Workflow Auditability, Rollback, and Emergency Stop.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class AuditEventType(str, Enum):
    WORKFLOW_PLAN_CREATED = "WORKFLOW_PLAN_CREATED"
    WORKFLOW_PLAN_APPROVED = "WORKFLOW_PLAN_APPROVED"
    WORKFLOW_PLAN_REJECTED = "WORKFLOW_PLAN_REJECTED"
    STEP_DISPATCHED = "STEP_DISPATCHED"
    STEP_COMPLETED = "STEP_COMPLETED"
    STEP_FAILED = "STEP_FAILED"
    STEP_SKIPPED = "STEP_SKIPPED"
    STEP_BLOCKED_BY_POLICY = "STEP_BLOCKED_BY_POLICY"
    STEP_COMPENSATED = "STEP_COMPENSATED"
    ROLLBACK_TRIGGERED = "ROLLBACK_TRIGGERED"
    ROLLBACK_COMPLETED = "ROLLBACK_COMPLETED"
    ROLLBACK_FAILED = "ROLLBACK_FAILED"
    EMERGENCY_STOP_TRIGGERED = "EMERGENCY_STOP_TRIGGERED"
    EMERGENCY_STOP_LIFTED = "EMERGENCY_STOP_LIFTED"
    CIRCUIT_BREAKER_TRIPPED = "CIRCUIT_BREAKER_TRIPPED"


class EmergencyStopScope(str, Enum):
    USER_LEVEL = "USER_LEVEL"
    ADMIN_GLOBAL = "ADMIN_GLOBAL"


class RollbackTriggerSource(str, Enum):
    USER_MANUAL = "USER_MANUAL"
    SYSTEM_FAILURE_AUTOROLLBACK = "SYSTEM_FAILURE_AUTOROLLBACK"
    EMERGENCY_STOP = "EMERGENCY_STOP"


class RollbackStatusEnum(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"


# Request / Response Schemas

class EmergencyStopRequest(BaseModel):
    reason: str
    scope: EmergencyStopScope = EmergencyStopScope.USER_LEVEL
    auto_cancel_pending: bool = True


class EmergencyStopLiftRequest(BaseModel):
    emergency_stop_id: uuid.UUID
    notes: Optional[str] = None


class EmergencyStopResponse(BaseModel):
    id: uuid.UUID
    scope: str
    user_id: Optional[uuid.UUID] = None
    triggered_by: str
    reason: str
    is_active: bool
    affected_plans_count: int
    affected_rules_count: int
    started_at: datetime
    lifted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class EmergencyStatusSummary(BaseModel):
    is_stopped: bool
    active_stops: List[EmergencyStopResponse]
    global_kill_switch_active: bool
    user_stop_active: bool


class RollbackRequest(BaseModel):
    reason: Optional[str] = "User requested manual rollback"
    force: bool = False


class RollbackRecordResponse(BaseModel):
    id: uuid.UUID
    plan_id: uuid.UUID
    user_id: uuid.UUID
    triggered_by: str
    status: str
    total_steps_to_compensate: int
    compensated_steps_count: int
    failed_compensations: Optional[List[Dict[str, Any]]] = None
    compensation_details: Optional[Dict[str, Any]] = None
    started_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class WorkflowAuditEventResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    plan_id: Optional[uuid.UUID] = None
    workflow_version: int
    event_type: str
    action_identifier: Optional[str] = None
    step_key: Optional[str] = None
    execution_timestamp: datetime
    policy_decision: Optional[str] = None
    approval_reference: Optional[str] = None
    result_status: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    correlation_id: Optional[str] = None
    sanitized_payload: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class SafetyOverviewResponse(BaseModel):
    active_plans_count: int
    awaiting_approval_count: int
    failed_plans_count: int
    reversible_plans_count: int
    emergency_stop_active: bool
    recent_audit_events: List[WorkflowAuditEventResponse]
    active_emergency_stops: List[EmergencyStopResponse]

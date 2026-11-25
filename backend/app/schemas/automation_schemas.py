"""
Pydantic schemas for User-Defined Automation Rules, Triggers, Conditions,
and Executions (ContextIQ Phase 7.2).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TriggerType(str, Enum):
    # Time-based triggers
    TIME_SCHEDULE = "TIME_SCHEDULE"
    TIME_INACTIVE = "TIME_INACTIVE"

    # Task-state triggers
    TASK_STATE_CHANGED = "TASK_STATE_CHANGED"
    TASK_CREATED = "TASK_CREATED"
    TASK_OVERDUE = "TASK_OVERDUE"

    # Forgetting-risk triggers
    FORGETTING_RISK_SPIKE = "FORGETTING_RISK_SPIKE"
    FORGETTING_THRESHOLD_EXCEEDED = "FORGETTING_THRESHOLD_EXCEEDED"

    # Recovery-state triggers
    RECOVERY_SESSION_ENDED = "RECOVERY_SESSION_ENDED"
    RECOVERY_HAZARD_HIGH = "RECOVERY_HAZARD_HIGH"

    # Calendar-event triggers
    CALENDAR_CONFLICT_DETECTED = "CALENDAR_CONFLICT_DETECTED"
    CALENDAR_EVENT_STARTING = "CALENDAR_EVENT_STARTING"
    SCHEDULE_BLOAT_DETECTED = "SCHEDULE_BLOAT_DETECTED"

    # Interruption-frequency triggers
    INTERRUPTION_BURST_DETECTED = "INTERRUPTION_BURST_DETECTED"
    THRASHING_DETECTED = "THRASHING_DETECTED"

    # Behavioral-friction triggers
    BFI_THRESHOLD_EXCEEDED = "BFI_THRESHOLD_EXCEEDED"
    COGNITIVE_FATIGUE_HIGH = "COGNITIVE_FATIGUE_HIGH"

    # User-defined manual triggers
    MANUAL_USER_TRIGGER = "MANUAL_USER_TRIGGER"


class ConditionOperator(str, Enum):
    EQUALS = "EQUALS"
    NOT_EQUALS = "NOT_EQUALS"
    GREATER_THAN = "GREATER_THAN"
    GREATER_THAN_OR_EQUAL = "GREATER_THAN_OR_EQUAL"
    LESS_THAN = "LESS_THAN"
    LESS_THAN_OR_EQUAL = "LESS_THAN_OR_EQUAL"
    BETWEEN = "BETWEEN"
    IS_TRUE = "IS_TRUE"
    IS_FALSE = "IS_FALSE"
    CONTAINS = "CONTAINS"
    IN_LIST = "IN_LIST"


class LogicalOperator(str, Enum):
    AND = "AND"
    OR = "OR"


class ExecutionStatus(str, Enum):
    EVALUATED_TRUE = "EVALUATED_TRUE"
    EVALUATED_FALSE = "EVALUATED_FALSE"
    SUPPRESSED_COOLDOWN = "SUPPRESSED_COOLDOWN"
    SUPPRESSED_QUIET_HOURS = "SUPPRESSED_QUIET_HOURS"
    SUPPRESSED_SCHEDULE = "SUPPRESSED_SCHEDULE"
    SUPPRESSED_MAX_DAILY = "SUPPRESSED_MAX_DAILY"
    SUPPRESSED_EXPIRED = "SUPPRESSED_EXPIRED"
    SUPPRESSED_DISABLED = "SUPPRESSED_DISABLED"
    SUPPRESSED_UNAUTHORIZED = "SUPPRESSED_UNAUTHORIZED"
    EXECUTED = "EXECUTED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    FAILED = "FAILED"


# ---------------------------------------------------------------------------
# Trigger Schemas
# ---------------------------------------------------------------------------
class AutomationTriggerCreate(BaseModel):
    trigger_type: TriggerType
    parameters: Dict[str, Any] = Field(default_factory=dict)
    is_authorized: bool = True
    authorization_source: Optional[str] = None


class AutomationTriggerResponse(BaseModel):
    id: uuid.UUID
    rule_id: uuid.UUID
    trigger_type: str
    parameters: Dict[str, Any]
    is_authorized: bool
    authorization_source: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Condition Schemas
# ---------------------------------------------------------------------------
class AutomationConditionCreate(BaseModel):
    condition_group: int = Field(default=0, ge=0, le=10)
    logical_operator: LogicalOperator = LogicalOperator.AND
    field_path: str = Field(min_length=2, max_length=128)
    operator: ConditionOperator
    expected_value: Any
    min_evidence_observations: int = Field(default=1, ge=1, le=1000)
    confidence_threshold: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("field_path")
    @classmethod
    def validate_field_path(cls, v: str) -> str:
        v = v.strip()
        # Security: protect against injection attempts
        if any(char in v for char in (";", "--", "/*", "*/", "exec", "eval", "__", "<script")):
            raise ValueError(f"Field path contains invalid characters or injection attempts: {v}")
        return v

    @model_validator(mode="after")
    def validate_operator_value_compatibility(self) -> AutomationConditionCreate:
        op = self.operator
        val = self.expected_value
        if op == ConditionOperator.BETWEEN:
            if not isinstance(val, (list, tuple)) or len(val) != 2:
                raise ValueError("Operator BETWEEN requires a 2-element list or tuple [min, max]")
            if val[0] > val[1]:
                raise ValueError(f"BETWEEN range min ({val[0]}) cannot exceed max ({val[1]})")
        elif op == ConditionOperator.IN_LIST:
            if not isinstance(val, list):
                raise ValueError("Operator IN_LIST requires a list of expected values")
        return self


class AutomationConditionResponse(BaseModel):
    id: uuid.UUID
    rule_id: uuid.UUID
    condition_group: int
    logical_operator: str
    field_path: str
    operator: str
    expected_value: Any
    min_evidence_observations: int
    confidence_threshold: float
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Action Definition Schemas
# ---------------------------------------------------------------------------
class AutomationActionCreate(BaseModel):
    action_order: int = Field(default=1, ge=1, le=20)
    action_identifier: str = Field(min_length=3, max_length=128)
    parameters_template: Dict[str, Any] = Field(default_factory=dict)
    is_critical: bool = True
    is_reversible: bool = True
    action_preview_template: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("action_identifier")
    @classmethod
    def validate_action_id(cls, v: str) -> str:
        v = v.strip()
        # Validate format namespace:action
        if ":" not in v:
            raise ValueError(f"Action identifier must be namespaced with ':' (e.g. 'calendar:insert_focus_block'), got: {v}")
        return v


class AutomationActionResponse(BaseModel):
    id: uuid.UUID
    rule_id: uuid.UUID
    action_order: int
    action_identifier: str
    parameters_template: Dict[str, Any]
    is_critical: bool
    is_reversible: bool
    action_preview_template: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Rule Schemas (Create / Update / Response)
# ---------------------------------------------------------------------------
class AutomationRuleCreate(BaseModel):
    name: str = Field(min_length=3, max_length=128)
    description: Optional[str] = None
    is_enabled: bool = True
    priority: int = Field(default=10, ge=1, le=100)
    cooldown_minutes: int = Field(default=30, ge=0, le=1440)
    max_executions_per_day: int = Field(default=5, ge=1, le=100)
    requires_approval: bool = True
    risk_tier: str = Field(default="Tier 2")
    active_schedule: Dict[str, Any] = Field(
        default_factory=lambda: {
            "days_of_week": [1, 2, 3, 4, 5],
            "start_time": "09:00",
            "end_time": "18:00",
            "timezone": "UTC",
        }
    )
    quiet_hours: Dict[str, Any] = Field(
        default_factory=lambda: {
            "enabled": True,
            "start_time": "22:00",
            "end_time": "07:00",
            "bypass_on_critical": False,
        }
    )
    expires_at: Optional[datetime] = None

    triggers: List[AutomationTriggerCreate] = Field(min_length=1)
    conditions: List[AutomationConditionCreate] = Field(default_factory=list)
    actions: List[AutomationActionCreate] = Field(min_length=1)


class AutomationRuleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=3, max_length=128)
    description: Optional[str] = None
    is_enabled: Optional[bool] = None
    priority: Optional[int] = Field(default=None, ge=1, le=100)
    cooldown_minutes: Optional[int] = Field(default=None, ge=0, le=1440)
    max_executions_per_day: Optional[int] = Field(default=None, ge=1, le=100)
    requires_approval: Optional[bool] = None
    risk_tier: Optional[str] = None
    active_schedule: Optional[Dict[str, Any]] = None
    quiet_hours: Optional[Dict[str, Any]] = None
    expires_at: Optional[datetime] = None
    change_summary: Optional[str] = None

    triggers: Optional[List[AutomationTriggerCreate]] = None
    conditions: Optional[List[AutomationConditionCreate]] = None
    actions: Optional[List[AutomationActionCreate]] = None


class AutomationRuleResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: Optional[str]
    is_enabled: bool
    version: int
    priority: int
    cooldown_minutes: int
    max_executions_per_day: int
    requires_approval: bool
    risk_tier: str
    active_schedule: Dict[str, Any]
    quiet_hours: Dict[str, Any]
    expires_at: Optional[datetime]
    last_triggered_at: Optional[datetime]
    execution_count_today: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AutomationRuleDetailResponse(AutomationRuleResponse):
    triggers: List[AutomationTriggerResponse] = Field(default_factory=list)
    conditions: List[AutomationConditionResponse] = Field(default_factory=list)
    actions: List[AutomationActionResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Execution & Version Schemas
# ---------------------------------------------------------------------------
class AutomationExecutionResponse(BaseModel):
    id: uuid.UUID
    rule_id: uuid.UUID
    user_id: uuid.UUID
    trigger_event_id: str
    trigger_type: str
    status: str
    matched_conditions: Dict[str, Any]
    suppression_reason: Optional[str]
    workflow_instance_id: Optional[uuid.UUID]
    idempotency_key: str
    execution_duration_ms: float
    executed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AutomationRuleVersionResponse(BaseModel):
    id: uuid.UUID
    rule_id: uuid.UUID
    version_number: int
    rule_snapshot: Dict[str, Any]
    change_summary: Optional[str]
    changed_by: Optional[uuid.UUID]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Evaluation & Dry-Run Schemas
# ---------------------------------------------------------------------------
class TriggerEvaluationRequest(BaseModel):
    trigger_type: TriggerType
    trigger_event_id: Optional[str] = None
    context_payload: Dict[str, Any] = Field(default_factory=dict)


class TriggerEvaluationResultItem(BaseModel):
    rule_id: uuid.UUID
    rule_name: str
    is_matched: bool
    status: ExecutionStatus
    matched_conditions: Dict[str, Any] = Field(default_factory=dict)
    suppression_reason: Optional[str] = None
    proposed_actions: List[Dict[str, Any]] = Field(default_factory=list)
    workflow_id: Optional[uuid.UUID] = None


class TriggerEvaluationResponse(BaseModel):
    trigger_type: str
    trigger_event_id: str
    evaluated_rules_count: int
    matched_rules_count: int
    results: List[TriggerEvaluationResultItem]

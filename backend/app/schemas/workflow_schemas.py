"""
Pydantic Schemas for Multi-Step Workflow Planning, Orchestration,
Action Contracts, and LLM Draft Proposals (ContextIQ Phase 7.4).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class WorkflowLifecycleState(str, Enum):
    CREATED = "CREATED"
    DRAFT = "DRAFT"
    VALIDATING = "VALIDATING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    SCHEDULED = "SCHEDULED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    ROLLED_BACK = "ROLLED_BACK"


class WorkflowCategory(str, Enum):
    TASK_MANAGEMENT = "TASK_MANAGEMENT"
    CALENDAR = "CALENDAR"
    REMINDER = "REMINDER"
    FOCUS_SESSION = "FOCUS_SESSION"
    RECOVERY_BUFFER = "RECOVERY_BUFFER"
    BEHAVIORAL_INTERVENTION = "BEHAVIORAL_INTERVENTION"
    CROSS_DEVICE = "CROSS_DEVICE"


class DependencyType(str, Enum):
    COMPLETION = "COMPLETION"   # Target executes after source completes (regardless of success)
    SUCCESS = "SUCCESS"         # Target executes only if source succeeds
    FAILURE = "FAILURE"         # Target executes only if source fails (failure branch)
    CONDITIONAL = "CONDITIONAL" # Target executes if condition payload evaluates to True


class ActionContractSchema(BaseModel):
    """Specification of an immutable, registered action contract."""
    identifier: str = Field(..., description="Globally unique namespaced identifier, e.g. 'calendar:insert_focus_block'")
    category: WorkflowCategory
    description: str
    required_permissions: List[str] = Field(default_factory=list)
    risk_tier: str = Field(default="Tier 1", description="Tier 0 (Zero-risk), Tier 1 (Low), Tier 2 (Consequential), Tier 3 (External/Critical)")
    is_reversible: bool = True
    compensating_action_identifier: Optional[str] = None
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    expected_output_schema: Dict[str, Any] = Field(default_factory=dict)
    side_effects_description: str = ""


# --- Step & Dependency Schemas ---

class WorkflowStepSchema(BaseModel):
    step_key: str = Field(..., description="Unique alphanumeric identifier within workflow, e.g. 'step_1_review'")
    name: str = Field(..., description="Human-readable step name")
    action_identifier: str = Field(..., description="Registered action contract identifier")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    order_index: int = Field(default=0, ge=0)
    is_optional: bool = Field(default=False)
    requires_approval: bool = Field(default=True)
    timeout_seconds: int = Field(default=300, ge=5, le=3600)
    condition_expression: Optional[Dict[str, Any]] = None
    compensation_action_identifier: Optional[str] = None
    compensation_parameters: Optional[Dict[str, Any]] = None
    estimated_duration_minutes: Optional[int] = Field(default=10, ge=1, le=480)


class WorkflowDependencySchema(BaseModel):
    source_step_key: str = Field(..., description="Preceding step key")
    target_step_key: str = Field(..., description="Dependent step key")
    dependency_type: DependencyType = Field(default=DependencyType.SUCCESS)
    condition_payload: Optional[Dict[str, Any]] = None


# --- Workflow Definition Schemas ---

class WorkflowDefinitionCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=128)
    description: Optional[str] = None
    workflow_category: WorkflowCategory = Field(default=WorkflowCategory.TASK_MANAGEMENT)
    trigger_type: Optional[str] = None
    is_active: bool = True
    steps: List[WorkflowStepSchema] = Field(default_factory=list)
    dependencies: List[WorkflowDependencySchema] = Field(default_factory=list)


class WorkflowDefinitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: Optional[str] = None
    workflow_category: str
    trigger_type: Optional[str] = None
    is_active: bool
    version: int
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    dependencies: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# --- Workflow Execution Plan Schemas ---

class WorkflowExecutionPlanCreate(BaseModel):
    workflow_definition_id: Optional[uuid.UUID] = None
    title: str = Field(..., min_length=3, max_length=255)
    trigger_context: Dict[str, Any] = Field(default_factory=dict)
    steps: List[WorkflowStepSchema]
    dependencies: List[WorkflowDependencySchema] = Field(default_factory=list)
    rationale: str = Field(..., min_length=5)
    expected_benefits: Dict[str, Any] = Field(default_factory=dict)
    potential_side_effects: Dict[str, Any] = Field(default_factory=dict)
    utility_score: Optional[float] = Field(default=0.85, ge=0.0, le=1.0)
    idempotency_key: Optional[str] = None


class PlanComparisonCandidate(BaseModel):
    plan_name: str
    strategy: str  # e.g., "AGGRESSIVE_FOCUS", "BALANCED_BUFFERED", "MINIMAL_INTRUSION"
    utility_score: float
    task_benefit_score: float
    schedule_feasibility_score: float
    recovery_impact_score: float
    notification_burden_score: float
    prediction_uncertainty_penalty: float
    trade_off_summary: str
    steps_count: int


class WorkflowExecutionPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_definition_id: Optional[uuid.UUID] = None
    user_id: uuid.UUID
    title: str
    status: str
    version: int
    idempotency_key: str
    trigger_context: Dict[str, Any] = Field(default_factory=dict)
    plan_steps: List[Dict[str, Any]] = Field(default_factory=list)
    plan_dependencies: List[Dict[str, Any]] = Field(default_factory=list)
    rationale: str
    expected_benefits: Dict[str, Any] = Field(default_factory=dict)
    potential_side_effects: Dict[str, Any] = Field(default_factory=dict)
    utility_score: float
    plan_comparison_metadata: Optional[Dict[str, Any]] = None
    reversibility_summary: Dict[str, Any] = Field(default_factory=dict)
    approved_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class PlanTransitionRequest(BaseModel):
    target_state: WorkflowLifecycleState
    reason: Optional[str] = Field(default=None, max_length=255)


# --- LLM Structured Output & Drafting ---

class LLMWorkflowStepDraft(BaseModel):
    step_key: str = Field(..., description="Unique identifier for step, e.g. 'step_1'")
    name: str = Field(..., description="Short imperative title, e.g. 'Schedule Recovery Buffer'")
    action_identifier: str = Field(..., description="Must exactly match an action from the registered catalog")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    order_index: int = Field(default=0)
    is_optional: bool = Field(default=False)
    requires_approval: bool = Field(default=True)
    estimated_duration_minutes: int = Field(default=15, ge=1, le=240)


class LLMWorkflowDependencyDraft(BaseModel):
    source_step_key: str
    target_step_key: str
    dependency_type: str = Field(default="SUCCESS")


class LLMWorkflowProposal(BaseModel):
    """
    Strict schema required for all LLM-drafted workflow proposals.
    Must be validated deterministically before conversion into an Execution Plan.
    """
    title: str = Field(..., min_length=5, max_length=255)
    rationale: str = Field(..., description="Explanation of why this workflow is proposed based on context")
    target_objective: str = Field(..., description="Core productivity or recovery goal")
    steps: List[LLMWorkflowStepDraft] = Field(..., min_length=1)
    dependencies: List[LLMWorkflowDependencyDraft] = Field(default_factory=list)
    expected_benefits: Dict[str, Any] = Field(default_factory=dict)
    potential_side_effects: Dict[str, Any] = Field(default_factory=dict)
    trade_off_analysis: str = Field(..., description="Honest assessment of friction or schedule trade-offs")


class IntelligentPlanningRequest(BaseModel):
    """Input payload to trigger multi-step workflow planning from behavioral signals."""
    user_id: Optional[uuid.UUID] = None
    task_id: Optional[uuid.UUID] = None
    trigger_type: str = Field(..., description="Trigger name, e.g. 'CALENDAR_CONFLICT', 'FORGETTING_RISK_SPIKE'")
    behavioral_context: Dict[str, Any] = Field(default_factory=dict)
    desired_strategy: Optional[str] = Field(default="BALANCED", description="'AGGRESSIVE', 'BALANCED', 'CONSERVATIVE'")
    generate_alternatives: bool = Field(default=True)

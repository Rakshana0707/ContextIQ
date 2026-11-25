"""
Pydantic v2 schemas for Behavioral Digital Twin Simulation and Proposed Workflow Orchestration (ContextIQ Phase 6.9).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field


class ScenarioType(str, Enum):
    MOVE_TASK_TIME = "MOVE_TASK_TIME"                      # Move task to morning / peak focus slot
    ADD_RECOVERY_BUFFER = "ADD_RECOVERY_BUFFER"            # Insert 10-15m buffer following interruption or task
    REDUCE_NOTIFICATIONS = "REDUCE_NOTIFICATIONS"          # Throttle or silence notifications
    SCHEDULE_FOCUS_SESSION = "SCHEDULE_FOCUS_SESSION"      # Dedicated protected 45-90m block
    DECOMPOSE_TASK = "DECOMPOSE_TASK"                      # Break complex task into micro-steps
    CUSTOM_SCENARIO = "CUSTOM_SCENARIO"                    # Compound multi-action hypothesis


class SimulationActionType(str, Enum):
    RESCHEDULE_TASK = "RESCHEDULE_TASK"
    CREATE_FOCUS_SESSION = "CREATE_FOCUS_SESSION"
    INSERT_RECOVERY_BUFFER = "INSERT_RECOVERY_BUFFER"
    CONFIGURE_REMINDER = "CONFIGURE_REMINDER"
    UPDATE_TASK_PRIORITY = "UPDATE_TASK_PRIORITY"


class WorkflowStatus(str, Enum):
    PROPOSED = "PROPOSED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    REVERTED = "REVERTED"


class SimulationOutputMetrics(BaseModel):
    """Estimated performance metrics for a specific plan. Clearly marked as simulated."""
    task_completion_probability: float = Field(..., ge=0.0, le=1.0, description="Estimated P(Completion on time)")
    recovery_duration_minutes: float = Field(..., ge=0.0, description="Estimated cognitive recovery time in minutes")
    behavioral_friction_index: float = Field(..., ge=0.0, le=100.0, description="Estimated Behavioral Friction Index BFI")
    schedule_feasibility: float = Field(..., ge=0.0, le=1.0, description="Calendar buffer & conflict-free feasibility")
    notification_burden: float = Field(..., ge=0.0, le=1.0, description="Estimated alert disruption & notification cost")
    uncertainty_interval: Tuple[float, float] = Field(..., description="90% Conformal uncertainty interval [lower, upper]")
    uncertainty_width: float = Field(..., description="Width of uncertainty interval")
    is_simulated: bool = Field(default=True, description="Invariant: simulated estimates are never presented as observed reality")


class CounterfactualDelta(BaseModel):
    """Incremental counterfactual lift over current baseline plan (Proposed - Baseline)."""
    delta_completion_pct: float = Field(..., description="Percentage point delta in completion likelihood")
    delta_recovery_minutes: float = Field(..., description="Minutes saved in recovery (negative = faster recovery)")
    delta_friction_points: float = Field(..., description="BFI points changed (negative = lower friction)")
    delta_notification_burden: float = Field(..., description="Delta in notification burden")
    delta_feasibility: float = Field(..., description="Delta in calendar feasibility")


class ScenarioSimulationRequest(BaseModel):
    user_id: Optional[uuid.UUID] = Field(None, description="User UUID")
    task_id: Optional[uuid.UUID] = Field(None, description="Target task UUID if applicable")
    scenario_type: ScenarioType = Field(default=ScenarioType.ADD_RECOVERY_BUFFER, description="Scenario hypothesis")
    scenario_name: Optional[str] = Field(None, description="Optional custom scenario name")
    input_parameters: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Custom parameters (e.g. shift_to_morning: true, buffer_duration: 15)"
    )


class ScenarioSimulationResult(BaseModel):
    """Single simulation scenario execution result."""
    scenario_id: Optional[uuid.UUID] = Field(None, description="Saved scenario UUID if persisted")
    scenario_name: str = Field(..., description="Name of scenario")
    scenario_type: ScenarioType = Field(..., description="Type of scenario")
    evaluated_at: datetime = Field(..., description="Simulation timestamp")
    baseline_plan: SimulationOutputMetrics = Field(..., description="Current observed / baseline plan metrics")
    simulated_plan: SimulationOutputMetrics = Field(..., description="Simulated scenario projection")
    counterfactual_deltas: CounterfactualDelta = Field(..., description="Incremental changes relative to baseline")
    assumptions: List[str] = Field(..., description="Underlying behavioral assumptions of the digital twin")
    model_version: str = Field(default="2.3.0-digital-twin", description="Model version used")
    feature_schema_version: str = Field(default="v2.3", description="Feature schema version")
    is_synthetic_estimate: bool = Field(default=True, description="Visual badge flag")
    disclaimer: str = Field(
        default="The digital twin is a model-based approximation of observed behavior. It is not a guarantee of future outcomes.",
        description="Scientific caveat",
    )


class ScenarioCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = Field(None, max_length=500)
    scenario_type: ScenarioType
    input_parameters: Dict[str, Any] = Field(default_factory=dict)
    task_id: Optional[uuid.UUID] = None


class ScenarioUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None


class ScenarioResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: Optional[str] = None
    scenario_type: ScenarioType
    input_parameters: Dict[str, Any]
    simulation_results: Dict[str, Any]
    assumptions: List[str]
    model_version: str
    feature_schema_version: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ScenarioCompareRequest(BaseModel):
    scenario_ids: List[uuid.UUID] = Field(..., min_length=2, max_length=5, description="List of scenario IDs to compare")


class ScenarioCompareResponse(BaseModel):
    user_id: uuid.UUID
    compared_at: datetime
    baseline_plan: SimulationOutputMetrics
    scenarios: List[ScenarioResponse]
    relative_rankings: List[Dict[str, Any]]
    trade_off_matrix: Dict[str, Dict[str, float]]
    disclaimer: str = "Simulated comparisons reflect conditional model predictions. Actual results depend on dynamic external context."


# ---------------------------------------------------------------------------
# Proposed Workflow Orchestration Schemas
# ---------------------------------------------------------------------------

class WorkflowActionItem(BaseModel):
    action_type: SimulationActionType = Field(..., description="Type of external action")
    target_id: Optional[str] = Field(None, description="Associated task, calendar, or window UUID")
    title: str = Field(..., description="Action title preview")
    description: str = Field(..., description="Step preview before execution")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Execution parameters")
    is_reversible: bool = Field(default=True, description="Whether action can be undone")
    execution_status: str = Field(default="PENDING", description="PENDING, COMPLETED, FAILED, or REVERTED")


class ProposedWorkflowResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    scenario_id: Optional[uuid.UUID] = None
    status: WorkflowStatus
    idempotency_key: str
    actions: List[WorkflowActionItem]
    permission_audit: Dict[str, Any]
    is_reversible: bool
    created_at: datetime
    approved_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    requires_explicit_approval: bool = True
    disclaimer: str = "Workflow contains proposed external actions. Explicit user authorization is required before any execution."


class WorkflowApprovalRequest(BaseModel):
    approved: bool = Field(..., description="True to approve, False to reject")
    rejection_reason: Optional[str] = None


class WorkflowExecutionResponse(BaseModel):
    workflow_id: uuid.UUID
    status: WorkflowStatus
    executed_actions_count: int
    execution_audit: List[Dict[str, Any]]
    executed_at: datetime
    is_reversible: bool
    message: str


class WorkflowRollbackResponse(BaseModel):
    workflow_id: uuid.UUID
    status: WorkflowStatus
    reverted_actions_count: int
    rollback_audit: List[Dict[str, Any]]
    reverted_at: datetime
    message: str

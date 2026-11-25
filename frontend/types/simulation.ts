/**
 * Behavioral Digital Twin Simulation and Proposed Workflow Types (ContextIQ Phase 6.9).
 */

export type ScenarioType =
  | "MOVE_TASK_TIME"
  | "ADD_RECOVERY_BUFFER"
  | "REDUCE_NOTIFICATIONS"
  | "SCHEDULE_FOCUS_SESSION"
  | "DECOMPOSE_TASK"
  | "CUSTOM_SCENARIO";

export type SimulationActionType =
  | "RESCHEDULE_TASK"
  | "CREATE_FOCUS_SESSION"
  | "INSERT_RECOVERY_BUFFER"
  | "CONFIGURE_REMINDER"
  | "UPDATE_TASK_PRIORITY";

export type WorkflowStatus =
  | "PROPOSED"
  | "PENDING_APPROVAL"
  | "APPROVED"
  | "EXECUTING"
  | "COMPLETED"
  | "CANCELLED"
  | "REVERTED";

export interface SimulationOutputMetrics {
  completion_probability: number;
  expected_recovery_duration_minutes: number;
  behavioral_friction_index: number;
  notification_burden_score: number;
  calendar_feasibility: number;
  recovery_duration_interval_lower: number;
  recovery_duration_interval_upper: number;
  completion_probability_interval_lower: number;
  completion_probability_interval_upper: number;
}

export interface CounterfactualDelta {
  completion_probability_delta: number;
  recovery_duration_delta_minutes: number;
  friction_delta: number;
  notification_burden_delta: number;
  summary: string;
}

export interface ScenarioSimulationResult {
  scenario_type: ScenarioType;
  hypothesis_description: string;
  baseline_metrics: SimulationOutputMetrics;
  simulated_metrics: SimulationOutputMetrics;
  counterfactual_delta: CounterfactualDelta;
  assumptions: string[];
  uncertainty_interval_coverage: number;
  model_version: string;
  feature_version: string;
  timestamp: string;
}

export interface SavedScenario {
  id: string;
  user_id: string;
  title: string;
  scenario_type: ScenarioType;
  hypothesis: string;
  input_parameters: Record<string, any>;
  baseline_metrics: SimulationOutputMetrics;
  simulated_metrics: SimulationOutputMetrics;
  counterfactual_delta: CounterfactualDelta;
  assumptions: string[];
  is_active_plan: boolean;
  model_version: string;
  feature_version: string;
  created_at: string;
  updated_at: string;
}

export interface ScenarioComparisonItem {
  scenario_id?: string | null;
  scenario_type: ScenarioType;
  title: string;
  completion_probability: number;
  completion_probability_delta: number;
  expected_recovery_minutes: number;
  recovery_minutes_delta: number;
  behavioral_friction: number;
  friction_delta: number;
  notification_burden: number;
  calendar_feasibility: number;
  is_active_plan: boolean;
}

export interface ScenarioCompareResponse {
  scenarios: ScenarioComparisonItem[];
  recommended_scenario_type?: ScenarioType | null;
  recommendation_rationale: string;
  compared_at: string;
}

export interface WorkflowActionItem {
  action_id: string;
  action_type: SimulationActionType;
  sequence_order: number;
  description: string;
  target_resource: string;
  parameters: Record<string, any>;
  estimated_duration_minutes: number;
  is_reversible: boolean;
  required_permissions: string[];
}

export interface ProposedWorkflow {
  id: string;
  scenario_id: string;
  user_id: string;
  title: string;
  status: WorkflowStatus;
  total_actions: number;
  actions: WorkflowActionItem[];
  estimated_total_duration_minutes: number;
  required_permissions: string[];
  is_reversible: boolean;
  idempotency_key: string;
  audit_trail: Array<Record<string, any>>;
  created_at: string;
  updated_at: string;
}

export interface WorkflowExecutionResponse {
  workflow_id: string;
  status: WorkflowStatus;
  executed_actions_count: number;
  execution_details: Array<Record<string, any>>;
  is_reverted: boolean;
  executed_at: string;
  revert_payload_available: boolean;
}

export interface WorkflowRollbackResponse {
  workflow_id: string;
  status: WorkflowStatus;
  reverted_actions_count: number;
  details: string;
  reverted_at: string;
}

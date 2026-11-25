/**
 * Types for Multi-Step Workflow Planning, Governed Orchestration,
 * and Execution Engine (Phase 7.4 & 7.5).
 */

export type WorkflowLifecycleState =
  | "CREATED"
  | "DRAFT"
  | "VALIDATING"
  | "AWAITING_APPROVAL"
  | "APPROVED"
  | "SCHEDULED"
  | "EXECUTING"
  | "COMPLETED"
  | "PARTIALLY_COMPLETED"
  | "FAILED"
  | "CANCELLED"
  | "EXPIRED"
  | "ROLLED_BACK";

export interface WorkflowStep {
  step_key: string;
  name: string;
  action_identifier: string;
  parameters: Record<string, any>;
  order_index: number;
  is_optional: boolean;
  requires_approval: boolean;
  timeout_seconds?: number;
  estimated_duration_minutes?: number;
  condition_expression?: Record<string, any>;
  compensation_action_identifier?: string;
}

export interface WorkflowDependency {
  source_step_key: string;
  target_step_key: string;
  dependency_type: "COMPLETION" | "SUCCESS" | "FAILURE" | "CONDITIONAL";
  condition_payload?: Record<string, any>;
}

export interface PlanComparisonCandidate {
  plan_name: string;
  strategy: string;
  utility_score: number;
  task_benefit_score: number;
  schedule_feasibility_score: number;
  recovery_impact_score: number;
  notification_burden_score: number;
  prediction_uncertainty_penalty: number;
  trade_off_summary: string;
  steps_count: number;
}

export interface WorkflowExecutionPlan {
  id: string;
  workflow_definition_id?: string;
  user_id: string;
  title: string;
  status: WorkflowLifecycleState;
  version: number;
  idempotency_key: string;
  trigger_context: Record<string, any>;
  plan_steps: WorkflowStep[];
  plan_dependencies: WorkflowDependency[];
  rationale: string;
  expected_benefits: Record<string, any>;
  potential_side_effects: Record<string, any>;
  utility_score: number;
  plan_comparison_metadata?: {
    scoring?: Record<string, any>;
    alternatives?: PlanComparisonCandidate[];
    llm_trade_off_analysis?: string;
  };
  reversibility_summary: {
    is_fully_reversible?: boolean;
    compensating_steps_count?: number;
    rollback_guarantee?: string;
  };
  approved_at?: string;
  executed_at?: string;
  expires_at?: string;
  created_at: string;
  updated_at: string;
}

export interface WorkflowStepExecution {
  id: string;
  plan_id: string;
  step_key: string;
  action_identifier: string;
  status: "PENDING" | "EXECUTING" | "COMPLETED" | "FAILED" | "SKIPPED" | "CANCELLED" | "COMPENSATED";
  attempt_count: number;
  max_attempts: number;
  idempotency_key: string;
  input_payload: Record<string, any>;
  output_payload?: Record<string, any>;
  error_message?: string;
  started_at?: string;
  completed_at?: string;
  compensation_status: string;
}

export interface WorkflowExecutionProgress {
  plan_id: string;
  title: string;
  status: WorkflowLifecycleState;
  version: number;
  total_steps: number;
  completed_steps: number;
  failed_steps: number;
  skipped_steps: number;
  progress_percentage: number;
  step_executions: WorkflowStepExecution[];
  executed_at?: string;
  is_reversible: boolean;
}

export interface ActionContract {
  identifier: string;
  category: string;
  description: string;
  required_permissions: string[];
  risk_tier: string;
  is_reversible: boolean;
  compensating_action_identifier?: string;
  input_schema: Record<string, any>;
  expected_output_schema: Record<string, any>;
  side_effects_description: string;
}

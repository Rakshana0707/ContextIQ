export type AuditEventType =
  | "WORKFLOW_PLAN_CREATED"
  | "WORKFLOW_PLAN_APPROVED"
  | "WORKFLOW_PLAN_REJECTED"
  | "STEP_DISPATCHED"
  | "STEP_COMPLETED"
  | "STEP_FAILED"
  | "STEP_SKIPPED"
  | "STEP_BLOCKED_BY_POLICY"
  | "STEP_COMPENSATED"
  | "ROLLBACK_TRIGGERED"
  | "ROLLBACK_COMPLETED"
  | "ROLLBACK_FAILED"
  | "EMERGENCY_STOP_TRIGGERED"
  | "EMERGENCY_STOP_LIFTED"
  | "CIRCUIT_BREAKER_TRIPPED";

export type EmergencyStopScope = "USER_LEVEL" | "ADMIN_GLOBAL";

export interface EmergencyStopEvent {
  id: string;
  scope: EmergencyStopScope | string;
  user_id?: string | null;
  triggered_by: string;
  reason: string;
  is_active: boolean;
  affected_plans_count: number;
  affected_rules_count: number;
  started_at: string;
  lifted_at?: string | null;
}

export interface EmergencyStatusSummary {
  is_stopped: boolean;
  active_stops: EmergencyStopEvent[];
  global_kill_switch_active: boolean;
  user_stop_active: boolean;
}

export interface WorkflowAuditEvent {
  id: string;
  user_id: string;
  plan_id?: string | null;
  workflow_version: number;
  event_type: AuditEventType | string;
  action_identifier?: string | null;
  step_key?: string | null;
  execution_timestamp: string;
  policy_decision?: string | null;
  approval_reference?: string | null;
  result_status?: string | null;
  error_details?: Record<string, any> | null;
  correlation_id?: string | null;
  sanitized_payload?: Record<string, any> | null;
}

export interface WorkflowRollbackRecord {
  id: string;
  plan_id: string;
  user_id: string;
  triggered_by: string;
  status: "IN_PROGRESS" | "COMPLETED" | "PARTIALLY_COMPLETED" | "FAILED" | string;
  total_steps_to_compensate: number;
  compensated_steps_count: number;
  failed_compensations?: Array<Record<string, any>> | null;
  compensation_details?: Record<string, any> | null;
  started_at: string;
  completed_at?: string | null;
}

export interface SafetyOverview {
  active_plans_count: number;
  awaiting_approval_count: number;
  failed_plans_count: number;
  reversible_plans_count: number;
  emergency_stop_active: boolean;
  recent_audit_events: WorkflowAuditEvent[];
  active_emergency_stops: EmergencyStopEvent[];
}

export interface ReversibilityCheckResult {
  plan_id: string;
  is_reversible: boolean;
  summary: string;
  step_details: Array<{
    step_key: string;
    action_identifier: string;
    is_reversible: boolean;
    has_receipt: boolean;
    compensation_status: string;
  }>;
}

/**
 * Automation Rules, Triggers, Conditions, and Execution Types (ContextIQ Phase 7.2).
 */

export type TriggerType =
  | "TIME_SCHEDULE"
  | "TIME_INACTIVE"
  | "TASK_STATE_CHANGED"
  | "TASK_CREATED"
  | "TASK_OVERDUE"
  | "FORGETTING_RISK_SPIKE"
  | "FORGETTING_THRESHOLD_EXCEEDED"
  | "RECOVERY_SESSION_ENDED"
  | "RECOVERY_HAZARD_HIGH"
  | "CALENDAR_CONFLICT_DETECTED"
  | "CALENDAR_EVENT_STARTING"
  | "SCHEDULE_BLOAT_DETECTED"
  | "INTERRUPTION_BURST_DETECTED"
  | "THRASHING_DETECTED"
  | "BFI_THRESHOLD_EXCEEDED"
  | "COGNITIVE_FATIGUE_HIGH"
  | "MANUAL_USER_TRIGGER";

export type ConditionOperator =
  | "EQUALS"
  | "NOT_EQUALS"
  | "GREATER_THAN"
  | "GREATER_THAN_OR_EQUAL"
  | "LESS_THAN"
  | "LESS_THAN_OR_EQUAL"
  | "BETWEEN"
  | "IS_TRUE"
  | "IS_FALSE"
  | "CONTAINS"
  | "IN_LIST";

export type LogicalOperator = "AND" | "OR";

export type ExecutionStatus =
  | "EVALUATED_TRUE"
  | "EVALUATED_FALSE"
  | "SUPPRESSED_COOLDOWN"
  | "SUPPRESSED_QUIET_HOURS"
  | "SUPPRESSED_SCHEDULE"
  | "SUPPRESSED_MAX_DAILY"
  | "SUPPRESSED_EXPIRED"
  | "SUPPRESSED_DISABLED"
  | "SUPPRESSED_UNAUTHORIZED"
  | "EXECUTED"
  | "PENDING_APPROVAL"
  | "FAILED";

export interface AutomationTrigger {
  id: string;
  rule_id: string;
  trigger_type: TriggerType;
  parameters: Record<string, any>;
  is_authorized: boolean;
  authorization_source?: string;
  created_at: string;
  updated_at: string;
}

export interface AutomationCondition {
  id: string;
  rule_id: string;
  condition_group: number;
  logical_operator: LogicalOperator;
  field_path: string;
  operator: ConditionOperator;
  expected_value: any;
  min_evidence_observations: number;
  confidence_threshold: number;
  created_at: string;
  updated_at: string;
}

export interface AutomationActionDefinition {
  id: string;
  rule_id: string;
  action_order: number;
  action_identifier: string;
  parameters_template: Record<string, any>;
  is_critical: boolean;
  is_reversible: boolean;
  action_preview_template: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface AutomationRule {
  id: string;
  user_id: string;
  name: string;
  description?: string;
  is_enabled: boolean;
  version: number;
  priority: number;
  cooldown_minutes: number;
  max_executions_per_day: number;
  requires_approval: boolean;
  risk_tier: string;
  active_schedule: {
    days_of_week: number[];
    start_time: string;
    end_time: string;
    timezone: string;
  };
  quiet_hours: {
    enabled: boolean;
    start_time: string;
    end_time: string;
    bypass_on_critical: boolean;
  };
  expires_at?: string;
  last_triggered_at?: string;
  execution_count_today: number;
  created_at: string;
  updated_at: string;
  triggers?: AutomationTrigger[];
  conditions?: AutomationCondition[];
  actions?: AutomationActionDefinition[];
}

export interface AutomationExecution {
  id: string;
  rule_id: string;
  user_id: string;
  trigger_event_id: string;
  trigger_type: string;
  status: ExecutionStatus;
  matched_conditions: Record<string, any>;
  suppression_reason?: string;
  workflow_instance_id?: string;
  idempotency_key: string;
  execution_duration_ms: number;
  executed_at: string;
}

export interface AutomationRuleVersion {
  id: string;
  rule_id: string;
  version_number: number;
  rule_snapshot: Record<string, any>;
  change_summary?: string;
  created_at: string;
}

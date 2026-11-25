/**
 * Multi-Objective Intervention Optimization Types (ContextIQ Phase 6.7).
 */

export type CandidateIntervention =
  | "no_intervention"
  | "immediate_reminder"
  | "delayed_reminder"
  | "calendar_rescheduling"
  | "short_recovery_buffer"
  | "focus_session_recommendation"
  | "break_large_task";

export type OptimizationObjective =
  | "task_completion"
  | "task_resumption"
  | "recovery_duration"
  | "behavioral_friction"
  | "notification_economy"
  | "interruption_comfort"
  | "user_preferences"
  | "schedule_feasibility";

export type HardConstraintType =
  | "quiet_hours"
  | "max_notification_freq"
  | "calendar_availability"
  | "working_hours"
  | "task_constraints"
  | "consent_permissions"
  | "user_opt_out";

export interface ObjectiveVectorData {
  task_completion: number;
  task_resumption: number;
  recovery_duration: number;
  behavioral_friction: number;
  notification_economy: number;
  interruption_comfort: number;
  user_preferences: number;
  schedule_feasibility: number;
}

export interface ObjectiveWeightsData {
  task_completion: number;
  task_resumption: number;
  recovery_duration: number;
  behavioral_friction: number;
  notification_economy: number;
  interruption_comfort: number;
  user_preferences: number;
  schedule_feasibility: number;
}

export interface OptimizationConstraintStatusData {
  constraint_type: HardConstraintType;
  passed: boolean;
  reason?: string | null;
}

export interface EvaluatedCandidateData {
  candidate: CandidateIntervention;
  title: string;
  is_feasible: boolean;
  constraint_violations: string[];
  objectives: ObjectiveVectorData;
  weighted_utility: number;
  net_utility_lift: number;
  is_pareto_optimal: boolean;
  pareto_rank: number;
  dominates: CandidateIntervention[];
  dominated_by: CandidateIntervention[];
  improved_objectives: string[];
  worsened_objectives: string[];
  confidence_score: number;
  uncertainty_width: number;
}

export interface MultiObjectiveOptimizationResponseData {
  optimization_id: string;
  user_id: string;
  evaluated_at: string;
  selected_intervention: CandidateIntervention;
  is_no_action: boolean;
  selection_rationale: string;
  effective_weights: ObjectiveWeightsData;
  context_adaptations: string[];
  pareto_frontier: EvaluatedCandidateData[];
  all_evaluated_candidates: EvaluatedCandidateData[];
  applied_constraints: OptimizationConstraintStatusData[];
  improved_objectives: string[];
  worsened_objectives: string[];
  requires_authorization: boolean;
  disclaimer: string;
}

export interface UserOptimizationPreferencesData {
  user_id: string;
  preferred_weights: ObjectiveWeightsData;
  opted_out_interventions: CandidateIntervention[];
  max_daily_interventions: number;
  max_hourly_interventions: number;
  cooldown_minutes_between_interventions: number;
  updated_at: string;
}

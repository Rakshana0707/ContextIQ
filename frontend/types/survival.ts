/**
 * Personalized Survival and Dynamic Risk Modeling Types (ContextIQ Phase 6.6).
 */

export type SurvivalEventTarget =
  | "task_abandonment"
  | "task_completion"
  | "confirmed_task_resumption"
  | "confirmed_recovery";

export type PersonalizationTier = "individual" | "group" | "population";

export type DynamicUpdateTrigger =
  | "new_interruption"
  | "deadline_approaching"
  | "task_state_change"
  | "user_interaction"
  | "context_change"
  | "calendar_conflict"
  | "periodic_tick";

export interface SurvivalCurvePointData {
  horizon_value: number;
  horizon_label: string;
  survival_probability: number;
  cumulative_event_probability: number;
  confidence_interval: [number, number];
}

export interface DynamicSurvivalPredictionResponseData {
  target: SurvivalEventTarget;
  user_id: string;
  task_id?: string | null;
  last_updated_at: string;
  time_unit: string;
  current_elapsed: number;
  update_trigger: DynamicUpdateTrigger;
  median_time_to_event?: number | null;
  expected_hazard_rate: number;
  survival_curve: SurvivalCurvePointData[];
  personalization_tier: PersonalizationTier;
  shrinkage_weight: number;
  user_sample_size: number;
  data_sufficiency_score: number;
  model_name: string;
  model_version: string;
  disclaimer: string;
}

export interface SurvivalBenchmarkMetricsData {
  model_name: string;
  target: SurvivalEventTarget;
  concordance_index: number;
  integrated_brier_score: number;
  time_dependent_auc_horizon_1: number;
  time_dependent_auc_horizon_2: number;
  horizon_calibration_error: number;
  is_champion: boolean;
  selection_rationale?: string | null;
}

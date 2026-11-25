/**
 * Causal Behavioral Modeling & Confounding Analysis Types (ContextIQ Phase 6.3).
 */

export type CausalQuestionId =
  | "recovery_buffer_on_resumption"
  | "adaptive_scheduling_on_completion"
  | "personalized_reminder_on_abandonment"
  | "notification_timing_on_friction";

export type CausalMethod =
  | "doubly_robust_aipw"
  | "inverse_probability_weighting"
  | "propensity_score_matching"
  | "regression_adjustment";

export type AnalysisStatus = "convincing" | "inconclusive" | "abstained";

export interface TargetTrialProtocolData {
  question_id: CausalQuestionId;
  title: string;
  eligibility_criteria: string[];
  treatment_strategy: string;
  control_strategy: string;
  time_zero_definition: string;
  follow_up_window: string;
  outcome_definition: string;
  causal_estimand: string;
  analysis_plan: string;
  immortal_time_bias_prevention: string;
}

export interface CovariateBalanceItemData {
  covariate_name: string;
  mean_treated: number;
  mean_control: number;
  smd_unadjusted: number;
  smd_adjusted: number;
  is_balanced: boolean;
}

export interface OverlapDiagnosticsData {
  common_support_min: number;
  common_support_max: number;
  treated_propensity_mean: number;
  control_propensity_mean: number;
  positivity_violations_count: number;
  positivity_violations_pct: number;
  has_sufficient_overlap: boolean;
}

export interface SensitivityAnalysisData {
  e_value_estimate: number;
  e_value_lower_bound: number;
  interpretation: string;
  robustness_assessment: "ROBUST" | "MODERATE" | "FRAGILE";
}

export interface SubgroupCATEData {
  subgroup_name: string;
  dimension: string;
  sample_size_treated: number;
  sample_size_control: number;
  estimated_cate: number | null;
  ci_lower: number | null;
  ci_upper: number | null;
  is_statistically_sound: boolean;
  abstention_reason?: string | null;
}

export interface CausalAnalysisResultData {
  question_id: CausalQuestionId;
  title: string;
  status: AnalysisStatus;
  method_used: CausalMethod;
  target_trial: TargetTrialProtocolData;
  sample_size_treated: number;
  sample_size_control: number;
  total_sample_size: number;
  raw_observational_difference: number;
  estimated_causal_effect: number | null;
  confidence_interval: [number, number] | null;
  standard_error: number | null;
  p_value: number | null;
  covariate_balance: CovariateBalanceItemData[];
  overlap_diagnostics: OverlapDiagnosticsData;
  sensitivity?: SensitivityAnalysisData | null;
  effect_heterogeneity: SubgroupCATEData[];
  identification_assumptions: string[];
  limitations: string[];
  abstention_explanation?: string | null;
  disclaimer: string;
}

export interface CausalQuestionSummary {
  question_id: string;
  title: string;
  treatment_node: string;
  outcome_node: string;
  adjustment_set: string[];
  forbidden_controls: string[];
  unmeasured_risks_count: number;
}

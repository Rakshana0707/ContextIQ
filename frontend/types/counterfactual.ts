/**
 * Counterfactual Recommendation and Intervention Comparison Types (ContextIQ Phase 6.4).
 */

export type CandidateIntervention =
  | "no_intervention"
  | "immediate_reminder"
  | "delayed_reminder"
  | "calendar_rescheduling"
  | "short_recovery_buffer"
  | "focus_session_recommendation"
  | "break_large_task";

export type DataCoverageTier = "strong" | "moderate" | "sparse" | "unsupported";

export type CounterfactualLearnerType =
  | "t_learner"
  | "s_learner"
  | "x_learner"
  | "doubly_robust_learner";

export type RecommendationStrategy =
  | "counterfactual_optimized"
  | "deterministic_fallback";

export interface PotentialOutcomeVectorData {
  task_resumption_probability: number;
  task_completion_probability: number;
  expected_recovery_duration_seconds: number;
  expected_behavioral_friction: number;
  expected_notification_burden: number;
}

export interface IncrementalBenefitVectorData {
  resumption_lift_pct: number;
  completion_lift_pct: number;
  recovery_time_saved_seconds: number;
  friction_reduction_points: number;
  burden_penalty: number;
}

export interface CounterfactualCandidateResultData {
  candidate: CandidateIntervention;
  title: string;
  description: string;
  category: string;
  is_supported: boolean;
  coverage_tier: DataCoverageTier;
  exclusion_reason?: string | null;
  potential_outcomes?: PotentialOutcomeVectorData | null;
  incremental_benefit?: IncrementalBenefitVectorData | null;
  composite_uplift_score?: number | null;
  uncertainty_intervals?: Record<string, [number, number]> | null;
  empirical_sample_size: number;
  empirical_execution_rate: number;
  overlap_score: number;
  learner_used: CounterfactualLearnerType;
  assumptions: string[];
}

export interface CounterfactualComparisonResponseData {
  context_id: string;
  user_id: string;
  evaluation_timestamp: string;
  target_task_id?: string | null;
  baseline_candidate: CandidateIntervention;
  candidates: CounterfactualCandidateResultData[];
  recommended_champion?: CandidateIntervention | null;
  recommendation_source: RecommendationStrategy;
  fallback_reason?: string | null;
  disclaimer: string;
}

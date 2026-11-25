/**
 * Uncertainty Quantification and Intelligent Abstention Types (ContextIQ Phase 6.8).
 */

export type AbstentionOutcome =
  | "PREDICTION_AVAILABLE"
  | "PREDICTION_WITH_CAUTION"
  | "INSUFFICIENT_EVIDENCE"
  | "UNSUPPORTED_INPUT"
  | "MODEL_UNAVAILABLE";

export type AbstentionReason =
  | "NONE"
  | "INSUFFICIENT_USER_HISTORY"
  | "OUT_OF_DISTRIBUTION"
  | "LOW_TELEMETRY_QUALITY"
  | "UNSEEN_EVENT_TYPE"
  | "MISSING_CRITICAL_INPUTS"
  | "HIGH_EPISTEMIC_UNCERTAINTY"
  | "UNSUPPORTED_INTERVENTION"
  | "MODEL_UNCALIBRATED";

export type ActionPolicyType =
  | "EXECUTE_AUTOMATED"
  | "EXECUTE_WITH_CAUTION"
  | "FALLBACK_DETERMINISTIC"
  | "ABSTAIN_AND_PROMPT_USER";

export interface UncertaintyDecompositionData {
  aleatoric_score: number;
  epistemic_score: number;
  total_uncertainty: number;
  is_epistemic_dominant: boolean;
  explanation: string;
}

export interface ReliabilityBinData {
  bin_index: number;
  bin_center: number;
  observed_frequency: number;
  predicted_frequency: number;
  sample_count: number;
}

export interface CalibrationMetricsData {
  calibration_method: string;
  expected_calibration_error: number;
  maximum_calibration_error: number;
  brier_score: number;
  is_well_calibrated: boolean;
  reliability_bins: ReliabilityBinData[];
}

export interface ConformalPredictionIntervalData {
  coverage_level: number;
  lower_bound: number;
  upper_bound: number;
  interval_width: number;
  calibration_sample_size: number;
  temporal_shift_warning?: string | null;
}

export interface DataCoverageAuditData {
  user_sample_size: number;
  telemetry_quality_score: number;
  ood_distance: number;
  is_out_of_distribution: boolean;
  unseen_event_types: string[];
  missing_critical_inputs: string[];
  data_coverage_tier: string;
}

export interface ModelUncertaintyAuditItemData {
  model_family: string;
  target_name: string;
  exposes_interval: boolean;
  interval_methodology?: string | null;
  decomposes_uncertainty: boolean;
  calibration_status: string;
  abstention_supported: boolean;
  known_limitations: string;
}

export interface DecisionSupportResponseData {
  decision_id: string;
  user_id: string;
  evaluated_at: string;
  model_name: string;
  abstention_outcome: AbstentionOutcome;
  abstention_reason: AbstentionReason;
  can_automate_recommendation: boolean;
  recommended_action_policy: ActionPolicyType;
  point_prediction?: number | null;
  calibrated_probability?: number | null;
  uncertainty_decomposition: UncertaintyDecompositionData;
  prediction_interval?: ConformalPredictionIntervalData | null;
  data_coverage: DataCoverageAuditData;
  calibration_metrics?: CalibrationMetricsData | null;
  user_facing_explanation: string;
  disclaimer: string;
}

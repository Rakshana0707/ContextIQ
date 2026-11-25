/**
 * Temporal Behavioral Sequence Modeling Types (ContextIQ Phase 6.5).
 */

export type SequencePredictionTarget =
  | "short_term_task_resumption"
  | "interruption_recovery_risk"
  | "future_context_switch"
  | "task_completion"
  | "behavioral_friction_trend";

export type SequenceModelArchitecture =
  | "tabular_gradient_boosting"
  | "gru_recurrent"
  | "temporal_convolutional_network"
  | "causal_transformer";

export interface ModelBenchmarkMetricsData {
  model_name: string;
  target: SequencePredictionTarget;
  roc_auc: number;
  pr_auc: number;
  brier_score: number;
  log_loss: number;
  training_time_seconds: number;
  inference_latency_ms: number;
  is_champion: boolean;
  selection_rationale?: string | null;
}

export interface SequencePredictionResponseData {
  target: SequencePredictionTarget;
  user_id: string;
  prediction_timestamp: string;
  predicted_probability: number;
  predicted_label: string;
  confidence_interval: [number, number];
  sequence_length: number;
  is_cold_start: boolean;
  model_architecture: SequenceModelArchitecture;
  model_version: string;
  top_temporal_attributions: Array<{
    event_type: string;
    relative_seconds: number;
    weight: number;
  }>;
  disclaimer: string;
}

export interface SequenceRegistryMetadataData {
  model_version: string;
  champion_architecture: SequenceModelArchitecture;
  supported_targets: SequencePredictionTarget[];
  max_sequence_length: number;
  vocabulary_size: number;
  training_snapshot_size: number;
  trained_at: string;
  benchmark_comparison: ModelBenchmarkMetricsData[];
}

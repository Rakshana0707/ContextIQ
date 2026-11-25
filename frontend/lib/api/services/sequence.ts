/**
 * Temporal Sequence Modeling API Client & Mock Service (ContextIQ Phase 6.5).
 */
import type {
  ModelBenchmarkMetricsData,
  SequencePredictionResponseData,
  SequencePredictionTarget,
  SequenceRegistryMetadataData,
} from "@/types/sequence";

export const mockSequencePrediction: SequencePredictionResponseData = {
  target: "short_term_task_resumption",
  user_id: "usr_mock_001",
  prediction_timestamp: new Date().toISOString(),
  predicted_probability: 0.78,
  predicted_label: "POSITIVE",
  confidence_interval: [0.63, 0.93],
  sequence_length: 18,
  is_cold_start: false,
  model_architecture: "gru_recurrent",
  model_version: "2.1.0-seq-prod",
  top_temporal_attributions: [
    { event_type: "APPLICATION_SWITCH", relative_seconds: 1420.0, weight: 0.35 },
    { event_type: "RECOVERY_BUFFER_DISPATCH", relative_seconds: 1540.0, weight: 0.72 },
    { event_type: "TASK_RESUME", relative_seconds: 1680.0, weight: 0.88 },
  ],
  disclaimer: "Sequence prediction derived strictly from historical event sequences (t <= t_pred). No future event leakage.",
};

export const mockSequenceBenchmarks: ModelBenchmarkMetricsData[] = [
  {
    model_name: "GRU Recurrent Model",
    target: "short_term_task_resumption",
    roc_auc: 0.862,
    pr_auc: 0.841,
    brier_score: 0.142,
    log_loss: 0.412,
    training_time_seconds: 0.85,
    inference_latency_ms: 1.82,
    is_champion: true,
    selection_rationale: "Champion: Demonstrates superior sequence-level predictive accuracy on chronological evaluation.",
  },
  {
    model_name: "Causal Transformer",
    target: "short_term_task_resumption",
    roc_auc: 0.851,
    pr_auc: 0.828,
    brier_score: 0.155,
    log_loss: 0.435,
    training_time_seconds: 1.45,
    inference_latency_ms: 3.45,
    is_champion: false,
    selection_rationale: "Candidate: Comparable accuracy but higher computational latency.",
  },
  {
    model_name: "Temporal ConvNet (TCN)",
    target: "short_term_task_resumption",
    roc_auc: 0.844,
    pr_auc: 0.819,
    brier_score: 0.160,
    log_loss: 0.448,
    training_time_seconds: 0.92,
    inference_latency_ms: 2.10,
    is_champion: false,
    selection_rationale: "Candidate: Effective causal receptive field, slightly below GRU on sparse sequences.",
  },
  {
    model_name: "Tabular Baseline (Gradient Boosting)",
    target: "short_term_task_resumption",
    roc_auc: 0.820,
    pr_auc: 0.795,
    brier_score: 0.178,
    log_loss: 0.490,
    training_time_seconds: 0.12,
    inference_latency_ms: 0.45,
    is_champion: false,
    selection_rationale: "Baseline: Strong reference model based on summary statistics.",
  },
];

export const sequenceApi = {
  async predictSequence(
    target: SequencePredictionTarget = "short_term_task_resumption"
  ): Promise<SequencePredictionResponseData> {
    try {
      const res = await fetch(`/api/v1/sequence/predict?target=${target}`);
      if (!res.ok) throw new Error("API error");
      return await res.json();
    } catch {
      return mockSequencePrediction;
    }
  },

  async getBenchmark(
    target: SequencePredictionTarget = "short_term_task_resumption"
  ): Promise<ModelBenchmarkMetricsData[]> {
    try {
      const res = await fetch(`/api/v1/sequence/benchmark?target=${target}`);
      if (!res.ok) throw new Error("API error");
      return await res.json();
    } catch {
      return mockSequenceBenchmarks;
    }
  },
};

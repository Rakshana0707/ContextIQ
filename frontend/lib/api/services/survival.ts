/**
 * Personalized Survival and Dynamic Risk API Client & Mock Service (ContextIQ Phase 6.6).
 */
import type {
  DynamicSurvivalPredictionResponseData,
  DynamicUpdateTrigger,
  PersonalizationTier,
  SurvivalBenchmarkMetricsData,
  SurvivalCurvePointData,
  SurvivalEventTarget,
} from "@/types/survival";

export const mockSurvivalPrediction: DynamicSurvivalPredictionResponseData = {
  target: "task_abandonment",
  user_id: "usr_mock_001",
  task_id: "tsk_mock_991",
  last_updated_at: new Date().toISOString(),
  time_unit: "hours",
  current_elapsed: 4.5,
  update_trigger: "new_interruption",
  median_time_to_event: 64.2,
  expected_hazard_rate: 0.021,
  survival_curve: [
    {
      horizon_value: 6.0,
      horizon_label: "6h",
      survival_probability: 0.88,
      cumulative_event_probability: 0.12,
      confidence_interval: [0.75, 0.98],
    },
    {
      horizon_value: 12.0,
      horizon_label: "12h",
      survival_probability: 0.79,
      cumulative_event_probability: 0.21,
      confidence_interval: [0.67, 0.91],
    },
    {
      horizon_value: 24.0,
      horizon_label: "24h",
      survival_probability: 0.65,
      cumulative_event_probability: 0.35,
      confidence_interval: [0.55, 0.75],
    },
    {
      horizon_value: 48.0,
      horizon_label: "48h",
      survival_probability: 0.48,
      cumulative_event_probability: 0.52,
      confidence_interval: [0.41, 0.56],
    },
    {
      horizon_value: 168.0,
      horizon_label: "7d",
      survival_probability: 0.18,
      cumulative_event_probability: 0.82,
      confidence_interval: [0.15, 0.21],
    },
  ],
  personalization_tier: "individual",
  shrinkage_weight: 0.71,
  user_sample_size: 37,
  data_sufficiency_score: 1.0,
  model_name: "Log-Normal AFT with Dynamic Landmarking",
  model_version: "2.2.0-dynamic-survival",
  disclaimer:
    "Dynamic survival estimates reflect conditional probability given survival to current elapsed time. No future information leakage.",
};

export const mockSurvivalBenchmarks: SurvivalBenchmarkMetricsData[] = [
  {
    model_name: "Log-Normal AFT (Champion)",
    target: "task_abandonment",
    concordance_index: 0.742,
    integrated_brier_score: 0.145,
    time_dependent_auc_horizon_1: 0.765,
    time_dependent_auc_horizon_2: 0.738,
    horizon_calibration_error: 0.035,
    is_champion: true,
    selection_rationale:
      "Champion: Demonstrates highest concordance index and best calibration for heavy-tailed cognitive events.",
  },
  {
    model_name: "Weibull AFT",
    target: "task_abandonment",
    concordance_index: 0.704,
    integrated_brier_score: 0.158,
    time_dependent_auc_horizon_1: 0.728,
    time_dependent_auc_horizon_2: 0.712,
    horizon_calibration_error: 0.048,
    is_champion: false,
    selection_rationale: "Candidate: Parametric alternative; slightly lower discrimination on extreme tail.",
  },
  {
    model_name: "Cox Proportional Hazards",
    target: "task_abandonment",
    concordance_index: 0.691,
    integrated_brier_score: 0.165,
    time_dependent_auc_horizon_1: 0.710,
    time_dependent_auc_horizon_2: 0.688,
    horizon_calibration_error: 0.052,
    is_champion: false,
    selection_rationale:
      "Candidate: Semi-parametric model; proportional hazards assumption partially violated over long horizons.",
  },
  {
    model_name: "Kaplan-Meier Baseline",
    target: "task_abandonment",
    concordance_index: 0.520,
    integrated_brier_score: 0.225,
    time_dependent_auc_horizon_1: 0.550,
    time_dependent_auc_horizon_2: 0.530,
    horizon_calibration_error: 0.082,
    is_champion: false,
    selection_rationale: "Baseline: Non-parametric reference without covariate adjustment.",
  },
];

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export const survivalApi = {
  async predictSurvival(
    target: SurvivalEventTarget = "task_abandonment",
    elapsed: number = 0.0,
    trigger: DynamicUpdateTrigger = "periodic_tick"
  ): Promise<DynamicSurvivalPredictionResponseData> {
    try {
      const res = await fetch(
        `${API_BASE}/survival/predict?target=${encodeURIComponent(target)}&current_time_elapsed=${elapsed}&update_trigger=${encodeURIComponent(trigger)}`,
        { headers: { "Content-Type": "application/json" } }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch {
      return {
        ...mockSurvivalPrediction,
        target,
        current_elapsed: elapsed,
        update_trigger: trigger,
      };
    }
  },

  async dynamicUpdate(
    target: SurvivalEventTarget,
    elapsed: number,
    trigger: DynamicUpdateTrigger
  ): Promise<DynamicSurvivalPredictionResponseData> {
    try {
      const res = await fetch(`${API_BASE}/survival/dynamic-update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target,
          current_time_elapsed: elapsed,
          update_trigger: trigger,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch {
      return {
        ...mockSurvivalPrediction,
        target,
        current_elapsed: elapsed,
        update_trigger: trigger,
      };
    }
  },

  async getBenchmark(
    target: SurvivalEventTarget = "task_abandonment"
  ): Promise<SurvivalBenchmarkMetricsData[]> {
    try {
      const res = await fetch(
        `${API_BASE}/survival/benchmark?target=${encodeURIComponent(target)}`,
        { headers: { "Content-Type": "application/json" } }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch {
      return mockSurvivalBenchmarks;
    }
  },
};

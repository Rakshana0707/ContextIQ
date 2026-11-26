/**
 * Frontend API client service for Intelligent Project Progress Forecasting (Phase 8.6).
 */
import { apiClient } from "@/lib/api/client";
import type {
  ForecastScenarioRequest,
  ForecastScenarioResult,
  ModelBenchmarkResult,
  ProjectForecast,
  ProjectForecastDashboardData,
} from "@/types/project_forecast";

const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK_API === "true";

export const MOCK_FORECAST: ProjectForecast = {
  id: "forecast-1",
  user_id: "user-1",
  project_id: "project-1",
  forecast_at: "2026-11-26T10:00:00Z",
  target_completion_date: "2026-12-15T00:00:00Z",
  estimated_completion_date: "2026-12-11T16:00:00Z",
  p10_completion_date: "2026-12-07T12:00:00Z",
  p90_completion_date: "2026-12-19T18:00:00Z",
  uncertainty_spread_days: 12.2,
  on_time_probability: 0.74,
  delay_risk_score: 0.26,
  delay_risk_tier: "MODERATE",
  expected_remaining_workload_hours: 32.5,
  remaining_tasks_count: 8,
  completed_tasks_count: 14,
  blocked_dependencies_count: 1,
  current_velocity_tasks_per_week: 4.8,
  required_velocity_tasks_per_week: 4.2,
  data_sufficiency: "DATA_SUFFICIENT",
  model_name: "ENSEMBLE_FORECASTER",
  major_delay_contributors: [
    {
      factor: "UNRESOLVED_BLOCKERS",
      impact_score: 0.45,
      description: "1 active dependency blocker halts downstream database migration task.",
      remediation_suggestion: "Prioritize prerequisite schema validation task in next morning focus block.",
    },
    {
      factor: "HIGH_PRIORITY_CONGESTION",
      impact_score: 0.35,
      description: "62% of remaining tasks are marked HIGH priority, inducing potential context fragmentation.",
      remediation_suggestion: "Sequence critical deliverables linearly to reduce cognitive switching overhead.",
    },
  ],
  milestone_forecasts: [
    {
      milestone_id: "m-1",
      title: "Core Data Contracts & Knowledge Graph",
      due_date: "2026-11-24T00:00:00Z",
      projected_completion_date: "2026-11-23T18:00:00Z",
      on_time_probability: 1.0,
      is_completed: true,
      risk_tier: "LOW",
    },
    {
      milestone_id: "m-2",
      title: "Dependency Intelligence Engine",
      due_date: "2026-11-28T00:00:00Z",
      projected_completion_date: "2026-11-27T14:00:00Z",
      on_time_probability: 0.88,
      is_completed: false,
      risk_tier: "LOW",
    },
    {
      milestone_id: "m-3",
      title: "Production Deployment & Telemetry Verification",
      due_date: "2026-12-15T00:00:00Z",
      projected_completion_date: "2026-12-11T16:00:00Z",
      on_time_probability: 0.74,
      is_completed: false,
      risk_tier: "MODERATE",
    },
  ],
  feature_snapshot: {
    remaining_tasks: 8,
    completed_tasks: 14,
    velocity_tasks_per_week: 4.8,
    weekly_focus_hours: 12.0,
    data_sufficiency: "DATA_SUFFICIENT",
  },
  notes: "Ensemble forecaster with Weibull hazard adjustment.",
  created_at: "2026-11-26T10:00:00Z",
  updated_at: "2026-11-26T10:00:00Z",
};

export const MOCK_DASHBOARD: ProjectForecastDashboardData = {
  project_id: "project-1",
  project_title: "ContextIQ Production Release (v1.0)",
  target_completion_date: "2026-12-15T00:00:00Z",
  forecast: MOCK_FORECAST,
  data_sufficiency: "DATA_SUFFICIENT",
  recent_forecasts: [MOCK_FORECAST],
  milestone_predictions: MOCK_FORECAST.milestone_forecasts,
  major_delay_contributors: MOCK_FORECAST.major_delay_contributors,
};

export const projectForecastApi = {
  async getProjectForecastDashboard(projectId: string): Promise<ProjectForecastDashboardData> {
    if (USE_MOCK) return MOCK_DASHBOARD;
    try {
      const res = await apiClient.get<ProjectForecastDashboardData>(`/forecasts/projects/${projectId}`);
      return res.data;
    } catch {
      return MOCK_DASHBOARD;
    }
  },

  async generateProjectForecast(
    projectId: string,
    modelType: string = "ENSEMBLE_FORECASTER"
  ): Promise<ProjectForecast> {
    if (USE_MOCK) return MOCK_FORECAST;
    const res = await apiClient.post<ProjectForecast>(`/forecasts/projects/${projectId}/generate`, {
      project_id: projectId,
      model_type: modelType,
      simulate_monte_carlo: true,
    });
    return res.data;
  },

  async runScenarioSimulation(payload: ForecastScenarioRequest): Promise<ForecastScenarioResult> {
    if (USE_MOCK) {
      const pLift = payload.resolve_blockers ? 0.16 : 0.08;
      const daysSaved = payload.additional_focus_hours_per_week ? payload.additional_focus_hours_per_week * 0.8 : 2.5;
      return {
        project_id: payload.project_id,
        baseline_on_time_probability: 0.74,
        scenario_on_time_probability: Math.min(0.96, 0.74 + pLift),
        probability_lift: pLift,
        baseline_estimated_completion: "2026-12-11T16:00:00Z",
        scenario_estimated_completion: "2026-12-08T12:00:00Z",
        days_saved: daysSaved,
        baseline_risk_tier: "MODERATE",
        scenario_risk_tier: "LOW",
        scenario_summary: `Counterfactual adjustments lift on-time probability to ${Math.round(
          (0.74 + pLift) * 100
        )}% and deliver completion ${daysSaved.toFixed(1)} days earlier.`,
        recommended_interventions: [
          "Resolve active blocking dependencies prior to milestone sprint.",
          "Allocate 3 additional focus hours weekly during morning windows.",
        ],
      };
    }
    const res = await apiClient.post<ForecastScenarioResult>(
      `/forecasts/projects/${payload.project_id}/scenario`,
      payload
    );
    return res.data;
  },

  async getModelBenchmarks(): Promise<ModelBenchmarkResult> {
    if (USE_MOCK) {
      return {
        benchmarked_at: "2026-11-26T12:00:00Z",
        models_evaluated: ["RULE_BASED_VELOCITY", "HISTORICAL_RATE", "SURVIVAL_HAZARD", "ENSEMBLE_FORECASTER"],
        mae_days_by_model: {
          RULE_BASED_VELOCITY: 4.8,
          HISTORICAL_RATE: 3.9,
          SURVIVAL_HAZARD: 3.4,
          ENSEMBLE_FORECASTER: 2.7,
        },
        rmse_days_by_model: {
          RULE_BASED_VELOCITY: 6.2,
          HISTORICAL_RATE: 5.1,
          SURVIVAL_HAZARD: 4.5,
          ENSEMBLE_FORECASTER: 3.6,
        },
        brier_score_by_model: {
          RULE_BASED_VELOCITY: 0.22,
          HISTORICAL_RATE: 0.18,
          SURVIVAL_HAZARD: 0.15,
          ENSEMBLE_FORECASTER: 0.11,
        },
        interval_coverage_p10_p90: {
          RULE_BASED_VELOCITY: 0.72,
          HISTORICAL_RATE: 0.79,
          SURVIVAL_HAZARD: 0.84,
          ENSEMBLE_FORECASTER: 0.89,
        },
        horizon_performance: {
          "7_days": { MAE_days: 1.4, Brier: 0.08, Coverage: 0.92 },
          "14_days": { MAE_days: 2.6, Brier: 0.12, Coverage: 0.89 },
          "30_days": { MAE_days: 4.1, Brier: 0.16, Coverage: 0.85 },
        },
        recommended_model: "ENSEMBLE_FORECASTER",
        benchmark_summary:
          "Ensemble Forecaster outperforms individual baselines with an MAE of 2.7 days and 89% P10-P90 coverage.",
      };
    }
    const res = await apiClient.get<ModelBenchmarkResult>("/forecasts/benchmark");
    return res.data;
  },
};

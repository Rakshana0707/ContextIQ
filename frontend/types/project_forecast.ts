/**
 * TypeScript definitions for Intelligent Project Progress Forecasting (Phase 8.6).
 */

export type DelayRiskTier = "LOW" | "MODERATE" | "HIGH" | "CRITICAL";

export type DataSufficiencyStatus =
  | "DATA_SUFFICIENT"
  | "LIMITED_HISTORY_FALLBACK"
  | "INSUFFICIENT_DATA";

export type ForecastingModelType =
  | "RULE_BASED_VELOCITY"
  | "HISTORICAL_RATE"
  | "SURVIVAL_HAZARD"
  | "ENSEMBLE_FORECASTER";

export interface MilestoneForecastItem {
  milestone_id: string;
  title: string;
  due_date?: string | null;
  projected_completion_date?: string | null;
  on_time_probability: number;
  is_completed: boolean;
  risk_tier: DelayRiskTier;
}

export interface DelayContributor {
  factor: string;
  impact_score: number;
  description: string;
  remediation_suggestion: string;
}

export interface ProjectForecast {
  id: string;
  user_id: string;
  project_id: string;
  forecast_at: string;
  target_completion_date?: string | null;
  estimated_completion_date?: string | null;
  p10_completion_date?: string | null;
  p90_completion_date?: string | null;
  uncertainty_spread_days: number;
  on_time_probability: number;
  delay_risk_score: number;
  delay_risk_tier: DelayRiskTier;
  expected_remaining_workload_hours: number;
  remaining_tasks_count: number;
  completed_tasks_count: number;
  blocked_dependencies_count: number;
  current_velocity_tasks_per_week: number;
  required_velocity_tasks_per_week: number;
  data_sufficiency: DataSufficiencyStatus;
  model_name: string;
  major_delay_contributors: DelayContributor[];
  milestone_forecasts: MilestoneForecastItem[];
  feature_snapshot: Record<string, any>;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ForecastScenarioRequest {
  project_id: string;
  prioritize_overdue_tasks?: boolean;
  additional_focus_hours_per_week?: number;
  resolve_blockers?: boolean;
  deadline_extension_days?: number;
}

export interface ForecastScenarioResult {
  project_id: string;
  baseline_on_time_probability: number;
  scenario_on_time_probability: number;
  probability_lift: number;
  baseline_estimated_completion?: string | null;
  scenario_estimated_completion?: string | null;
  days_saved: number;
  baseline_risk_tier: string;
  scenario_risk_tier: string;
  scenario_summary: string;
  recommended_interventions: string[];
}

export interface ModelBenchmarkResult {
  benchmarked_at: string;
  models_evaluated: string[];
  mae_days_by_model: Record<string, number>;
  rmse_days_by_model: Record<string, number>;
  brier_score_by_model: Record<string, number>;
  interval_coverage_p10_p90: Record<string, number>;
  horizon_performance: Record<string, { MAE_days: number; Brier: number; Coverage: number }>;
  recommended_model: string;
  benchmark_summary: string;
}

export interface ProjectForecastDashboardData {
  project_id: string;
  project_title: string;
  target_completion_date?: string | null;
  forecast?: ProjectForecast | null;
  data_sufficiency: DataSufficiencyStatus;
  recent_forecasts: ProjectForecast[];
  milestone_predictions: MilestoneForecastItem[];
  major_delay_contributors: DelayContributor[];
}

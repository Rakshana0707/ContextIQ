/**
 * TypeScript definitions for Long-Term Behavioral Trend Analysis (Phase 8.7).
 */

export type TrendCategory =
  | "FOCUS_CONSISTENCY"
  | "RECOVERY_EFFICIENCY"
  | "CONTEXT_SWITCH_FREQUENCY"
  | "TASK_COMPLETION_CONSISTENCY"
  | "DEADLINE_ADHERENCE"
  | "BEHAVIORAL_FRICTION"
  | "INTERRUPTION_EXPOSURE"
  | "INTERVENTION_EFFECTIVENESS"
  | "GOAL_PROGRESS";

export type TrendDirection = "IMPROVING" | "STABLE" | "DEGRADING" | "VOLATILE";

export type TemporalGranularity = "DAILY" | "WEEKLY" | "MONTHLY" | "QUARTERLY" | "CUSTOM";

export interface DailyTrendPoint {
  date: string;
  focus_minutes: number;
  focus_consistency: number;
  recovery_efficiency: number;
  context_switches_per_hour: number;
  tasks_completed: number;
  deadline_adherence: number;
  behavioral_friction: number;
  data_coverage_pct: number;
  rolling_7d_focus?: number | null;
  rolling_30d_focus?: number | null;
  ema_friction?: number | null;
}

export interface TrendCategorySummary {
  category: TrendCategory;
  current_period_mean: number;
  previous_period_mean: number;
  personal_baseline_mean: number;
  period_change_pct: number;
  baseline_change_pct: number;
  trend_direction: TrendDirection;
  slope: number;
  confidence: number;
  descriptive_summary: string;
}

export interface BehavioralMilestone {
  id: string;
  user_id: string;
  milestone_type: string;
  title: string;
  description: string;
  detected_at: string;
  evaluation_period_start: string;
  evaluation_period_end: string;
  change_magnitude_pct: number;
  statistical_confidence: number;
  baseline_value: number;
  observed_value: number;
  supporting_evidence: Record<string, any>;
  is_acknowledged: boolean;
}

export interface ChangePoint {
  id: string;
  metric_name: string;
  change_point_at: string;
  change_type: string;
  prior_mean: number;
  subsequent_mean: number;
  magnitude_delta: number;
  p_value: number;
  description: string;
}

export interface InterventionComparison {
  intervention_id?: string | null;
  title: string;
  accepted_at: string;
  pre_period_friction: number;
  post_period_friction: number;
  friction_delta: number;
  pre_period_focus_mins: number;
  post_period_focus_mins: number;
  focus_delta: number;
  observational_note: string;
}

export interface BehavioralInsightsSummary {
  what_improved: string[];
  what_became_less_consistent: string[];
  patterns_changed: string[];
  interventions_associated: string[];
  needs_attention: string[];
}

export interface BehavioralTrendsDashboardData {
  user_id: string;
  granularity: TemporalGranularity;
  date_range: { start_date: string; end_date: string };
  overall_data_coverage_pct: number;
  observed_days_count: number;
  expected_days_count: number;
  daily_series: DailyTrendPoint[];
  category_summaries: TrendCategorySummary[];
  milestones: BehavioralMilestone[];
  change_points: ChangePoint[];
  intervention_comparisons: InterventionComparison[];
  long_term_insights: BehavioralInsightsSummary;
}

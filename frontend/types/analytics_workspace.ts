export type AnalyticsDomain =
  | "PROJECT_TIME_ALLOCATION"
  | "GOAL_BLOCKED_TASKS"
  | "PROJECT_DELAY_RISK"
  | "TASK_POSTPONEMENT_TYPES"
  | "RECOVERY_DURATION_TREND"
  | "INTERVENTION_HISTORICAL_EVIDENCE"
  | "DEADLINE_PRIORITY_CONFLICTS"
  | "CROSS_PROJECT_PROGRESS"
  | "CUSTOM_PRODUCTIVITY_QUERY";

export type ChartType = "BAR" | "LINE" | "PIE" | "RADAR" | "TIMELINE" | "TABLE";

export interface AnalyticsTimeRange {
  lookback_days?: number | null;
  start_date?: string | null;
  end_date?: string | null;
  label: string;
}

export interface AnalyticsQueryPlan {
  plan_id: string;
  target_domain: AnalyticsDomain;
  entity: string;
  time_range: AnalyticsTimeRange;
  filters: Record<string, any>;
  group_by?: string | null;
  aggregation: string;
  sort_by?: string | null;
  sort_order: "ASC" | "DESC";
  limit: number;
  comparison_mode?: string | null;
  is_valid: boolean;
  planning_rationale: string;
}

export interface AnalyticsDataPoint {
  label: string;
  value: number;
  secondary_value?: number | null;
  category?: string | null;
  color?: string | null;
  metadata?: Record<string, any>;
}

export interface AnalyticsVisualizationSpec {
  chart_type: ChartType;
  title: string;
  x_axis_label?: string | null;
  y_axis_label?: string | null;
  series: AnalyticsDataPoint[];
  chart_config: Record<string, any>;
}

export interface DecisionRecommendation {
  decision_type: string;
  target_title: string;
  target_id?: string | null;
  score: number;
  rank: number;
  rationale: string;
  suggested_action: string;
}

export interface AnalyticsQueryRequest {
  query: string;
  lookback_days?: number | null;
  filters?: Record<string, any> | null;
}

export interface AnalyticsQueryResponse {
  query: string;
  plan: AnalyticsQueryPlan;
  summary_answer: string;
  calculation_details: Record<string, any>;
  time_range: Record<string, any>;
  supporting_records: Record<string, any>[];
  limitations: string[];
  suggested_decisions: DecisionRecommendation[];
  visualization: AnalyticsVisualizationSpec;
  epistemic_disclaimer: string;
}

export interface SavedAnalyticsQueryCreate {
  title: string;
  query_text: string;
  target_domain?: string;
  plan_snapshot?: Record<string, any> | null;
  is_favorite?: boolean;
}

export interface SavedAnalyticsQueryRead {
  id: string;
  title: string;
  query_text: string;
  target_domain: string;
  is_favorite: boolean;
  created_at: string;
  last_run_at?: string | null;
  plan_snapshot: Record<string, any>;
}

export interface SavedAnalyticsQueryListResponse {
  queries: SavedAnalyticsQueryRead[];
  total: number;
}

export interface AnalyticsSuggestionItem {
  question: string;
  category: string;
  expected_chart_type: string;
  description: string;
}

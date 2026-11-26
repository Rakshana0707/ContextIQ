/**
 * Frontend API client service for Long-Term Behavioral Trend Analysis (Phase 8.7).
 */
import { apiClient } from "@/lib/api/client";
import type {
  BehavioralMilestone,
  BehavioralTrendsDashboardData,
  TrendCategorySummary,
} from "@/types/behavioral_trend";

const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK_API === "true";

export const MOCK_TRENDS_DASHBOARD: BehavioralTrendsDashboardData = {
  user_id: "user-1",
  granularity: "DAILY",
  date_range: { start_date: "2026-10-28", end_date: "2026-11-26" },
  overall_data_coverage_pct: 92.5,
  observed_days_count: 28,
  expected_days_count: 30,
  daily_series: [
    {
      date: "2026-11-20",
      focus_minutes: 185.0,
      focus_consistency: 0.82,
      recovery_efficiency: 0.88,
      context_switches_per_hour: 4.2,
      tasks_completed: 4,
      deadline_adherence: 0.95,
      behavioral_friction: 28.5,
      data_coverage_pct: 95.0,
      rolling_7d_focus: 178.0,
      rolling_30d_focus: 162.0,
      ema_friction: 31.2,
    },
    {
      date: "2026-11-21",
      focus_minutes: 210.0,
      focus_consistency: 0.85,
      recovery_efficiency: 0.91,
      context_switches_per_hour: 3.8,
      tasks_completed: 5,
      deadline_adherence: 1.0,
      behavioral_friction: 24.0,
      data_coverage_pct: 98.0,
      rolling_7d_focus: 184.0,
      rolling_30d_focus: 165.0,
      ema_friction: 29.8,
    },
    {
      date: "2026-11-22",
      focus_minutes: 195.0,
      focus_consistency: 0.84,
      recovery_efficiency: 0.89,
      context_switches_per_hour: 4.0,
      tasks_completed: 3,
      deadline_adherence: 0.92,
      behavioral_friction: 26.5,
      data_coverage_pct: 92.0,
      rolling_7d_focus: 188.0,
      rolling_30d_focus: 167.0,
      ema_friction: 29.1,
    },
    {
      date: "2026-11-23",
      focus_minutes: 225.0,
      focus_consistency: 0.89,
      recovery_efficiency: 0.93,
      context_switches_per_hour: 3.4,
      tasks_completed: 6,
      deadline_adherence: 1.0,
      behavioral_friction: 21.0,
      data_coverage_pct: 100.0,
      rolling_7d_focus: 195.0,
      rolling_30d_focus: 171.0,
      ema_friction: 27.5,
    },
    {
      date: "2026-11-24",
      focus_minutes: 240.0,
      focus_consistency: 0.91,
      recovery_efficiency: 0.94,
      context_switches_per_hour: 3.1,
      tasks_completed: 5,
      deadline_adherence: 1.0,
      behavioral_friction: 19.5,
      data_coverage_pct: 96.0,
      rolling_7d_focus: 204.0,
      rolling_30d_focus: 174.0,
      ema_friction: 25.9,
    },
    {
      date: "2026-11-25",
      focus_minutes: 215.0,
      focus_consistency: 0.88,
      recovery_efficiency: 0.90,
      context_switches_per_hour: 3.6,
      tasks_completed: 4,
      deadline_adherence: 0.98,
      behavioral_friction: 22.0,
      data_coverage_pct: 94.0,
      rolling_7d_focus: 208.0,
      rolling_30d_focus: 176.0,
      ema_friction: 25.1,
    },
    {
      date: "2026-11-26",
      focus_minutes: 230.0,
      focus_consistency: 0.90,
      recovery_efficiency: 0.92,
      context_switches_per_hour: 3.3,
      tasks_completed: 5,
      deadline_adherence: 1.0,
      behavioral_friction: 20.5,
      data_coverage_pct: 97.0,
      rolling_7d_focus: 214.0,
      rolling_30d_focus: 179.0,
      ema_friction: 24.2,
    },
  ],
  category_summaries: [
    {
      category: "FOCUS_CONSISTENCY",
      current_period_mean: 0.87,
      previous_period_mean: 0.72,
      personal_baseline_mean: 0.68,
      period_change_pct: 20.8,
      baseline_change_pct: 27.9,
      trend_direction: "IMPROVING",
      slope: 0.015,
      confidence: 0.94,
      descriptive_summary: "Focus regularity increased by +20.8% over the period and +27.9% vs 90-day baseline.",
    },
    {
      category: "RECOVERY_EFFICIENCY",
      current_period_mean: 0.91,
      previous_period_mean: 0.79,
      personal_baseline_mean: 0.74,
      period_change_pct: 15.2,
      baseline_change_pct: 23.0,
      trend_direction: "IMPROVING",
      slope: 0.012,
      confidence: 0.92,
      descriptive_summary: "Post-interruption recovery lag decreased to an average of 38 seconds.",
    },
    {
      category: "BEHAVIORAL_FRICTION",
      current_period_mean: 23.1,
      previous_period_mean: 34.5,
      personal_baseline_mean: 38.2,
      period_change_pct: -33.0,
      baseline_change_pct: -39.5,
      trend_direction: "IMPROVING",
      slope: -0.85,
      confidence: 0.95,
      descriptive_summary: "Composite friction index dropped by 33.0%, indicating smoother workflow momentum.",
    },
    {
      category: "DEADLINE_ADHERENCE",
      current_period_mean: 0.98,
      previous_period_mean: 0.88,
      personal_baseline_mean: 0.84,
      period_change_pct: 11.4,
      baseline_change_pct: 16.7,
      trend_direction: "IMPROVING",
      slope: 0.008,
      confidence: 0.96,
      descriptive_summary: "Tasks completed on time reached 98% during the evaluated period.",
    },
    {
      category: "CONTEXT_SWITCH_FREQUENCY",
      current_period_mean: 3.5,
      previous_period_mean: 5.2,
      personal_baseline_mean: 5.8,
      period_change_pct: -32.7,
      baseline_change_pct: -39.7,
      trend_direction: "IMPROVING",
      slope: -0.12,
      confidence: 0.91,
      descriptive_summary: "Rapid multi-app switching frequency decreased significantly.",
    },
  ],
  milestones: [
    {
      id: "m-1",
      user_id: "user-1",
      milestone_type: "SUSTAINED_FOCUS_CONSISTENCY_IMPROVEMENT",
      title: "Milestone: Focus Consistency Leap (+28%)",
      description: "Observed statistically significant 28% improvement sustained across consecutive weeks (0.68 → 0.87).",
      detected_at: "2026-11-22T00:00:00Z",
      evaluation_period_start: "2026-11-08T00:00:00Z",
      evaluation_period_end: "2026-11-22T00:00:00Z",
      change_magnitude_pct: 27.9,
      statistical_confidence: 0.96,
      baseline_value: 0.68,
      observed_value: 0.87,
      supporting_evidence: { sample_size: 14, p_value: 0.01 },
      is_acknowledged: false,
    },
    {
      id: "m-2",
      user_id: "user-1",
      milestone_type: "SUSTAINED_BEHAVIORAL_FRICTION_IMPROVEMENT",
      title: "Milestone: Low-Friction Regime Achieved (-35%)",
      description: "Cognitive resistance dropped by 35% following notification controls and morning focus scheduling.",
      detected_at: "2026-11-15T00:00:00Z",
      evaluation_period_start: "2026-11-01T00:00:00Z",
      evaluation_period_end: "2026-11-15T00:00:00Z",
      change_magnitude_pct: 35.2,
      statistical_confidence: 0.98,
      baseline_value: 38.2,
      observed_value: 23.1,
      supporting_evidence: { sample_size: 14, delta: -15.1 },
      is_acknowledged: true,
    },
  ],
  change_points: [
    {
      id: "cp-1",
      metric_name: "behavioral_friction",
      change_point_at: "2026-11-15T00:00:00Z",
      change_type: "STEP_DECREASE",
      prior_mean: 35.8,
      subsequent_mean: 23.4,
      magnitude_delta: -12.4,
      p_value: 0.015,
      description: "Structural step-decrease in behavioral friction following scheduling adjustment.",
    },
  ],
  intervention_comparisons: [
    {
      intervention_id: "rec-1",
      title: "Morning Peak Focus Window Protection",
      accepted_at: "2026-11-12T09:30:00Z",
      pre_period_friction: 36.2,
      post_period_friction: 23.8,
      friction_delta: -12.4,
      pre_period_focus_mins: 155.0,
      post_period_focus_mins: 215.0,
      focus_delta: 60.0,
      observational_note:
        "Descriptive before-and-after comparison. Differences represent observed associations and must not be interpreted as proven counterfactual causal effects without a randomized holdout.",
    },
  ],
  long_term_insights: {
    what_improved: [
      "Focus Consistency improved by 20.8% over the evaluated period.",
      "Recovery Efficiency improved by 15.2%, with average recovery lag down to 38 seconds.",
      "Behavioral Friction dropped by 33.0%, indicating smooth task execution momentum.",
      "Deadline Adherence remained at an exceptional 98% across all deliverables.",
    ],
    what_became_less_consistent: [
      "Interruption exposure exhibited minor volatility on mid-week afternoons.",
    ],
    patterns_changed: [
      "Achieved milestone: Focus Consistency Leap (+28%)",
      "Achieved milestone: Low-Friction Regime Achieved (-35%)",
    ],
    interventions_associated: [
      "Intervention 'Morning Peak Focus Window Protection' was followed by an observational reduction of 12.4 points in Behavioral Friction.",
    ],
    needs_attention: [
      "Maintain morning focus protection blocks to preserve current high-consistency trajectory.",
    ],
  },
};

export const behavioralTrendApi = {
  async getDashboard(
    lookbackDays: number = 30,
    granularity: string = "DAILY"
  ): Promise<BehavioralTrendsDashboardData> {
    if (USE_MOCK) return MOCK_TRENDS_DASHBOARD;
    try {
      const res = await apiClient.get<BehavioralTrendsDashboardData>(
        `/trends/dashboard?lookback_days=${lookbackDays}&granularity=${granularity}`
      );
      return res.data;
    } catch {
      return MOCK_TRENDS_DASHBOARD;
    }
  },

  async getTrendCategories(lookbackDays: number = 30): Promise<TrendCategorySummary[]> {
    if (USE_MOCK) return MOCK_TRENDS_DASHBOARD.category_summaries;
    try {
      const res = await apiClient.get<TrendCategorySummary[]>(`/trends/categories?lookback_days=${lookbackDays}`);
      return res.data;
    } catch {
      return MOCK_TRENDS_DASHBOARD.category_summaries;
    }
  },

  async listMilestones(): Promise<BehavioralMilestone[]> {
    if (USE_MOCK) return MOCK_TRENDS_DASHBOARD.milestones;
    try {
      const res = await apiClient.get<BehavioralMilestone[]>("/trends/milestones");
      return res.data;
    } catch {
      return MOCK_TRENDS_DASHBOARD.milestones;
    }
  },

  async acknowledgeMilestone(milestoneId: string): Promise<BehavioralMilestone> {
    if (USE_MOCK) {
      const m = MOCK_TRENDS_DASHBOARD.milestones.find((x) => x.id === milestoneId);
      if (m) m.is_acknowledged = true;
      return m || MOCK_TRENDS_DASHBOARD.milestones[0];
    }
    const res = await apiClient.post<BehavioralMilestone>(`/trends/milestones/${milestoneId}/acknowledge`);
    return res.data;
  },
};

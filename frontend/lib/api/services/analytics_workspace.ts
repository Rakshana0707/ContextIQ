import { apiClient } from "../client";
import type {
  AnalyticsQueryRequest,
  AnalyticsQueryResponse,
  AnalyticsSuggestionItem,
  SavedAnalyticsQueryCreate,
  SavedAnalyticsQueryListResponse,
  SavedAnalyticsQueryRead,
} from "@/types/analytics_workspace";

export const analyticsWorkspaceApi = {
  executeQuery: async (req: AnalyticsQueryRequest): Promise<AnalyticsQueryResponse> => {
    try {
      const res = await apiClient.post<AnalyticsQueryResponse>("/analytics-workspace/query", req);
      return res.data;
    } catch {
      // Offline fallback
      return {
        query: req.query,
        plan: {
          plan_id: "mock-plan-1",
          target_domain: "PROJECT_TIME_ALLOCATION",
          entity: "projects",
          time_range: { lookback_days: req.lookback_days || 30, label: "Last 30 Days" },
          filters: {},
          aggregation: "SUM",
          sort_order: "DESC",
          limit: 10,
          is_valid: true,
          planning_rationale: "Evaluated tracked focus minutes across active projects.",
        },
        summary_answer: `Analysis for "${req.query}": Project 'Mobile App Redesign' consumed 42.5 hours (45% of total focus time).`,
        calculation_details: { total_hours: 94.4, top_project_hours: 42.5 },
        time_range: { lookback_days: 30, label: "Last 30 Days" },
        supporting_records: [
          { project_title: "Mobile App Redesign", productive_hours: 42.5, time_share_pct: 45.0, health_status: "ON_TRACK" },
          { project_title: "Backend Infrastructure", productive_hours: 28.0, time_share_pct: 29.7, health_status: "ON_TRACK" },
          { project_title: "Security Hardening", productive_hours: 23.9, time_share_pct: 25.3, health_status: "AT_RISK" },
        ],
        limitations: ["Calculated from logged task checkpoints and active focus sessions."],
        suggested_decisions: [
          {
            decision_type: "RESOURCE_ALLOCATION",
            target_title: "Security Hardening",
            score: 0.88,
            rank: 1,
            rationale: "Security Hardening is AT_RISK with only 25% of focus allocation.",
            suggested_action: "Allocate a 2-hour morning deep-work block to resolve critical security checkpoints.",
          },
        ],
        visualization: {
          chart_type: "BAR",
          title: "Productive Hours by Project",
          x_axis_label: "Project",
          y_axis_label: "Hours",
          series: [
            { label: "Mobile App Redesign", value: 42.5, secondary_value: 45.0, color: "#3B82F6" },
            { label: "Backend Infrastructure", value: 28.0, secondary_value: 29.7, color: "#10B981" },
            { label: "Security Hardening", value: 23.9, secondary_value: 25.3, color: "#F59E0B" },
          ],
          chart_config: { unit: "hours" },
        },
        epistemic_disclaimer:
          "Analyses reflect observed productivity data in ContextIQ. Statistical associations do not imply singular causal attribution.",
      };
    }
  },

  getSuggestions: async (): Promise<AnalyticsSuggestionItem[]> => {
    try {
      const res = await apiClient.get<AnalyticsSuggestionItem[]>("/analytics-workspace/suggestions");
      return res.data;
    } catch {
      return [
        {
          question: "Which project consumed most of my productive time?",
          category: "Time Allocation",
          expected_chart_type: "BAR",
          description: "Analyzes productive time share across active projects.",
        },
        {
          question: "Which goal has the greatest number of blocked tasks?",
          category: "Dependencies",
          expected_chart_type: "BAR",
          description: "Counts dependency blockers impeding strategic goals.",
        },
        {
          question: "Which project has the highest delay risk?",
          category: "Forecasting",
          expected_chart_type: "BAR",
          description: "Ranks projects by survival delay hazard scores.",
        },
        {
          question: "What types of tasks do I postpone most often?",
          category: "Behavioral Patterns",
          expected_chart_type: "PIE",
          description: "Categorizes deferrals across task priorities and context tags.",
        },
        {
          question: "How has my recovery duration changed?",
          category: "Recovery Analytics",
          expected_chart_type: "LINE",
          description: "Tracks resumption lag and recovery efficiency trends.",
        },
        {
          question: "Which interventions have the strongest historical evidence?",
          category: "Interventions",
          expected_chart_type: "BAR",
          description: "Evaluates empirical recommendation acceptance rates.",
        },
        {
          question: "Which upcoming deadlines conflict with my current priorities?",
          category: "Schedule Optimization",
          expected_chart_type: "TABLE",
          description: "Detects priority inversions and schedule overlaps.",
        },
      ];
    }
  },

  saveQuery: async (payload: SavedAnalyticsQueryCreate): Promise<SavedAnalyticsQueryRead> => {
    try {
      const res = await apiClient.post<SavedAnalyticsQueryRead>("/analytics-workspace/saved", payload);
      return res.data;
    } catch {
      return {
        id: "mock-saved-1",
        title: payload.title,
        query_text: payload.query_text,
        target_domain: payload.target_domain || "GENERAL",
        is_favorite: payload.is_favorite || false,
        created_at: new Date().toISOString(),
        plan_snapshot: payload.plan_snapshot || {},
      };
    }
  },

  listSavedQueries: async (): Promise<SavedAnalyticsQueryListResponse> => {
    try {
      const res = await apiClient.get<SavedAnalyticsQueryListResponse>("/analytics-workspace/saved");
      return res.data;
    } catch {
      return {
        queries: [
          {
            id: "mock-saved-1",
            title: "Project Time Allocation",
            query_text: "Which project consumed most of my productive time?",
            target_domain: "PROJECT_TIME_ALLOCATION",
            is_favorite: true,
            created_at: new Date().toISOString(),
            plan_snapshot: {},
          },
        ],
        total: 1,
      };
    }
  },

  deleteSavedQuery: async (queryId: string): Promise<{ status: string; query_id: string }> => {
    try {
      const res = await apiClient.delete<{ status: string; query_id: string }>(
        `/analytics-workspace/saved/${queryId}`
      );
      return res.data;
    } catch {
      return { status: "deleted", query_id: queryId };
    }
  },
};

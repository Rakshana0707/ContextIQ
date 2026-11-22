import { apiClient, mockResult } from "../client";
import type { ApiResult } from "@/types";
import type {
  TelemetryAgentStatus,
  TelemetryEventItem,
  DetectedInterruptionItem,
  InterruptionFeedbackPayload,
  RecoveryAnalyticsData,
  BehavioralFrictionData,
  InterruptionTrendPoint,
  PersonalBaselineData,
  DailyTelemetryOverview,
} from "@/types/telemetry";

// ---------------------------------------------------------------------------
// Mock Data for Offline & Dev Fallback
// ---------------------------------------------------------------------------

const mockAgentStatus: TelemetryAgentStatus = {
  status: "online",
  last_seen: new Date(Date.now() - 15_000).toISOString(),
  pending_events: 0,
  agent_version: "0.2.0-win",
  is_paused: false,
  device_id: "win-workstation-contextiq-01",
};

const mockOverview: DailyTelemetryOverview = {
  total_events_today: 482,
  total_focus_minutes: 275,
  total_idle_minutes: 42,
  detected_interruptions_count: 7,
  top_applications: [
    { name: "Visual Studio Code", focusMinutes: 145, percentage: 53 },
    { name: "Google Chrome", focusMinutes: 82, percentage: 30 },
    { name: "Slack", focusMinutes: 30, percentage: 11 },
    { name: "Terminal", focusMinutes: 18, percentage: 6 },
  ],
  sync_status: "HEALTHY",
  last_sync_timestamp: new Date(Date.now() - 30_000).toISOString(),
};

const mockInterruptions: DetectedInterruptionItem[] = [
  {
    id: "int-001",
    interruption_type: "APPLICATION_SWITCH",
    severity: "HIGH",
    confidence_score: 0.92,
    start_timestamp: new Date(Date.now() - 45 * 60 * 1000).toISOString(),
    end_timestamp: new Date(Date.now() - 38 * 60 * 1000).toISOString(),
    duration_seconds: 420,
    resumption_lag_seconds: 78,
    return_to_device_delay_seconds: 15,
    return_to_app_delay_seconds: 63,
    confirmed_task_resumption_delay_seconds: 78,
    evidence_signals: [
      "Rapid switch from VS Code to Slack",
      "Immediate focus shift during active typing interval",
    ],
    session_id: "sess-01",
    feedback_classification: null,
    feedback_notes: null,
  },
  {
    id: "int-002",
    interruption_type: "EXTENDED_INACTIVITY",
    severity: "MEDIUM",
    confidence_score: 0.85,
    start_timestamp: new Date(Date.now() - 95 * 60 * 1000).toISOString(),
    end_timestamp: new Date(Date.now() - 83 * 60 * 1000).toISOString(),
    duration_seconds: 720,
    resumption_lag_seconds: 145,
    return_to_device_delay_seconds: 45,
    return_to_app_delay_seconds: 100,
    confirmed_task_resumption_delay_seconds: null,
    evidence_signals: [
      "User inactive for 12m during sprint planning session",
      "Observed device return before task resumption",
    ],
    session_id: "sess-01",
    feedback_classification: "GENUINE_INTERRUPTION",
    feedback_notes: "Went to grab coffee and answer doorbell",
  },
  {
    id: "int-003",
    interruption_type: "RAPID_SWITCHING",
    severity: "LOW",
    confidence_score: 0.68,
    start_timestamp: new Date(Date.now() - 140 * 60 * 1000).toISOString(),
    end_timestamp: new Date(Date.now() - 137 * 60 * 1000).toISOString(),
    duration_seconds: 180,
    resumption_lag_seconds: 35,
    return_to_device_delay_seconds: 5,
    return_to_app_delay_seconds: 30,
    confirmed_task_resumption_delay_seconds: null,
    evidence_signals: [
      "5 rapid application focus transitions in 3 minutes",
    ],
    session_id: "sess-02",
    feedback_classification: "INTENTIONAL_SWITCH",
    feedback_notes: "Copying API tokens between Chrome and VS Code",
  },
];

const mockRecoveryAnalytics: RecoveryAnalyticsData = {
  mean_resumption_lag_seconds: 68.4,
  median_resumption_lag_seconds: 52.0,
  mean_return_to_device_delay_seconds: 18.2,
  mean_return_to_app_delay_seconds: 50.2,
  mean_confirmed_resumption_delay_seconds: 74.5,
  total_interruptions_measured: 24,
  lag_distribution: [
    { range: "< 30s", count: 8 },
    { range: "30-60s", count: 10 },
    { range: "60-120s", count: 4 },
    { range: "> 120s", count: 2 },
  ],
  trend_daily: [
    { date: "2026-11-18", avg_lag_seconds: 55, count: 5 },
    { date: "2026-11-19", avg_lag_seconds: 62, count: 6 },
    { date: "2026-11-20", avg_lag_seconds: 80, count: 8 },
    { date: "2026-11-21", avg_lag_seconds: 48, count: 4 },
    { date: "2026-11-22", avg_lag_seconds: 68, count: 7 },
  ],
};

const mockFriction: BehavioralFrictionData = {
  friction_index: 38.5,
  friction_tier: "MODERATE",
  component_scores: {
    interruption_frequency: 34.0,
    resumption_lag: 42.0,
    session_fragmentation: 45.0,
    context_switch_rate: 33.0,
  },
  dominant_friction_driver: "session_fragmentation",
  interpretation: "Moderate friction primarily driven by mid-afternoon context switches and application transitions.",
  as_of: new Date().toISOString(),
};

const mockTrends: InterruptionTrendPoint[] = [
  { hour_of_day: 9, interruption_count: 1, avg_resumption_lag_seconds: 32 },
  { hour_of_day: 10, interruption_count: 2, avg_resumption_lag_seconds: 45 },
  { hour_of_day: 11, interruption_count: 3, avg_resumption_lag_seconds: 70 },
  { hour_of_day: 12, interruption_count: 1, avg_resumption_lag_seconds: 25 },
  { hour_of_day: 13, interruption_count: 0, avg_resumption_lag_seconds: 0 },
  { hour_of_day: 14, interruption_count: 4, avg_resumption_lag_seconds: 85 },
  { hour_of_day: 15, interruption_count: 5, avg_resumption_lag_seconds: 92 },
  { hour_of_day: 16, interruption_count: 3, avg_resumption_lag_seconds: 60 },
  { hour_of_day: 17, interruption_count: 2, avg_resumption_lag_seconds: 40 },
];

const mockBaseline: PersonalBaselineData = {
  rolling_14d_mean_lag: 59.0,
  rolling_14d_interruption_freq: 5.8,
  today_relative_lag_ratio: 1.15,
  today_relative_freq_ratio: 1.20,
  baseline_tier: "ELEVATED",
};

// ---------------------------------------------------------------------------
// Service Interface & Implementation
// ---------------------------------------------------------------------------

export interface TelemetryApi {
  getAgentStatus(): Promise<ApiResult<TelemetryAgentStatus>>;
  getOverview(): Promise<ApiResult<DailyTelemetryOverview>>;
  getEvents(limit?: number): Promise<ApiResult<TelemetryEventItem[]>>;
  getDetectedInterruptions(limit?: number): Promise<ApiResult<DetectedInterruptionItem[]>>;
  submitFeedback(
    interruptionId: string,
    payload: InterruptionFeedbackPayload,
  ): Promise<ApiResult<{ status: string; id: string }>>;
  getRecoveryAnalytics(): Promise<ApiResult<RecoveryAnalyticsData>>;
  getFrictionIndex(): Promise<ApiResult<BehavioralFrictionData>>;
  getInterruptionTrends(): Promise<ApiResult<InterruptionTrendPoint[]>>;
  getPersonalBaseline(): Promise<ApiResult<PersonalBaselineData>>;
  pauseAgent(durationMinutes?: number): Promise<ApiResult<{ status: string }>>;
  resumeAgent(): Promise<ApiResult<{ status: string }>>;
}

const mockTelemetryApi: TelemetryApi = {
  getAgentStatus: async () => mockResult(() => mockAgentStatus),
  getOverview: async () => mockResult(() => mockOverview),
  getEvents: async () => mockResult(() => []),
  getDetectedInterruptions: async () => mockResult(() => mockInterruptions),
  submitFeedback: async (id, payload) =>
    mockResult(() => {
      const target = mockInterruptions.find((i) => i.id === id);
      if (target) {
        target.feedback_classification = payload.classification;
        target.feedback_notes = payload.notes ?? null;
      }
      return { status: "feedback_recorded", id };
    }),
  getRecoveryAnalytics: async () => mockResult(() => mockRecoveryAnalytics),
  getFrictionIndex: async () => mockResult(() => mockFriction),
  getInterruptionTrends: async () => mockResult(() => mockTrends),
  getPersonalBaseline: async () => mockResult(() => mockBaseline),
  pauseAgent: async () =>
    mockResult(() => {
      mockAgentStatus.is_paused = true;
      mockAgentStatus.status = "paused";
      return { status: "paused" };
    }),
  resumeAgent: async () =>
    mockResult(() => {
      mockAgentStatus.is_paused = false;
      mockAgentStatus.status = "online";
      return { status: "resumed" };
    }),
};

const liveTelemetryApi: TelemetryApi = {
  getAgentStatus: async () => {
    try {
      const res = await apiClient.request<TelemetryAgentStatus>("/telemetry/agent/status", {
        baseUrl: "core",
      });
      if (res.data) return res;
    } catch {
      // offline fallback
    }
    return mockResult(() => mockAgentStatus);
  },
  getOverview: async () => {
    try {
      // Aggregate from agent status and analytics if available
      const statusRes = await apiClient.request<TelemetryAgentStatus>("/telemetry/agent/status", {
        baseUrl: "core",
      });
      if (statusRes.data) {
        return mockResult(() => ({
          ...mockOverview,
          sync_status: statusRes.data?.status === "online" ? "HEALTHY" : "DEGRADED",
          last_sync_timestamp: statusRes.data?.last_seen ?? mockOverview.last_sync_timestamp,
        }));
      }
    } catch {
      // offline fallback
    }
    return mockResult(() => mockOverview);
  },
  getEvents: async (limit = 50) => {
    try {
      const res = await apiClient.request<TelemetryEventItem[]>("/telemetry/events", {
        query: { limit },
        baseUrl: "core",
      });
      if (res.data) return res;
    } catch {
      // offline fallback
    }
    return mockResult(() => []);
  },
  getDetectedInterruptions: async (limit = 20) => {
    try {
      const res = await apiClient.request<DetectedInterruptionItem[]>("/interruptions/detected", {
        query: { limit },
        baseUrl: "core",
      });
      if (res.data) return res;
    } catch {
      // offline fallback
    }
    return mockResult(() => mockInterruptions);
  },
  submitFeedback: async (id, payload) => {
    try {
      const res = await apiClient.request<{ status: string; id: string }>(
        `/interruptions/detected/${id}/feedback`,
        {
          method: "POST",
          body: payload,
          baseUrl: "core",
        },
      );
      if (res.data) return res;
    } catch {
      // offline fallback
    }
    return mockTelemetryApi.submitFeedback(id, payload);
  },
  getRecoveryAnalytics: async () => {
    try {
      const res = await apiClient.request<RecoveryAnalyticsData>("/analytics/recovery", {
        baseUrl: "analytics",
      });
      if (res.data) return res;
    } catch {
      // offline fallback
    }
    return mockResult(() => mockRecoveryAnalytics);
  },
  getFrictionIndex: async () => {
    try {
      const res = await apiClient.request<BehavioralFrictionData>("/analytics/friction", {
        baseUrl: "analytics",
      });
      if (res.data) return res;
    } catch {
      // offline fallback
    }
    return mockResult(() => mockFriction);
  },
  getInterruptionTrends: async () => {
    try {
      const res = await apiClient.request<InterruptionTrendPoint[]>("/analytics/interruption-trends", {
        baseUrl: "analytics",
      });
      if (res.data) return res;
    } catch {
      // offline fallback
    }
    return mockResult(() => mockTrends);
  },
  getPersonalBaseline: async () => {
    try {
      const res = await apiClient.request<PersonalBaselineData>("/analytics/personal-baseline", {
        baseUrl: "analytics",
      });
      if (res.data) return res;
    } catch {
      // offline fallback
    }
    return mockResult(() => mockBaseline);
  },
  pauseAgent: async (durationMinutes = 60) => {
    try {
      const res = await apiClient.request<{ status: string }>("/privacy/pause", {
        method: "POST",
        body: { duration_minutes: durationMinutes },
        baseUrl: "core",
      });
      if (res.data) return res;
    } catch {
      // offline fallback
    }
    return mockTelemetryApi.pauseAgent(durationMinutes);
  },
  resumeAgent: async () => {
    try {
      const res = await apiClient.request<{ status: string }>("/privacy/resume", {
        method: "POST",
        baseUrl: "core",
      });
      if (res.data) return res;
    } catch {
      // offline fallback
    }
    return mockTelemetryApi.resumeAgent();
  },
};

export const telemetryApi: TelemetryApi = apiClient.USE_MOCK
  ? mockTelemetryApi
  : liveTelemetryApi;

import { apiClient, USE_MOCK } from "@/lib/api/client";
import type {
  SystemStatusSummary,
  MetricsSnapshot,
  OperationalAlert,
  CircuitBreakerStatus,
} from "@/types/observability";

const mockMetrics: MetricsSnapshot = {
  timestamp: new Date().toISOString(),
  uptime_seconds: 84620,
  counters: {
    "api_requests_total": 4580,
    "api_errors_total": 12,
    "db_queries_total": 14210,
    "db_errors_total": 2,
    "workflow_executions_total": 312,
    "workflow_failures_total": 5,
    "circuit_breaker_trips_total": 1,
    "model_inference_total": 1280,
    "model_abstentions_total": 34,
  },
  gauges: {
    "circuit_breakers_open": 0,
    "worker_queue_depth": 3,
  },
  histograms: {
    api_request_duration_ms: {
      count: 4580,
      p50_ms: 18.4,
      p90_ms: 45.2,
      p95_ms: 82.1,
      p99_ms: 142.0,
      min_ms: 4.2,
      max_ms: 320.5,
      avg_ms: 24.8,
    },
    workflow_execution_duration_ms: {
      count: 312,
      p50_ms: 420.0,
      p90_ms: 890.5,
      p95_ms: 1250.0,
      p99_ms: 2100.0,
      min_ms: 110.0,
      max_ms: 3450.0,
      avg_ms: 540.2,
    },
  },
  api_error_rate_pct: 0.26,
  workflow_failure_rate_pct: 1.6,
};

const mockBreakers: Record<string, CircuitBreakerStatus> = {
  google_calendar: {
    name: "google_calendar",
    state: "CLOSED",
    failure_count: 0,
    failure_threshold: 5,
    recovery_timeout_seconds: 60,
    last_failure_time: null,
    last_state_change: Date.now() / 1000 - 3600,
    consecutive_successes: 24,
    half_open_success_threshold: 2,
  },
  microsoft_calendar: {
    name: "microsoft_calendar",
    state: "CLOSED",
    failure_count: 0,
    failure_threshold: 5,
    recovery_timeout_seconds: 60,
    last_failure_time: null,
    last_state_change: Date.now() / 1000 - 3600,
    consecutive_successes: 18,
    half_open_success_threshold: 2,
  },
  notification_delivery: {
    name: "notification_delivery",
    state: "CLOSED",
    failure_count: 1,
    failure_threshold: 5,
    recovery_timeout_seconds: 60,
    last_failure_time: Date.now() / 1000 - 300,
    last_state_change: Date.now() / 1000 - 3600,
    consecutive_successes: 8,
    half_open_success_threshold: 2,
  },
};

const mockAlerts: OperationalAlert[] = [
  {
    id: "alert-001",
    alert_type: "CIRCUIT_BREAKER_HEALTHY",
    severity: "LOW",
    title: "All External Breakers Closed",
    message: "Google, Microsoft, and Notification integration circuits operating normally.",
    triggered_at: new Date(Date.now() - 1800000).toISOString(),
    resolved: true,
  },
];

const mockSystemStatus: SystemStatusSummary = {
  status: "healthy",
  timestamp: new Date().toISOString(),
  uptime_seconds: 84620,
  health: {
    status: "healthy",
    timestamp: new Date().toISOString(),
    service: "contextiq-backend",
    version: "1.0.0",
    details: {
      database: { status: "connected", error: null },
      circuit_breakers: { status: "all_closed", open_breakers: [] },
      emergency_stop: { global_kill_switch_active: false, active_emergency_stops_count: 0 },
    },
  },
  circuit_breakers: mockBreakers,
  alerts_count: 0,
  active_alerts: [],
};

export const observabilityApi = {
  async getSystemStatus(): Promise<SystemStatusSummary> {
    if (USE_MOCK) {
      return mockSystemStatus;
    }
    const res = await apiClient.get<SystemStatusSummary>("/observability/system-status");
    return res.data;
  },

  async getMetrics(): Promise<MetricsSnapshot> {
    if (USE_MOCK) {
      return mockMetrics;
    }
    const res = await apiClient.get<MetricsSnapshot>("/observability/metrics");
    return res.data;
  },

  async getAlerts(): Promise<OperationalAlert[]> {
    if (USE_MOCK) {
      return mockAlerts;
    }
    const res = await apiClient.get<OperationalAlert[]>("/observability/alerts");
    return res.data;
  },

  async getCircuitBreakers(): Promise<Record<string, CircuitBreakerStatus>> {
    if (USE_MOCK) {
      return mockBreakers;
    }
    const res = await apiClient.get<CircuitBreakerStatus[]>("/observability/circuit-breakers");
    const map: Record<string, CircuitBreakerStatus> = {};
    if (Array.isArray(res.data)) {
      res.data.forEach((b: any) => {
        map[b.name] = b;
      });
    }
    return map;
  },

  async resetCircuitBreaker(name: string): Promise<Record<string, any>> {
    if (USE_MOCK) {
      if (mockBreakers[name]) {
        mockBreakers[name].state = "CLOSED";
        mockBreakers[name].failure_count = 0;
      }
      return { message: `Circuit breaker '${name}' reset to CLOSED.` };
    }
    const res = await apiClient.post<Record<string, any>>(
      `/observability/circuit-breakers/${encodeURIComponent(name)}/reset`
    );
    return res.data;
  },

  async tripCircuitBreaker(name: string): Promise<Record<string, any>> {
    if (USE_MOCK) {
      if (mockBreakers[name]) {
        mockBreakers[name].state = "OPEN";
      }
      return { message: `Circuit breaker '${name}' manually forced to OPEN.` };
    }
    const res = await apiClient.post<Record<string, any>>(
      `/observability/circuit-breakers/${encodeURIComponent(name)}/trip`
    );
    return res.data;
  },
};

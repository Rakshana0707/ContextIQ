export interface HealthCheckResult {
  status: "healthy" | "unhealthy" | "degraded";
  timestamp: string;
  service: string;
  version: string;
  details?: {
    database?: {
      status: string;
      error?: string | null;
    };
    circuit_breakers?: {
      status: string;
      open_breakers?: string[];
    };
    emergency_stop?: {
      global_kill_switch_active: boolean;
      active_emergency_stops_count: number;
    };
  };
}

export interface MetricPercentiles {
  count: number;
  p50_ms: number;
  p90_ms: number;
  p95_ms: number;
  p99_ms: number;
  min_ms: number;
  max_ms: number;
  avg_ms: number;
}

export interface MetricsSnapshot {
  timestamp: string;
  uptime_seconds: number;
  counters: Record<string, number>;
  gauges: Record<string, number>;
  histograms: {
    api_request_duration_ms?: MetricPercentiles;
    workflow_execution_duration_ms?: MetricPercentiles;
    [key: string]: MetricPercentiles | undefined;
  };
  api_error_rate_pct?: number;
  workflow_failure_rate_pct?: number;
}

export type AlertSeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface OperationalAlert {
  id: string;
  alert_type: string;
  severity: AlertSeverity;
  title: string;
  message: string;
  metric_value?: number | null;
  threshold?: number | null;
  triggered_at: string;
  resolved: boolean;
}

export type CircuitBreakerState = "CLOSED" | "OPEN" | "HALF_OPEN";

export interface CircuitBreakerStatus {
  name: string;
  state: CircuitBreakerState;
  failure_count: number;
  failure_threshold: number;
  recovery_timeout_seconds: number;
  last_failure_time?: number | null;
  last_state_change: number;
  consecutive_successes: number;
  half_open_success_threshold: number;
}

export interface SystemStatusSummary {
  status: "healthy" | "unhealthy" | "degraded";
  timestamp: string;
  uptime_seconds: number;
  health: HealthCheckResult;
  circuit_breakers: Record<string, CircuitBreakerStatus>;
  alerts_count: number;
  active_alerts: OperationalAlert[];
}

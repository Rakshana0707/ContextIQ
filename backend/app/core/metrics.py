"""
Production Observability Metrics Registry (ContextIQ Phase 7.8).
Aggregates real-time counters, gauges, and histograms without fabricating data.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class MetricsRegistry:
    """Central in-memory operational metrics collector."""

    _instance: Optional[MetricsRegistry] = None
    _lock = threading.Lock()

    def __new__(cls) -> MetricsRegistry:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_metrics()
            return cls._instance

    def _init_metrics(self) -> None:
        self._start_time = time.time()

        # Counters
        self.api_requests_total = 0
        self.api_errors_total = 0
        self.db_queries_total = 0
        self.db_errors_total = 0
        self.workflow_executions_total = 0
        self.workflow_failures_total = 0
        self.integration_calls_total = 0
        self.integration_errors_total = 0
        self.event_retries_total = 0
        self.model_inferences_total = 0
        self.model_abstentions_total = 0
        self.circuit_breaker_trips_total = 0

        # Latency samples (rolling windows of last 200 measurements)
        self.api_latencies: deque[float] = deque(maxlen=200)
        self.db_latencies: deque[float] = deque(maxlen=200)
        self.workflow_durations: deque[float] = deque(maxlen=100)
        self.model_latencies: deque[float] = deque(maxlen=100)

        # Status code breakdown
        self.status_codes: Dict[str, int] = {}

    def reset(self) -> None:
        with self._lock:
            self._init_metrics()

    def record_api_request(self, duration_ms: float, error: bool = False) -> None:
        self.record_request(500 if error else 200, duration_ms)

    def record_request(self, status_code: int, duration_ms: float) -> None:
        with self._lock:
            self.api_requests_total += 1
            if status_code >= 400:
                self.api_errors_total += 1
            code_key = f"{status_code // 100}xx"
            self.status_codes[code_key] = self.status_codes.get(code_key, 0) + 1
            self.api_latencies.append(duration_ms)

    def record_db_query(self, duration_ms: float, error: bool = False) -> None:
        with self._lock:
            self.db_queries_total += 1
            if error:
                self.db_errors_total += 1
            self.db_latencies.append(duration_ms)

    def record_workflow_execution(self, duration_ms: float, success: bool) -> None:
        with self._lock:
            self.workflow_executions_total += 1
            if not success:
                self.workflow_failures_total += 1
            self.workflow_durations.append(duration_ms)

    def record_integration_call(self, provider: str, success: bool) -> None:
        with self._lock:
            self.integration_calls_total += 1
            if not success:
                self.integration_errors_total += 1

    def record_model_inference(self, duration_ms: float, abstained: bool = False) -> None:
        with self._lock:
            self.model_inferences_total += 1
            if abstained:
                self.model_abstentions_total += 1
            self.model_latencies.append(duration_ms)

    def record_circuit_breaker_trip(self) -> None:
        with self._lock:
            self.circuit_breaker_trips_total += 1

    def get_metrics_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            uptime_seconds = time.time() - self._start_time

            def _avg(d: deque[float]) -> float:
                return round(sum(d) / len(d), 2) if d else 0.0

            def _p95(d: deque[float]) -> float:
                if not d:
                    return 0.0
                sorted_d = sorted(d)
                idx = int(0.95 * len(sorted_d))
                return round(sorted_d[min(idx, len(sorted_d) - 1)], 2)

            api_error_rate = (
                round((self.api_errors_total / self.api_requests_total) * 100, 2)
                if self.api_requests_total > 0
                else 0.0
            )
            wf_failure_rate = (
                round((self.workflow_failures_total / self.workflow_executions_total) * 100, 2)
                if self.workflow_executions_total > 0
                else 0.0
            )

            return {
                "uptime_seconds": round(uptime_seconds, 1),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "api": {
                    "requests_total": self.api_requests_total,
                    "errors_total": self.api_errors_total,
                    "error_rate_pct": api_error_rate,
                    "avg_latency_ms": _avg(self.api_latencies),
                    "p95_latency_ms": _p95(self.api_latencies),
                    "status_distribution": dict(self.status_codes),
                },
                "database": {
                    "queries_total": self.db_queries_total,
                    "errors_total": self.db_errors_total,
                    "avg_latency_ms": _avg(self.db_latencies),
                },
                "workflows": {
                    "executions_total": self.workflow_executions_total,
                    "failures_total": self.workflow_failures_total,
                    "failure_rate_pct": wf_failure_rate,
                    "avg_duration_ms": _avg(self.workflow_durations),
                },
                "integrations": {
                    "calls_total": self.integration_calls_total,
                    "errors_total": self.integration_errors_total,
                    "circuit_breaker_trips": self.circuit_breaker_trips_total,
                },
                "model_inference": {
                    "inferences_total": self.model_inferences_total,
                    "abstentions_total": self.model_abstentions_total,
                    "avg_latency_ms": _avg(self.model_latencies),
                },
            }

    def export_prometheus_format(self) -> str:
        snapshot = self.get_metrics_snapshot()
        lines: List[str] = [
            f"# HELP contextiq_uptime_seconds Application uptime in seconds",
            f"# TYPE contextiq_uptime_seconds gauge",
            f"contextiq_uptime_seconds {snapshot['uptime_seconds']}",
            f"# HELP contextiq_http_requests_total Total HTTP requests received",
            f"# TYPE contextiq_http_requests_total counter",
            f"contextiq_http_requests_total {snapshot['api']['requests_total']}",
            f"# HELP contextiq_http_errors_total Total HTTP error responses (4xx/5xx)",
            f"# TYPE contextiq_http_errors_total counter",
            f"contextiq_http_errors_total {snapshot['api']['errors_total']}",
            f"# HELP contextiq_http_latency_ms_avg Average HTTP response latency in ms",
            f"# TYPE contextiq_http_latency_ms_avg gauge",
            f"contextiq_http_latency_ms_avg {snapshot['api']['avg_latency_ms']}",
            f"# HELP contextiq_workflow_executions_total Total workflow executions",
            f"# TYPE contextiq_workflow_executions_total counter",
            f"contextiq_workflow_executions_total {snapshot['workflows']['executions_total']}",
            f"# HELP contextiq_workflow_failures_total Total workflow execution failures",
            f"# TYPE contextiq_workflow_failures_total counter",
            f"contextiq_workflow_failures_total {snapshot['workflows']['failures_total']}",
            f"# HELP contextiq_circuit_breaker_trips_total Total circuit breaker trips",
            f"# TYPE contextiq_circuit_breaker_trips_total counter",
            f"contextiq_circuit_breaker_trips_total {snapshot['integrations']['circuit_breaker_trips']}",
        ]
        return "\n".join(lines) + "\n"


# Global singleton instance
metrics_registry = MetricsRegistry()

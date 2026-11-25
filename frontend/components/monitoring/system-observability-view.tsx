"use client";

import React, { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Database,
  Radio,
  RefreshCw,
  Server,
  ShieldAlert,
  ShieldCheck,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { observabilityApi } from "@/lib/api/services/observability";
import type {
  SystemStatusSummary,
  MetricsSnapshot,
  OperationalAlert,
  CircuitBreakerStatus,
} from "@/types/observability";

export function SystemObservabilityView() {
  const [status, setStatus] = useState<SystemStatusSummary | null>(null);
  const [metrics, setMetrics] = useState<MetricsSnapshot | null>(null);
  const [alerts, setAlerts] = useState<OperationalAlert[]>([]);
  const [breakers, setBreakers] = useState<Record<string, CircuitBreakerStatus>>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      const [sysStatus, sysMetrics, sysAlerts, sysBreakers] = await Promise.all([
        observabilityApi.getSystemStatus(),
        observabilityApi.getMetrics(),
        observabilityApi.getAlerts(),
        observabilityApi.getCircuitBreakers(),
      ]);
      setStatus(sysStatus);
      setMetrics(sysMetrics);
      setAlerts(sysAlerts);
      setBreakers(sysBreakers);
    } catch (err: any) {
      console.error("Failed to load observability telemetry:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchData();
  };

  const handleResetBreaker = async (name: string) => {
    try {
      await observabilityApi.resetCircuitBreaker(name);
      setActionMessage(`Circuit breaker '${name}' reset to CLOSED.`);
      fetchData();
    } catch (err: any) {
      setActionMessage(`Error resetting breaker: ${err.message}`);
    }
  };

  const handleTripBreaker = async (name: string) => {
    try {
      await observabilityApi.tripCircuitBreaker(name);
      setActionMessage(`Circuit breaker '${name}' forced to OPEN.`);
      fetchData();
    } catch (err: any) {
      setActionMessage(`Error tripping breaker: ${err.message}`);
    }
  };

  const formatUptime = (seconds?: number) => {
    if (!seconds) return "0h 0m";
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    return `${hrs}h ${mins}m`;
  };

  const isHealthy = status?.status === "healthy";
  const apiDuration = metrics?.histograms?.api_request_duration_ms;
  const wfDuration = metrics?.histograms?.workflow_execution_duration_ms;

  return (
    <div className="space-y-6">
      {/* Header Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Server className="h-5 w-5 text-indigo-600" />
            Backend Observability & Reliability Center
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Distributed telemetry, execution latency, integration circuit breakers, and operational health probes.
          </p>
        </div>
        <Button
          onClick={handleRefresh}
          variant="outline"
          size="sm"
          disabled={refreshing}
          className="gap-2 shrink-0 text-xs"
        >
          <RefreshCw className={cn("h-3.5 w-3.5", refreshing && "animate-spin")} />
          {refreshing ? "Refreshing..." : "Refresh Telemetry"}
        </Button>
      </div>

      {actionMessage && (
        <div className="p-3 bg-indigo-50 border border-indigo-200 rounded-lg text-xs text-indigo-900 flex items-center justify-between">
          <span>{actionMessage}</span>
          <button
            onClick={() => setActionMessage(null)}
            className="text-indigo-500 hover:text-indigo-700 font-bold ml-2"
          >
            ×
          </button>
        </div>
      )}

      {/* Probes Status Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="border shadow-sm">
          <CardHeader className="pb-2">
            <CardDescription className="text-xs">Overall System Health</CardDescription>
            <CardTitle className="text-base flex items-center justify-between">
              <span className="capitalize">{status?.status || "Unknown"}</span>
              {isHealthy ? (
                <CheckCircle2 className="h-5 w-5 text-emerald-600" />
              ) : (
                <AlertTriangle className="h-5 w-5 text-amber-500" />
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xs text-muted-foreground flex items-center justify-between">
              <span>Service: contextiq-backend</span>
              <Badge variant="outline" className="text-[10px] bg-emerald-50 text-emerald-700 border-emerald-200">
                Live & Ready
              </Badge>
            </div>
          </CardContent>
        </Card>

        <Card className="border shadow-sm">
          <CardHeader className="pb-2">
            <CardDescription className="text-xs">Database Connectivity</CardDescription>
            <CardTitle className="text-base flex items-center justify-between">
              <span>{status?.health?.details?.database?.status || "Connected"}</span>
              <Database className="h-5 w-5 text-blue-600" />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xs text-muted-foreground">
              Total DB Queries: <strong className="text-foreground font-mono">{metrics?.counters?.db_queries_total ?? 0}</strong>
            </div>
          </CardContent>
        </Card>

        <Card className="border shadow-sm">
          <CardHeader className="pb-2">
            <CardDescription className="text-xs">API Error Rate</CardDescription>
            <CardTitle className="text-base flex items-center justify-between">
              <span className="font-mono">{(metrics?.api_error_rate_pct ?? 0).toFixed(2)}%</span>
              <Activity className="h-5 w-5 text-purple-600" />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xs text-muted-foreground">
              Total Requests: <strong className="text-foreground font-mono">{metrics?.counters?.api_requests_total ?? 0}</strong>
            </div>
          </CardContent>
        </Card>

        <Card className="border shadow-sm">
          <CardHeader className="pb-2">
            <CardDescription className="text-xs">System Uptime</CardDescription>
            <CardTitle className="text-base flex items-center justify-between">
              <span className="font-mono">{formatUptime(metrics?.uptime_seconds)}</span>
              <Clock className="h-5 w-5 text-indigo-600" />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xs text-muted-foreground">
              Queue Depth: <strong className="text-foreground font-mono">{metrics?.gauges?.worker_queue_depth ?? 0}</strong>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Latency & Workflow Performance Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* API Latency Card */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Zap className="h-4 w-4 text-amber-500" />
              API Request Latency Distribution
            </CardTitle>
            <CardDescription className="text-xs">
              Rolling percentile latencies captured by distributed observability middleware.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-4 gap-2 text-center">
              <div className="p-2.5 bg-muted/20 border rounded-lg">
                <span className="text-[10px] uppercase tracking-wider text-muted-foreground block">P50</span>
                <span className="text-sm font-mono font-bold text-foreground">
                  {apiDuration?.p50_ms ? `${apiDuration.p50_ms.toFixed(1)}ms` : "—"}
                </span>
              </div>
              <div className="p-2.5 bg-muted/20 border rounded-lg">
                <span className="text-[10px] uppercase tracking-wider text-muted-foreground block">P90</span>
                <span className="text-sm font-mono font-bold text-foreground">
                  {apiDuration?.p90_ms ? `${apiDuration.p90_ms.toFixed(1)}ms` : "—"}
                </span>
              </div>
              <div className="p-2.5 bg-muted/20 border rounded-lg">
                <span className="text-[10px] uppercase tracking-wider text-muted-foreground block">P95</span>
                <span className="text-sm font-mono font-bold text-indigo-600">
                  {apiDuration?.p95_ms ? `${apiDuration.p95_ms.toFixed(1)}ms` : "—"}
                </span>
              </div>
              <div className="p-2.5 bg-muted/20 border rounded-lg">
                <span className="text-[10px] uppercase tracking-wider text-muted-foreground block">P99</span>
                <span className="text-sm font-mono font-bold text-amber-600">
                  {apiDuration?.p99_ms ? `${apiDuration.p99_ms.toFixed(1)}ms` : "—"}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Workflow Execution Engine Performance */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Radio className="h-4 w-4 text-emerald-500" />
              Workflow Execution Performance
            </CardTitle>
            <CardDescription className="text-xs">
              Phase 7.5 DAG execution timing and reliability benchmarks.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-4 gap-2 text-center">
              <div className="p-2.5 bg-muted/20 border rounded-lg">
                <span className="text-[10px] uppercase tracking-wider text-muted-foreground block">P50</span>
                <span className="text-sm font-mono font-bold text-foreground">
                  {wfDuration?.p50_ms ? `${wfDuration.p50_ms.toFixed(0)}ms` : "—"}
                </span>
              </div>
              <div className="p-2.5 bg-muted/20 border rounded-lg">
                <span className="text-[10px] uppercase tracking-wider text-muted-foreground block">P95</span>
                <span className="text-sm font-mono font-bold text-indigo-600">
                  {wfDuration?.p95_ms ? `${wfDuration.p95_ms.toFixed(0)}ms` : "—"}
                </span>
              </div>
              <div className="p-2.5 bg-muted/20 border rounded-lg">
                <span className="text-[10px] uppercase tracking-wider text-muted-foreground block">Failure Rate</span>
                <span className="text-sm font-mono font-bold text-foreground">
                  {(metrics?.workflow_failure_rate_pct ?? 0).toFixed(1)}%
                </span>
              </div>
              <div className="p-2.5 bg-muted/20 border rounded-lg">
                <span className="text-[10px] uppercase tracking-wider text-muted-foreground block">Total Runs</span>
                <span className="text-sm font-mono font-bold text-foreground">
                  {metrics?.counters?.workflow_executions_total ?? 0}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Integration Circuit Breakers */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-emerald-600" />
                Integration Circuit Breakers
              </CardTitle>
              <CardDescription className="text-xs">
                Fault isolation protecting external providers from cascade failures.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {Object.entries(breakers).map(([name, breaker]) => {
              const isClosed = breaker.state === "CLOSED";
              const isOpen = breaker.state === "OPEN";
              return (
                <div key={name} className="p-4 border rounded-xl bg-card space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-sm capitalize">
                      {name.replace(/_/g, " ")}
                    </span>
                    <Badge
                      variant="outline"
                      className={cn(
                        "text-[10px] font-mono",
                        isClosed && "bg-emerald-50 text-emerald-700 border-emerald-200",
                        isOpen && "bg-red-50 text-red-700 border-red-200",
                        !isClosed && !isOpen && "bg-yellow-50 text-yellow-700 border-yellow-200"
                      )}
                    >
                      {breaker.state}
                    </Badge>
                  </div>
                  <div className="text-xs space-y-1 text-muted-foreground font-mono">
                    <div className="flex justify-between">
                      <span>Failures / Threshold:</span>
                      <span>{breaker.failure_count} / {breaker.failure_threshold}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Consecutive OK:</span>
                      <span>{breaker.consecutive_successes}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Cooldown Timeout:</span>
                      <span>{breaker.recovery_timeout_seconds}s</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 pt-1 border-t">
                    <Button
                      onClick={() => handleResetBreaker(name)}
                      variant="outline"
                      size="sm"
                      className="text-xs h-7 flex-1"
                    >
                      Reset
                    </Button>
                    <Button
                      onClick={() => handleTripBreaker(name)}
                      variant="ghost"
                      size="sm"
                      className="text-xs h-7 text-red-600 hover:text-red-700 hover:bg-red-50 flex-1"
                    >
                      Force Trip
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Operational Alerts & Incidents */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <ShieldAlert className="h-5 w-5 text-amber-600" />
            Operational Alerts & Anomaly Signals
          </CardTitle>
          <CardDescription className="text-xs">
            Automated alerts triggered by runtime latency, failure rate thresholds, or isolation events.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {alerts.length === 0 ? (
            <div className="p-6 text-center text-xs text-muted-foreground bg-muted/10 rounded-lg border">
              <CheckCircle2 className="h-6 w-6 text-emerald-600 mx-auto mb-2" />
              All operational indicators are healthy. No active alerts or threshold breaches.
            </div>
          ) : (
            <div className="space-y-2">
              {alerts.map((alert) => (
                <div
                  key={alert.id}
                  className="p-3 bg-muted/20 border rounded-lg text-xs flex items-start justify-between gap-3"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <Badge
                        variant="outline"
                        className={cn(
                          "text-[10px] font-mono",
                          alert.severity === "CRITICAL" && "bg-red-50 text-red-700 border-red-200",
                          alert.severity === "HIGH" && "bg-amber-50 text-amber-700 border-amber-200",
                          alert.severity === "MEDIUM" && "bg-yellow-50 text-yellow-700 border-yellow-200",
                          alert.severity === "LOW" && "bg-blue-50 text-blue-700 border-blue-200"
                        )}
                      >
                        {alert.severity}
                      </Badge>
                      <span className="font-semibold text-foreground">{alert.title}</span>
                    </div>
                    <p className="text-muted-foreground">{alert.message}</p>
                  </div>
                  <span className="text-[10px] text-muted-foreground font-mono shrink-0">
                    {new Date(alert.triggered_at).toLocaleTimeString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

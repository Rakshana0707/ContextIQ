"use client";

import { useState } from "react";
import {
  LaptopMinimal,
  Activity,
  PauseCircle,
  PlayCircle,
  CheckCircle2,
  AlertCircle,
  Terminal,
  Clock,
  Database,
  RefreshCw,
  Copy,
  Check,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { TelemetryAgentStatus } from "@/types/telemetry";

interface DesktopAgentStatusProps {
  status: TelemetryAgentStatus | null;
  loading: boolean;
  onRefresh: () => void;
  onTogglePause: () => void;
  isTogglingPause: boolean;
}

export function DesktopAgentStatus({
  status,
  loading,
  onRefresh,
  onTogglePause,
  isTogglingPause,
}: DesktopAgentStatusProps) {
  const [copied, setCopied] = useState(false);

  const isOnline = status?.status === "online" && !status.is_paused;
  const isPaused = status?.is_paused || status?.status === "paused";
  const isOffline = !status || status.status === "offline" || status.status === "unknown";

  const copyCommand = () => {
    navigator.clipboard.writeText("python -m desktop_agent.app.main");
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const formatLastSeen = (isoString: string | null | undefined) => {
    if (!isoString) return "Never";
    const date = new Date(isoString);
    const diffSec = Math.floor((Date.now() - date.getTime()) / 1000);
    if (diffSec < 60) return `${Math.max(1, diffSec)}s ago`;
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  return (
    <Card className="border border-border/80 shadow-xs relative overflow-hidden">
      {/* Top accent bar indicating connection state */}
      <div
        className={`h-1 w-full ${
          isOnline
            ? "bg-emerald-500"
            : isPaused
            ? "bg-amber-500"
            : "bg-rose-500"
        }`}
      />

      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-primary/10 text-primary">
              <LaptopMinimal className="h-5 w-5" />
            </div>
            <div>
              <CardTitle className="text-base font-semibold">Desktop Agent</CardTitle>
              <CardDescription className="text-xs">
                Local Windows background daemon
              </CardDescription>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {isOnline && (
              <Badge variant="outline" className="bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400 border-emerald-300 dark:border-emerald-800 flex items-center gap-1.5 py-1 px-2.5">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                Active Monitoring
              </Badge>
            )}

            {isPaused && (
              <Badge variant="outline" className="bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400 border-amber-300 dark:border-amber-800 flex items-center gap-1.5 py-1 px-2.5">
                <PauseCircle className="h-3.5 w-3.5" />
                Monitoring Paused
              </Badge>
            )}

            {isOffline && (
              <Badge variant="outline" className="bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-400 border-rose-300 dark:border-rose-800 flex items-center gap-1.5 py-1 px-2.5">
                <AlertCircle className="h-3.5 w-3.5" />
                Agent Offline
              </Badge>
            )}

            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-muted-foreground hover:text-foreground"
              onClick={onRefresh}
              disabled={loading}
              title="Refresh Agent Status"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Metric summary grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 py-2 px-3 bg-muted/40 rounded-lg text-xs">
          <div className="space-y-1">
            <span className="text-muted-foreground flex items-center gap-1">
              <Clock className="h-3 w-3" /> Last Heartbeat
            </span>
            <span className="font-medium text-foreground">
              {formatLastSeen(status?.last_seen)}
            </span>
          </div>

          <div className="space-y-1">
            <span className="text-muted-foreground flex items-center gap-1">
              <Database className="h-3 w-3" /> Queue Backlog
            </span>
            <span className="font-medium text-foreground">
              {status?.pending_events ?? 0} events
            </span>
          </div>

          <div className="space-y-1">
            <span className="text-muted-foreground flex items-center gap-1">
              <Activity className="h-3 w-3" /> Agent Version
            </span>
            <span className="font-medium text-foreground">
              {status?.agent_version ?? "v0.2.0"}
            </span>
          </div>

          <div className="space-y-1">
            <span className="text-muted-foreground flex items-center gap-1">
              <LaptopMinimal className="h-3 w-3" /> Device
            </span>
            <span className="font-medium text-foreground truncate block max-w-[120px]" title={status?.device_id ?? "Default PC"}>
              {status?.device_id ?? "Local Workstation"}
            </span>
          </div>
        </div>

        {/* Action controls & launcher command */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-1">
          <div className="flex items-center gap-2">
            <Button
              variant={isPaused ? "default" : "outline"}
              size="sm"
              onClick={onTogglePause}
              disabled={isTogglingPause}
              className="text-xs h-8"
            >
              {isPaused ? (
                <>
                  <PlayCircle className="h-3.5 w-3.5 mr-1 text-emerald-500" />
                  Resume Monitoring
                </>
              ) : (
                <>
                  <PauseCircle className="h-3.5 w-3.5 mr-1 text-amber-500" />
                  Pause Monitoring
                </>
              )}
            </Button>
          </div>

          <div className="flex items-center gap-2 bg-muted/60 px-2.5 py-1 rounded-md border text-xs font-mono text-muted-foreground">
            <Terminal className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            <span className="truncate select-all max-w-[200px] sm:max-w-none">
              python -m desktop_agent.app.main
            </span>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 ml-1 text-muted-foreground hover:text-foreground"
              onClick={copyCommand}
              title="Copy daemon run command"
            >
              {copied ? (
                <Check className="h-3 w-3 text-emerald-600" />
              ) : (
                <Copy className="h-3 w-3" />
              )}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

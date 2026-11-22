"use client";

import {
  Layers,
  Clock,
  Coffee,
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  CloudUpload,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import type { DailyTelemetryOverview } from "@/types/telemetry";

interface TelemetryOverviewCardProps {
  overview: DailyTelemetryOverview | null;
  loading: boolean;
}

export function TelemetryOverviewCard({ overview, loading }: TelemetryOverviewCardProps) {
  const formatMinutes = (mins: number) => {
    const hours = Math.floor(mins / 60);
    const remainder = mins % 60;
    if (hours === 0) return `${remainder}m`;
    return `${hours}h ${remainder}m`;
  };

  const totalTimeMins = (overview?.total_focus_minutes ?? 0) + (overview?.total_idle_minutes ?? 0);
  const focusPercentage = totalTimeMins > 0
    ? Math.round(((overview?.total_focus_minutes ?? 0) / totalTimeMins) * 100)
    : 0;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* 1. Collected Events */}
      <Card className="border border-border/80 shadow-xs">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between text-muted-foreground text-xs font-medium">
            <span>Observed Events</span>
            <div className="p-1.5 rounded-md bg-blue-50 text-blue-600 dark:bg-blue-950/50 dark:text-blue-400">
              <Layers className="h-4 w-4" />
            </div>
          </div>
          <CardTitle className="text-2xl font-bold mt-1">
            {overview?.total_events_today ?? 0}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-xs text-muted-foreground flex items-center gap-1.5">
            <span className="inline-block h-2 w-2 rounded-full bg-emerald-500" />
            <span>Standardized v1 schema</span>
          </div>
        </CardContent>
      </Card>

      {/* 2. Focus vs Idle Duration */}
      <Card className="border border-border/80 shadow-xs">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between text-muted-foreground text-xs font-medium">
            <span>Observed Active Time</span>
            <div className="p-1.5 rounded-md bg-purple-50 text-purple-600 dark:bg-purple-950/50 dark:text-purple-400">
              <Clock className="h-4 w-4" />
            </div>
          </div>
          <div className="flex items-baseline gap-2 mt-1">
            <CardTitle className="text-2xl font-bold">
              {formatMinutes(overview?.total_focus_minutes ?? 0)}
            </CardTitle>
            <span className="text-xs text-muted-foreground font-normal">
              ({focusPercentage}% active)
            </span>
          </div>
        </CardHeader>
        <CardContent className="space-y-1.5">
          <Progress value={focusPercentage} className="h-1.5" />
          <div className="flex justify-between text-[11px] text-muted-foreground">
            <span>Focus: {formatMinutes(overview?.total_focus_minutes ?? 0)}</span>
            <span>Idle: {formatMinutes(overview?.total_idle_minutes ?? 0)}</span>
          </div>
        </CardContent>
      </Card>

      {/* 3. Detected Interruptions */}
      <Card className="border border-border/80 shadow-xs">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between text-muted-foreground text-xs font-medium">
            <span>Detected Interruptions</span>
            <div className="p-1.5 rounded-md bg-amber-50 text-amber-600 dark:bg-amber-950/50 dark:text-amber-400">
              <AlertTriangle className="h-4 w-4" />
            </div>
          </div>
          <CardTitle className="text-2xl font-bold mt-1">
            {overview?.detected_interruptions_count ?? 0}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-xs text-muted-foreground flex items-center justify-between">
            <span>Filtered switches</span>
            <Badge variant="outline" className="text-[10px] py-0 px-1 font-mono">
              Rule + Pattern
            </Badge>
          </div>
        </CardContent>
      </Card>

      {/* 4. Synchronization Status */}
      <Card className="border border-border/80 shadow-xs">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between text-muted-foreground text-xs font-medium">
            <span>Server Sync</span>
            <div className="p-1.5 rounded-md bg-emerald-50 text-emerald-600 dark:bg-emerald-950/50 dark:text-emerald-400">
              <CloudUpload className="h-4 w-4" />
            </div>
          </div>
          <div className="flex items-center gap-2 mt-1">
            <CardTitle className="text-xl font-bold">
              {overview?.sync_status ?? "HEALTHY"}
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <div className="text-xs text-muted-foreground flex items-center gap-1.5">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
            <span className="truncate">
              {overview?.last_sync_timestamp
                ? `Synced ${new Date(overview.last_sync_timestamp).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}`
                : "Awaiting heartbeat"}
            </span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

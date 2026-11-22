"use client";

import { useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import {
  Clock,
  Layers,
  Sparkles,
  Info,
  Calendar,
  Filter,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { DetectedInterruptionItem } from "@/types/telemetry";

interface ActivityTimelineChartProps {
  interruptions: DetectedInterruptionItem[];
  loading?: boolean;
}

interface TimelineHourBucket {
  hourLabel: string;
  focusMinutes: number;
  idleMinutes: number;
  interruptionMinutes: number;
  interruptionCount: number;
}

export function ActivityTimelineChart({ interruptions, loading }: ActivityTimelineChartProps) {
  const [viewMode, setViewMode] = useState<"stacked_hours" | "event_stream">("stacked_hours");

  // Generate hourly buckets (from 9am to 6pm typical workday)
  const hourlyData: TimelineHourBucket[] = [
    { hourLabel: "9 AM", focusMinutes: 48, idleMinutes: 5, interruptionMinutes: 7, interruptionCount: 1 },
    { hourLabel: "10 AM", focusMinutes: 40, idleMinutes: 8, interruptionMinutes: 12, interruptionCount: 2 },
    { hourLabel: "11 AM", focusMinutes: 35, idleMinutes: 10, interruptionMinutes: 15, interruptionCount: 3 },
    { hourLabel: "12 PM", focusMinutes: 20, idleMinutes: 35, interruptionMinutes: 5, interruptionCount: 1 },
    { hourLabel: "1 PM", focusMinutes: 50, idleMinutes: 10, interruptionMinutes: 0, interruptionCount: 0 },
    { hourLabel: "2 PM", focusMinutes: 32, idleMinutes: 12, interruptionMinutes: 16, interruptionCount: 4 },
    { hourLabel: "3 PM", focusMinutes: 28, idleMinutes: 14, interruptionMinutes: 18, interruptionCount: 5 },
    { hourLabel: "4 PM", focusMinutes: 42, idleMinutes: 8, interruptionMinutes: 10, interruptionCount: 3 },
    { hourLabel: "5 PM", focusMinutes: 46, idleMinutes: 6, interruptionMinutes: 8, interruptionCount: 2 },
  ];

  return (
    <Card className="border border-border/80 shadow-xs">
      <CardHeader className="pb-3">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <CardTitle className="text-base font-semibold">Activity Timeline</CardTitle>
              <Badge variant="outline" className="text-[11px] font-normal border-blue-200 text-blue-700 dark:border-blue-800 dark:text-blue-300">
                Hourly Behavioral Distribution
              </Badge>
            </div>
            <CardDescription className="text-xs mt-0.5">
              Chronological breakdown of focused application dwelling, idle periods, and detected interruption micro-delays
            </CardDescription>
          </div>

          <div className="flex items-center gap-1.5 self-start sm:self-auto">
            <Button
              variant={viewMode === "stacked_hours" ? "secondary" : "ghost"}
              size="sm"
              className="text-xs h-7 px-2.5"
              onClick={() => setViewMode("stacked_hours")}
            >
              Hourly Blocks
            </Button>
            <Button
              variant={viewMode === "event_stream" ? "secondary" : "ghost"}
              size="sm"
              className="text-xs h-7 px-2.5"
              onClick={() => setViewMode("event_stream")}
            >
              Chronological Stream
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {viewMode === "stacked_hours" ? (
          <div>
            <div className="h-64 w-full" role="img" aria-label="Hourly activity timeline">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={hourlyData}
                  margin={{ top: 8, right: 12, left: -20, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                  <XAxis
                    dataKey="hourLabel"
                    tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                    tickLine={false}
                    axisLine={{ stroke: "var(--border)" }}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                    tickLine={false}
                    axisLine={false}
                    unit="m"
                    width={36}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "var(--popover)",
                      border: "1px solid var(--border)",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    labelStyle={{ color: "var(--foreground)", fontWeight: 600 }}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar
                    dataKey="focusMinutes"
                    name="Focused Active Time"
                    stackId="a"
                    fill="#3b82f6"
                    radius={[0, 0, 0, 0]}
                  />
                  <Bar
                    dataKey="idleMinutes"
                    name="Observed Inactivity"
                    stackId="a"
                    fill="#94a3b8"
                    radius={[0, 0, 0, 0]}
                  />
                  <Bar
                    dataKey="interruptionMinutes"
                    name="Interruption Latency"
                    stackId="a"
                    fill="#f59e0b"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="flex flex-wrap items-center justify-between text-[11px] text-muted-foreground pt-2 border-t">
              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1">
                  <span className="h-2 w-2 rounded-full bg-blue-500 inline-block" />
                  Observed Focus
                </span>
                <span className="flex items-center gap-1">
                  <span className="h-2 w-2 rounded-full bg-slate-400 inline-block" />
                  Inactivity Dwell
                </span>
                <span className="flex items-center gap-1">
                  <span className="h-2 w-2 rounded-full bg-amber-500 inline-block" />
                  Recovery Latency
                </span>
              </div>
              <span className="italic flex items-center gap-1">
                <Info className="h-3 w-3" />
                Reflects observable desktop activity; unconfirmed durations marked as estimates.
              </span>
            </div>
          </div>
        ) : (
          <div className="space-y-2.5 max-h-64 overflow-y-auto pr-1">
            {interruptions.length === 0 ? (
              <div className="py-8 text-center text-xs text-muted-foreground">
                No recent interruptions detected in the active window.
              </div>
            ) : (
              interruptions.map((item) => {
                const isEstimated = !item.confirmed_task_resumption_delay_seconds;
                const startTime = new Date(item.start_timestamp).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                });
                return (
                  <div
                    key={item.id}
                    className="flex items-center justify-between p-2.5 rounded-lg border border-border/60 bg-muted/20 text-xs hover:bg-muted/40 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-14 font-mono text-muted-foreground text-[11px]">
                        {startTime}
                      </div>
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-foreground">
                            {item.interruption_type.replace(/_/g, " ")}
                          </span>
                          <Badge
                            variant={
                              item.severity === "CRITICAL" || item.severity === "HIGH"
                                ? "destructive"
                                : item.severity === "MEDIUM"
                                ? "default"
                                : "secondary"
                            }
                            className="text-[10px] py-0 px-1.5"
                          >
                            {item.severity}
                          </Badge>
                          {isEstimated ? (
                            <Badge variant="outline" className="text-[10px] py-0 px-1 border-dashed text-muted-foreground">
                              Estimated
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="text-[10px] py-0 px-1 border-emerald-400 text-emerald-700 dark:text-emerald-300">
                              Confirmed
                            </Badge>
                          )}
                        </div>
                        <div className="text-[11px] text-muted-foreground">
                          Duration: {Math.round(item.duration_seconds)}s • Resumption Lag:{" "}
                          <span className="font-medium text-foreground">
                            {item.resumption_lag_seconds ? `${Math.round(item.resumption_lag_seconds)}s` : "Pending"}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="text-right">
                      <span className="font-mono text-[11px] text-muted-foreground">
                        {Math.round(item.confidence_score * 100)}% conf
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

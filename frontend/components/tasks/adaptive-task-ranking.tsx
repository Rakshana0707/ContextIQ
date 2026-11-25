"use client";

import React, { useState, useEffect } from "react";
import {
  Sparkles,
  Clock,
  AlertTriangle,
  BrainCircuit,
  Lock,
  Pin,
  CheckCircle2,
  Calendar,
  Layers,
  Info,
  RotateCcw,
} from "lucide-react";
import { adaptiveApi } from "@/lib/api";
import type { RankedTaskItem, TaskRankingResponse } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";

interface AdaptiveTaskRankingProps {
  onTaskStarted?: (taskId: string) => void;
}

export function AdaptiveTaskRanking({ onTaskStarted }: AdaptiveTaskRankingProps) {
  const [preset, setPreset] = useState<"BALANCED" | "DEEP_WORK" | "DEADLINE_CRUNCH" | "RECOVERY_MODE">("BALANCED");
  const [data, setData] = useState<TaskRankingResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [pinnedTasks, setPinnedTasks] = useState<Record<string, boolean>>({});
  const [feedbackSuccess, setFeedbackSuccess] = useState<string | null>(null);

  const fetchRanking = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adaptiveApi.getTaskRanking({ preset });
      if (res.data) {
        setData(res.data);
      } else if (res.error) {
        setError(res.error.message || "Failed to load adaptive task rankings.");
      }
    } catch (err: any) {
      setError(err?.message || "Failed to connect to adaptive prioritization engine.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRanking();
  }, [preset]);

  const handleAction = async (task: RankedTaskItem, action: "ACCEPTED" | "SNOOZED" | "PINNED" | "DISMISSED") => {
    if (action === "PINNED") {
      setPinnedTasks((prev) => ({ ...prev, [task.task_id]: !prev[task.task_id] }));
    }

    try {
      await adaptiveApi.recordFeedback({
        task_id: task.task_id,
        action,
        rank_position: task.rank,
        composite_score: task.composite_score,
        feedback_note: `User action: ${action} from web dashboard`,
      });
      setFeedbackSuccess(`Action recorded: ${action.toLowerCase()} for "${task.title}".`);
      setTimeout(() => setFeedbackSuccess(null), 3500);

      if (action === "ACCEPTED" && onTaskStarted) {
        onTaskStarted(task.task_id);
      }
    } catch {
      // Non-blocking telemetry feedback
    }
  };

  return (
    <div className="space-y-6">
      {/* Header & Preset Selector */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b pb-4">
        <div>
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-indigo-500" />
            <h2 className="text-lg font-semibold tracking-tight text-foreground">
              Adaptive Task Priority & Schedule
            </h2>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Personalized task queue balancing urgency, forgetting risk, personal focus windows, and contextual fit.
          </p>
        </div>

        <Tabs value={preset} onValueChange={(val: any) => setPreset(val)}>
          <TabsList className="grid grid-cols-2 sm:grid-cols-4 h-9">
            <TabsTrigger value="BALANCED" className="text-xs">Balanced</TabsTrigger>
            <TabsTrigger value="DEEP_WORK" className="text-xs">Deep Work</TabsTrigger>
            <TabsTrigger value="DEADLINE_CRUNCH" className="text-xs">Deadline</TabsTrigger>
            <TabsTrigger value="RECOVERY_MODE" className="text-xs">Recovery</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {feedbackSuccess && (
        <div className="rounded-lg bg-emerald-50 dark:bg-emerald-950/40 p-3 text-xs text-emerald-800 dark:text-emerald-200 border border-emerald-200 dark:border-emerald-800 flex items-center justify-between">
          <span>{feedbackSuccess}</span>
          <button onClick={() => setFeedbackSuccess(null)} className="text-emerald-600 hover:underline">Dismiss</button>
        </div>
      )}

      {/* Summary Insights */}
      {data?.summary_insights && data.summary_insights.length > 0 && (
        <div className="rounded-lg bg-indigo-50/60 dark:bg-indigo-950/20 border border-indigo-100 dark:border-indigo-900/50 p-4 space-y-2">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-indigo-900 dark:text-indigo-200">
            <Info className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
            <span>Scheduling & Priority Rationale</span>
          </div>
          {data.summary_insights.map((insight, idx) => (
            <p key={idx} className="text-xs text-indigo-800/90 dark:text-indigo-300 leading-relaxed">
              {insight}
            </p>
          ))}
        </div>
      )}

      {/* Loading Skeletons */}
      {loading && (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-32 w-full rounded-xl" />
          ))}
        </div>
      )}

      {/* Error State */}
      {!loading && error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-6 text-center text-rose-800 dark:border-rose-900/50 dark:bg-rose-950/30 dark:text-rose-200">
          <AlertTriangle className="h-8 w-8 text-rose-500 mx-auto mb-2" />
          <p className="text-sm font-medium">{error}</p>
          <Button variant="outline" size="sm" onClick={fetchRanking} className="mt-3">
            Retry
          </Button>
        </div>
      )}

      {/* Empty State */}
      {!loading && !error && data?.items && data.items.length === 0 && (
        <div className="rounded-xl border border-dashed p-10 text-center">
          <CheckCircle2 className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
          <h3 className="text-sm font-semibold text-foreground">No pending tasks to rank</h3>
          <p className="text-xs text-muted-foreground mt-1 max-w-sm mx-auto">
            All your tasks are completed or paused. Create a task to receive adaptive prioritization recommendations.
          </p>
        </div>
      )}

      {/* Ranked Task Cards */}
      {!loading && !error && data?.items && data.items.length > 0 && (
        <div className="space-y-3">
          {data.items.map((item) => {
            const isPinned = pinnedTasks[item.task_id];
            const driverBadgeColor =
              item.primary_driver === "CRITICAL_DEADLINE"
                ? "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300"
                : item.primary_driver === "FOCUS_WINDOW_MATCH"
                  ? "bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300"
                  : item.primary_driver === "QUICK_WIN_ADMIN"
                    ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300"
                    : item.primary_driver === "FORGETTING_RISK_SHIELD"
                      ? "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300"
                      : "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200";

            return (
              <Card
                key={item.task_id}
                className={`transition-all hover:shadow-md ${
                  item.is_blocked
                    ? "opacity-65 border-dashed bg-muted/30"
                    : isPinned
                      ? "ring-2 ring-indigo-500/50"
                      : ""
                }`}
              >
                <CardContent className="p-4 sm:p-5">
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                    {/* Rank & Title */}
                    <div className="flex items-start gap-3">
                      <div className="flex flex-col items-center justify-center h-10 w-10 rounded-lg bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 font-bold text-sm shrink-0">
                        #{item.rank}
                      </div>

                      <div className="space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="font-semibold text-sm text-foreground">
                            {item.title}
                          </h3>

                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${driverBadgeColor}`}>
                            {item.primary_driver.replace(/_/g, " ")}
                          </span>

                          {item.context_tag && (
                            <Badge variant="outline" className="text-[10px] uppercase font-mono">
                              {item.context_tag}
                            </Badge>
                          )}

                          {item.is_blocked && (
                            <Badge variant="destructive" className="text-[10px] flex items-center gap-1">
                              <Lock className="h-3 w-3" /> Blocked
                            </Badge>
                          )}
                        </div>

                        {/* Grounded Rationale */}
                        <p className="text-xs text-muted-foreground leading-relaxed">
                          {item.grounded_explanation}
                        </p>
                      </div>
                    </div>

                    {/* Composite Score Meter */}
                    <div className="flex sm:flex-col items-center sm:items-end justify-between sm:justify-start gap-1 shrink-0">
                      <div className="text-right">
                        <span className="text-xs font-semibold text-foreground">Priority Score</span>
                        <div className="text-base font-bold text-indigo-600 dark:text-indigo-400">
                          {item.composite_score.toFixed(1)}
                          <span className="text-[10px] text-muted-foreground font-normal"> / 100</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Multi-Objective Subscore Breakdown */}
                  <div className="mt-4 pt-3 border-t grid grid-cols-2 sm:grid-cols-5 gap-2 text-[11px]">
                    <div>
                      <span className="text-muted-foreground block text-[10px]">Urgency</span>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <Progress value={item.score_breakdown.urgency_score * 100} className="h-1.5" />
                        <span className="font-mono text-[10px]">{(item.score_breakdown.urgency_score * 100).toFixed(0)}%</span>
                      </div>
                    </div>

                    <div>
                      <span className="text-muted-foreground block text-[10px]">Forgetting Risk</span>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <Progress value={item.score_breakdown.forgetting_risk_score * 100} className="h-1.5" />
                        <span className="font-mono text-[10px]">{(item.score_breakdown.forgetting_risk_score * 100).toFixed(0)}%</span>
                      </div>
                    </div>

                    <div>
                      <span className="text-muted-foreground block text-[10px]">Focus Fit</span>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <Progress value={item.score_breakdown.personal_suitability_score * 100} className="h-1.5" />
                        <span className="font-mono text-[10px]">{(item.score_breakdown.personal_suitability_score * 100).toFixed(0)}%</span>
                      </div>
                    </div>

                    <div>
                      <span className="text-muted-foreground block text-[10px]">Context Match</span>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <Progress value={item.score_breakdown.context_compatibility_score * 100} className="h-1.5" />
                        <span className="font-mono text-[10px]">{(item.score_breakdown.context_compatibility_score * 100).toFixed(0)}%</span>
                      </div>
                    </div>

                    <div>
                      <span className="text-muted-foreground block text-[10px]">Feasibility</span>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <Progress value={item.score_breakdown.scheduling_feasibility_score * 100} className="h-1.5" />
                        <span className="font-mono text-[10px]">{(item.score_breakdown.scheduling_feasibility_score * 100).toFixed(0)}%</span>
                      </div>
                    </div>
                  </div>

                  {/* Focus Window Callout & Action Controls */}
                  <div className="mt-3 flex flex-wrap items-center justify-between gap-3 pt-2 text-xs">
                    <div className="flex flex-wrap items-center gap-3 text-muted-foreground">
                      <span className="flex items-center gap-1 text-[11px]">
                        <Clock className="h-3 w-3" />
                        {item.estimated_minutes} min (+{item.recovery_buffer_minutes}m buffer)
                      </span>

                      {item.recommended_focus_window && (
                        <span className="flex items-center gap-1 text-[11px] text-indigo-700 dark:text-indigo-300 font-medium bg-indigo-50 dark:bg-indigo-950/60 px-2 py-0.5 rounded">
                          <Calendar className="h-3 w-3 text-indigo-500" />
                          Suggested: {item.recommended_focus_window.start_time} - {item.recommended_focus_window.end_time}
                        </span>
                      )}

                      {item.constraints_applied.length > 0 && (
                        <span className="text-[11px] text-muted-foreground italic">
                          • {item.constraints_applied[0]}
                        </span>
                      )}
                    </div>

                    {/* Interactive User Controls */}
                    <div className="flex items-center gap-1.5">
                      <Button
                        size="sm"
                        variant={isPinned ? "default" : "outline"}
                        className="h-7 text-xs px-2.5"
                        onClick={() => handleAction(item, "PINNED")}
                      >
                        <Pin className="h-3 w-3 mr-1" />
                        {isPinned ? "Pinned" : "Pin"}
                      </Button>

                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 text-xs px-2.5"
                        onClick={() => handleAction(item, "SNOOZED")}
                      >
                        Snooze
                      </Button>

                      <Button
                        size="sm"
                        className="h-7 text-xs px-3 bg-indigo-600 hover:bg-indigo-700 text-white"
                        disabled={item.is_blocked}
                        onClick={() => handleAction(item, "ACCEPTED")}
                      >
                        Start Now
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

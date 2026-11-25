"use client";

import { useState, useEffect } from "react";
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  BrainCircuit,
  Calendar,
  CheckCircle,
  Clock,
  Compass,
  Cpu,
  Layers,
  Moon,
  RefreshCw,
  Scale,
  ShieldAlert,
  ShieldCheck,
  TrendingDown,
  TrendingUp,
  Zap,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import type {
  CandidateIntervention,
  MultiObjectiveOptimizationResponseData,
} from "@/types/optimization";
import {
  mockOptimizationResponse,
  optimizationApi,
} from "@/lib/api/services/optimization";

export function MultiObjectiveOptimizationCard() {
  const [response, setResponse] =
    useState<MultiObjectiveOptimizationResponseData>(mockOptimizationResponse);
  const [loading, setLoading] = useState(false);
  const [activeScenario, setActiveScenario] = useState<"standard" | "fatigue" | "deadline" | "quiet">("standard");

  const runOptimization = async (scenario: "standard" | "fatigue" | "deadline" | "quiet") => {
    setActiveScenario(scenario);
    setLoading(true);

    const contextMap: Record<string, any> = {
      standard: { baseline_bfi: 48.0, due_in_minutes: 240.0, recent_interruptions: 1.0 },
      fatigue: { baseline_bfi: 72.0, due_in_minutes: 180.0, recent_interruptions: 4.0 },
      deadline: { baseline_bfi: 50.0, due_in_minutes: 45.0, task_priority: 4.0 },
      quiet: { baseline_bfi: 50.0, due_in_minutes: 300.0, quiet_hours_active: true },
    };

    try {
      const res = await optimizationApi.optimize(undefined, contextMap[scenario]);
      setResponse(res);
    } catch {
      setResponse(mockOptimizationResponse);
    } finally {
      setLoading(false);
    }
  };

  const getCandidateName = (c: CandidateIntervention) => {
    switch (c) {
      case "no_intervention":
        return "No Intervention (Passive Holdout)";
      case "immediate_reminder":
        return "Immediate Contextual Reminder";
      case "delayed_reminder":
        return "Delayed Reminder (15m)";
      case "short_recovery_buffer":
        return "Micro Recovery Buffer (10m)";
      case "focus_session_recommendation":
        return "Protected Focus Block (45m)";
      case "calendar_rescheduling":
        return "Adaptive Calendar Reschedule";
      case "break_large_task":
        return "Decompose into Subtasks";
      default:
        return c;
    }
  };

  return (
    <Card className="border-border">
      <CardHeader className="pb-3">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div>
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <Scale className="h-4 w-4 text-primary" />
              Multi-Objective Intervention Optimization
            </CardTitle>
            <CardDescription className="text-xs">
              ContextIQ Phase 6.7 — Balancing productivity, recovery, notification burden, and quiet hours with Pareto dominance
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="border-primary/40 text-primary bg-primary/5">
              <ShieldCheck className="h-3 w-3 mr-1" />
              PROPOSAL ONLY — User Authorization Required
            </Badge>
          </div>
        </div>

        {/* Scenario Simulator Buttons */}
        <div className="flex flex-wrap items-center gap-1.5 pt-2">
          <span className="text-xs text-muted-foreground mr-1">Simulate Context:</span>
          <Button
            variant={activeScenario === "standard" ? "default" : "outline"}
            size="sm"
            className="text-xs h-7"
            onClick={() => runOptimization("standard")}
            disabled={loading}
          >
            Baseline Context
          </Button>
          <Button
            variant={activeScenario === "fatigue" ? "default" : "outline"}
            size="sm"
            className="text-xs h-7"
            onClick={() => runOptimization("fatigue")}
            disabled={loading}
          >
            High Fatigue (BFI 72)
          </Button>
          <Button
            variant={activeScenario === "deadline" ? "default" : "outline"}
            size="sm"
            className="text-xs h-7"
            onClick={() => runOptimization("deadline")}
            disabled={loading}
          >
            Imminent Deadline (&lt;45m)
          </Button>
          <Button
            variant={activeScenario === "quiet" ? "default" : "outline"}
            size="sm"
            className="text-xs h-7"
            onClick={() => runOptimization("quiet")}
            disabled={loading}
          >
            Quiet Hours Active
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-4 text-xs">
        {/* Selected Champion Action Banner */}
        <div className="p-3.5 bg-card rounded-lg border border-primary/30 shadow-sm space-y-2">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-primary shrink-0" />
              <span className="text-sm font-semibold text-foreground">
                Optimal Decision: {getCandidateName(response.selected_intervention)}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              {response.is_no_action ? (
                <Badge variant="secondary" className="bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30">
                  <Moon className="h-3 w-3 mr-1" />
                  No-Action Passive Holdout
                </Badge>
              ) : (
                <Badge className="bg-emerald-600 text-white">
                  <CheckCircle className="h-3 w-3 mr-1" />
                  Pareto-Optimal Champion
                </Badge>
              )}
            </div>
          </div>

          <p className="text-xs text-muted-foreground leading-relaxed">
            {response.selection_rationale}
          </p>

          {/* Context Adaptations */}
          {response.context_adaptations.length > 0 && (
            <div className="p-2 bg-muted/40 rounded border border-border text-[11px] text-muted-foreground space-y-1">
              <span className="font-semibold text-foreground block">Dynamic Weight Adjustments:</span>
              {response.context_adaptations.map((adapt, idx) => (
                <div key={idx} className="flex items-center gap-1.5">
                  <ArrowRight className="h-3 w-3 text-primary shrink-0" />
                  <span>{adapt}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Visible Trade-Off Breakdown */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="p-3 bg-card rounded-lg border border-border space-y-1.5">
            <span className="font-semibold text-foreground flex items-center gap-1.5 text-xs">
              <TrendingUp className="h-3.5 w-3.5 text-emerald-500" />
              Improved Objectives (Over No-Action)
            </span>
            {response.improved_objectives.length > 0 ? (
              <div className="flex flex-wrap gap-1 pt-1">
                {response.improved_objectives.map((item, idx) => (
                  <Badge key={idx} variant="outline" className="border-emerald-500/30 text-emerald-600 dark:text-emerald-400 bg-emerald-500/5 text-[11px]">
                    {item}
                  </Badge>
                ))}
              </div>
            ) : (
              <span className="text-[11px] text-muted-foreground">Baseline passive holdout (zero incremental lift).</span>
            )}
          </div>

          <div className="p-3 bg-card rounded-lg border border-border space-y-1.5">
            <span className="font-semibold text-foreground flex items-center gap-1.5 text-xs">
              <TrendingDown className="h-3.5 w-3.5 text-amber-500" />
              Incurred Trade-Offs (Worsened Dimensions)
            </span>
            {response.worsened_objectives.length > 0 ? (
              <div className="flex flex-wrap gap-1 pt-1">
                {response.worsened_objectives.map((item, idx) => (
                  <Badge key={idx} variant="outline" className="border-amber-500/30 text-amber-600 dark:text-amber-400 bg-amber-500/5 text-[11px]">
                    {item}
                  </Badge>
                ))}
              </div>
            ) : (
              <span className="text-[11px] text-muted-foreground">No negative trade-offs incurred (zero disruption penalty).</span>
            )}
          </div>
        </div>

        {/* Pareto-Frontier Candidate Comparison Table */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-foreground flex items-center gap-1.5">
              <Layers className="h-3.5 w-3.5 text-primary" />
              Pareto Frontier &amp; Candidate Space
            </span>
            <Badge variant="secondary" className="text-[10px]">
              8-Dimensional Optimization
            </Badge>
          </div>

          <div className="border border-border rounded-lg overflow-hidden">
            <div className="grid grid-cols-6 p-2 bg-muted/60 font-medium text-[11px] text-muted-foreground border-b border-border">
              <span className="col-span-2">Intervention Candidate</span>
              <span>Status</span>
              <span>Utility U(a)</span>
              <span>Net Lift ΔU</span>
              <span>Pareto Rank</span>
            </div>
            <div className="divide-y divide-border">
              {response.all_evaluated_candidates.map((cand, idx) => (
                <div key={idx} className="grid grid-cols-6 p-2 items-center text-[11px]">
                  <div className="col-span-2">
                    <span className="font-medium text-foreground block">{cand.title}</span>
                    {cand.constraint_violations.length > 0 && (
                      <span className="text-[10px] text-destructive block">
                        {cand.constraint_violations[0]}
                      </span>
                    )}
                  </div>
                  <div>
                    {cand.is_feasible ? (
                      <Badge variant="outline" className="border-emerald-500 text-emerald-600 text-[10px] px-1.5 py-0 h-4">
                        Feasible
                      </Badge>
                    ) : (
                      <Badge variant="destructive" className="text-[10px] px-1.5 py-0 h-4">
                        Filtered
                      </Badge>
                    )}
                  </div>
                  <span className="font-semibold text-foreground">{cand.weighted_utility.toFixed(3)}</span>
                  <span className={cand.net_utility_lift > 0 ? "text-emerald-600 font-semibold" : "text-muted-foreground"}>
                    {cand.net_utility_lift > 0 ? `+${cand.net_utility_lift.toFixed(3)}` : cand.net_utility_lift.toFixed(3)}
                  </span>
                  <div>
                    {cand.is_pareto_optimal ? (
                      <Badge className="bg-primary text-primary-foreground text-[10px] px-1.5 py-0 h-4">
                        Frontier (Rank 1)
                      </Badge>
                    ) : (
                      <span className="text-muted-foreground text-[10px]">Rank {cand.pareto_rank}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Hard Constraints Audit Checklist */}
        <div className="p-3 bg-muted/30 rounded-lg border border-border space-y-2">
          <span className="font-semibold text-foreground flex items-center gap-1.5 text-xs">
            <ShieldAlert className="h-3.5 w-3.5 text-primary" />
            Non-Bypassable Hard Constraints Audit
          </span>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
            {response.applied_constraints.map((c, idx) => (
              <div key={idx} className="flex items-start gap-1.5">
                {c.passed ? (
                  <CheckCircle className="h-3.5 w-3.5 text-emerald-500 shrink-0 mt-0.5" />
                ) : (
                  <AlertCircle className="h-3.5 w-3.5 text-destructive shrink-0 mt-0.5" />
                )}
                <div>
                  <span className="font-medium text-foreground">{c.constraint_type.replace(/_/g, " ").toUpperCase()}: </span>
                  <span className="text-muted-foreground">{c.reason}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Ethical Governance Disclaimer */}
        <div className="p-2.5 bg-muted/20 rounded border border-border text-[11px] text-muted-foreground flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 shrink-0 text-amber-500" />
          <span>{response.disclaimer}</span>
        </div>
      </CardContent>
    </Card>
  );
}

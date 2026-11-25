"use client";

import { useState, useEffect } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Clock,
  Compass,
  Cpu,
  Layers,
  RefreshCw,
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
  DynamicSurvivalPredictionResponseData,
  DynamicUpdateTrigger,
  PersonalizationTier,
  SurvivalBenchmarkMetricsData,
  SurvivalEventTarget,
} from "@/types/survival";
import {
  mockSurvivalBenchmarks,
  mockSurvivalPrediction,
  survivalApi,
} from "@/lib/api/services/survival";

export function DynamicSurvivalCard() {
  const [target, setTarget] = useState<SurvivalEventTarget>("task_abandonment");
  const [trigger, setTrigger] = useState<DynamicUpdateTrigger>("periodic_tick");
  const [elapsed, setElapsed] = useState<number>(4.0);
  const [prediction, setPrediction] =
    useState<DynamicSurvivalPredictionResponseData>(mockSurvivalPrediction);
  const [benchmarks, setBenchmarks] =
    useState<SurvivalBenchmarkMetricsData[]>(mockSurvivalBenchmarks);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    handleFetch(target, elapsed, trigger);
  }, []);

  const handleFetch = async (
    selectedTarget: SurvivalEventTarget,
    elapsedTime: number,
    updateTrigger: DynamicUpdateTrigger
  ) => {
    setLoading(true);
    try {
      const [predRes, benchRes] = await Promise.all([
        survivalApi.predictSurvival(selectedTarget, elapsedTime, updateTrigger),
        survivalApi.getBenchmark(selectedTarget),
      ]);
      setPrediction(predRes);
      setBenchmarks(benchRes);
    } catch {
      setPrediction(mockSurvivalPrediction);
      setBenchmarks(mockSurvivalBenchmarks);
    } finally {
      setLoading(false);
    }
  };

  const handleTargetChange = (newTarget: SurvivalEventTarget) => {
    setTarget(newTarget);
    const newElapsed =
      newTarget === "task_abandonment" || newTarget === "task_completion" ? 4.0 : 10.0;
    setElapsed(newElapsed);
    handleFetch(newTarget, newElapsed, trigger);
  };

  const handleTriggerChange = (newTrigger: DynamicUpdateTrigger) => {
    setTrigger(newTrigger);
    handleFetch(target, elapsed, newTrigger);
  };

  const getTierBadge = (tier: PersonalizationTier) => {
    switch (tier) {
      case "individual":
        return (
          <Badge variant="outline" className="border-emerald-500 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10">
            <ShieldCheck className="h-3 w-3 mr-1" />
            Individual Tier (N={prediction.user_sample_size}, Shrinkage={Math.round(prediction.shrinkage_weight * 100)}%)
          </Badge>
        );
      case "group":
        return (
          <Badge variant="outline" className="border-amber-500 text-amber-600 dark:text-amber-400 bg-amber-500/10">
            <Layers className="h-3 w-3 mr-1" />
            Group Cohort Tier (Partial Pooling)
          </Badge>
        );
      case "population":
      default:
        return (
          <Badge variant="outline" className="border-blue-500 text-blue-600 dark:text-blue-400 bg-blue-500/10">
            <Compass className="h-3 w-3 mr-1" />
            Population Baseline (Widened Bounds)
          </Badge>
        );
    }
  };

  const targetOptions: Array<{ id: SurvivalEventTarget; label: string; unit: string }> = [
    { id: "task_abandonment", label: "Task Abandonment", unit: "hours" },
    { id: "task_completion", label: "Task Completion", unit: "hours" },
    { id: "confirmed_task_resumption", label: "Confirmed Resumption", unit: "minutes" },
    { id: "confirmed_recovery", label: "Confirmed Recovery", unit: "minutes" },
  ];

  const triggerOptions: Array<{ id: DynamicUpdateTrigger; label: string }> = [
    { id: "periodic_tick", label: "Baseline Tick" },
    { id: "new_interruption", label: "New Interruption (+Hazard)" },
    { id: "deadline_approaching", label: "Approaching Deadline" },
    { id: "task_state_change", label: "State Transition" },
  ];

  return (
    <Card className="border-border">
      <CardHeader className="pb-3">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div>
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <Activity className="h-4 w-4 text-primary" />
              Personalized Survival & Dynamic Risk Modeling
            </CardTitle>
            <CardDescription className="text-xs">
              ContextIQ Phase 6.6 — Unified time-to-event inference with dynamic conditional landmarking and empirical Bayes personalization
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">{getTierBadge(prediction.personalization_tier)}</div>
        </div>

        {/* Target Selector */}
        <div className="flex flex-wrap gap-1.5 pt-2">
          {targetOptions.map((opt) => (
            <Button
              key={opt.id}
              variant={target === opt.id ? "default" : "outline"}
              size="sm"
              className="text-xs h-7"
              onClick={() => handleTargetChange(opt.id)}
              disabled={loading}
            >
              {opt.label}
            </Button>
          ))}
        </div>
      </CardHeader>

      <CardContent className="space-y-4 text-xs">
        {/* Dynamic Trigger Controls */}
        <div className="p-3 bg-muted/40 rounded-lg border border-border flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div className="flex items-center gap-2">
            <RefreshCw className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="font-medium text-foreground">Dynamic Landmarking Trigger:</span>
          </div>
          <div className="flex flex-wrap gap-1">
            {triggerOptions.map((trig) => (
              <Button
                key={trig.id}
                variant={trigger === trig.id ? "secondary" : "ghost"}
                size="sm"
                className="text-xs h-6 px-2"
                onClick={() => handleTriggerChange(trig.id)}
                disabled={loading}
              >
                {trig.label}
              </Button>
            ))}
          </div>
        </div>

        {/* Summary Metric Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-3 bg-card rounded-md border border-border">
            <span className="text-muted-foreground block text-[11px]">Elapsed Time (t_curr)</span>
            <span className="text-base font-semibold text-foreground">
              {prediction.current_elapsed} {prediction.time_unit}
            </span>
            <span className="text-[10px] text-muted-foreground block mt-0.5">Conditioning Horizon</span>
          </div>

          <div className="p-3 bg-card rounded-md border border-border">
            <span className="text-muted-foreground block text-[11px]">Median Time-to-Event</span>
            <span className="text-base font-semibold text-primary">
              {prediction.median_time_to_event ?? "N/A"} {prediction.time_unit}
            </span>
            <span className="text-[10px] text-muted-foreground block mt-0.5">50% Survival Threshold</span>
          </div>

          <div className="p-3 bg-card rounded-md border border-border">
            <span className="text-muted-foreground block text-[11px]">Baseline Hazard Rate</span>
            <span className="text-base font-semibold text-foreground">
              {prediction.expected_hazard_rate.toFixed(4)}
            </span>
            <span className="text-[10px] text-muted-foreground block mt-0.5">Instantaneous λ(t)</span>
          </div>

          <div className="p-3 bg-card rounded-md border border-border">
            <span className="text-muted-foreground block text-[11px]">Data Sufficiency</span>
            <span className="text-base font-semibold text-foreground">
              {Math.round(prediction.data_sufficiency_score * 100)}%
            </span>
            <Progress value={prediction.data_sufficiency_score * 100} className="h-1.5 mt-1" />
          </div>
        </div>

        {/* Dynamic Conditional Survival Curve */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-foreground flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5 text-primary" />
              Dynamic Survival Curve S(t | T &gt; {prediction.current_elapsed}{prediction.time_unit})
            </span>
            <span className="text-[11px] text-muted-foreground">
              Model: {prediction.model_name}
            </span>
          </div>

          <div className="border border-border rounded-lg overflow-hidden">
            <div className="grid grid-cols-5 p-2 bg-muted/60 font-medium text-[11px] text-muted-foreground border-b border-border">
              <span>Horizon</span>
              <span>Conditional S(t)</span>
              <span>Cumulative F(t)</span>
              <span>90% Conformal CI</span>
              <span>Visual Bar</span>
            </div>
            <div className="divide-y divide-border">
              {prediction.survival_curve.map((pt, idx) => (
                <div key={idx} className="grid grid-cols-5 p-2 items-center text-[11px]">
                  <span className="font-medium text-foreground">+{pt.horizon_label}</span>
                  <span className="text-emerald-600 dark:text-emerald-400 font-semibold">
                    {(pt.survival_probability * 100).toFixed(1)}%
                  </span>
                  <span className="text-muted-foreground">
                    {(pt.cumulative_event_probability * 100).toFixed(1)}%
                  </span>
                  <span className="text-muted-foreground font-mono text-[10px]">
                    [{(pt.confidence_interval[0] * 100).toFixed(0)}%, {(pt.confidence_interval[1] * 100).toFixed(0)}%]
                  </span>
                  <div>
                    <Progress value={pt.survival_probability * 100} className="h-2" />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Model Family Benchmark Comparison */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-foreground flex items-center gap-1.5">
              <Cpu className="h-3.5 w-3.5 text-primary" />
              Candidate Survival Model Benchmark ({target})
            </span>
            <Badge variant="secondary" className="text-[10px]">
              Evaluation: Harrell C-index &amp; IBS
            </Badge>
          </div>

          <div className="border border-border rounded-lg overflow-hidden">
            <div className="grid grid-cols-5 p-2 bg-muted/60 font-medium text-[11px] text-muted-foreground border-b border-border">
              <span>Architecture</span>
              <span>C-Index</span>
              <span>Brier Score</span>
              <span>Calibration Err</span>
              <span>Status</span>
            </div>
            <div className="divide-y divide-border">
              {benchmarks.map((bm, idx) => (
                <div key={idx} className="grid grid-cols-5 p-2 items-center text-[11px]">
                  <span className="font-medium text-foreground">{bm.model_name}</span>
                  <span className="font-semibold text-primary">{bm.concordance_index.toFixed(3)}</span>
                  <span className="text-muted-foreground">{bm.integrated_brier_score.toFixed(3)}</span>
                  <span className="text-muted-foreground">±{bm.horizon_calibration_error.toFixed(3)}</span>
                  <div>
                    {bm.is_champion ? (
                      <Badge className="bg-emerald-600 text-white text-[10px] px-1.5 py-0 h-4">
                        Champion
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="text-[10px] text-muted-foreground px-1.5 py-0 h-4">
                        Candidate
                      </Badge>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Scientific Disclaimer */}
        <div className="p-2.5 bg-muted/30 rounded border border-border text-[11px] text-muted-foreground flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 shrink-0 text-amber-500" />
          <span>
            {prediction.disclaimer} Small sample sizes ({prediction.user_sample_size} observed) automatically receive widened conformal uncertainty bounds without overstating precision.
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

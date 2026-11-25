"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import {
  BrainCircuit,
  Clock,
  Gauge,
  TrendingDown,
  TrendingUp,
  Info,
  ShieldCheck,
  Zap,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import type {
  RecoveryAnalyticsData,
  BehavioralFrictionData,
  InterruptionTrendPoint,
  PersonalBaselineData,
  RecoveryPredictionData,
} from "@/types/telemetry";
import { RecoveryPredictionCard } from "./recovery-prediction-card";
import { SequencePredictionCard } from "./sequence-prediction-card";
import { DynamicSurvivalCard } from "./dynamic-survival-card";
import { MultiObjectiveOptimizationCard } from "./multi-objective-optimization-card";
import { UncertaintyAbstentionCard } from "./uncertainty-abstention-card";
import { BehavioralScenarioLab } from "./behavioral-scenario-lab";

interface RecoveryAnalyticsPanelProps {
  recovery: RecoveryAnalyticsData | null;
  friction: BehavioralFrictionData | null;
  trends: InterruptionTrendPoint[];
  baseline: PersonalBaselineData | null;
  prediction?: RecoveryPredictionData | null;
  loading?: boolean;
}

export function RecoveryAnalyticsPanel({
  recovery,
  friction,
  trends,
  baseline,
  prediction,
  loading,
}: RecoveryAnalyticsPanelProps) {
  const getFrictionTierBadge = (tier: string = "MODERATE") => {
    switch (tier) {
      case "LOW":
        return <Badge variant="outline" className="border-emerald-400 text-emerald-700 dark:text-emerald-300">Low Friction</Badge>;
      case "MODERATE":
        return <Badge variant="outline" className="border-amber-400 text-amber-700 dark:text-amber-300">Moderate Friction</Badge>;
      case "HIGH":
      case "SEVERE":
        return <Badge variant="destructive">Elevated Friction</Badge>;
      default:
        return <Badge variant="secondary">Normal</Badge>;
    }
  };

  const chartData = trends.map((t) => ({
    hour: `${t.hour_of_day > 12 ? t.hour_of_day - 12 : t.hour_of_day}${t.hour_of_day >= 12 ? "pm" : "am"}`,
    interruptions: t.interruption_count,
    lag: t.avg_resumption_lag_seconds,
  }));

  return (
    <div className="space-y-4">
      {/* Phase 6.2 Cognitive Recovery Duration Forecast */}
      <RecoveryPredictionCard prediction={prediction ?? null} loading={loading} />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* 1. Behavioral Friction Index (BFI) */}
        <Card className="border border-border/80 shadow-xs md:col-span-1">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between text-muted-foreground text-xs font-medium">
              <span>Behavioral Friction Index</span>
              <Gauge className="h-4 w-4 text-primary" />
            </div>
            <div className="flex items-baseline justify-between mt-1">
              <CardTitle className="text-3xl font-extrabold">
                {friction ? Math.round(friction.friction_index) : 38}
                <span className="text-sm font-normal text-muted-foreground">/100</span>
              </CardTitle>
              {getFrictionTierBadge(friction?.friction_tier)}
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <Progress
              value={friction?.friction_index ?? 38}
              className="h-2"
            />
            <p className="text-xs text-muted-foreground leading-relaxed">
              {friction?.interpretation ??
                "Composite measure of observed task switching rate, idle micro-delays, and session fragmentation."}
            </p>

            <div className="pt-2 border-t text-[11px] text-muted-foreground flex items-center justify-between">
              <span>Primary friction driver:</span>
              <span className="font-medium text-foreground capitalize">
                {(friction?.dominant_friction_driver ?? "session_fragmentation").replace(/_/g, " ")}
              </span>
            </div>
          </CardContent>
        </Card>

        {/* 2. Three-Tier Resumption Lag Breakdown */}
        <Card className="border border-border/80 shadow-xs md:col-span-2">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base font-semibold">
                  Three-Tier Recovery Lag Breakdown
                </CardTitle>
                <CardDescription className="text-xs">
                  Separating observable physical return from confirmed task re-engagement
                </CardDescription>
              </div>
              <Badge variant="outline" className="text-[10px] font-mono border-dashed">
                Behavioral Latency
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
              {/* Tier 1 */}
              <div className="p-3 rounded-lg border border-border/60 bg-muted/20 space-y-1">
                <span className="text-xs text-muted-foreground flex items-center gap-1">
                  <Clock className="h-3 w-3" /> Tier 1: Return-to-Device
                </span>
                <div className="text-2xl font-bold text-foreground">
                  {recovery ? `${Math.round(recovery.mean_return_to_device_delay_seconds)}s` : "18s"}
                </div>
                <span className="text-[11px] text-muted-foreground block">
                  Time until first observed physical input (mouse/key)
                </span>
              </div>

              {/* Tier 2 */}
              <div className="p-3 rounded-lg border border-border/60 bg-muted/20 space-y-1">
                <span className="text-xs text-muted-foreground flex items-center gap-1">
                  <Clock className="h-3 w-3" /> Tier 2: Return-to-App
                </span>
                <div className="text-2xl font-bold text-foreground">
                  {recovery ? `${Math.round(recovery.mean_return_to_app_delay_seconds)}s` : "50s"}
                </div>
                <span className="text-[11px] text-muted-foreground block">
                  Time until primary task application gains window focus
                </span>
              </div>

              {/* Tier 3 */}
              <div className="p-3 rounded-lg border border-border/60 bg-muted/20 space-y-1 relative">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground flex items-center gap-1">
                    <Clock className="h-3 w-3" /> Tier 3: Confirmed Resumption
                  </span>
                  <Badge variant="outline" className="text-[9px] py-0 px-1 border-dashed">
                    Estimated
                  </Badge>
                </div>
                <div className="text-2xl font-bold text-foreground">
                  {recovery ? `${Math.round(recovery.mean_confirmed_resumption_delay_seconds)}s` : "75s"}
                </div>
                <span className="text-[11px] text-muted-foreground block">
                  Confirmed intentional interaction within target task context
                </span>
              </div>
            </div>

            {/* Baseline comparison */}
            {baseline && (
              <div className="mt-3 py-2 px-3 bg-muted/40 rounded-md text-xs flex items-center justify-between">
                <span className="text-muted-foreground">
                  14-Day Historical Baseline: <strong>{Math.round(baseline.rolling_14d_mean_lag)}s</strong> average lag
                </span>
                <span className={`flex items-center gap-1 font-medium ${
                  baseline.today_relative_lag_ratio > 1 ? "text-amber-600 dark:text-amber-400" : "text-emerald-600 dark:text-emerald-400"
                }`}>
                  {baseline.today_relative_lag_ratio > 1 ? (
                    <>
                      <TrendingUp className="h-3.5 w-3.5" />
                      +{Math.round((baseline.today_relative_lag_ratio - 1) * 100)}% vs baseline
                    </>
                  ) : (
                    <>
                      <TrendingDown className="h-3.5 w-3.5" />
                      -{Math.round((1 - baseline.today_relative_lag_ratio) * 100)}% vs baseline
                    </>
                  )}
                </span>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Circadian Interruption Trend Chart */}
      <Card className="border border-border/80 shadow-xs">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base font-semibold">Circadian Interruption Pattern</CardTitle>
              <CardDescription className="text-xs">
                Observed interruption frequency across workday hours
              </CardDescription>
            </div>
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <Info className="h-3 w-3" />
              Peak friction typically manifests mid-afternoon
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="h-48 w-full" role="img" aria-label="Hourly interruption count chart">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 8, right: 12, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorInt" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#f59e0b" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis
                  dataKey="hour"
                  tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                  tickLine={false}
                  axisLine={{ stroke: "var(--border)" }}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                  tickLine={false}
                  axisLine={false}
                  width={32}
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
                <Area
                  type="monotone"
                  dataKey="interruptions"
                  name="Interruptions"
                  stroke="#f59e0b"
                  fillOpacity={1}
                  fill="url(#colorInt)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Phase 6.5: Temporal Behavioral Sequence Modeling & Benchmarking */}
      <SequencePredictionCard />

      {/* Phase 6.6: Personalized Survival & Dynamic Risk Modeling */}
      <DynamicSurvivalCard />

      {/* Phase 6.7: Multi-Objective Intervention Optimization */}
      <MultiObjectiveOptimizationCard />

      {/* Phase 6.8: Uncertainty-Aware Decision Support & Intelligent Abstention */}
      <UncertaintyAbstentionCard />

      {/* Phase 6.9: Behavioral Digital Twin Simulation & Proposed Workflow Lab */}
      <BehavioralScenarioLab />
    </div>
  );
}

"use client";

import React from "react";
import {
  BrainCircuit,
  Clock,
  Sparkles,
  Info,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  ShieldCheck,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import type { RecoveryPredictionData } from "@/types/telemetry";

interface RecoveryPredictionCardProps {
  prediction: RecoveryPredictionData | null;
  loading?: boolean;
}

export function RecoveryPredictionCard({ prediction, loading }: RecoveryPredictionCardProps) {
  if (loading || !prediction) {
    return (
      <Card className="border border-border/80 shadow-xs">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between text-muted-foreground text-xs font-medium">
            <span className="flex items-center gap-1.5">
              <BrainCircuit className="h-4 w-4 text-primary animate-pulse" />
              Cognitive Recovery Duration Forecast (Phase 6.2)
            </span>
            <Badge variant="outline">Calculating...</Badge>
          </div>
          <CardTitle className="text-xl font-bold mt-1">Loading Predictive Recovery Model...</CardTitle>
        </CardHeader>
      </Card>
    );
  }

  const {
    estimated_recovery_duration_minutes,
    confidence_interval,
    confidence_tier,
    is_personalized,
    recovery_probabilities,
    main_contributing_factors,
    model_version,
    disclaimer,
  } = prediction;

  const getTierBadge = (tier: string) => {
    switch (tier) {
      case "CONFIDENT":
      case "ESTABLISHED":
        return (
          <Badge variant="outline" className="border-emerald-500/40 text-emerald-700 dark:text-emerald-300 gap-1">
            <ShieldCheck className="h-3 w-3" />
            Personalized Twin ({tier})
          </Badge>
        );
      case "EMERGING":
        return (
          <Badge variant="outline" className="border-amber-500/40 text-amber-700 dark:text-amber-300 gap-1">
            <Clock className="h-3 w-3" />
            Emerging Profile
          </Badge>
        );
      case "COLD_START":
      default:
        return (
          <Badge variant="secondary" className="gap-1 text-muted-foreground">
            <Info className="h-3 w-3" />
            Population Baseline (Cold Start)
          </Badge>
        );
    }
  };

  return (
    <Card className="border border-border/80 shadow-xs bg-gradient-to-br from-card via-card to-muted/20">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-medium text-muted-foreground">
          <span className="flex items-center gap-1.5 text-primary">
            <BrainCircuit className="h-4 w-4" />
            Cognitive Recovery Duration Prediction (Phase 6.2)
          </span>
          <div className="flex items-center gap-2">
            {getTierBadge(confidence_tier)}
            <Badge variant="outline" className="text-[10px] font-mono">
              {model_version}
            </Badge>
          </div>
        </div>

        <div className="flex flex-col md:flex-row md:items-baseline justify-between gap-2 mt-2">
          <div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-extrabold tracking-tight">
                {estimated_recovery_duration_minutes.toFixed(1)}
              </span>
              <span className="text-sm font-medium text-muted-foreground">minutes to full task resumption</span>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              90% Conformal Prediction Interval:{" "}
              <span className="font-semibold text-foreground">
                [{confidence_interval.lower_minutes.toFixed(1)}m – {confidence_interval.upper_minutes.toFixed(1)}m]
              </span>
            </p>
          </div>

          {!is_personalized && (
            <div className="flex items-center gap-1.5 text-xs text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40 px-2.5 py-1 rounded-md border border-amber-200 dark:border-amber-900/60">
              <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
              <span>Widened uncertainty applied for cold-start history</span>
            </div>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-4 pt-1">
        {/* Multi-Horizon Resumption Probabilities */}
        <div>
          <div className="flex items-center justify-between text-xs font-medium text-muted-foreground mb-2">
            <span>Cumulative Task Resumption Likelihood by Horizon</span>
            <span className="text-[11px]">P(T_recovery ≤ Horizon)</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
            {Object.entries(recovery_probabilities).map(([horizon, prob]) => {
              const pct = Math.round(prob * 100);
              return (
                <div
                  key={horizon}
                  className="rounded-lg border border-border/70 bg-card/60 p-2.5 flex flex-col justify-between space-y-1.5"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold">{horizon} Horizon</span>
                    <span className="text-xs font-mono font-bold">{pct}%</span>
                  </div>
                  <Progress value={pct} className="h-1.5" />
                </div>
              );
            })}
          </div>
        </div>

        {/* Contributing Factor Explanations */}
        {main_contributing_factors.length > 0 && (
          <div>
            <span className="text-xs font-medium text-muted-foreground block mb-1.5">
              Top Behavioral & Contextual Contributors:
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {main_contributing_factors.map((factor, idx) => (
                <div
                  key={idx}
                  className="text-xs rounded-md border border-border/60 bg-muted/30 p-2 flex items-start gap-2"
                >
                  {factor.direction === "INCREASES_RECOVERY" ? (
                    <TrendingUp className="h-3.5 w-3.5 text-amber-600 shrink-0 mt-0.5" />
                  ) : (
                    <TrendingDown className="h-3.5 w-3.5 text-emerald-600 shrink-0 mt-0.5" />
                  )}
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-1.5 font-medium">
                      <span>{factor.explanation}</span>
                      <span
                        className={`text-[10px] font-mono font-semibold ${
                          factor.impact_minutes > 0 ? "text-amber-600" : "text-emerald-600"
                        }`}
                      >
                        {factor.impact_minutes > 0 ? `+${factor.impact_minutes}m` : `${factor.impact_minutes}m`}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Scientific Disclaimer Footer */}
        <p className="text-[11px] text-muted-foreground/80 italic border-t border-border/60 pt-2 flex items-center gap-1.5">
          <Info className="h-3 w-3 shrink-0 text-muted-foreground" />
          <span>{disclaimer}</span>
        </p>
      </CardContent>
    </Card>
  );
}

"use client";

import { useState, useEffect } from "react";
import {
  Sparkles,
  Scale,
  ShieldCheck,
  AlertCircle,
  HelpCircle,
  TrendingUp,
  CheckCircle2,
  XCircle,
  Clock,
  Layers,
  BarChart3,
  Sliders,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import type {
  CounterfactualCandidateResultData,
  CounterfactualComparisonResponseData,
  CounterfactualLearnerType,
  DataCoverageTier,
} from "@/types/counterfactual";
import { counterfactualApi, mockCounterfactualResponse } from "@/lib/api/services/counterfactual";

export function CounterfactualComparisonCard() {
  const [learner, setLearner] = useState<CounterfactualLearnerType>("doubly_robust_learner");
  const [data, setData] = useState<CounterfactualComparisonResponseData>(mockCounterfactualResponse);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    handleFetch(learner);
  }, []);

  const handleFetch = async (selectedLearner: CounterfactualLearnerType) => {
    setLoading(true);
    try {
      const res = await counterfactualApi.compareInterventions(selectedLearner);
      setData(res);
    } catch {
      setData(mockCounterfactualResponse);
    } finally {
      setLoading(false);
    }
  };

  const getTierBadge = (tier: DataCoverageTier) => {
    switch (tier) {
      case "strong":
        return <Badge className="bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 text-[10px]">Strong Coverage (±15%)</Badge>;
      case "moderate":
        return <Badge variant="outline" className="bg-blue-500/15 text-blue-600 dark:text-blue-400 border-blue-500/30 text-[10px]">Moderate (±25%)</Badge>;
      case "sparse":
        return <Badge variant="outline" className="bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30 text-[10px]">Sparse (±45%)</Badge>;
      case "unsupported":
      default:
        return <Badge variant="destructive" className="bg-rose-500/15 text-rose-600 dark:text-rose-400 border-rose-500/30 text-[10px]">Unsupported</Badge>;
    }
  };

  return (
    <Card className="border-border">
      <CardHeader className="pb-3">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div>
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" />
              Counterfactual Alternative Evaluation & Uplift Comparison
            </CardTitle>
            <CardDescription className="text-xs">
              Simulates multi-treatment potential outcomes Y(a) across candidate interventions to optimize behavioral recommendations.
            </CardDescription>
          </div>

          <div className="flex items-center gap-1.5 self-start sm:self-auto">
            <span className="text-xs text-muted-foreground mr-1">Learner:</span>
            {[
              { id: "doubly_robust_learner", label: "DR-Learner" },
              { id: "t_learner", label: "T-Learner" },
              { id: "x_learner", label: "X-Learner" },
            ].map((l) => (
              <Button
                key={l.id}
                variant={learner === l.id ? "default" : "outline"}
                size="sm"
                className="text-xs h-7 px-2.5"
                onClick={() => {
                  setLearner(l.id as CounterfactualLearnerType);
                  handleFetch(l.id as CounterfactualLearnerType);
                }}
              >
                {l.label}
              </Button>
            ))}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Recommendation Source Banner */}
        <div className="flex items-center justify-between p-3 rounded-lg bg-muted/40 border text-xs">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-emerald-500" />
            <div>
              <span className="font-semibold text-foreground">Recommendation Strategy: </span>
              <span className="font-mono text-primary font-semibold">
                {data.recommendation_source.replace(/_/g, " ").toUpperCase()}
              </span>
              {data.recommended_champion && (
                <span className="text-muted-foreground ml-2">
                  (Selected Champion: <span className="text-foreground font-semibold font-mono">{data.recommended_champion}</span>)
                </span>
              )}
            </div>
          </div>
          <Badge variant="outline" className="text-[10px]">
            Model-Driven Policy
          </Badge>
        </div>

        {/* Candidate Alternatives Comparison Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="py-2.5 font-medium">Candidate Intervention</th>
                <th className="py-2.5 font-medium">Coverage</th>
                <th className="py-2.5 font-medium">Resumption Lift</th>
                <th className="py-2.5 font-medium">Completion Lift</th>
                <th className="py-2.5 font-medium">Friction Reduction</th>
                <th className="py-2.5 font-medium">Burden Cost</th>
                <th className="py-2.5 font-medium text-right">Composite Uplift</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/50">
              {data.candidates.map((cand) => {
                const isChampion = cand.candidate === data.recommended_champion;
                return (
                  <tr
                    key={cand.candidate}
                    className={`hover:bg-muted/30 transition-colors ${
                      isChampion ? "bg-primary/5 font-medium" : ""
                    } ${!cand.is_supported ? "opacity-60" : ""}`}
                  >
                    {/* Candidate Name & Description */}
                    <td className="py-3 pr-3">
                      <div className="flex items-center gap-1.5">
                        {isChampion && <Sparkles className="h-3 w-3 text-primary shrink-0" />}
                        <span className="font-semibold text-foreground">{cand.title}</span>
                      </div>
                      <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-1">
                        {cand.description}
                      </p>
                      {!cand.is_supported && cand.exclusion_reason && (
                        <p className="text-[10px] text-rose-500 mt-1 flex items-center gap-1">
                          <XCircle className="h-3 w-3 shrink-0" />
                          {cand.exclusion_reason}
                        </p>
                      )}
                    </td>

                    {/* Coverage Tier */}
                    <td className="py-3 whitespace-nowrap">
                      {getTierBadge(cand.coverage_tier)}
                      <div className="text-[10px] text-muted-foreground mt-0.5">
                        N={cand.empirical_sample_size} · Exec: {(cand.empirical_execution_rate * 100).toFixed(0)}%
                      </div>
                    </td>

                    {/* Resumption Lift */}
                    <td className="py-3 font-mono">
                      {cand.incremental_benefit ? (
                        <span
                          className={
                            cand.incremental_benefit.resumption_lift_pct >= 0
                              ? "text-emerald-600 dark:text-emerald-400 font-semibold"
                              : "text-rose-500"
                          }
                        >
                          {cand.incremental_benefit.resumption_lift_pct >= 0 ? "+" : ""}
                          {cand.incremental_benefit.resumption_lift_pct.toFixed(1)}%
                        </span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>

                    {/* Completion Lift */}
                    <td className="py-3 font-mono">
                      {cand.incremental_benefit ? (
                        <span
                          className={
                            cand.incremental_benefit.completion_lift_pct >= 0
                              ? "text-emerald-600 dark:text-emerald-400 font-semibold"
                              : "text-rose-500"
                          }
                        >
                          {cand.incremental_benefit.completion_lift_pct >= 0 ? "+" : ""}
                          {cand.incremental_benefit.completion_lift_pct.toFixed(1)}%
                        </span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>

                    {/* Friction Reduction */}
                    <td className="py-3 font-mono">
                      {cand.incremental_benefit ? (
                        <span className="text-blue-600 dark:text-blue-400 font-semibold">
                          -{cand.incremental_benefit.friction_reduction_points.toFixed(1)} pts
                        </span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>

                    {/* Burden Cost */}
                    <td className="py-3 font-mono text-muted-foreground">
                      {cand.incremental_benefit ? (
                        <span>{(cand.incremental_benefit.burden_penalty * 100).toFixed(0)}%</span>
                      ) : (
                        "—"
                      )}
                    </td>

                    {/* Composite Uplift Score */}
                    <td className="py-3 text-right font-mono">
                      {cand.composite_uplift_score !== null && cand.composite_uplift_score !== undefined ? (
                        <Badge
                          variant={isChampion ? "default" : "outline"}
                          className={`text-xs ${
                            isChampion
                              ? "bg-primary text-primary-foreground"
                              : cand.composite_uplift_score > 0
                              ? "text-emerald-600 border-emerald-500/30"
                              : "text-muted-foreground"
                          }`}
                        >
                          {cand.composite_uplift_score > 0 ? "+" : ""}
                          {cand.composite_uplift_score.toFixed(1)}
                        </Badge>
                      ) : (
                        <span className="text-[10px] text-muted-foreground italic">Excluded</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Scientific Disclaimer Footer */}
        <p className="text-[11px] text-muted-foreground pt-2 border-t leading-relaxed">
          <span className="font-semibold text-foreground">Disclaimer: </span>
          {data.disclaimer}
        </p>
      </CardContent>
    </Card>
  );
}

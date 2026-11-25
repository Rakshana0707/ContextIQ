"use client";

import { useState, useEffect } from "react";
import {
  GitFork,
  ShieldCheck,
  AlertTriangle,
  Scale,
  Sparkles,
  Info,
  Layers,
  ArrowRight,
  CheckCircle,
  HelpCircle,
  TrendingUp,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type {
  CausalAnalysisResultData,
  CausalQuestionId,
  CausalMethod,
  CausalQuestionSummary,
} from "@/types/causal";
import { causalApi, mockCausalResult } from "@/lib/api/services/causal";

export function CausalAnalysisPanel() {
  const [questions, setQuestions] = useState<CausalQuestionSummary[]>([]);
  const [selectedQuestion, setSelectedQuestion] = useState<CausalQuestionId>("recovery_buffer_on_resumption");
  const [selectedMethod, setSelectedMethod] = useState<CausalMethod>("doubly_robust_aipw");
  const [result, setResult] = useState<CausalAnalysisResultData>(mockCausalResult);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    causalApi.getQuestions().then((qs) => {
      if (qs && qs.length > 0) setQuestions(qs);
    });
  }, []);

  const handleRunEvaluation = async (qId: CausalQuestionId, method: CausalMethod) => {
    setLoading(true);
    try {
      const res = await causalApi.evaluateQuestion(qId, method);
      setResult(res);
    } catch {
      setResult(mockCausalResult);
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "convincing":
        return <Badge className="bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30">Causal Claim Defensible</Badge>;
      case "inconclusive":
        return <Badge variant="outline" className="bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30">Inconclusive Evidence</Badge>;
      case "abstained":
      default:
        return <Badge variant="destructive" className="bg-rose-500/15 text-rose-600 dark:text-rose-400 border-rose-500/30">Analysis Abstained</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner: Scientific Integrity Invariant */}
      <Alert className="bg-primary/5 border-primary/20">
        <Scale className="h-4 w-4 text-primary" />
        <AlertTitle className="text-xs font-semibold">Causal Behavioral Modeling & Confounding Guardrails</AlertTitle>
        <AlertDescription className="text-xs text-muted-foreground mt-1">
          {result.disclaimer}
        </AlertDescription>
      </Alert>

      {/* Target Question Selector */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <GitFork className="h-4 w-4 text-primary" />
              Target Causal Investigation
            </CardTitle>
            <div className="flex gap-2">
              <Button
                variant={selectedMethod === "doubly_robust_aipw" ? "default" : "outline"}
                size="sm"
                className="text-xs h-7"
                onClick={() => {
                  setSelectedMethod("doubly_robust_aipw");
                  handleRunEvaluation(selectedQuestion, "doubly_robust_aipw");
                }}
              >
                Doubly Robust AIPW
              </Button>
              <Button
                variant={selectedMethod === "inverse_probability_weighting" ? "default" : "outline"}
                size="sm"
                className="text-xs h-7"
                onClick={() => {
                  setSelectedMethod("inverse_probability_weighting");
                  handleRunEvaluation(selectedQuestion, "inverse_probability_weighting");
                }}
              >
                IPW Weighting
              </Button>
              <Button
                variant={selectedMethod === "propensity_score_matching" ? "default" : "outline"}
                size="sm"
                className="text-xs h-7"
                onClick={() => {
                  setSelectedMethod("propensity_score_matching");
                  handleRunEvaluation(selectedQuestion, "propensity_score_matching");
                }}
              >
                PS Matching
              </Button>
            </div>
          </div>
          <CardDescription className="text-xs">
            Evaluates whether automated behavioral interventions cause measurable cognitive recovery improvements.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
            {[
              { id: "recovery_buffer_on_resumption", title: "Recovery Buffer → Resumption" },
              { id: "adaptive_scheduling_on_completion", title: "Adaptive Scheduling → Completion" },
              { id: "personalized_reminder_on_abandonment", title: "Personalized Reminder → Retention" },
              { id: "notification_timing_on_friction", title: "Slack-Timing → Friction Reduction" },
            ].map((q) => (
              <Button
                key={q.id}
                variant={selectedQuestion === q.id ? "secondary" : "outline"}
                className={`text-xs justify-start h-9 ${selectedQuestion === q.id ? "border-primary/50 font-semibold" : ""}`}
                onClick={() => {
                  setSelectedQuestion(q.id as CausalQuestionId);
                  handleRunEvaluation(q.id as CausalQuestionId, selectedMethod);
                }}
              >
                {q.title}
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Main Analysis Findings */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Card 1: Estimated Causal Effect */}
        <Card className="lg:col-span-1">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-xs font-medium text-muted-foreground">Adjusted Causal Effect</CardTitle>
              {getStatusBadge(result.status)}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <div className="text-3xl font-bold tracking-tight">
                {result.estimated_causal_effect !== null ? (
                  <span>
                    {result.estimated_causal_effect > 0 ? "+" : ""}
                    {(result.estimated_causal_effect * 100).toFixed(1)}%
                  </span>
                ) : (
                  <span className="text-muted-foreground text-xl">Abstained</span>
                )}
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                {result.target_trial.causal_estimand.replace(/_/g, " ").toUpperCase()} vs Control Holdout
              </p>
            </div>

            {result.confidence_interval && (
              <div className="bg-muted/40 p-2.5 rounded-md text-xs space-y-1">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">95% Confidence Interval:</span>
                  <span className="font-mono font-medium">
                    [{(result.confidence_interval[0] * 100).toFixed(1)}%, {(result.confidence_interval[1] * 100).toFixed(1)}%]
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Two-tailed p-value:</span>
                  <span className="font-mono font-medium">{result.p_value ? result.p_value.toFixed(4) : "N/A"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Observational raw diff:</span>
                  <span className="font-mono text-muted-foreground">
                    {(result.raw_observational_difference * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
            )}

            <div className="text-xs text-muted-foreground">
              Sample: Treated <span className="font-medium text-foreground">{result.sample_size_treated}</span> · Control{" "}
              <span className="font-medium text-foreground">{result.sample_size_control}</span> (Total N={result.total_sample_size})
            </div>
          </CardContent>
        </Card>

        {/* Card 2: Sensitivity to Unmeasured Confounding (E-Value) */}
        <Card className="lg:col-span-1">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-xs font-medium text-muted-foreground">Sensitivity Analysis (E-Value)</CardTitle>
              {result.sensitivity && (
                <Badge
                  variant="outline"
                  className={
                    result.sensitivity.robustness_assessment === "ROBUST"
                      ? "text-emerald-500 border-emerald-500/30"
                      : "text-amber-500 border-amber-500/30"
                  }
                >
                  {result.sensitivity.robustness_assessment}
                </Badge>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <div className="text-3xl font-bold font-mono">
                {result.sensitivity ? result.sensitivity.e_value_estimate.toFixed(2) : "N/A"}
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                Min relative risk required by an unmeasured confounder to explain away effect
              </p>
            </div>
            {result.sensitivity && (
              <div className="bg-muted/40 p-2.5 rounded-md text-xs space-y-1">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Lower Bound E-Value:</span>
                  <span className="font-mono font-medium">{result.sensitivity.e_value_lower_bound.toFixed(2)}</span>
                </div>
                <p className="text-xs text-muted-foreground pt-1 leading-relaxed">
                  {result.sensitivity.interpretation}
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Card 3: Target Trial & Time Zero Alignment */}
        <Card className="lg:col-span-1">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">Target Trial Protocol</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-xs">
            <div>
              <span className="font-semibold text-foreground">Time Zero (T0): </span>
              <span className="text-muted-foreground">{result.target_trial.time_zero_definition}</span>
            </div>
            <div>
              <span className="font-semibold text-foreground">Follow-up Window: </span>
              <span className="text-muted-foreground">{result.target_trial.follow_up_window}</span>
            </div>
            <div>
              <span className="font-semibold text-foreground">Immortal-Time Guard: </span>
              <span className="text-muted-foreground">{result.target_trial.immortal_time_bias_prevention}</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Covariate Balance (SMD) Table */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Scale className="h-4 w-4 text-primary" />
              Covariate Balance Diagnostics (SMD)
            </CardTitle>
            <Badge variant="outline" className="text-xs">
              Threshold: |SMD| ≤ 0.10
            </Badge>
          </div>
          <CardDescription className="text-xs">
            Compares pre-treatment confounder balance before vs after adjustment to confirm elimination of selection bias.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="py-2 font-medium">Pre-Treatment Covariate</th>
                  <th className="py-2 font-medium">Treated Mean</th>
                  <th className="py-2 font-medium">Control Mean</th>
                  <th className="py-2 font-medium">Unadjusted SMD</th>
                  <th className="py-2 font-medium">Adjusted SMD</th>
                  <th className="py-2 font-medium text-right">Balance Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/50">
                {result.covariate_balance.map((item) => (
                  <tr key={item.covariate_name} className="hover:bg-muted/30">
                    <td className="py-2 font-mono font-medium">{item.covariate_name}</td>
                    <td className="py-2 font-mono">{item.mean_treated.toFixed(1)}</td>
                    <td className="py-2 font-mono">{item.mean_control.toFixed(1)}</td>
                    <td className="py-2 font-mono text-amber-600 dark:text-amber-400">
                      {item.smd_unadjusted.toFixed(2)}
                    </td>
                    <td className="py-2 font-mono font-semibold text-emerald-600 dark:text-emerald-400">
                      {item.smd_adjusted.toFixed(2)}
                    </td>
                    <td className="py-2 text-right">
                      {item.is_balanced ? (
                        <Badge variant="outline" className="text-emerald-600 border-emerald-500/30 text-[10px]">
                          Balanced
                        </Badge>
                      ) : (
                        <Badge variant="destructive" className="text-[10px]">
                          Imbalanced
                        </Badge>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Subgroup Effect Heterogeneity (CATE) */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-primary" />
            Subgroup Effect Heterogeneity (Conditional ATE)
          </CardTitle>
          <CardDescription className="text-xs">
            Evaluates conditional effects across task categories and user profiles. Strata with N &lt; 30 are suppressed to prevent spurious claims.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {result.effect_heterogeneity.map((sub) => (
              <div key={sub.subgroup_name} className="border rounded-md p-3 space-y-1.5 bg-muted/20">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-xs">{sub.subgroup_name}</span>
                  <Badge variant={sub.is_statistically_sound ? "secondary" : "outline"} className="text-[10px]">
                    N = {sub.sample_size_treated + sub.sample_size_control}
                  </Badge>
                </div>
                {sub.is_statistically_sound && sub.estimated_cate !== null ? (
                  <div>
                    <div className="text-xl font-bold font-mono text-emerald-600 dark:text-emerald-400">
                      {(sub.estimated_cate * 100).toFixed(1)}%
                    </div>
                    <p className="text-[10px] text-muted-foreground font-mono">
                      95% CI: [{(sub.ci_lower! * 100).toFixed(1)}%, {(sub.ci_upper! * 100).toFixed(1)}%]
                    </p>
                  </div>
                ) : (
                  <p className="text-[10px] text-amber-600 dark:text-amber-400 leading-tight pt-1">
                    {sub.abstention_reason}
                  </p>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

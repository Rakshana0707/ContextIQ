"use client";

import { useState, useEffect } from "react";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  BrainCircuit,
  CheckCircle,
  Compass,
  Cpu,
  Layers,
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
  AbstentionOutcome,
  CalibrationMetricsData,
  DecisionSupportResponseData,
} from "@/types/uncertainty";
import {
  mockCalibrationBenchmarks,
  mockDecisionSupportResponse,
  uncertaintyApi,
} from "@/lib/api/services/uncertainty";

export function UncertaintyAbstentionCard() {
  const [response, setResponse] =
    useState<DecisionSupportResponseData>(mockDecisionSupportResponse);
  const [benchmarks, setBenchmarks] =
    useState<CalibrationMetricsData[]>(mockCalibrationBenchmarks);
  const [loading, setLoading] = useState(false);
  const [activeScenario, setActiveScenario] = useState<"normal" | "coldstart" | "ood" | "degraded">("normal");

  const runSimulation = async (scenario: "normal" | "coldstart" | "ood" | "degraded") => {
    setActiveScenario(scenario);
    setLoading(true);

    const scenarioConfigs: Record<string, any> = {
      normal: {
        baseline_bfi: 48.0,
        task_priority: 2.0,
        recent_interruptions: 2.0,
        monitored_hours_last_24h: 7.0,
      },
      coldstart: {
        baseline_bfi: 50.0,
        task_priority: 2.0,
        monitored_hours_last_24h: 2.0,
      },
      ood: {
        baseline_bfi: 99.0, // Extreme OOD
        task_priority: 4.0,
        recent_interruptions: 9.0,
        monitored_hours_last_24h: 6.0,
      },
      degraded: {
        baseline_bfi: 52.0,
        monitored_hours_last_24h: 1.5, // < 35%
      },
    };

    try {
      const res = await uncertaintyApi.evaluate(undefined, "forgetting_risk", scenarioConfigs[scenario]);
      setResponse(res);
    } catch {
      setResponse(mockDecisionSupportResponse);
    } finally {
      setLoading(false);
    }
  };

  const getOutcomeBadge = (outcome: AbstentionOutcome) => {
    switch (outcome) {
      case "PREDICTION_AVAILABLE":
        return (
          <Badge className="bg-emerald-600 text-white flex items-center gap-1">
            <ShieldCheck className="h-3 w-3" />
            Prediction Available (Automation Authorized)
          </Badge>
        );
      case "PREDICTION_WITH_CAUTION":
        return (
          <Badge variant="outline" className="border-amber-500 text-amber-600 dark:text-amber-400 bg-amber-500/10 flex items-center gap-1">
            <AlertTriangle className="h-3 w-3" />
            Prediction with Caution (Disclosure Required)
          </Badge>
        );
      case "INSUFFICIENT_EVIDENCE":
        return (
          <Badge variant="outline" className="border-purple-500 text-purple-600 dark:text-purple-400 bg-purple-500/10 flex items-center gap-1">
            <AlertCircle className="h-3 w-3" />
            Abstained: Insufficient Evidence
          </Badge>
        );
      case "UNSUPPORTED_INPUT":
        return (
          <Badge variant="destructive" className="flex items-center gap-1">
            <ShieldAlert className="h-3 w-3" />
            Abstained: Unsupported Input (OOD)
          </Badge>
        );
      case "MODEL_UNAVAILABLE":
      default:
        return (
          <Badge variant="secondary" className="flex items-center gap-1">
            <AlertCircle className="h-3 w-3" />
            Model Unavailable
          </Badge>
        );
    }
  };

  return (
    <Card className="border-border">
      <CardHeader className="pb-3">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div>
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <Compass className="h-4 w-4 text-primary" />
              Uncertainty-Aware Decision Support &amp; Intelligent Abstention
            </CardTitle>
            <CardDescription className="text-xs">
              ContextIQ Phase 6.8 — Separating aleatoric vs epistemic uncertainty, conformal prediction intervals, and explicit abstention
            </CardDescription>
          </div>
          <div>{getOutcomeBadge(response.abstention_outcome)}</div>
        </div>

        {/* Scenario Simulator Buttons */}
        <div className="flex flex-wrap items-center gap-1.5 pt-2">
          <span className="text-xs text-muted-foreground mr-1">Simulate Telemetry:</span>
          <Button
            variant={activeScenario === "normal" ? "default" : "outline"}
            size="sm"
            className="text-xs h-7"
            onClick={() => runSimulation("normal")}
            disabled={loading}
          >
            Verified History (N=32)
          </Button>
          <Button
            variant={activeScenario === "coldstart" ? "default" : "outline"}
            size="sm"
            className="text-xs h-7"
            onClick={() => runSimulation("coldstart")}
            disabled={loading}
          >
            Cold-Start User (N &lt; 5)
          </Button>
          <Button
            variant={activeScenario === "ood" ? "default" : "outline"}
            size="sm"
            className="text-xs h-7"
            onClick={() => runSimulation("ood")}
            disabled={loading}
          >
            Extreme OOD (BFI 99)
          </Button>
          <Button
            variant={activeScenario === "degraded" ? "default" : "outline"}
            size="sm"
            className="text-xs h-7"
            onClick={() => runSimulation("degraded")}
            disabled={loading}
          >
            Degraded Telemetry (&lt;35%)
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-4 text-xs">
        {/* Outcome & Policy Directive Banner */}
        <div className="p-3.5 bg-card rounded-lg border border-border shadow-sm space-y-2">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
            <span className="font-semibold text-foreground text-xs flex items-center gap-1.5">
              <Zap className="h-3.5 w-3.5 text-primary" />
              Action Policy Directive: {response.recommended_action_policy}
            </span>
            <Badge variant="outline" className="text-[10px] text-muted-foreground">
              {response.can_automate_recommendation ? "Automated Ranking Allowed" : "Automated Ranking Blocked"}
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">
            {response.user_facing_explanation}
          </p>
        </div>

        {/* Uncertainty Decomposition & Interval Metrics */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-3 bg-card rounded-md border border-border">
            <span className="text-muted-foreground block text-[11px]">Calibrated Probability</span>
            <span className="text-base font-semibold text-foreground">
              {response.calibrated_probability !== null && response.calibrated_probability !== undefined
                ? `${(response.calibrated_probability * 100).toFixed(1)}%`
                : "Abstained"}
            </span>
            <span className="text-[10px] text-muted-foreground block mt-0.5">Isotonic Calibrated</span>
          </div>

          <div className="p-3 bg-card rounded-md border border-border">
            <span className="text-muted-foreground block text-[11px]">90% Conformal Interval</span>
            <span className="text-base font-semibold text-primary">
              {response.prediction_interval
                ? `[${(response.prediction_interval.lower_bound * 100).toFixed(0)}%, ${(response.prediction_interval.upper_bound * 100).toFixed(0)}%]`
                : "Unavailable"}
            </span>
            <span className="text-[10px] text-muted-foreground block mt-0.5">
              {response.prediction_interval ? `Width: ±${(response.prediction_interval.interval_width * 50).toFixed(0)}%` : "Withheld on Abstention"}
            </span>
          </div>

          <div className="p-3 bg-card rounded-md border border-border">
            <span className="text-muted-foreground block text-[11px]">Aleatoric (Noise)</span>
            <span className="text-base font-semibold text-foreground">
              {response.uncertainty_decomposition.aleatoric_score.toFixed(2)}
            </span>
            <Progress value={response.uncertainty_decomposition.aleatoric_score * 100} className="h-1.5 mt-1" />
          </div>

          <div className="p-3 bg-card rounded-md border border-border">
            <span className="text-muted-foreground block text-[11px]">Epistemic (Data Lack)</span>
            <span className="text-base font-semibold text-foreground">
              {response.uncertainty_decomposition.epistemic_score.toFixed(2)}
            </span>
            <Progress value={response.uncertainty_decomposition.epistemic_score * 100} className="h-1.5 mt-1" />
          </div>
        </div>

        {/* Data Coverage & Reliability Audit */}
        <div className="p-3 bg-muted/40 rounded-lg border border-border space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-foreground text-xs flex items-center gap-1.5">
              <ShieldCheck className="h-3.5 w-3.5 text-primary" />
              Evidence Coverage &amp; Out-of-Distribution Audit
            </span>
            <Badge variant="outline" className="text-[10px]">
              Coverage Tier: {response.data_coverage.data_coverage_tier}
            </Badge>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
            <div>
              <span className="text-muted-foreground block">User Observations:</span>
              <span className="font-medium text-foreground">{response.data_coverage.user_sample_size} records</span>
            </div>
            <div>
              <span className="text-muted-foreground block">Telemetry Quality:</span>
              <span className="font-medium text-foreground">
                {(response.data_coverage.telemetry_quality_score * 100).toFixed(0)}% monitored
              </span>
            </div>
            <div>
              <span className="text-muted-foreground block">OOD Distance:</span>
              <span className={response.data_coverage.is_out_of_distribution ? "text-destructive font-semibold" : "font-medium text-foreground"}>
                {response.data_coverage.ood_distance.toFixed(2)} {response.data_coverage.is_out_of_distribution ? "(OOD Alert)" : "(In Envelope)"}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground block">Critical Inputs:</span>
              <span className="font-medium text-foreground">
                {response.data_coverage.missing_critical_inputs.length === 0 ? "Complete" : `${response.data_coverage.missing_critical_inputs.length} missing`}
              </span>
            </div>
          </div>
        </div>

        {/* Probability Calibration Benchmark Table */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-foreground flex items-center gap-1.5">
              <Cpu className="h-3.5 w-3.5 text-primary" />
              Probability Calibration Evaluation (Held-Out Validation Data)
            </span>
            <Badge variant="secondary" className="text-[10px]">
              Expected Calibration Error (ECE)
            </Badge>
          </div>

          <div className="border border-border rounded-lg overflow-hidden">
            <div className="grid grid-cols-4 p-2 bg-muted/60 font-medium text-[11px] text-muted-foreground border-b border-border">
              <span>Calibration Method</span>
              <span>ECE (Error)</span>
              <span>Brier Score</span>
              <span>Calibration Status</span>
            </div>
            <div className="divide-y divide-border">
              {benchmarks.map((bm, idx) => (
                <div key={idx} className="grid grid-cols-4 p-2 items-center text-[11px]">
                  <span className="font-medium text-foreground">{bm.calibration_method}</span>
                  <span className="font-semibold text-primary">{bm.expected_calibration_error.toFixed(3)}</span>
                  <span className="text-muted-foreground">{bm.brier_score.toFixed(3)}</span>
                  <div>
                    {bm.is_well_calibrated ? (
                      <Badge className="bg-emerald-600 text-white text-[10px] px-1.5 py-0 h-4">
                        Well-Calibrated
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="text-[10px] text-amber-500 border-amber-500 px-1.5 py-0 h-4">
                        Suboptimal
                      </Badge>
                    )}
                  </div>
                </div>
              ))}
            </div>
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

"use client";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  AlertTriangle,
  CheckCircle,
  Clock,
  Info,
  BrainCircuit,
  Timer,
  Zap,
  Activity,
  AlertCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { ForgettingPrediction } from "@/types";
import { SHAPWaterfall } from "@/components/predictions/shap-waterfall";

interface EnhancedPredictionCardProps {
  prediction: ForgettingPrediction;
}

export function EnhancedPredictionCard({ prediction }: EnhancedPredictionCardProps) {
  const riskCategory = prediction.riskCategory || prediction.riskLevel;

  const riskConfig = {
    CRITICAL: {
      color: "text-purple-700",
      bg: "bg-purple-50",
      border: "border-purple-300",
      icon: AlertTriangle,
      badge: "bg-purple-100 text-purple-800 border-purple-200",
    },
    HIGH: {
      color: "text-red-700",
      bg: "bg-red-50",
      border: "border-red-200",
      icon: AlertTriangle,
      badge: "bg-red-100 text-red-800 border-red-200",
    },
    MEDIUM: {
      color: "text-yellow-700",
      bg: "bg-yellow-50",
      border: "border-yellow-200",
      icon: Clock,
      badge: "bg-yellow-100 text-yellow-800 border-yellow-200",
    },
    LOW: {
      color: "text-green-700",
      bg: "bg-green-50",
      border: "border-green-200",
      icon: CheckCircle,
      badge: "bg-green-100 text-green-800 border-green-200",
    },
  };

  const config =
    riskConfig[riskCategory as keyof typeof riskConfig] ||
    riskConfig[prediction.riskLevel as keyof typeof riskConfig] ||
    riskConfig.MEDIUM;

  const RiskIcon = config.icon;

  return (
    <Card className={cn("border-l-4 shadow-sm transition-all hover:shadow-md", config.border)}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <CardTitle className="text-base mb-1 font-semibold">{prediction.taskTitle}</CardTitle>
            <CardDescription className="text-xs flex flex-wrap items-center gap-2">
              <span>Model v{prediction.modelVersion}</span>
              <span>•</span>
              <span>Exp v{prediction.explanationVersion || "2.7.0"}</span>
              {prediction.inferenceLatencyMs !== undefined && (
                <>
                  <span>•</span>
                  <span className="flex items-center gap-0.5 text-slate-500">
                    <Zap className="h-3 w-3 text-amber-500" />
                    {prediction.inferenceLatencyMs.toFixed(1)}ms
                  </span>
                </>
              )}
            </CardDescription>
          </div>
          <Badge variant="outline" className={cn("ml-2 font-medium shrink-0", config.badge)}>
            {riskCategory}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Error / Degradation State Display */}
        {prediction.error && (
          <div className="p-3 rounded-lg bg-red-50 border border-red-200 flex items-start gap-2 text-xs text-red-800">
            <AlertCircle className="h-4 w-4 text-red-600 mt-0.5 shrink-0" />
            <div>
              <p className="font-semibold">Prediction Degradation</p>
              <p>{prediction.error}</p>
            </div>
          </div>
        )}

        {/* Cold-Start / Insufficient-Data Warning */}
        {prediction.isColdStart && (
          <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 flex items-start gap-2 text-xs text-amber-900">
            <Info className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
            <div>
              <span className="font-semibold">Insufficient User History: </span>
              <span>
                Personalized task baseline unavailable (Tier: {prediction.coldStartTier || "COLD_START"}). Empirical
                Bayes shrinkage applied.
              </span>
            </div>
          </div>
        )}

        {/* Probability Visualization */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-sm font-medium text-slate-700">Calibrated Forget Risk</span>
            <span className={cn("text-lg font-bold", config.color)}>{prediction.riskScore.toFixed(1)}%</span>
          </div>
          <Progress value={prediction.riskScore} className="h-2" />
          {prediction.confidenceInterval && (
            <p className="text-[11px] text-muted-foreground mt-1 text-right">
              95% CI: [{(prediction.confidenceInterval[0] * 100).toFixed(1)}% –{" "}
              {(prediction.confidenceInterval[1] * 100).toFixed(1)}%]
            </p>
          )}
        </div>

        {/* Grounded Natural Language Explanation */}
        {prediction.naturalLanguageExplanation && (
          <div className="p-2.5 rounded-lg bg-blue-50/70 border border-blue-100 flex items-start gap-2 text-xs text-blue-900 leading-relaxed">
            <BrainCircuit className="h-4 w-4 text-blue-600 mt-0.5 shrink-0" />
            <p>{prediction.naturalLanguageExplanation}</p>
          </div>
        )}

        {/* Time-Dependent Survival Analysis Forecast */}
        {prediction.survivalEstimates && prediction.survivalEstimates.length > 0 && (
          <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-700 flex items-center gap-1.5">
                <Timer className="h-3.5 w-3.5 text-indigo-600" />
                Survival Probability Over Time S(t)
              </span>
              {prediction.medianSurvivalHours && (
                <span className="text-[11px] text-indigo-700 font-medium bg-indigo-50 px-2 py-0.5 rounded border border-indigo-100">
                  Median: {prediction.medianSurvivalHours}h
                </span>
              )}
            </div>
            <div className="grid grid-cols-5 gap-1.5 text-center">
              {prediction.survivalEstimates.map((pt) => (
                <div key={pt.horizonHours} className="bg-white p-1.5 rounded border border-slate-100 text-[11px]">
                  <p className="text-slate-500 font-medium">{pt.horizonHours}h</p>
                  <p className="font-bold text-slate-800">{(pt.survivalProbability * 100).toFixed(0)}%</p>
                  <p className="text-[9px] text-rose-500">{(pt.forgettingRisk * 100).toFixed(0)}% lapse</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Risk Policy / Category */}
        <div className={cn("flex items-center gap-2 p-3 rounded-lg", config.bg)}>
          <RiskIcon className={cn("h-5 w-5", config.color)} />
          <div className="flex-1">
            <p className="text-sm font-semibold text-gray-900">{riskCategory} Risk Tier</p>
            <p className="text-xs text-gray-600">{getRiskDescription(riskCategory)}</p>
          </div>
        </div>

        {/* SHAP Waterfall / Feature Contributions */}
        {prediction.reasons && prediction.reasons.length > 0 && (
          <SHAPWaterfall reasons={prediction.reasons} baseValue={prediction.baseValue} />
        )}

        {/* Provenance Metadata */}
        <div className="border-t pt-3 text-xs text-muted-foreground flex items-center justify-between">
          <span className="flex items-center gap-1">
            <Activity className="h-3.5 w-3.5 text-slate-400" />
            Evaluated
          </span>
          <span className="font-medium">{new Date(prediction.generatedAt).toLocaleString()}</span>
        </div>
      </CardContent>
    </Card>
  );
}

function getRiskDescription(riskLevel: string): string {
  switch (riskLevel) {
    case "CRITICAL":
      return "Severe prospective memory vulnerability — immediate interruption mitigation required";
    case "HIGH":
      return "High probability of omission — automated proactive reminder recommended";
    case "MEDIUM":
      return "Moderate delay risk — contextual prompt queued on next state transition";
    case "LOW":
      return "Low forgetting risk — standard passive monitoring sufficient";
    default:
      return "Monitored prospective memory task";
  }
}

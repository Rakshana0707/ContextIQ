"use client";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { AlertTriangle, CheckCircle, Clock, Info, BrainCircuit } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ForgettingPrediction } from "@/types";
import { SHAPWaterfall } from "@/components/predictions/shap-waterfall";

interface EnhancedPredictionCardProps {
  prediction: ForgettingPrediction;
}

export function EnhancedPredictionCard({ prediction }: EnhancedPredictionCardProps) {
  const riskConfig = {
    HIGH: { color: "text-red-700", bg: "bg-red-50", border: "border-red-200", icon: AlertTriangle },
    MEDIUM: { color: "text-yellow-700", bg: "bg-yellow-50", border: "border-yellow-200", icon: Clock },
    LOW: { color: "text-green-700", bg: "bg-green-50", border: "border-green-200", icon: CheckCircle },
  };

  const config = riskConfig[prediction.riskLevel];
  const RiskIcon = config.icon;

  return (
    <Card className={cn("border-l-4", config.border)}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <CardTitle className="text-base mb-1">{prediction.taskTitle}</CardTitle>
            <CardDescription className="text-xs flex items-center gap-2">
              <span>Model v{prediction.modelVersion}</span>
              <span>•</span>
              <span>Exp v{prediction.explanationVersion || "2.7.0"}</span>
            </CardDescription>
          </div>
          <Badge
            variant="outline"
            className={cn("ml-2", config.bg, config.color, config.border)}
          >
            {prediction.riskLevel}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Probability Visualization */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">Forget Probability</span>
            <span className={cn("text-lg font-bold", config.color)}>
              {prediction.riskScore.toFixed(1)}%
            </span>
          </div>
          <Progress
            value={prediction.riskScore}
            className="h-2"
          />
        </div>

        {/* Natural Language Explanation / Intelligence Layer Reasoning */}
        {prediction.naturalLanguageExplanation && (
          <div className="p-2.5 rounded-lg bg-blue-50/70 border border-blue-100 flex items-start gap-2 text-xs text-blue-900">
            <BrainCircuit className="h-4 w-4 text-blue-600 mt-0.5 shrink-0" />
            <p className="leading-relaxed">{prediction.naturalLanguageExplanation}</p>
          </div>
        )}

        {/* Risk Category */}
        <div className={cn("flex items-center gap-2 p-3 rounded-lg", config.bg)}>
          <RiskIcon className={cn("h-5 w-5", config.color)} />
          <div className="flex-1">
            <p className="text-sm font-semibold text-gray-900">
              {prediction.riskLevel} Risk
            </p>
            <p className="text-xs text-gray-600">
              {getRiskDescription(prediction.riskLevel)}
            </p>
          </div>
        </div>

        {/* SHAP Waterfall / Feature Contributions */}
        {prediction.reasons && prediction.reasons.length > 0 && (
          <SHAPWaterfall
            reasons={prediction.reasons}
            baseValue={prediction.baseValue}
          />
        )}

        {/* Confidence/Sample Information */}
        <div className="border-t pt-3 text-xs text-muted-foreground">
          <div className="flex justify-between">
            <span>Generated</span>
            <span className="font-medium">{new Date(prediction.generatedAt).toLocaleDateString()}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function getRiskDescription(riskLevel: string): string {
  switch (riskLevel) {
    case "HIGH":
      return "High probability of forgetting - immediate attention recommended";
    case "MEDIUM":
      return "Moderate risk - consider proactive measures";
    case "LOW":
      return "Low risk - normal monitoring sufficient";
    default:
      return "";
  }
}

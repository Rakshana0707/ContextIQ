"use client";

import { useState, useEffect } from "react";
import {
  Layers,
  Cpu,
  TrendingUp,
  Activity,
  ShieldCheck,
  CheckCircle,
  Clock,
  Sparkles,
  ArrowRight,
  Info,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import type {
  ModelBenchmarkMetricsData,
  SequencePredictionResponseData,
  SequencePredictionTarget,
} from "@/types/sequence";
import { sequenceApi, mockSequencePrediction, mockSequenceBenchmarks } from "@/lib/api/services/sequence";

export function SequencePredictionCard() {
  const [target, setTarget] = useState<SequencePredictionTarget>("short_term_task_resumption");
  const [prediction, setPrediction] = useState<SequencePredictionResponseData>(mockSequencePrediction);
  const [benchmarks, setBenchmarks] = useState<ModelBenchmarkMetricsData[]>(mockSequenceBenchmarks);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    handleFetch(target);
  }, []);

  const handleFetch = async (selectedTarget: SequencePredictionTarget) => {
    setLoading(true);
    try {
      const [predRes, benchRes] = await Promise.all([
        sequenceApi.predictSequence(selectedTarget),
        sequenceApi.getBenchmark(selectedTarget),
      ]);
      setPrediction(predRes);
      setBenchmarks(benchRes);
    } catch {
      setPrediction(mockSequencePrediction);
      setBenchmarks(mockSequenceBenchmarks);
    } finally {
      setLoading(false);
    }
  };

  const targets = [
    { id: "short_term_task_resumption", label: "Resumption" },
    { id: "interruption_recovery_risk", label: "Recovery Risk" },
    { id: "future_context_switch", label: "Context Switch" },
    { id: "task_completion", label: "Completion" },
  ];

  return (
    <Card className="border-border">
      <CardHeader className="pb-3">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div>
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <Layers className="h-4 w-4 text-primary" />
              Advanced Behavioral Sequence Modeling & Benchmarking
            </CardTitle>
            <CardDescription className="text-xs">
              Learns chronological behavioral dynamics from ordered activity and interruption histories without temporal leakage.
            </CardDescription>
          </div>

          <div className="flex items-center gap-1.5 self-start sm:self-auto">
            {targets.map((t) => (
              <Button
                key={t.id}
                variant={target === t.id ? "default" : "outline"}
                size="sm"
                className="text-xs h-7 px-2.5"
                onClick={() => {
                  setTarget(t.id as SequencePredictionTarget);
                  handleFetch(t.id as SequencePredictionTarget);
                }}
              >
                {t.label}
              </Button>
            ))}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Top Prediction Overview */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {/* Tile 1: Predicted Probability */}
          <div className="border rounded-md p-3 bg-muted/20 space-y-2">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>Sequence Forecast</span>
              <Badge variant="outline" className="text-[10px] font-mono">
                {prediction.model_architecture.toUpperCase()}
              </Badge>
            </div>
            <div>
              <div className="text-2xl font-bold font-mono">
                {(prediction.predicted_probability * 100).toFixed(1)}%
              </div>
              <Progress value={prediction.predicted_probability * 100} className="h-1.5 mt-2" />
            </div>
            <div className="text-[11px] text-muted-foreground flex justify-between font-mono">
              <span>90% Interval:</span>
              <span>
                [{(prediction.confidence_interval[0] * 100).toFixed(0)}%, {(prediction.confidence_interval[1] * 100).toFixed(0)}%]
              </span>
            </div>
          </div>

          {/* Tile 2: Temporal Sequence Window */}
          <div className="border rounded-md p-3 bg-muted/20 space-y-2">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>Input Sequence Window</span>
              <Badge
                variant={prediction.is_cold_start ? "outline" : "secondary"}
                className={`text-[10px] ${prediction.is_cold_start ? "text-amber-500 border-amber-500/30" : ""}`}
              >
                {prediction.is_cold_start ? "Cold Start (L < 5)" : "Full History"}
              </Badge>
            </div>
            <div className="text-2xl font-bold font-mono">
              L = {prediction.sequence_length} events
            </div>
            <p className="text-[11px] text-muted-foreground">
              Chronologically ordered tokens up to T<sub>pred</sub> with zero future contamination.
            </p>
          </div>

          {/* Tile 3: Recent Event Attributions */}
          <div className="border rounded-md p-3 bg-muted/20 space-y-1.5">
            <div className="text-xs text-muted-foreground">Top Temporal Attributions</div>
            <div className="space-y-1 pt-1">
              {prediction.top_temporal_attributions.map((att, idx) => (
                <div key={idx} className="flex items-center justify-between text-[11px]">
                  <span className="font-mono text-foreground font-medium truncate max-w-[140px]">
                    {att.event_type}
                  </span>
                  <span className="font-mono text-muted-foreground">
                    w = {att.weight.toFixed(2)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Model Architecture Benchmarking Table */}
        <div className="border rounded-md p-3 space-y-2 bg-muted/10">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold flex items-center gap-1.5">
              <Cpu className="h-3.5 w-3.5 text-primary" />
              Candidate Sequence Model Benchmark (Chronological Split)
            </span>
            <Badge variant="outline" className="text-[10px]">
              Selection Rule: ΔPR-AUC ≥ +0.02
            </Badge>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="py-2 font-medium">Model Architecture</th>
                  <th className="py-2 font-medium">ROC-AUC</th>
                  <th className="py-2 font-medium">PR-AUC</th>
                  <th className="py-2 font-medium">Brier Score</th>
                  <th className="py-2 font-medium">Inference Latency</th>
                  <th className="py-2 font-medium text-right">Production Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/50">
                {benchmarks.map((m) => (
                  <tr key={m.model_name} className={m.is_champion ? "bg-primary/5 font-medium" : ""}>
                    <td className="py-2 font-medium">
                      <div className="flex items-center gap-1.5">
                        {m.is_champion && <Sparkles className="h-3 w-3 text-primary shrink-0" />}
                        <span>{m.model_name}</span>
                      </div>
                    </td>
                    <td className="py-2 font-mono font-semibold text-emerald-600 dark:text-emerald-400">
                      {m.roc_auc.toFixed(3)}
                    </td>
                    <td className="py-2 font-mono">{m.pr_auc.toFixed(3)}</td>
                    <td className="py-2 font-mono">{m.brier_score.toFixed(3)}</td>
                    <td className="py-2 font-mono text-muted-foreground">{m.inference_latency_ms.toFixed(2)} ms</td>
                    <td className="py-2 text-right">
                      {m.is_champion ? (
                        <Badge className="bg-primary text-primary-foreground text-[10px]">
                          Champion
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="text-[10px] text-muted-foreground">
                          Candidate
                        </Badge>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Disclaimer */}
        <p className="text-[10px] text-muted-foreground italic leading-relaxed pt-1 border-t">
          {prediction.disclaimer}
        </p>
      </CardContent>
    </Card>
  );
}

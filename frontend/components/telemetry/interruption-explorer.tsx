"use client";

import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle,
  HelpCircle,
  XCircle,
  Check,
  ChevronDown,
  ChevronUp,
  MessageSquare,
  ShieldAlert,
  ArrowRight,
  Filter,
  Sparkles,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type {
  DetectedInterruptionItem,
  InterruptionFeedbackClassification,
  InterruptionFeedbackPayload,
  InterruptionSeverity,
} from "@/types/telemetry";

interface InterruptionExplorerProps {
  interruptions: DetectedInterruptionItem[];
  onSubmitFeedback: (id: string, payload: InterruptionFeedbackPayload) => Promise<void>;
  loading?: boolean;
}

export function InterruptionExplorer({
  interruptions,
  onSubmitFeedback,
  loading,
}: InterruptionExplorerProps) {
  const [selectedSeverity, setSelectedSeverity] = useState<string>("ALL");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [notesInput, setNotesInput] = useState<Record<string, string>>({});
  const [submittingId, setSubmittingId] = useState<string | null>(null);

  const filteredInterruptions = interruptions.filter((item) => {
    if (selectedSeverity === "ALL") return true;
    return item.severity === selectedSeverity;
  });

  const handleFeedback = async (
    id: string,
    classification: InterruptionFeedbackClassification,
  ) => {
    setSubmittingId(id);
    try {
      await onSubmitFeedback(id, {
        classification,
        notes: notesInput[id] || undefined,
      });
    } finally {
      setSubmittingId(null);
    }
  };

  const getSeverityBadgeVariant = (severity: InterruptionSeverity) => {
    switch (severity) {
      case "CRITICAL":
      case "HIGH":
        return "destructive";
      case "MEDIUM":
        return "default";
      case "LOW":
      default:
        return "secondary";
    }
  };

  return (
    <Card className="border border-border/80 shadow-xs">
      <CardHeader className="pb-3">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <CardTitle className="text-base font-semibold">Interruption Explorer</CardTitle>
              <Badge variant="outline" className="text-[11px] font-normal border-amber-200 text-amber-700 dark:border-amber-800 dark:text-amber-400">
                Feedback Calibration
              </Badge>
            </div>
            <CardDescription className="text-xs mt-0.5">
              Inspect detected context switches and calibrate models with ground-truth feedback
            </CardDescription>
          </div>

          {/* Filter options */}
          <div className="flex items-center gap-1.5 self-start sm:self-auto">
            <span className="text-xs text-muted-foreground mr-1 flex items-center gap-1">
              <Filter className="h-3 w-3" /> Severity:
            </span>
            {["ALL", "HIGH", "MEDIUM", "LOW"].map((sev) => (
              <Button
                key={sev}
                variant={selectedSeverity === sev ? "secondary" : "ghost"}
                size="sm"
                className="text-xs h-7 px-2"
                onClick={() => setSelectedSeverity(sev)}
              >
                {sev}
              </Button>
            ))}
          </div>
        </div>
      </CardHeader>

      <CardContent>
        {filteredInterruptions.length === 0 ? (
          <div className="py-12 text-center text-xs text-muted-foreground space-y-2">
            <CheckCircle className="h-8 w-8 text-emerald-500 mx-auto opacity-80" />
            <p>No interruptions matching the current severity filter.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredInterruptions.map((item) => {
              const isExpanded = expandedId === item.id;
              const hasFeedback = !!item.feedback_classification;
              const isSubmitting = submittingId === item.id;

              return (
                <div
                  key={item.id}
                  className="rounded-lg border border-border/70 bg-card p-3.5 space-y-3 transition-colors hover:border-border"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                    <div className="flex items-center gap-2.5">
                      <Badge variant={getSeverityBadgeVariant(item.severity)} className="text-[10px] px-1.5 py-0.5">
                        {item.severity}
                      </Badge>
                      <span className="font-semibold text-sm text-foreground">
                        {item.interruption_type.replace(/_/g, " ")}
                      </span>
                      <span className="text-xs text-muted-foreground font-mono">
                        {new Date(item.start_timestamp).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">
                        Duration: <strong className="text-foreground">{Math.round(item.duration_seconds)}s</strong>
                      </span>
                      <span className="text-xs text-muted-foreground">•</span>
                      <span className="text-xs text-muted-foreground">
                        Observed Lag:{" "}
                        <strong className="text-foreground">
                          {item.resumption_lag_seconds ? `${Math.round(item.resumption_lag_seconds)}s` : "Pending"}
                        </strong>
                      </span>

                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0 ml-1 text-muted-foreground hover:text-foreground"
                        onClick={() => setExpandedId(isExpanded ? null : item.id)}
                        title="Toggle evidence breakdown"
                      >
                        {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                      </Button>
                    </div>
                  </div>

                  {/* Delay Tiers Summary */}
                  <div className="grid grid-cols-3 gap-2 py-1.5 px-2.5 bg-muted/30 rounded-md text-[11px]">
                    <div>
                      <span className="text-muted-foreground block">Return-to-Device:</span>
                      <span className="font-medium text-foreground">
                        {item.return_to_device_delay_seconds != null
                          ? `${Math.round(item.return_to_device_delay_seconds)}s`
                          : "—"}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground block">Return-to-App:</span>
                      <span className="font-medium text-foreground">
                        {item.return_to_app_delay_seconds != null
                          ? `${Math.round(item.return_to_app_delay_seconds)}s`
                          : "—"}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground block">Confirmed Resumption:</span>
                      <span className="font-medium text-foreground">
                        {item.confirmed_task_resumption_delay_seconds != null ? (
                          <span className="text-emerald-600 dark:text-emerald-400 font-semibold">
                            {Math.round(item.confirmed_task_resumption_delay_seconds)}s
                          </span>
                        ) : (
                          <span className="text-muted-foreground italic">Estimated</span>
                        )}
                      </span>
                    </div>
                  </div>

                  {/* Expanded Evidence & Notes */}
                  {isExpanded && (
                    <div className="pt-2 border-t border-border/60 space-y-2 text-xs">
                      <div>
                        <span className="font-medium text-muted-foreground block mb-1">
                          Observed Signals & Evidence:
                        </span>
                        <ul className="list-disc pl-4 space-y-0.5 text-muted-foreground">
                          {Array.isArray(item.evidence_signals) ? (
                            item.evidence_signals.map((sig, idx) => (
                              <li key={idx}>{String(sig)}</li>
                            ))
                          ) : (
                            <li>Rule-based heuristic pattern match</li>
                          )}
                        </ul>
                      </div>

                      <div className="pt-1">
                        <label className="text-[11px] text-muted-foreground block mb-1">
                          Feedback notes (optional context):
                        </label>
                        <Input
                          placeholder="e.g., Answering quick question from colleague..."
                          value={notesInput[item.id] ?? item.feedback_notes ?? ""}
                          onChange={(e) =>
                            setNotesInput((prev) => ({ ...prev, [item.id]: e.target.value }))
                          }
                          className="h-8 text-xs"
                          disabled={isSubmitting}
                        />
                      </div>
                    </div>
                  )}

                  {/* Feedback Action Buttons */}
                  <div className="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-border/40">
                    <div className="text-[11px] text-muted-foreground">
                      {hasFeedback ? (
                        <span className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 font-medium">
                          <Check className="h-3 w-3" />
                          Marked as {item.feedback_classification?.replace(/_/g, " ")}
                        </span>
                      ) : (
                        <span>Was this an actual work disruption?</span>
                      )}
                    </div>

                    <div className="flex items-center gap-1.5">
                      <Button
                        variant={item.feedback_classification === "GENUINE_INTERRUPTION" ? "default" : "outline"}
                        size="sm"
                        className="h-7 text-xs px-2.5"
                        onClick={() => handleFeedback(item.id, "GENUINE_INTERRUPTION")}
                        disabled={isSubmitting}
                      >
                        <AlertTriangle className="h-3 w-3 mr-1 text-amber-500" />
                        Genuine Interruption
                      </Button>

                      <Button
                        variant={item.feedback_classification === "INTENTIONAL_SWITCH" ? "default" : "outline"}
                        size="sm"
                        className="h-7 text-xs px-2.5"
                        onClick={() => handleFeedback(item.id, "INTENTIONAL_SWITCH")}
                        disabled={isSubmitting}
                      >
                        <CheckCircle className="h-3 w-3 mr-1 text-blue-500" />
                        Intentional Switch
                      </Button>

                      <Button
                        variant={item.feedback_classification === "INCORRECT_DETECTION" ? "destructive" : "ghost"}
                        size="sm"
                        className="h-7 text-xs px-2 text-muted-foreground hover:text-foreground"
                        onClick={() => handleFeedback(item.id, "INCORRECT_DETECTION")}
                        disabled={isSubmitting}
                      >
                        <XCircle className="h-3 w-3 mr-1" />
                        Dismiss
                      </Button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

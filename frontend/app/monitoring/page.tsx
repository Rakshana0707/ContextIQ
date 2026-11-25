"use client";

import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  TrendingUp,
  History,
  Layers,
  ArrowUpRight,
  ArrowDownRight,
  Server,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { SystemObservabilityView } from "@/components/monitoring/system-observability-view";

// Mock data representing monitoring API response
const INITIAL_MONITORING_STATUS = {
  model_name: "logistic_regression",
  model_version: "1.1.0",
  status: "HEALTHY",
  overall_drift: "STABLE",
  baseline_pr_auc: 0.4676,
  baseline_roc_auc: 0.6770,
  baseline_brier: 0.2234,
  last_trained: "2026-11-20T14:00:00Z",
  total_deployments: 3,
};

const INITIAL_CHALLENGER = {
  status: "PENDING_APPROVAL",
  candidate_version: "1.2.0",
  current_champion_version: "1.1.0",
  candidate_model_type: "logistic_regression",
  created_at: new Date().toISOString(),
  champion_metrics: { pr_auc: 0.4676, roc_auc: 0.6770, brier_score: 0.2234 },
  challenger_metrics: { pr_auc: 0.4782, roc_auc: 0.6845, brier_score: 0.2180 },
  delta_pr_auc: 0.0106,
  meets_promotion_criteria: true,
  recommendation: "PROMOTE_CHALLENGER",
  reason: "Challenger v1.2.0 improves PR-AUC by +0.0106 on held-out temporal evaluation window.",
};

const FEATURE_DRIFT_ROWS = [
  { feature: "deadline_distance_hours", display: "Deadline Proximity", type: "numeric", psi: 0.042, ks_pval: 0.38, missing_delta: 0.0, status: "STABLE" },
  { feature: "historical_forgetting_rate", display: "Historical Forgetting Rate", type: "numeric", psi: 0.061, ks_pval: 0.24, missing_delta: 0.0, status: "STABLE" },
  { feature: "interruptions_today", display: "Daily Interruptions", type: "numeric", psi: 0.128, ks_pval: 0.03, missing_delta: 0.0, status: "MODERATE" },
  { feature: "recent_context_switches", display: "Recent Context Switches", type: "numeric", psi: 0.054, ks_pval: 0.19, missing_delta: 0.0, status: "STABLE" },
  { feature: "avg_interruption_duration", display: "Avg Interruption Duration", type: "numeric", psi: 0.038, ks_pval: 0.42, missing_delta: 0.0, status: "STABLE" },
  { feature: "task_category", display: "Task Category", type: "categorical", psi: 0.048, js_div: 0.032, missing_delta: 0.0, status: "STABLE" },
  { feature: "priority", display: "Task Priority", type: "categorical", psi: 0.025, js_div: 0.018, missing_delta: 0.0, status: "STABLE" },
  { feature: "tasks_today", display: "Tasks Today", type: "numeric", psi: 0.077, ks_pval: 0.11, missing_delta: 0.0, status: "STABLE" },
];

const DEPLOYMENT_HISTORY = [
  { event_id: "DEP-2026112001", type: "PROMOTION", version: "1.1.0", model: "logistic_regression", approved_by: "MLOps Admin", timestamp: "2026-11-20 14:00", reason: "Phase 2.5 probability calibration & threshold upgrade" },
  { event_id: "DEP-2026111802", type: "PROMOTION", version: "1.0.0", model: "logistic_regression", approved_by: "MLOps Admin", timestamp: "2026-11-18 10:30", reason: "Initial benchmark champion model promotion" },
];

export default function MonitoringPage() {
  const [challenger, setChallenger] = useState<any>(INITIAL_CHALLENGER);
  const [modelStatus, setModelStatus] = useState<any>(INITIAL_MONITORING_STATUS);
  const [history, setHistory] = useState(DEPLOYMENT_HISTORY);
  const [isRetraining, setIsRetraining] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const handleTriggerRetrain = () => {
    setIsRetraining(true);
    setActionMessage("Executing 10-step temporal retraining pipeline in background...");
    setTimeout(() => {
      setIsRetraining(false);
      setChallenger({
        ...INITIAL_CHALLENGER,
        status: "PENDING_APPROVAL",
        candidate_version: "1.2.0",
        created_at: new Date().toISOString(),
      });
      setActionMessage("Retraining completed! Challenger v1.2.0 generated and awaiting approval.");
    }, 1500);
  };

  const handleApprove = () => {
    setModelStatus((prev: any) => ({
      ...prev,
      model_version: challenger.candidate_version,
      last_trained: new Date().toISOString(),
      total_deployments: prev.total_deployments + 1,
    }));
    const newEvent = {
      event_id: `DEP-${Date.now().toString().slice(-8)}`,
      type: "PROMOTION",
      version: challenger.candidate_version,
      model: challenger.candidate_model_type,
      approved_by: "MLOps Admin (UI)",
      timestamp: new Date().toLocaleString(),
      reason: challenger.reason,
    };
    setHistory([newEvent, ...history]);
    setChallenger(null);
    setActionMessage(`Successfully deployed Challenger v${challenger.candidate_version} to production!`);
  };

  const handleReject = () => {
    setChallenger(null);
    setActionMessage("Candidate challenger model rejected. Production model left untouched.");
  };

  const handleRollback = () => {
    if (history.length > 1) {
      const prev = history[1];
      setModelStatus((status: any) => ({
        ...status,
        model_version: prev.version,
      }));
      const rollbackEvent = {
        event_id: `DEP-${Date.now().toString().slice(-8)}`,
        type: "ROLLBACK",
        version: prev.version,
        model: prev.model,
        approved_by: "MLOps Admin (Rollback)",
        timestamp: new Date().toLocaleString(),
        reason: `Reverted to previous stable version v${prev.version}`,
      };
      setHistory([rollbackEvent, ...history]);
      setActionMessage(`Rollback executed! Restored previous production model v${prev.version}.`);
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Activity className="h-6 w-6 text-blue-600" />
            ML Observability & Continual Learning
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Statistical drift monitoring, champion vs. challenger evaluation, and audited model governance.
          </p>
        </div>
        <Button
          onClick={handleTriggerRetrain}
          disabled={isRetraining}
          className="gap-2 bg-blue-600 hover:bg-blue-700 text-white shrink-0"
        >
          <RefreshCw className={cn("h-4 w-4", isRetraining && "animate-spin")} />
          {isRetraining ? "Evaluating Pipeline..." : "Trigger Retraining"}
        </Button>
      </div>

      {actionMessage && (
        <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-900 flex items-center justify-between">
          <span>{actionMessage}</span>
          <button onClick={() => setActionMessage(null)} className="text-blue-500 hover:text-blue-700 font-bold ml-2">
            ×
          </button>
        </div>
      )}

      {/* KPI Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="text-xs">Active Champion</CardDescription>
            <CardTitle className="text-lg flex items-center justify-between">
              <span className="font-mono text-base">{modelStatus.model_name}</span>
              <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-200 font-mono">
                v{modelStatus.model_version}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xs text-muted-foreground">
              Status: <span className="text-emerald-600 font-semibold">Active In Production</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="text-xs">Overall Drift Status</CardDescription>
            <CardTitle className="text-lg flex items-center justify-between">
              <span>{modelStatus.overall_drift}</span>
              <CheckCircle className="h-5 w-5 text-emerald-600" />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xs text-muted-foreground">
              Feature PSI: <span className="font-semibold text-foreground">0.054 (Safe)</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="text-xs">Baseline PR-AUC</CardDescription>
            <CardTitle className="text-lg flex items-center justify-between">
              <span className="font-mono">{modelStatus.baseline_pr_auc.toFixed(4)}</span>
              <TrendingUp className="h-5 w-5 text-blue-600" />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xs text-muted-foreground">
              ROC-AUC: <span className="font-mono font-medium">{modelStatus.baseline_roc_auc.toFixed(4)}</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="text-xs">Model Governance</CardDescription>
            <CardTitle className="text-lg flex items-center justify-between">
              <span>{modelStatus.total_deployments} Deployments</span>
              <ShieldCheck className="h-5 w-5 text-indigo-600" />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xs text-muted-foreground">
              Human Gate: <span className="text-indigo-600 font-semibold">Enforced</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Champion vs Challenger Governance Card (Gate 9) */}
      {challenger && (
        <Card className="border-2 border-blue-500/60 shadow-sm bg-gradient-to-r from-blue-50/30 to-indigo-50/20">
          <CardHeader className="pb-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <div className="flex items-center gap-2">
                  <Badge className="bg-amber-500 text-white font-mono text-[10px]">HUMAN APPROVAL REQUIRED</Badge>
                  <span className="text-xs text-muted-foreground font-mono">Step 9/10</span>
                </div>
                <CardTitle className="text-base font-semibold mt-1">
                  Champion vs. Challenger Candidate Review
                </CardTitle>
                <CardDescription className="text-xs">
                  {challenger.reason}
                </CardDescription>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <Button
                  onClick={handleReject}
                  variant="outline"
                  size="sm"
                  className="text-red-600 border-red-200 hover:bg-red-50"
                >
                  Reject Candidate
                </Button>
                <Button
                  onClick={handleApprove}
                  size="sm"
                  className="bg-emerald-600 hover:bg-emerald-700 text-white gap-1"
                >
                  <CheckCircle className="h-4 w-4" />
                  Approve Deployment
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2 border-t text-xs">
              <div className="p-3 bg-white dark:bg-card rounded-lg border">
                <span className="text-muted-foreground font-medium">Metric Comparison</span>
                <div className="mt-2 space-y-1 font-mono">
                  <div className="flex justify-between">
                    <span>PR-AUC:</span>
                    <span>
                      {challenger.champion_metrics.pr_auc.toFixed(4)} →{" "}
                      <strong className="text-emerald-600">{challenger.challenger_metrics.pr_auc.toFixed(4)}</strong>
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>ROC-AUC:</span>
                    <span>
                      {challenger.champion_metrics.roc_auc.toFixed(4)} →{" "}
                      <strong>{challenger.challenger_metrics.roc_auc.toFixed(4)}</strong>
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Brier Score:</span>
                    <span>
                      {challenger.champion_metrics.brier_score.toFixed(4)} →{" "}
                      <strong className="text-emerald-600">{challenger.challenger_metrics.brier_score.toFixed(4)}</strong>
                    </span>
                  </div>
                </div>
              </div>

              <div className="p-3 bg-white dark:bg-card rounded-lg border">
                <span className="text-muted-foreground font-medium">Performance Delta</span>
                <div className="mt-2 space-y-1">
                  <div className="flex items-center gap-1.5 text-emerald-600 font-semibold font-mono text-sm">
                    <ArrowUpRight className="h-4 w-4" />
                    +{ (challenger.delta_pr_auc * 100).toFixed(2) }% PR-AUC Gain
                  </div>
                  <p className="text-[11px] text-muted-foreground">
                    Exceeds minimum candidate threshold (Δ ≥ +0.0100). No feature or label leakage detected.
                  </p>
                </div>
              </div>

              <div className="p-3 bg-white dark:bg-card rounded-lg border">
                <span className="text-muted-foreground font-medium">Safety Verification</span>
                <div className="mt-2 space-y-1 text-[11px] text-muted-foreground">
                  <div>✓ Calibration: Platt Scaling fitted (ECE &lt; 0.02)</div>
                  <div>✓ Explainability: Verified non-causal SHAP values</div>
                  <div>✓ Pre-deployment archive ready for instant rollback</div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Main Tabs: Feature Drift vs Deployment History */}
      <Tabs defaultValue="features" className="space-y-4">
        <TabsList>
          <TabsTrigger value="features" className="gap-2">
            <Activity className="h-4 w-4" />
            Feature Drift Metrics
          </TabsTrigger>
          <TabsTrigger value="history" className="gap-2">
            <History className="h-4 w-4" />
            Deployment History & Rollback
          </TabsTrigger>
          <TabsTrigger value="reliability" className="gap-2">
            <Server className="h-4 w-4" />
            System Reliability & Observability
          </TabsTrigger>
        </TabsList>

        {/* Feature Drift Tab */}
        <TabsContent value="features">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold">Population Stability Index & Distribution Diagnostics</CardTitle>
              <CardDescription className="text-xs">
                Statistical drift evaluated against the training baseline reference profile (PSI &lt; 0.10: Stable, 0.10–0.20: Moderate, ≥ 0.20: Drift).
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="border-b bg-muted/30 text-muted-foreground">
                    <tr>
                      <th className="py-2.5 px-3 font-medium">Feature</th>
                      <th className="py-2.5 px-3 font-medium">Type</th>
                      <th className="py-2.5 px-3 font-medium">PSI</th>
                      <th className="py-2.5 px-3 font-medium">KS p-value / JSD</th>
                      <th className="py-2.5 px-3 font-medium">Missing Δ</th>
                      <th className="py-2.5 px-3 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {FEATURE_DRIFT_ROWS.map((row) => (
                      <tr key={row.feature} className="hover:bg-muted/20">
                        <td className="py-2.5 px-3 font-medium">
                          {row.display}
                          <span className="block text-[10px] text-muted-foreground font-mono">{row.feature}</span>
                        </td>
                        <td className="py-2.5 px-3 capitalize text-muted-foreground">{row.type}</td>
                        <td className="py-2.5 px-3 font-mono font-medium">{row.psi.toFixed(3)}</td>
                        <td className="py-2.5 px-3 font-mono text-muted-foreground">
                          {row.ks_pval !== undefined ? `p=${row.ks_pval.toFixed(2)}` : `JSD=${row.js_div?.toFixed(3)}`}
                        </td>
                        <td className="py-2.5 px-3 font-mono text-muted-foreground">+{row.missing_delta.toFixed(2)}%</td>
                        <td className="py-2.5 px-3">
                          <Badge
                            variant="outline"
                            className={cn(
                              "text-[10px]",
                              row.status === "STABLE"
                                ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                                : "bg-yellow-50 text-yellow-700 border-yellow-200"
                            )}
                          >
                            {row.status}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Deployment History Tab */}
        <TabsContent value="history">
          <Card>
            <CardHeader className="flex-row items-center justify-between pb-3">
              <div>
                <CardTitle className="text-base font-semibold">Model Deployment Audit Ledger</CardTitle>
                <CardDescription className="text-xs">
                  Historical promotions, approvals, and rollback events.
                </CardDescription>
              </div>
              <Button
                onClick={handleRollback}
                variant="outline"
                size="sm"
                className="gap-1.5 text-xs text-amber-700 border-amber-300 hover:bg-amber-50"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Rollback to Previous Version
              </Button>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {history.map((item) => (
                  <div key={item.event_id} className="p-3 bg-muted/20 border rounded-lg text-xs space-y-1">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Badge
                          variant="outline"
                          className={cn(
                            "text-[10px] font-mono",
                            item.type === "PROMOTION"
                              ? "bg-blue-50 text-blue-700 border-blue-200"
                              : "bg-amber-50 text-amber-700 border-amber-200"
                          )}
                        >
                          {item.type}
                        </Badge>
                        <span className="font-semibold text-foreground">
                          {item.model} v{item.version}
                        </span>
                      </div>
                      <span className="text-muted-foreground font-mono text-[11px]">{item.timestamp}</span>
                    </div>
                    <p className="text-muted-foreground">{item.reason}</p>
                    <div className="text-[11px] text-muted-foreground/80 flex items-center gap-2 pt-0.5">
                      <span>Approved by: <strong className="font-medium text-foreground">{item.approved_by}</strong></span>
                      <span>•</span>
                      <span className="font-mono text-[10px]">{item.event_id}</span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* System Reliability Tab */}
        <TabsContent value="reliability">
          <SystemObservabilityView />
        </TabsContent>
      </Tabs>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import {
  Zap,
  Sparkles,
  CheckCircle2,
  XCircle,
  Clock,
  Clock3,
  RotateCcw,
  Info,
  Check,
  X,
  ShieldCheck,
  BrainCircuit,
  Layers,
} from "lucide-react";
import {
  adaptiveApi,
  UserInterventionItem,
} from "@/lib/api/services/adaptive";

export default function InterventionCenterPage() {
  const [interventions, setInterventions] = useState<UserInterventionItem[]>([]);
  const [activeTab, setActiveTab] = useState<"ACTIVE" | "COMPLETED" | "ALL">("ACTIVE");
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const fetchInterventions = async () => {
    setLoading(true);
    try {
      const res = await adaptiveApi.getInterventionHistory(50);
      if (res.data) setInterventions(res.data);
    } catch {
      // Non-blocking failover
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInterventions();
  }, []);

  const handleGenerate = async () => {
    setActionLoading(true);
    try {
      const res = await adaptiveApi.generateInterventions();
      if (res.data) {
        setStatusMessage(`Generated ${res.data.generated_count} contextual interventions.`);
        await fetchInterventions();
      }
    } finally {
      setActionLoading(false);
    }
  };

  const handleAction = async (id: string, action: "ACCEPT" | "DISMISS" | "DEFER" | "COMPLETE") => {
    try {
      await adaptiveApi.actionIntervention(id, action, `Action: ${action} via dashboard`);
      setInterventions((prev) =>
        prev.map((item) => (item.id === id ? { ...item, lifecycle_status: action === "ACCEPT" ? "ACCEPTED" : action === "DISMISS" ? "DISMISSED" : action === "DEFER" ? "DEFERRED" : "COMPLETED" } : item))
      );
      setStatusMessage(`Intervention marked as ${action.toLowerCase()}.`);
    } catch {
      // Ignore
    }
  };

  const filteredInterventions = interventions.filter((item) => {
    if (activeTab === "ACTIVE") {
      return ["GENERATED", "PRESENTED", "ACCEPTED", "DEFERRED"].includes(item.lifecycle_status);
    }
    if (activeTab === "COMPLETED") {
      return item.lifecycle_status === "COMPLETED";
    }
    return true;
  });

  const getCategoryBadgeClass = (category: string) => {
    switch (category) {
      case "FOCUS":
        return "bg-indigo-500/15 text-indigo-600 dark:text-indigo-400 border-indigo-500/30";
      case "RECOVERY":
        return "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30";
      case "TASK":
        return "bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30";
      case "CONTEXTUAL":
        return "bg-violet-500/15 text-violet-600 dark:text-violet-400 border-violet-500/30";
      default:
        return "bg-slate-500/15 text-slate-600 dark:text-slate-400 border-slate-500/30";
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto p-4 sm:p-6 lg:p-8 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border/70 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20 shadow-xs">
              <Zap className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-xl sm:text-2xl font-black tracking-tight text-foreground flex items-center gap-2">
                Personalized Intervention Center
              </h1>
              <p className="text-xs text-muted-foreground">
                Actionable micro-interventions grounded in observed cognitive friction, forgetting risk, and focus windows.
              </p>
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={handleGenerate}
          disabled={actionLoading}
          className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold shadow-sm transition-all"
        >
          <Sparkles className="h-3.5 w-3.5" />
          <span>{actionLoading ? "Evaluating..." : "Generate Interventions"}</span>
        </button>
      </div>

      {statusMessage && (
        <div className="p-3 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-xs font-semibold text-indigo-700 dark:text-indigo-300 flex items-center justify-between">
          <span>{statusMessage}</span>
          <button type="button" onClick={() => setStatusMessage(null)} className="text-muted-foreground hover:text-foreground">
            &times;
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-border/60 pb-2">
        <button
          type="button"
          onClick={() => setActiveTab("ACTIVE")}
          className={`px-3 py-1.5 rounded-xl font-bold text-xs transition-all ${
            activeTab === "ACTIVE"
              ? "bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 border border-indigo-200/80 dark:border-indigo-900/60"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          Active & Pending
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("COMPLETED")}
          className={`px-3 py-1.5 rounded-xl font-bold text-xs transition-all ${
            activeTab === "COMPLETED"
              ? "bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 border border-indigo-200/80 dark:border-indigo-900/60"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          Completed
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("ALL")}
          className={`px-3 py-1.5 rounded-xl font-bold text-xs transition-all ${
            activeTab === "ALL"
              ? "bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 border border-indigo-200/80 dark:border-indigo-900/60"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          All History ({interventions.length})
        </button>
      </div>

      {/* Interventions List */}
      {loading && interventions.length === 0 ? (
        <div className="py-16 text-center text-xs text-muted-foreground">Evaluating contextual interventions...</div>
      ) : filteredInterventions.length === 0 ? (
        <div className="py-16 text-center space-y-2 border border-dashed border-border/80 rounded-2xl bg-card">
          <div className="flex h-12 w-12 mx-auto items-center justify-center rounded-full bg-indigo-500/10 text-indigo-500">
            <CheckCircle2 className="h-6 w-6" />
          </div>
          <h4 className="font-bold text-sm text-foreground">No Pending Interventions</h4>
          <p className="text-xs text-muted-foreground max-w-sm mx-auto">
            Your current working context is stable with optimal cognitive flow. New interventions will appear when micro-delays or forgetting risks spike.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredInterventions.map((item) => (
            <div key={item.id} className="p-5 rounded-2xl border border-border/70 bg-card shadow-xs space-y-3 flex flex-col justify-between">
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border uppercase ${getCategoryBadgeClass(item.intervention_category)}`}>
                    {item.intervention_category}
                  </span>
                  <div className="flex items-center gap-1.5 text-[10px] font-mono text-muted-foreground">
                    <Clock3 className="h-3 w-3" />
                    <span>Relevance {(item.relevance_score).toFixed(0)}%</span>
                  </div>
                </div>

                <h3 className="font-bold text-sm text-foreground leading-snug">{item.title}</h3>
                <p className="text-xs text-muted-foreground leading-relaxed">{item.message}</p>

                {/* Grounded Explainability Section */}
                <div className="p-3 rounded-xl bg-muted/40 border border-border/50 text-xs space-y-1.5">
                  <div className="flex items-center gap-1 text-[11px] font-semibold text-foreground">
                    <BrainCircuit className="h-3.5 w-3.5 text-indigo-500" />
                    <span>Why ContextIQ Recommends This:</span>
                  </div>
                  <p className="text-[11px] text-muted-foreground leading-relaxed">
                    {item.trigger_condition}
                  </p>
                  <div className="flex items-center justify-between pt-1 border-t border-border/30 text-[10px] text-muted-foreground">
                    <span>Expected: {item.expected_outcome}</span>
                    <span className="font-mono uppercase font-bold text-indigo-600 dark:text-indigo-400">
                      Effort: {item.estimated_effort}
                    </span>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-between pt-2 border-t border-border/40">
                <span className="text-[10px] font-mono text-muted-foreground uppercase">
                  Status: {item.lifecycle_status}
                </span>

                {item.lifecycle_status !== "COMPLETED" && item.lifecycle_status !== "DISMISSED" && (
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() => handleAction(item.id, "ACCEPT")}
                      className="px-2.5 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs flex items-center gap-1 shadow-xs transition-colors"
                    >
                      <Check className="h-3.5 w-3.5" /> Accept
                    </button>
                    <button
                      type="button"
                      onClick={() => handleAction(item.id, "COMPLETE")}
                      className="px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs flex items-center gap-1 shadow-xs transition-colors"
                    >
                      Complete
                    </button>
                    <button
                      type="button"
                      onClick={() => handleAction(item.id, "DISMISS")}
                      className="p-1 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                      title="Dismiss"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

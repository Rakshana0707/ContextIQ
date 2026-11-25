"use client";

import React, { useState } from "react";
import {
  Sparkles,
  RefreshCw,
  Plus,
  Play,
  Layers,
  Clock,
  Shield,
  ArrowRight,
  CheckCircle2,
  Filter,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { WorkflowExecutionPlan } from "@/types/workflows";

interface WorkflowPlanListProps {
  plans: WorkflowExecutionPlan[];
  loading: boolean;
  onRefresh: () => void;
  onSelectPlan: (plan: WorkflowExecutionPlan) => void;
  onSynthesize: () => void;
}

export const WorkflowPlanList: React.FC<WorkflowPlanListProps> = ({
  plans,
  loading,
  onRefresh,
  onSelectPlan,
  onSynthesize,
}) => {
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  const filteredPlans = plans.filter((p) => {
    if (statusFilter === "ALL") return true;
    return p.status === statusFilter;
  });

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="p-4 rounded-xl bg-gradient-to-r from-indigo-950/40 via-zinc-900 to-zinc-900 border border-indigo-800/30 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-indigo-400" />
            <h3 className="font-semibold text-zinc-100 text-sm">
              Intelligent Multi-Step Workflow Orchestration
            </h3>
          </div>
          <p className="text-xs text-zinc-400 mt-1">
            Converts forgetting risks, calendar conflicts, and recovery delays into structured, multi-step governed action plans.
          </p>
        </div>

        <Button
          size="sm"
          onClick={onSynthesize}
          className="h-8 text-xs bg-indigo-600 hover:bg-indigo-500 text-white font-medium gap-1.5 shrink-0"
        >
          <Play className="w-3.5 h-3.5" />
          Synthesize 7-Step Plan
        </Button>
      </div>

      {/* Filter and Refresh Bar */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-zinc-400" />
          <span className="text-xs text-zinc-400 font-medium">Lifecycle Filter:</span>
          {(["ALL", "AWAITING_APPROVAL", "APPROVED", "EXECUTING", "COMPLETED", "CANCELLED"] as const).map(
            (status) => (
              <button
                key={status}
                onClick={() => setStatusFilter(status)}
                className={`px-2.5 py-1 text-xs rounded-md font-medium transition-colors ${
                  statusFilter === status
                    ? "bg-zinc-800 text-indigo-400 border border-zinc-700"
                    : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900"
                }`}
              >
                {status.replace(/_/g, " ")}
              </button>
            )
          )}
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={onRefresh}
          disabled={loading}
          className="h-8 text-xs border-zinc-700 bg-zinc-800/60 hover:bg-zinc-800 text-zinc-300"
        >
          <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? "animate-spin" : ""}`} />
          Refresh Plans
        </Button>
      </div>

      {/* Plan Cards */}
      {filteredPlans.length === 0 ? (
        <div className="p-12 text-center border border-dashed border-zinc-800 rounded-xl bg-zinc-950/40">
          <Layers className="w-8 h-8 text-zinc-600 mx-auto mb-3" />
          <h4 className="text-sm font-semibold text-zinc-300">No Workflow Plans Found</h4>
          <p className="text-xs text-zinc-500 mt-1 max-w-md mx-auto">
            Click &apos;Synthesize 7-Step Plan&apos; to generate a governed multi-step focus and recovery workflow.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredPlans.map((plan) => (
            <div
              key={plan.id}
              onClick={() => onSelectPlan(plan)}
              className="p-4 rounded-xl bg-zinc-900/80 border border-zinc-800 hover:border-zinc-700 cursor-pointer transition-all shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4"
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <h4 className="font-semibold text-zinc-100 text-sm hover:text-indigo-400 transition-colors">
                    {plan.title}
                  </h4>
                  <Badge
                    variant="outline"
                    className={`text-[11px] ${
                      plan.status === "AWAITING_APPROVAL"
                        ? "text-amber-400 border-amber-500/30 bg-amber-500/10"
                        : plan.status === "APPROVED"
                        ? "text-emerald-400 border-emerald-500/30 bg-emerald-500/10"
                        : "text-zinc-400 border-zinc-700"
                    }`}
                  >
                    {plan.status.replace(/_/g, " ")}
                  </Badge>
                  <span className="text-xs font-mono text-zinc-500">v{plan.version}</span>
                </div>
                <p className="text-xs text-zinc-400 line-clamp-1">{plan.rationale}</p>
                <div className="flex items-center gap-3 text-[11px] text-zinc-500 font-mono pt-1">
                  <span>{plan.plan_steps.length} Steps</span>
                  <span>•</span>
                  <span>Utility: {plan.utility_score}</span>
                  <span>•</span>
                  <span>Created {new Date(plan.created_at).toLocaleDateString()}</span>
                </div>
              </div>

              <div className="flex items-center gap-2 self-end md:self-center shrink-0">
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 text-xs border-zinc-700 bg-zinc-800/80 hover:bg-zinc-800 text-zinc-200"
                >
                  Preview & Review Plan
                  <ArrowRight className="w-3.5 h-3.5 ml-1.5 text-zinc-400" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

"use client";

import React, { useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Brain,
  Calendar,
  Check,
  CheckCircle2,
  Clock,
  Layers,
  RotateCcw,
  Shield,
  ShieldCheck,
  Sparkles,
  X,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { WorkflowStepCard } from "./workflow-step-card";
import type { WorkflowExecutionPlan, PlanComparisonCandidate } from "@/types/workflows";

interface WorkflowPreviewModalProps {
  plan: WorkflowExecutionPlan | null;
  isOpen: boolean;
  onClose: () => void;
  onApprove: (planId: string) => void;
  onReject: (planId: string) => void;
}

export const WorkflowPreviewModal: React.FC<WorkflowPreviewModalProps> = ({
  plan,
  isOpen,
  onClose,
  onApprove,
  onReject,
}) => {
  const [activeStrategyIndex, setActiveStrategyIndex] = useState(0);

  if (!isOpen || !plan) return null;

  const alternatives: PlanComparisonCandidate[] =
    plan.plan_comparison_metadata?.alternatives || [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in">
      <div className="relative w-full max-w-4xl max-h-[90vh] bg-zinc-900 border border-zinc-700/80 rounded-2xl shadow-2xl flex flex-col overflow-hidden text-zinc-100">
        {/* Header */}
        <div className="p-5 border-b border-zinc-800 flex items-start justify-between gap-4 bg-zinc-950/60">
          <div className="flex items-start gap-3">
            <div className="p-2.5 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 mt-0.5">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-base font-bold text-zinc-100">{plan.title}</h2>
                <Badge variant="outline" className="text-xs text-amber-400 border-amber-500/30 bg-amber-500/10">
                  {plan.status}
                </Badge>
                <span className="text-xs font-mono text-zinc-400">v{plan.version}</span>
              </div>
              <p className="text-xs text-zinc-400 mt-1">
                Governed autonomous multi-step workflow proposal awaiting user confirmation.
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Scrollable Body */}
        <div className="p-6 overflow-y-auto space-y-6 text-xs">
          {/* Rationale and Strategy Ribbon */}
          <div className="p-4 rounded-xl bg-zinc-950/60 border border-zinc-800 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-zinc-200 flex items-center gap-1.5">
                <Brain className="w-4 h-4 text-cyan-400" />
                Strategic Rationale & Cognitive Intent
              </span>
              <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-zinc-300 font-mono text-[11px]">
                <Shield className="w-3.5 h-3.5 text-cyan-400" />
                Utility Score: {plan.utility_score}
              </div>
            </div>
            <p className="text-zinc-300 leading-relaxed">{plan.rationale}</p>
          </div>

          {/* Expected Effects & Reversibility Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-3.5 rounded-xl bg-emerald-950/20 border border-emerald-800/30 space-y-1.5">
              <div className="flex items-center gap-1.5 text-emerald-400 font-semibold text-xs">
                <CheckCircle2 className="w-4 h-4" />
                Expected Productivity Benefits
              </div>
              <div className="space-y-1 text-zinc-300">
                {Object.entries(plan.expected_benefits).map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between text-[11px]">
                    <span className="capitalize">{k.replace(/_/g, " ")}:</span>
                    <span className="font-semibold text-emerald-300">{String(v)}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 space-y-1.5">
              <div className="flex items-center gap-1.5 text-zinc-300 font-semibold text-xs">
                <RotateCcw className="w-4 h-4 text-cyan-400" />
                Reversibility & Compensation Guarantee
              </div>
              <p className="text-[11px] text-zinc-400">
                {plan.reversibility_summary.rollback_guarantee || "Fully reversible via registered inverse compensating actions."}
              </p>
            </div>
          </div>

          {/* Plan Comparison Tabs (Alternative Strategies) */}
          {alternatives.length > 0 && (
            <div className="space-y-2">
              <span className="font-semibold text-zinc-200 flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-indigo-400" />
                Multi-Attribute Plan Comparison
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                {alternatives.map((alt, idx) => (
                  <button
                    key={alt.strategy}
                    type="button"
                    onClick={() => setActiveStrategyIndex(idx)}
                    className={`p-3 rounded-lg border text-left transition-all ${
                      activeStrategyIndex === idx
                        ? "bg-zinc-800/90 border-indigo-500/80 shadow-sm"
                        : "bg-zinc-950/60 border-zinc-800 hover:border-zinc-700"
                    }`}
                  >
                    <div className="flex items-center justify-between text-[11px] font-semibold text-zinc-200 mb-1">
                      <span>{alt.strategy}</span>
                      <span className="text-cyan-400 font-mono">U: {alt.utility_score}</span>
                    </div>
                    <p className="text-[10px] text-zinc-400 line-clamp-2">{alt.trade_off_summary}</p>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Step-by-Step DAG Plan */}
          <div className="space-y-3">
            <span className="font-semibold text-zinc-200 flex items-center gap-1.5">
              <Clock className="w-4 h-4 text-amber-400" />
              Governed Execution Steps ({plan.plan_steps.length} Steps)
            </span>
            <div className="space-y-1 pt-1">
              {plan.plan_steps.map((step, idx) => (
                <WorkflowStepCard
                  key={step.step_key}
                  step={step}
                  isLast={idx === plan.plan_steps.length - 1}
                />
              ))}
            </div>
          </div>
        </div>

        {/* Footer / Approval Controls */}
        <div className="p-4 border-t border-zinc-800 bg-zinc-950/80 flex items-center justify-between gap-3 flex-wrap">
          <div className="text-[11px] text-zinc-400 flex items-center gap-1.5">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            Deterministic validation passed: zero arbitrary code execution.
          </div>

          <div className="flex items-center gap-2.5">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onReject(plan.id)}
              className="h-8 text-xs border-zinc-700 bg-zinc-800/60 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200"
            >
              <X className="w-3.5 h-3.5 mr-1" />
              Reject & Cancel
            </Button>

            <Button
              size="sm"
              onClick={() => onApprove(plan.id)}
              className="h-8 text-xs bg-indigo-600 hover:bg-indigo-500 text-white font-medium"
            >
              <Check className="w-3.5 h-3.5 mr-1" />
              Approve Workflow Plan
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

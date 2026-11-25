"use client";

import React from "react";
import {
  ArrowRight,
  Calendar,
  CheckCircle2,
  Clock,
  Layers,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { WorkflowStep } from "@/types/workflows";

interface WorkflowStepCardProps {
  step: WorkflowStep;
  isLast?: boolean;
}

export const WorkflowStepCard: React.FC<WorkflowStepCardProps> = ({ step, isLast }) => {
  const isCalendar = step.action_identifier.startsWith("calendar:");
  const isFocus = step.action_identifier.startsWith("focus:");
  const isRecovery = step.action_identifier.startsWith("recovery:");
  const isTask = step.action_identifier.startsWith("task:");

  const getStepIcon = () => {
    if (isCalendar) return <Calendar className="w-4 h-4 text-rose-400" />;
    if (isFocus) return <Zap className="w-4 h-4 text-amber-400" />;
    if (isRecovery) return <CheckCircle2 className="w-4 h-4 text-emerald-400" />;
    if (isTask) return <Layers className="w-4 h-4 text-indigo-400" />;
    return <Clock className="w-4 h-4 text-cyan-400" />;
  };

  return (
    <div className="relative flex items-start gap-3">
      {/* Step Number Circle */}
      <div className="flex flex-col items-center">
        <div className="flex items-center justify-center w-7 h-7 rounded-full bg-zinc-800 border border-zinc-700 text-xs font-bold text-zinc-200 shrink-0">
          {step.order_index}
        </div>
        {!isLast && <div className="w-0.5 h-full min-h-[36px] bg-zinc-800 my-1" />}
      </div>

      {/* Step Content Card */}
      <div className="flex-1 bg-zinc-900/80 border border-zinc-800 rounded-lg p-3.5 mb-3 hover:border-zinc-700 transition-colors">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded bg-zinc-800/80 text-zinc-300">
              {getStepIcon()}
            </div>
            <div>
              <h4 className="text-xs font-semibold text-zinc-100">{step.name}</h4>
              <p className="text-[11px] font-mono text-zinc-400">{step.action_identifier}</p>
            </div>
          </div>

          <div className="flex items-center gap-1.5 flex-wrap">
            {step.estimated_duration_minutes && (
              <span className="text-[10px] text-zinc-400 flex items-center gap-1 bg-zinc-950 px-2 py-0.5 rounded border border-zinc-800">
                <Clock className="w-3 h-3 text-zinc-400" />
                {step.estimated_duration_minutes}m
              </span>
            )}
            {step.requires_approval ? (
              <Badge variant="outline" className="text-[10px] text-amber-400 border-amber-500/30 bg-amber-500/10">
                Requires Approval
              </Badge>
            ) : (
              <Badge variant="outline" className="text-[10px] text-emerald-400 border-emerald-500/30 bg-emerald-500/10">
                Pre-authorized
              </Badge>
            )}
          </div>
        </div>

        {/* Parameters Preview */}
        {step.parameters && Object.keys(step.parameters).length > 0 && (
          <div className="mt-2.5 p-2 rounded bg-zinc-950 font-mono text-[10px] text-zinc-400 border border-zinc-800/80 overflow-x-auto">
            <span className="text-zinc-400 font-sans font-medium block mb-1">Contract Parameters:</span>
            <pre>{JSON.stringify(step.parameters, null, 2)}</pre>
          </div>
        )}
      </div>
    </div>
  );
};

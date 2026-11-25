"use client";

import React, { useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  Clock,
  Play,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  X,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { workflowsApi } from "@/lib/api/services/workflows";
import type { WorkflowExecutionProgress, WorkflowStepExecution } from "@/types/workflows";

interface WorkflowExecutionProgressProps {
  planId: string;
  initialStatus: string;
  onStatusChange?: (newStatus: string) => void;
}

export const WorkflowExecutionProgressView: React.FC<WorkflowExecutionProgressProps> = ({
  planId,
  initialStatus,
  onStatusChange,
}) => {
  const [progress, setProgress] = useState<WorkflowExecutionProgress | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchProgress = async () => {
    try {
      const data = await workflowsApi.getExecutionProgress(planId);
      setProgress(data);
      if (onStatusChange && data.status !== initialStatus) {
        onStatusChange(data.status);
      }
    } catch (err: any) {
      console.error("Failed to fetch execution progress:", err);
    }
  };

  useEffect(() => {
    fetchProgress();
    // Poll progress if EXECUTING
    const interval = setInterval(() => {
      fetchProgress();
    }, 2000);
    return () => clearInterval(interval);
  }, [planId]);

  const handleExecute = async () => {
    setActionLoading(true);
    setError(null);
    try {
      const updated = await workflowsApi.executePlan(planId, false, false);
      if (onStatusChange) onStatusChange(updated.status);
      fetchProgress();
    } catch (err: any) {
      setError(err?.message || "Execution failed");
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancel = async () => {
    setActionLoading(true);
    try {
      const updated = await workflowsApi.cancelExecution(planId);
      if (onStatusChange) onStatusChange(updated.status);
      fetchProgress();
    } catch (err: any) {
      setError(err?.message || "Cancel failed");
    } finally {
      setActionLoading(false);
    }
  };

  const handleRollback = async () => {
    if (!confirm("Are you sure you want to revert all completed side effects for this workflow?")) return;
    setActionLoading(true);
    try {
      const updated = await workflowsApi.rollbackExecution(planId);
      if (onStatusChange) onStatusChange(updated.status);
      fetchProgress();
    } catch (err: any) {
      setError(err?.message || "Rollback failed");
    } finally {
      setActionLoading(false);
    }
  };

  const getStepStatusBadge = (status: string) => {
    switch (status) {
      case "COMPLETED":
        return <Badge variant="outline" className="text-emerald-400 border-emerald-500/30 bg-emerald-500/10">Completed</Badge>;
      case "EXECUTING":
        return <Badge variant="outline" className="text-cyan-400 border-cyan-500/30 bg-cyan-500/10 animate-pulse">Executing...</Badge>;
      case "FAILED":
        return <Badge variant="outline" className="text-rose-400 border-rose-500/30 bg-rose-500/10">Failed</Badge>;
      case "SKIPPED":
        return <Badge variant="outline" className="text-zinc-500 border-zinc-700 bg-zinc-800">Skipped</Badge>;
      case "COMPENSATED":
        return <Badge variant="outline" className="text-purple-400 border-purple-500/30 bg-purple-500/10">Reverted</Badge>;
      default:
        return <Badge variant="outline" className="text-zinc-400 border-zinc-700">Pending</Badge>;
    }
  };

  const currentStatus = progress?.status || initialStatus;

  return (
    <div className="space-y-4 p-4 rounded-xl bg-zinc-950/80 border border-zinc-800 text-xs">
      {/* Header and Progress Bar */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="font-semibold text-zinc-200 flex items-center gap-1.5">
            <Clock className="w-4 h-4 text-cyan-400" />
            Execution Lifecycle & Progress
          </span>
          <div className="flex items-center gap-2">
            <span className="font-mono text-zinc-400">
              {progress ? `${progress.completed_steps}/${progress.total_steps} Steps (${progress.progress_percentage}%)` : "Initializing..."}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={fetchProgress}
              className="h-6 w-6 p-0 text-zinc-400 hover:text-zinc-200"
            >
              <RefreshCw className="w-3 h-3" />
            </Button>
          </div>
        </div>

        {/* Progress bar */}
        <div className="w-full bg-zinc-800 h-2 rounded-full overflow-hidden">
          <div
            className={`h-full transition-all duration-500 ${
              currentStatus === "FAILED"
                ? "bg-rose-500"
                : currentStatus === "COMPLETED"
                ? "bg-emerald-500"
                : "bg-cyan-500"
            }`}
            style={{ width: `${progress?.progress_percentage || 0}%` }}
          />
        </div>
      </div>

      {/* Error alert if failure occurred */}
      {error && (
        <div className="p-3 rounded-lg bg-rose-950/30 border border-rose-800/40 text-rose-300 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold block">Execution Error:</span>
            <span>{error}</span>
          </div>
        </div>
      )}

      {/* Step Receipts List */}
      {progress && progress.step_executions.length > 0 && (
        <div className="space-y-2 pt-2 border-t border-zinc-800/80">
          <span className="text-[11px] font-semibold text-zinc-300">Step Execution Audit Trail</span>
          <div className="space-y-1.5">
            {progress.step_executions.map((s) => (
              <div
                key={s.id || s.step_key}
                className="flex items-center justify-between p-2 rounded bg-zinc-900 border border-zinc-800 text-[11px]"
              >
                <div className="space-y-0.5">
                  <div className="font-mono font-medium text-zinc-200">{s.step_key}</div>
                  <div className="text-[10px] text-zinc-500 font-mono">{s.action_identifier}</div>
                  {s.error_message && (
                    <div className="text-[10px] text-rose-400">{s.error_message}</div>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-zinc-500">Attempt {s.attempt_count}/{s.max_attempts}</span>
                  {getStepStatusBadge(s.status)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Control Buttons */}
      <div className="flex items-center justify-between pt-3 border-t border-zinc-800/80 flex-wrap gap-2">
        <div className="text-[11px] text-zinc-500 flex items-center gap-1.5">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          Idempotent execution with compensation audit
        </div>

        <div className="flex items-center gap-2">
          {currentStatus === "APPROVED" && (
            <Button
              size="sm"
              onClick={handleExecute}
              disabled={actionLoading}
              className="h-8 text-xs bg-emerald-600 hover:bg-emerald-500 text-white font-medium"
            >
              <Play className="w-3.5 h-3.5 mr-1" />
              Start Workflow Execution
            </Button>
          )}

          {currentStatus === "EXECUTING" && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleCancel}
              disabled={actionLoading}
              className="h-8 text-xs border-zinc-700 bg-zinc-800 hover:bg-zinc-700 text-zinc-300"
            >
              <X className="w-3.5 h-3.5 mr-1 text-rose-400" />
              Cancel Execution
            </Button>
          )}

          {(currentStatus === "COMPLETED" || currentStatus === "PARTIALLY_COMPLETED" || currentStatus === "FAILED") && progress?.is_reversible && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleRollback}
              disabled={actionLoading}
              className="h-8 text-xs border-zinc-700 bg-zinc-800/80 hover:bg-zinc-800 text-amber-300"
            >
              <RotateCcw className="w-3.5 h-3.5 mr-1" />
              Rollback Side Effects
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};

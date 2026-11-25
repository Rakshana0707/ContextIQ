"use client";

import React from "react";
import type { AutomationExecution } from "@/types/automations";
import { CheckCircle2, Clock, AlertTriangle, XCircle, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";

interface ExecutionHistoryTableProps {
  executions: AutomationExecution[];
}

export function ExecutionHistoryTable({ executions }: ExecutionHistoryTableProps) {
  if (executions.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border/80 p-6 text-center text-xs text-muted-foreground bg-muted/10">
        No executions recorded yet. Triggers will log evaluation outcomes and matched conditions here.
      </div>
    );
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "EXECUTED":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="h-3 w-3" /> EXECUTED
          </span>
        );
      case "PENDING_APPROVAL":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20">
            <Clock className="h-3 w-3" /> PENDING APPROVAL
          </span>
        );
      case "SUPPRESSED_COOLDOWN":
      case "SUPPRESSED_QUIET_HOURS":
      case "SUPPRESSED_MAX_DAILY":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
            <AlertTriangle className="h-3 w-3" /> {status.replace("SUPPRESSED_", "")}
          </span>
        );
      case "FAILED":
      case "SUPPRESSED_UNAUTHORIZED":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20">
            <XCircle className="h-3 w-3" /> {status}
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-muted text-muted-foreground">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="rounded-xl border border-border/80 overflow-hidden bg-card/70 backdrop-blur-sm shadow-xs">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-muted/50 border-b border-border/70 text-[10px] uppercase font-bold text-muted-foreground">
            <tr>
              <th className="px-4 py-3">Timestamp</th>
              <th className="px-4 py-3">Trigger Event</th>
              <th className="px-4 py-3">Outcome</th>
              <th className="px-4 py-3">Condition Match / Suppression</th>
              <th className="px-4 py-3 text-right">Latency</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60">
            {executions.map((exec) => (
              <tr key={exec.id} className="hover:bg-muted/30 transition-colors">
                <td className="px-4 py-3 font-mono text-muted-foreground whitespace-nowrap">
                  {new Date(exec.executed_at).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  })}
                </td>
                <td className="px-4 py-3 font-mono font-semibold text-foreground">
                  {exec.trigger_type}
                </td>
                <td className="px-4 py-3">{getStatusBadge(exec.status)}</td>
                <td className="px-4 py-3 text-muted-foreground">
                  {exec.suppression_reason ? (
                    <span className="text-amber-600 dark:text-amber-400 text-[11px]">
                      {exec.suppression_reason}
                    </span>
                  ) : (
                    <span className="font-mono text-[11px] text-foreground">
                      {JSON.stringify(exec.matched_conditions)}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-right font-mono text-muted-foreground">
                  {exec.execution_duration_ms}ms
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

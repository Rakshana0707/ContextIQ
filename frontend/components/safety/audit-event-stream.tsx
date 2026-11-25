"use client";

import React from "react";
import type { WorkflowAuditEvent } from "@/types/safety";
import {
  ShieldAlert,
  ShieldCheck,
  RotateCcw,
  AlertTriangle,
  Play,
  CheckCircle2,
  XCircle,
  Clock,
} from "lucide-react";

interface AuditEventStreamProps {
  events: WorkflowAuditEvent[];
}

export const AuditEventStream: React.FC<AuditEventStreamProps> = ({ events }) => {
  if (events.length === 0) {
    return (
      <div className="p-8 text-center text-slate-500 bg-slate-900/40 rounded-xl border border-slate-800">
        No workflow audit events recorded yet.
      </div>
    );
  }

  const getEventBadge = (type: string) => {
    switch (type) {
      case "EMERGENCY_STOP_TRIGGERED":
      case "CIRCUIT_BREAKER_TRIPPED":
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-red-950/80 text-red-400 border border-red-800/80 flex items-center gap-1">
            <ShieldAlert className="w-3 h-3" /> STOP ENGAGED
          </span>
        );
      case "EMERGENCY_STOP_LIFTED":
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-950/80 text-emerald-400 border border-emerald-800/80 flex items-center gap-1">
            <Play className="w-3 h-3" /> STOP LIFTED
          </span>
        );
      case "ROLLBACK_TRIGGERED":
      case "STEP_COMPENSATED":
      case "ROLLBACK_COMPLETED":
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-amber-950/80 text-amber-400 border border-amber-800/80 flex items-center gap-1">
            <RotateCcw className="w-3 h-3" /> {type.replace("WORKFLOW_", "")}
          </span>
        );
      case "STEP_COMPLETED":
      case "WORKFLOW_PLAN_APPROVED":
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-950/60 text-emerald-400 border border-emerald-800/60 flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" /> {type.replace("WORKFLOW_PLAN_", "")}
          </span>
        );
      case "STEP_BLOCKED_BY_POLICY":
      case "STEP_FAILED":
      case "WORKFLOW_PLAN_REJECTED":
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-red-950/60 text-red-400 border border-red-800/60 flex items-center gap-1">
            <XCircle className="w-3 h-3" /> {type}
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-slate-800 text-slate-300 border border-slate-700">
            {type}
          </span>
        );
    }
  };

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/50">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-950/80 text-xs font-semibold text-slate-400 border-b border-slate-800">
          <tr>
            <th className="px-4 py-3">Timestamp</th>
            <th className="px-4 py-3">Event Type</th>
            <th className="px-4 py-3">Action Identifier</th>
            <th className="px-4 py-3">Step Key</th>
            <th className="px-4 py-3">Policy Decision</th>
            <th className="px-4 py-3">Result / Payload Summary</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/60 font-mono text-xs text-slate-300">
          {events.map((evt) => (
            <tr key={evt.id} className="hover:bg-slate-800/30 transition-colors">
              <td className="px-4 py-3 text-slate-400 whitespace-nowrap">
                {new Date(evt.execution_timestamp).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                })}
              </td>
              <td className="px-4 py-3">{getEventBadge(evt.event_type)}</td>
              <td className="px-4 py-3 text-indigo-300 font-sans">
                {evt.action_identifier || "—"}
              </td>
              <td className="px-4 py-3 text-slate-400">{evt.step_key || "—"}</td>
              <td className="px-4 py-3">
                {evt.policy_decision ? (
                  <span className="text-slate-300 font-semibold">{evt.policy_decision}</span>
                ) : (
                  <span className="text-slate-500">—</span>
                )}
              </td>
              <td className="px-4 py-3 font-sans text-slate-300 max-w-xs truncate">
                {evt.result_status ||
                  (evt.sanitized_payload
                    ? JSON.stringify(evt.sanitized_payload)
                    : "No payload")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

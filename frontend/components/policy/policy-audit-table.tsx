"use client";

import React from "react";
import type { PolicyAuditTrail } from "@/types/policy";
import { ShieldCheck, ShieldAlert, AlertCircle, Clock } from "lucide-react";

interface PolicyAuditTableProps {
  logs: PolicyAuditTrail[];
}

export const PolicyAuditTable: React.FC<PolicyAuditTableProps> = ({ logs }) => {
  if (logs.length === 0) {
    return (
      <div className="p-8 text-center text-slate-500 bg-slate-900/40 rounded-xl border border-slate-800">
        No policy decisions recorded yet.
      </div>
    );
  }

  const getDecisionBadge = (decision: string) => {
    switch (decision) {
      case "ALLOWED":
      case "GRANTED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-950/60 text-emerald-400 border border-emerald-800/60">
            <ShieldCheck className="w-3 h-3" />
            {decision}
          </span>
        );
      case "BLOCKED_BY_QUIET_HOURS":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-950/60 text-amber-400 border border-amber-800/60">
            <Clock className="w-3 h-3" />
            QUIET HOURS
          </span>
        );
      case "DENIED":
      case "REVOKED":
      case "BLOCKED_BY_POLICY":
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-950/60 text-red-400 border border-red-800/60">
            <ShieldAlert className="w-3 h-3" />
            {decision}
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
            <th className="px-4 py-3">Action</th>
            <th className="px-4 py-3">Scope Checked</th>
            <th className="px-4 py-3">Decision</th>
            <th className="px-4 py-3">Risk Tier</th>
            <th className="px-4 py-3">Policy Reason / Note</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/60 font-mono text-xs text-slate-300">
          {logs.map((log) => (
            <tr key={log.id} className="hover:bg-slate-800/30 transition-colors">
              <td className="px-4 py-3 text-slate-400 whitespace-nowrap">
                {new Date(log.evaluated_at).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                })}
              </td>
              <td className="px-4 py-3 font-semibold text-slate-200">
                {log.action_identifier}
              </td>
              <td className="px-4 py-3 text-indigo-300">
                {log.scope_checked || "—"}
              </td>
              <td className="px-4 py-3">{getDecisionBadge(log.decision)}</td>
              <td className="px-4 py-3 text-slate-400 font-sans">{log.risk_tier}</td>
              <td className="px-4 py-3 font-sans text-slate-300 max-w-xs truncate">
                {log.reason || "Policy criteria satisfied."}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

"use client";

import React, { useEffect, useState } from "react";
import type {
  EmergencyStopEvent,
  SafetyOverview,
  WorkflowAuditEvent,
  WorkflowRollbackRecord,
} from "@/types/safety";
import type { WorkflowExecutionPlan } from "@/types/workflows";
import { safetyApi } from "@/lib/api/services/safety";
import { workflowsApi } from "@/lib/api/services/workflows";
import { EmergencyStopBanner } from "./emergency-stop-banner";
import { EmergencyStopModal } from "./emergency-stop-modal";
import { AuditEventStream } from "./audit-event-stream";
import {
  ShieldAlert,
  AlertOctagon,
  RotateCcw,
  RefreshCw,
  Activity,
  CheckCircle2,
  XCircle,
  FileText,
  Lock,
} from "lucide-react";
import { Button } from "@/components/ui/button";

export const SafetyDashboardView: React.FC = () => {
  const [overview, setOverview] = useState<SafetyOverview | null>(null);
  const [plans, setPlans] = useState<WorkflowExecutionPlan[]>([]);
  const [auditEvents, setAuditEvents] = useState<WorkflowAuditEvent[]>([]);
  const [rollbackRecords, setRollbackRecords] = useState<WorkflowRollbackRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [isStopModalOpen, setIsStopModalOpen] = useState(false);
  const [rollingBackId, setRollingBackId] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [ov, plansData, events, rbs] = await Promise.all([
        safetyApi.getOverview(),
        workflowsApi.listPlans(),
        safetyApi.getAuditEvents(40),
        safetyApi.getRollbackRecords(20),
      ]);
      setOverview(ov);
      setPlans(plansData);
      setAuditEvents(events);
      setRollbackRecords(rbs);
    } catch (err) {
      console.error("Failed to load safety data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleTriggerEmergencyStop = async (
    reason: string,
    scope: "USER_LEVEL" | "ADMIN_GLOBAL"
  ) => {
    try {
      await safetyApi.triggerEmergencyStop({ reason, scope });
      await loadData();
    } catch (err: any) {
      alert(`Failed to engage emergency stop: ${err?.message}`);
    }
  };

  const handleLiftEmergencyStop = async (id: string) => {
    try {
      await safetyApi.liftEmergencyStop({ emergency_stop_id: id });
      await loadData();
    } catch (err: any) {
      alert(`Failed to lift emergency stop: ${err?.message}`);
    }
  };

  const handleRollback = async (planId: string) => {
    const confirmed = confirm(
      "Are you sure you want to roll back this workflow? All reversible side effects (calendar holds, priority shifts, notifications) will be inverted in reverse execution order."
    );
    if (!confirmed) return;

    setRollingBackId(planId);
    try {
      await safetyApi.executeRollback(planId, { reason: "User manual safety rollback" });
      await loadData();
      alert("Workflow successfully rolled back.");
    } catch (err: any) {
      alert(`Rollback failed: ${err?.message}`);
    } finally {
      setRollingBackId(null);
    }
  };

  const reversiblePlans = plans.filter((p) =>
    ["COMPLETED", "PARTIALLY_COMPLETED", "FAILED"].includes(p.status)
  );

  return (
    <div className="space-y-6">
      {/* Emergency Stop Banner if active */}
      {overview && (
        <EmergencyStopBanner
          stops={overview.active_emergency_stops}
          onLift={handleLiftEmergencyStop}
        />
      )}

      {/* Header and Emergency Action Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 rounded-2xl border border-slate-800 bg-slate-900/60 shadow-sm">
        <div>
          <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-red-500" />
            Automation Safety & Emergency Controls
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Real-time circuit breakers, reverse-compensation rollback, and append-only audit evidence.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Button
            size="sm"
            variant="outline"
            onClick={loadData}
            className="text-xs border-slate-700 text-slate-300 h-9"
          >
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Refresh
          </Button>

          <Button
            size="sm"
            onClick={() => setIsStopModalOpen(true)}
            className="bg-red-700 hover:bg-red-600 text-white font-bold text-xs h-9 px-4 gap-1.5 shadow-lg shadow-red-950/40"
          >
            <AlertOctagon className="w-4 h-4" />
            EMERGENCY STOP
          </Button>
        </div>
      </div>

      {/* Metric Cards Ribbon */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60">
          <p className="text-xs font-semibold text-slate-400 uppercase">Active Running</p>
          <h3 className="text-2xl font-bold text-indigo-400 mt-1">
            {overview?.active_plans_count || 0}
          </h3>
          <p className="text-[11px] text-slate-500 mt-0.5">Under execution fencing</p>
        </div>

        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60">
          <p className="text-xs font-semibold text-slate-400 uppercase">Reversible Operations</p>
          <h3 className="text-2xl font-bold text-emerald-400 mt-1">
            {reversiblePlans.length}
          </h3>
          <p className="text-[11px] text-slate-500 mt-0.5">With compensating actions</p>
        </div>

        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60">
          <p className="text-xs font-semibold text-slate-400 uppercase">Failed Workflows</p>
          <h3 className="text-2xl font-bold text-amber-400 mt-1">
            {overview?.failed_plans_count || 0}
          </h3>
          <p className="text-[11px] text-slate-500 mt-0.5">Safe checkpoint paused</p>
        </div>

        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60">
          <p className="text-xs font-semibold text-slate-400 uppercase">Kill Switch State</p>
          <h3
            className={`text-2xl font-bold mt-1 ${
              overview?.emergency_stop_active ? "text-red-400" : "text-slate-200"
            }`}
          >
            {overview?.emergency_stop_active ? "ENGAGED" : "NOMINAL"}
          </h3>
          <p className="text-[11px] text-slate-500 mt-0.5">
            {overview?.emergency_stop_active
              ? "All actions fenced"
              : "Execution permitted"}
          </p>
        </div>
      </div>

      {/* Reversible Workflows Section */}
      <div className="space-y-3">
        <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
          <RotateCcw className="w-4 h-4 text-emerald-400" />
          Reversible Workflows & Compensation Actions
        </h3>
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/80 text-slate-400 font-semibold border-b border-slate-800">
              <tr>
                <th className="px-4 py-3">Workflow Plan</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Completed Steps</th>
                <th className="px-4 py-3">Reversibility Guarantee</th>
                <th className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              {reversiblePlans.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                    No executed workflows currently eligible for rollback.
                  </td>
                </tr>
              ) : (
                reversiblePlans.map((p) => {
                  const isRolledBack = p.status === "ROLLED_BACK";
                  return (
                    <tr key={p.id} className="hover:bg-slate-800/20 transition-colors">
                      <td className="px-4 py-3 font-medium text-slate-200">
                        {p.title}
                        <div className="text-[11px] text-slate-500 font-mono">
                          ID: {p.id.slice(0, 8)}...
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            isRolledBack
                              ? "bg-slate-800 text-slate-400"
                              : p.status === "COMPLETED"
                              ? "bg-emerald-950/80 text-emerald-400 border border-emerald-800/60"
                              : "bg-amber-950/80 text-amber-400 border border-amber-800/60"
                          }`}
                        >
                          {p.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono">
                        {p.plan_steps.length} steps configured
                      </td>
                      <td className="px-4 py-3 text-slate-400">
                        {p.reversibility_summary?.rollback_guarantee ||
                          "Full state reversal supported."}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={isRolledBack || rollingBackId === p.id}
                          onClick={() => handleRollback(p.id)}
                          className="h-7 text-xs border-amber-700/60 text-amber-400 hover:bg-amber-950/40 hover:text-amber-300"
                        >
                          <RotateCcw className="w-3 h-3 mr-1" />
                          {isRolledBack
                            ? "Rolled Back"
                            : rollingBackId === p.id
                            ? "Reversing..."
                            : "Roll Back"}
                        </Button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Immutable Workflow Audit Stream */}
      <div className="space-y-3 pt-2">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <FileText className="w-4 h-4 text-indigo-400" />
              Immutable Workflow Audit Stream
            </h3>
            <p className="text-xs text-slate-400">
              Cryptographically timestamped, append-only records of every workflow dispatch, approval, policy check, and compensation.
            </p>
          </div>
        </div>
        <AuditEventStream events={auditEvents} />
      </div>

      {/* Emergency Stop Modal */}
      <EmergencyStopModal
        isOpen={isStopModalOpen}
        onClose={() => setIsStopModalOpen(false)}
        onConfirm={handleTriggerEmergencyStop}
      />
    </div>
  );
};

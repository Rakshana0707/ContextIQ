"use client";

import React, { useEffect, useState } from "react";
import type {
  PolicyConsent,
  UserPolicyOverview,
  PolicyAuditTrail,
  PermissionScope,
} from "@/types/policy";
import { policyApi } from "@/lib/api/services/policy";
import { PermissionScopeCard } from "./permission-scope-card";
import { PolicyAuditTable } from "./policy-audit-table";
import {
  ShieldCheck,
  Shield,
  Moon,
  AlertTriangle,
  History,
  Lock,
  Layers,
  RefreshCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";

export const PolicyCenterView: React.FC = () => {
  const [overview, setOverview] = useState<UserPolicyOverview | null>(null);
  const [auditLogs, setAuditLogs] = useState<PolicyAuditTrail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadPolicyData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [ov, logs] = await Promise.all([
        policyApi.getOverview(),
        policyApi.getAuditHistory(30),
      ]);
      setOverview(ov);
      setAuditLogs(logs);
    } catch (err: any) {
      setError(err?.message || "Failed to load policy data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPolicyData();
  }, []);

  const handleGrant = async (scope: PermissionScope) => {
    try {
      await policyApi.grantPermission({ scope });
      await loadPolicyData();
    } catch (err: any) {
      alert(`Error granting permission: ${err?.message}`);
    }
  };

  const handleRevoke = async (scope: PermissionScope) => {
    const confirmRevoke = confirm(
      `Are you sure you want to revoke consent for '${scope}'? Any scheduled or active workflows requiring this permission will be automatically cancelled.`
    );
    if (!confirmRevoke) return;

    try {
      await policyApi.revokePermission({
        scope,
        reason: "User revoked consent via Policy Center",
      });
      await loadPolicyData();
    } catch (err: any) {
      alert(`Error revoking permission: ${err?.message}`);
    }
  };

  if (loading && !overview) {
    return (
      <div className="flex items-center justify-center p-12 text-slate-400">
        <RefreshCw className="w-6 h-6 animate-spin mr-2" />
        Loading Policy & Consent Center...
      </div>
    );
  }

  const activeScopesCount = overview?.active_scopes.length || 0;
  const totalScopesCount = overview?.permissions.length || 0;

  return (
    <div className="space-y-6">
      {/* Top Banner / Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Active Permission Scopes
            </p>
            <h3 className="text-2xl font-bold text-slate-100 mt-1">
              {activeScopesCount} / {totalScopesCount}
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Deterministic least-privilege enforcement
            </p>
          </div>
          <div className="p-3 bg-indigo-950/40 border border-indigo-700/50 rounded-xl text-indigo-400">
            <ShieldCheck className="w-6 h-6" />
          </div>
        </div>

        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Quiet Hours Protection
            </p>
            <h3 className="text-2xl font-bold text-slate-100 mt-1">
              {overview?.quiet_hours_active ? "Active" : "Standard"}
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              {overview?.quiet_hours_active
                ? "Notifications suppressed during sleep"
                : "Active window (22:00 - 08:00)"}
            </p>
          </div>
          <div className="p-3 bg-amber-950/40 border border-amber-700/50 rounded-xl text-amber-400">
            <Moon className="w-6 h-6" />
          </div>
        </div>

        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Consequential Safety
            </p>
            <h3 className="text-2xl font-bold text-slate-100 mt-1">Strict Approval</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              LLMs cannot grant or elevate permissions
            </p>
          </div>
          <div className="p-3 bg-emerald-950/40 border border-emerald-700/50 rounded-xl text-emerald-400">
            <Lock className="w-6 h-6" />
          </div>
        </div>
      </div>

      {/* Scope Toggles List */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
            <Shield className="w-5 h-5 text-indigo-400" />
            Governed Permission Scopes
          </h3>
          <Button
            size="sm"
            variant="outline"
            onClick={loadPolicyData}
            className="text-xs border-slate-700 text-slate-300"
          >
            <RefreshCw className="w-3.5 h-3.5 mr-1" /> Refresh
          </Button>
        </div>

        <div className="grid grid-cols-1 gap-3">
          {overview?.permissions.map((consent) => (
            <PermissionScopeCard
              key={consent.id || consent.scope}
              consent={consent}
              onGrant={handleGrant}
              onRevoke={handleRevoke}
            />
          ))}
        </div>
      </div>

      {/* Policy Audit History */}
      <div className="space-y-3 pt-4">
        <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
          <History className="w-5 h-5 text-indigo-400" />
          Policy Evaluation Audit Log
        </h3>
        <p className="text-xs text-slate-400">
          Immutable execution log recording every deterministic authorization decision, quiet hour suppression, and revocation event.
        </p>
        <PolicyAuditTable logs={auditLogs} />
      </div>
    </div>
  );
};

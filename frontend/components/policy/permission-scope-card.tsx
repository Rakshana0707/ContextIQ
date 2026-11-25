"use client";

import React, { useState } from "react";
import type { PolicyConsent, PermissionScope } from "@/types/policy";
import {
  ShieldCheck,
  ShieldAlert,
  Calendar,
  CheckSquare,
  Bell,
  Monitor,
  MapPin,
  Clock,
  Workflow,
  RotateCcw,
  Check,
  AlertTriangle,
} from "lucide-react";
import { Button } from "@/components/ui/button";

interface PermissionScopeCardProps {
  consent: PolicyConsent;
  onGrant: (scope: PermissionScope) => Promise<void>;
  onRevoke: (scope: PermissionScope) => Promise<void>;
}

const SCOPE_METADATA: Record<
  string,
  {
    title: string;
    description: string;
    category: "Tasks" | "Calendar" | "System & Telemetry" | "Orchestration";
    icon: any;
    riskTier: "INFORMATIONAL" | "REVERSIBLE" | "EXTERNAL" | "CONSEQUENTIAL";
  }
> = {
  "tasks:read": {
    title: "Read Task Information",
    description: "Inspect task lists, tags, priorities, and deadlines to compute forgetting risk.",
    category: "Tasks",
    icon: CheckSquare,
    riskTier: "INFORMATIONAL",
  },
  "tasks:write": {
    title: "Modify Task Information",
    description: "Update task priorities, defer tasks, and decompose complex tasks into actionable subtasks.",
    category: "Tasks",
    icon: CheckSquare,
    riskTier: "REVERSIBLE",
  },
  "calendar:read": {
    title: "Read Calendar Schedule",
    description: "Access meeting start and end times to identify focus blocks and detect schedule conflicts.",
    category: "Calendar",
    icon: Calendar,
    riskTier: "INFORMATIONAL",
  },
  "calendar:events:create": {
    title: "Create Calendar Events",
    description: "Insert scheduled focus sessions, cognitive recovery buffers, and protected task blocks.",
    category: "Calendar",
    icon: Calendar,
    riskTier: "EXTERNAL",
  },
  "calendar:events:modify": {
    title: "Modify & Reschedule Events",
    description: "Reschedule conflicting appointments and adjust calendar commitments upon explicit user confirmation.",
    category: "Calendar",
    icon: Calendar,
    riskTier: "CONSEQUENTIAL",
  },
  "notifications:send": {
    title: "Send Proactive Notifications",
    description: "Dispatch context warming alerts, deadline warnings, and break reminders across authorized devices.",
    category: "System & Telemetry",
    icon: Bell,
    riskTier: "EXTERNAL",
  },
  "telemetry:desktop:collect": {
    title: "Collect Desktop Telemetry",
    description: "Detect active application transitions and idle periods while honoring application exclusion blacklists.",
    category: "System & Telemetry",
    icon: Monitor,
    riskTier: "INFORMATIONAL",
  },
  "location:read": {
    title: "Use Location Context",
    description: "Recognize place-routine associations (Home vs Office) to trigger contextual task recommendations.",
    category: "System & Telemetry",
    icon: MapPin,
    riskTier: "INFORMATIONAL",
  },
  "automation:schedule:run": {
    title: "Run Scheduled Automation",
    description: "Evaluate user-defined trigger conditions and dispatch rule actions on configured cadences.",
    category: "Orchestration",
    icon: Clock,
    riskTier: "REVERSIBLE",
  },
  "workflows:execute": {
    title: "Execute Multi-Step Workflows",
    description: "Coordinate governed, multi-step actions across tasks, calendars, and focus sessions with rollback support.",
    category: "Orchestration",
    icon: Workflow,
    riskTier: "REVERSIBLE",
  },
};

export const PermissionScopeCard: React.FC<PermissionScopeCardProps> = ({
  consent,
  onGrant,
  onRevoke,
}) => {
  const [loading, setLoading] = useState(false);
  const isGranted = consent.consent_status === "GRANTED";
  const meta = SCOPE_METADATA[consent.scope] || {
    title: consent.scope,
    description: "System governed permission scope.",
    category: "System & Telemetry",
    icon: ShieldCheck,
    riskTier: "INFORMATIONAL",
  };

  const Icon = meta.icon;

  const handleToggle = async () => {
    setLoading(true);
    try {
      if (isGranted) {
        await onRevoke(consent.scope as PermissionScope);
      } else {
        await onGrant(consent.scope as PermissionScope);
      }
    } finally {
      setLoading(false);
    }
  };

  const getTierBadge = () => {
    switch (meta.riskTier) {
      case "CONSEQUENTIAL":
        return (
          <span className="px-2 py-0.5 rounded text-xs font-semibold bg-red-950/60 text-red-400 border border-red-800/60">
            Tier 3: Consequential (Strict Approval)
          </span>
        );
      case "EXTERNAL":
        return (
          <span className="px-2 py-0.5 rounded text-xs font-semibold bg-amber-950/60 text-amber-400 border border-amber-800/60">
            Tier 2: External (Approval Required)
          </span>
        );
      case "REVERSIBLE":
        return (
          <span className="px-2 py-0.5 rounded text-xs font-semibold bg-blue-950/60 text-blue-400 border border-blue-800/60">
            Tier 1: Reversible Internal
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded text-xs font-semibold bg-slate-800 text-slate-300 border border-slate-700">
            Tier 0: Informational
          </span>
        );
    }
  };

  return (
    <div
      className={`rounded-xl border p-5 transition-all ${
        isGranted
          ? "bg-slate-900/60 border-slate-800 shadow-sm"
          : "bg-slate-950/40 border-slate-800/50 opacity-80"
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3.5">
          <div
            className={`p-2.5 rounded-lg border ${
              isGranted
                ? "bg-indigo-950/40 border-indigo-700/50 text-indigo-400"
                : "bg-slate-800/50 border-slate-700/50 text-slate-500"
            }`}
          >
            <Icon className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h4 className="text-base font-semibold text-slate-100">{meta.title}</h4>
              <code className="text-xs text-slate-400 bg-slate-950 px-1.5 py-0.5 rounded border border-slate-800 font-mono">
                {consent.scope}
              </code>
              {getTierBadge()}
            </div>
            <p className="text-sm text-slate-400 mt-1.5 leading-relaxed">{meta.description}</p>
            <div className="flex items-center gap-4 text-xs text-slate-500 mt-3">
              <span>Source: <strong className="text-slate-400">{consent.source}</strong></span>
              <span>Version: <strong className="text-slate-400">{consent.consent_version}</strong></span>
              {consent.device_id && (
                <span>Device: <strong className="text-slate-400">{consent.device_id}</strong></span>
              )}
              {consent.integration_id && (
                <span>Integration: <strong className="text-slate-400">{consent.integration_id}</strong></span>
              )}
            </div>
          </div>
        </div>

        <div className="flex flex-col items-end gap-2 shrink-0">
          <Button
            size="sm"
            variant={isGranted ? "outline" : "default"}
            disabled={loading}
            onClick={handleToggle}
            className={`text-xs h-8 px-3 font-medium transition-colors ${
              isGranted
                ? "border-red-800/60 text-red-400 hover:bg-red-950/40 hover:text-red-300"
                : "bg-emerald-600 hover:bg-emerald-500 text-white"
            }`}
          >
            {isGranted ? (
              <>
                <ShieldAlert className="w-3.5 h-3.5 mr-1.5" />
                Revoke Consent
              </>
            ) : (
              <>
                <ShieldCheck className="w-3.5 h-3.5 mr-1.5" />
                Grant Scope
              </>
            )}
          </Button>

          <span
            className={`text-[11px] font-medium flex items-center gap-1 ${
              isGranted ? "text-emerald-400" : "text-amber-400"
            }`}
          >
            {isGranted ? (
              <>
                <Check className="w-3 h-3" /> Active & Granted
              </>
            ) : (
              <>
                <AlertTriangle className="w-3 h-3" /> Revoked / Blocked
              </>
            )}
          </span>
        </div>
      </div>
    </div>
  );
};

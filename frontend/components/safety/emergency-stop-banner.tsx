"use client";

import React from "react";
import type { EmergencyStopEvent } from "@/types/safety";
import { AlertOctagon, ShieldAlert, Play, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";

interface EmergencyStopBannerProps {
  stops: EmergencyStopEvent[];
  onLift: (id: string) => Promise<void>;
}

export const EmergencyStopBanner: React.FC<EmergencyStopBannerProps> = ({
  stops,
  onLift,
}) => {
  const activeStops = stops.filter((s) => s.is_active);
  if (activeStops.length === 0) return null;

  const currentStop = activeStops[0];

  return (
    <div className="rounded-xl border border-red-600/80 bg-red-950/70 p-4 text-red-200 shadow-lg shadow-red-950/50 animate-pulse">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg bg-red-900/80 border border-red-700 text-red-200 shrink-0">
            <AlertOctagon className="w-6 h-6 animate-spin text-red-300" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="text-base font-bold text-red-100 flex items-center gap-1.5">
                EMERGENCY STOP ACTIVE ({currentStop.scope})
              </h3>
              <span className="text-xs bg-red-900 px-2 py-0.5 rounded-full font-mono text-red-200 border border-red-700">
                Kill Switch Engaged
              </span>
            </div>
            <p className="text-xs text-red-300 mt-1">
              <strong>Reason:</strong> {currentStop.reason}
            </p>
            <div className="flex items-center gap-4 text-[11px] text-red-400 mt-2">
              <span>Triggered By: <strong>{currentStop.triggered_by}</strong></span>
              <span>Cancelled Workflows: <strong>{currentStop.affected_plans_count}</strong></span>
              <span>Disabled Rules: <strong>{currentStop.affected_rules_count}</strong></span>
              <span>Started: <strong>{new Date(currentStop.started_at).toLocaleTimeString()}</strong></span>
            </div>
          </div>
        </div>

        <div className="shrink-0">
          <Button
            size="sm"
            onClick={() => onLift(currentStop.id)}
            className="bg-red-800 hover:bg-emerald-600 hover:text-white text-red-100 border border-red-600 font-semibold text-xs h-9 gap-1.5 transition-colors"
          >
            <Play className="w-3.5 h-3.5" />
            Resume System / Lift Stop
          </Button>
        </div>
      </div>
    </div>
  );
};

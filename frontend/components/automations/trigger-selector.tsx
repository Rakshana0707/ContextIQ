"use client";

import React from "react";
import type { TriggerType } from "@/types/automations";
import {
  Clock,
  AlertTriangle,
  Flame,
  Calendar,
  Activity,
  Layers,
  Sparkles,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";

export interface TriggerOption {
  type: TriggerType;
  label: string;
  category: "Predictive" | "Telemetry" | "Calendar" | "Temporal" | "Manual";
  description: string;
  icon: React.ElementType;
  defaultField: string;
}

export const TRIGGER_OPTIONS: TriggerOption[] = [
  {
    type: "FORGETTING_THRESHOLD_EXCEEDED",
    label: "Forgetting Risk Threshold",
    category: "Predictive",
    description: "Fires when task prospective lapse probability exceeds configured risk.",
    icon: Flame,
    defaultField: "forgetting_risk.probability",
  },
  {
    type: "RECOVERY_SESSION_ENDED",
    label: "Focus Session Ended",
    category: "Telemetry",
    description: "Fires immediately upon completion of a deep work focus session.",
    icon: Activity,
    defaultField: "session.duration_minutes",
  },
  {
    type: "THRASHING_DETECTED",
    label: "Context Thrashing Burst",
    category: "Telemetry",
    description: "Fires when rapid switching across unrelated applications is detected.",
    icon: AlertTriangle,
    defaultField: "telemetry.switches_per_minute",
  },
  {
    type: "CALENDAR_CONFLICT_DETECTED",
    label: "Calendar Overlap / Conflict",
    category: "Calendar",
    description: "Fires when two external calendar events overlap or create zero-buffer collision.",
    icon: Calendar,
    defaultField: "calendar.conflict_minutes",
  },
  {
    type: "BFI_THRESHOLD_EXCEEDED",
    label: "Behavioral Friction Index Spike",
    category: "Predictive",
    description: "Fires when composite cognitive friction index exceeds safe baseline.",
    icon: Zap,
    defaultField: "context.bfi",
  },
  {
    type: "TIME_INACTIVE",
    label: "Task Inactivity Timeout",
    category: "Temporal",
    description: "Fires when a pending high-priority task has had zero progress for hours.",
    icon: Clock,
    defaultField: "task.inactive_hours",
  },
  {
    type: "TASK_STATE_CHANGED",
    label: "Task Status Transition",
    category: "Temporal",
    description: "Fires when a task status moves to IN_PROGRESS, COMPLETED, or BLOCKED.",
    icon: Layers,
    defaultField: "task.status",
  },
  {
    type: "MANUAL_USER_TRIGGER",
    label: "User On-Demand Trigger",
    category: "Manual",
    description: "Fires explicitly when triggered from desktop hotkey or mobile companion.",
    icon: Sparkles,
    defaultField: "manual.intent",
  },
];

interface TriggerSelectorProps {
  selected: TriggerType;
  onSelect: (type: TriggerType) => void;
}

export function TriggerSelector({ selected, onSelect }: TriggerSelectorProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
      {TRIGGER_OPTIONS.map((opt) => {
        const Icon = opt.icon;
        const isSelected = selected === opt.type;
        return (
          <button
            key={opt.type}
            type="button"
            onClick={() => onSelect(opt.type)}
            className={cn(
              "flex flex-col text-left p-3 rounded-xl border transition-all text-sm",
              isSelected
                ? "border-indigo-500 bg-indigo-50/70 dark:bg-indigo-950/40 shadow-sm ring-1 ring-indigo-500/50"
                : "border-border/70 hover:border-border hover:bg-muted/50 bg-card/60"
            )}
          >
            <div className="flex items-center justify-between w-full mb-1">
              <div className="flex items-center gap-2">
                <div
                  className={cn(
                    "p-1.5 rounded-lg",
                    isSelected
                      ? "bg-indigo-600 text-white"
                      : "bg-muted text-muted-foreground"
                  )}
                >
                  <Icon className="h-4 w-4" />
                </div>
                <span className="font-semibold text-foreground text-xs">
                  {opt.label}
                </span>
              </div>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                {opt.category}
              </span>
            </div>
            <p className="text-[11px] text-muted-foreground line-clamp-2">
              {opt.description}
            </p>
          </button>
        );
      })}
    </div>
  );
}

"use client";

import React from "react";
import type { AutomationRule } from "@/types/automations";
import {
  Sparkles,
  ToggleLeft,
  ToggleRight,
  Edit2,
  Trash2,
  Clock,
  Shield,
  Layers,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface RuleListProps {
  rules: AutomationRule[];
  onToggle: (id: string) => void;
  onEdit: (rule: AutomationRule) => void;
  onDelete: (id: string) => void;
}

export function RuleList({
  rules,
  onToggle,
  onEdit,
  onDelete,
}: RuleListProps) {
  if (rules.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-border/80 p-8 text-center space-y-3 bg-muted/10">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
          <Sparkles className="h-6 w-6" />
        </div>
        <h4 className="text-sm font-bold text-foreground">
          No Automation Rules Configured
        </h4>
        <p className="text-xs text-muted-foreground max-w-sm mx-auto">
          Create personalized behavioral rules to automatically schedule recovery buffers, protect focus windows, or stage reminders.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {rules.map((rule) => {
        const trigger = rule.triggers?.[0];
        const action = rule.actions?.[0];
        const isEnabled = rule.is_enabled;

        return (
          <div
            key={rule.id}
            className={cn(
              "rounded-2xl border p-4 transition-all bg-card/80 backdrop-blur-sm shadow-xs space-y-3",
              isEnabled
                ? "border-border/80 hover:border-indigo-500/40 hover:shadow-md"
                : "border-border/40 opacity-70 bg-muted/20"
            )}
          >
            {/* Top row: Title, Status, Quick Controls */}
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <h4 className="text-sm font-bold text-foreground">
                    {rule.name}
                  </h4>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-muted text-muted-foreground">
                    v{rule.version}
                  </span>
                  <span
                    className={cn(
                      "px-2 py-0.5 rounded-full text-[10px] font-mono font-bold",
                      rule.risk_tier === "Tier 1"
                        ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
                        : "bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20"
                    )}
                  >
                    {rule.risk_tier}
                  </span>
                  {rule.requires_approval ? (
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20">
                      Approval Required
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                      Auto-Execute
                    </span>
                  )}
                </div>
                {rule.description && (
                  <p className="text-xs text-muted-foreground line-clamp-2">
                    {rule.description}
                  </p>
                )}
              </div>

              {/* Toggle switch & action buttons */}
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => onToggle(rule.id)}
                  title={isEnabled ? "Disable rule" : "Enable rule"}
                  className={cn(
                    "flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold transition-colors border",
                    isEnabled
                      ? "bg-emerald-500/10 text-emerald-600 border-emerald-500/20 hover:bg-emerald-500/20"
                      : "bg-muted text-muted-foreground border-border hover:bg-muted/80"
                  )}
                >
                  {isEnabled ? (
                    <>
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                      Active
                    </>
                  ) : (
                    <>
                      <AlertCircle className="h-3.5 w-3.5 text-muted-foreground" />
                      Disabled
                    </>
                  )}
                </button>

                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onEdit(rule)}
                  className="h-7 w-7 p-0"
                  title="Edit rule"
                >
                  <Edit2 className="h-3.5 w-3.5" />
                </Button>

                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onDelete(rule.id)}
                  className="h-7 w-7 p-0 text-muted-foreground hover:text-rose-500"
                  title="Delete rule"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>

            {/* Middle row: Trigger -> Condition -> Action chips */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 p-2.5 rounded-xl bg-muted/30 border border-border/50 text-xs font-mono">
              <div>
                <span className="text-[10px] uppercase font-bold text-muted-foreground block">
                  Trigger
                </span>
                <span className="text-foreground font-semibold truncate block">
                  {trigger?.trigger_type || "No trigger configured"}
                </span>
              </div>

              <div>
                <span className="text-[10px] uppercase font-bold text-muted-foreground block">
                  Conditions ({rule.conditions?.length || 0})
                </span>
                <span className="text-foreground font-semibold truncate block">
                  {rule.conditions?.[0]
                    ? `${rule.conditions[0].field_path} ${rule.conditions[0].operator}`
                    : "Always passes"}
                </span>
              </div>

              <div>
                <span className="text-[10px] uppercase font-bold text-muted-foreground block">
                  Action
                </span>
                <span className="text-foreground font-semibold truncate block">
                  {action?.action_identifier || "No action set"}
                </span>
              </div>
            </div>

            {/* Bottom row: Cooldown, Daily limits, Last triggered */}
            <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-1">
              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  Cooldown: {rule.cooldown_minutes}m
                </span>
                <span className="flex items-center gap-1">
                  <Shield className="h-3 w-3" />
                  Max {rule.max_executions_per_day}/day ({rule.execution_count_today} used)
                </span>
              </div>

              <span>
                {rule.last_triggered_at
                  ? `Last triggered: ${new Date(rule.last_triggered_at).toLocaleTimeString()}`
                  : "Never triggered"}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

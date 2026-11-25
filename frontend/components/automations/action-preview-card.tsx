"use client";

import React from "react";
import { ShieldCheck, RotateCcw, AlertCircle, ArrowRight, Zap } from "lucide-react";
import { cn } from "@/lib/utils";

interface ActionPreviewCardProps {
  actionIdentifier: string;
  previewTitle?: string;
  previewDescription?: string;
  parameters?: Record<string, any>;
  isReversible?: boolean;
  requiresApproval?: boolean;
  riskTier?: string;
}

export const ACTION_PRESETS: Record<
  string,
  { title: string; desc: string; category: string; reversible: boolean; tier: string }
> = {
  "reminder:stage_context_warming": {
    title: "Pre-Stage 15-Minute Task Warming Nudge",
    desc: "Delivers a gentle focus preview before risk of lapse manifests.",
    category: "Reminder",
    reversible: true,
    tier: "Tier 1",
  },
  "recovery:insert_post_interruption_buffer": {
    title: "Insert 10-Minute Cognitive Recovery Buffer",
    desc: "Guarantees working memory recharge after intense deep work or disruption.",
    category: "Recovery",
    reversible: true,
    tier: "Tier 2",
  },
  "calendar:insert_focus_block": {
    title: "Reserve 60-Minute Calendar Focus Block",
    desc: "Guards external calendar against meeting collisions during peak window.",
    category: "Calendar",
    reversible: true,
    tier: "Tier 2",
  },
  "task:decompose_into_subtasks": {
    title: "Decompose Task into 3 Staged Subtasks",
    desc: "Partitions high-friction tasks into achievable milestones with checkpoints.",
    category: "Task",
    reversible: true,
    tier: "Tier 1",
  },
  "intervention:anti_thrash_fullscreen_prompt": {
    title: "Calming Focus Re-centering Prompt",
    desc: "Halts attention dissipation and presents active task resumption anchor.",
    category: "Intervention",
    reversible: false,
    tier: "Tier 1",
  },
  "cross_device:sync_dnd_focus_mode": {
    title: "Sync Do-Not-Disturb Across All Devices",
    desc: "Silences notifications simultaneously on desktop and mobile companion.",
    category: "Cross-Device",
    reversible: true,
    tier: "Tier 1",
  },
};

export function ActionPreviewCard({
  actionIdentifier,
  previewTitle,
  previewDescription,
  parameters = {},
  isReversible = true,
  requiresApproval = true,
  riskTier = "Tier 2",
}: ActionPreviewCardProps) {
  const preset = ACTION_PRESETS[actionIdentifier] || {
    title: previewTitle || actionIdentifier,
    desc: previewDescription || "Custom automated workflow action.",
    category: "Custom",
    reversible: isReversible,
    tier: riskTier,
  };

  return (
    <div className="rounded-xl border border-indigo-500/20 bg-gradient-to-br from-indigo-50/50 via-card to-background dark:from-indigo-950/20 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-indigo-600 text-white shadow-xs">
            <Zap className="h-4 w-4" />
          </div>
          <div>
            <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-indigo-600 dark:text-indigo-400">
              Action Plan Preview
            </span>
            <h4 className="text-xs font-bold text-foreground">
              {preset.title}
            </h4>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <span
            className={cn(
              "px-2 py-0.5 rounded-full text-[10px] font-mono font-bold",
              riskTier === "Tier 1"
                ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
                : "bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20"
            )}
          >
            {riskTier}
          </span>
          {isReversible && (
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20 flex items-center gap-1">
              <RotateCcw className="h-2.5 w-2.5" /> Reversible
            </span>
          )}
        </div>
      </div>

      <p className="text-xs text-muted-foreground leading-relaxed">
        {preset.desc}
      </p>

      {/* Parameters preview */}
      {Object.keys(parameters).length > 0 && (
        <div className="p-2.5 rounded-lg bg-muted/40 border border-border/50 text-[11px] font-mono space-y-1">
          <div className="text-[10px] uppercase font-bold text-muted-foreground">
            Payload Configuration
          </div>
          {Object.entries(parameters).map(([key, value]) => (
            <div key={key} className="flex justify-between text-muted-foreground">
              <span>{key}:</span>
              <span className="text-foreground font-semibold">{String(value)}</span>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between pt-1 border-t border-border/50 text-[11px] text-muted-foreground">
        <span className="flex items-center gap-1">
          <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
          {requiresApproval
            ? "Requires explicit confirmation before external execution"
            : "Autonomous execution pre-authorized"}
        </span>
        <span className="font-mono text-[10px] text-muted-foreground/80">
          id: {actionIdentifier}
        </span>
      </div>
    </div>
  );
}

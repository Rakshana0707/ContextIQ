"use client";

import React from "react";
import { cn } from "@/lib/utils";
import type { PredictionReason } from "@/types";

interface SHAPWaterfallProps {
  reasons: PredictionReason[];
  baseValue?: number;
  className?: string;
}

export function SHAPWaterfall({ reasons, baseValue, className }: SHAPWaterfallProps) {
  if (!reasons || reasons.length === 0) {
    return null;
  }

  // Find max magnitude for relative bar width normalization
  const maxImpact = Math.max(
    ...reasons.map((r) => Math.abs(r.impact ?? (r.weight || 0.1))),
    0.1
  );

  return (
    <div className={cn("space-y-3 pt-2", className)}>
      <div className="flex items-center justify-between text-xs text-muted-foreground border-b pb-1.5">
        <span className="font-semibold tracking-wide uppercase">
          SHAP Feature Contributions
        </span>
        <div className="flex items-center gap-3 text-[11px]">
          <span className="flex items-center gap-1">
            <span className="inline-block w-2.5 h-2.5 rounded-sm bg-rose-500" />
            Increases Risk
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-2.5 h-2.5 rounded-sm bg-emerald-500" />
            Reduces Risk
          </span>
        </div>
      </div>

      <div className="space-y-2">
        {reasons.map((reason, idx) => {
          const weight = reason.weight ?? 0;
          const impact = reason.impact ?? (reason.direction === "decreasing" ? -weight : weight);
          const isPositive = impact >= 0;
          const absImpact = Math.abs(impact);
          const barWidthPercent = Math.min(100, Math.round((absImpact / (maxImpact || 1)) * 100));

          return (
            <div key={idx} className="group text-xs">
              <div className="flex items-baseline justify-between mb-1">
                <div className="flex items-center gap-1.5">
                  <span className="font-medium text-foreground">
                    {reason.label || reason.feature}
                  </span>
                  {reason.actualValue && (
                    <span className="text-[11px] px-1.5 py-0.2 bg-muted rounded text-muted-foreground font-mono">
                      {reason.actualValue}
                    </span>
                  )}
                </div>
                <span
                  className={cn(
                    "font-mono font-semibold tabular-nums text-[11px]",
                    isPositive ? "text-rose-600 dark:text-rose-400" : "text-emerald-600 dark:text-emerald-400"
                  )}
                >
                  {isPositive ? "+" : ""}
                  {impact.toFixed(3)}
                </span>
              </div>

              {/* Directional Waterfall Bar */}
              <div className="h-2 w-full bg-muted/40 rounded overflow-hidden flex relative">
                {isPositive ? (
                  <div className="w-full flex">
                    <div
                      className="h-full bg-rose-500/80 rounded-r transition-all duration-300"
                      style={{ width: `${barWidthPercent}%` }}
                    />
                  </div>
                ) : (
                  <div className="w-full flex justify-end">
                    <div
                      className="h-full bg-emerald-500/80 rounded-l transition-all duration-300"
                      style={{ width: `${barWidthPercent}%` }}
                    />
                  </div>
                )}
              </div>

              {reason.detail && (
                <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-1">
                  {reason.detail}
                </p>
              )}
            </div>
          );
        })}
      </div>

      <p className="text-[10px] text-muted-foreground/80 italic pt-1 border-t">
        * SHAP attributions represent correlational associations with model output, not causal factors.
      </p>
    </div>
  );
}

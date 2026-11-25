"use client";

import React from "react";
import type { ConditionOperator, LogicalOperator } from "@/types/automations";
import { Plus, Trash2, Sliders, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";

export interface ConditionRow {
  field_path: string;
  operator: ConditionOperator;
  expected_value: any;
  logical_operator: LogicalOperator;
  condition_group: number;
}

interface ConditionBuilderProps {
  conditions: ConditionRow[];
  onChange: (conditions: ConditionRow[]) => void;
}

export const OPERATOR_LABELS: Record<ConditionOperator, string> = {
  GREATER_THAN: "> (Greater than)",
  GREATER_THAN_OR_EQUAL: ">= (Greater than or equal)",
  LESS_THAN: "< (Less than)",
  LESS_THAN_OR_EQUAL: "<= (Less than or equal)",
  EQUALS: "== (Equals)",
  NOT_EQUALS: "!= (Does not equal)",
  BETWEEN: "Between [min, max]",
  IN_LIST: "In List [a, b, ...]",
  CONTAINS: "Contains substring",
  IS_TRUE: "Is True",
  IS_FALSE: "Is False",
};

export function ConditionBuilder({ conditions, onChange }: ConditionBuilderProps) {
  const addCondition = () => {
    onChange([
      ...conditions,
      {
        field_path: "task.priority",
        operator: "EQUALS",
        expected_value: "HIGH",
        logical_operator: "AND",
        condition_group: 0,
      },
    ]);
  };

  const removeCondition = (index: number) => {
    const updated = conditions.filter((_, i) => i !== index);
    onChange(updated);
  };

  const updateCondition = (index: number, patch: Partial<ConditionRow>) => {
    const updated = [...conditions];
    updated[index] = { ...updated[index], ...patch };
    onChange(updated);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="text-xs font-semibold text-foreground flex items-center gap-1.5">
          <Sliders className="h-3.5 w-3.5 text-indigo-500" />
          Condition Predicates ({conditions.length})
        </label>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={addCondition}
          className="h-7 text-xs gap-1 border-dashed"
        >
          <Plus className="h-3 w-3" /> Add Condition
        </Button>
      </div>

      {conditions.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border/80 p-4 text-center text-xs text-muted-foreground bg-muted/20">
          No condition filters set. Rule will evaluate directly on the trigger event.
        </div>
      ) : (
        <div className="space-y-2">
          {conditions.map((cond, idx) => (
            <div
              key={idx}
              className="flex flex-col sm:flex-row items-center gap-2 p-2.5 rounded-xl border border-border/70 bg-card text-xs shadow-xs"
            >
              {idx > 0 && (
                <select
                  value={cond.logical_operator}
                  onChange={(e) =>
                    updateCondition(idx, {
                      logical_operator: e.target.value as LogicalOperator,
                    })
                  }
                  className="h-8 px-2 rounded-lg border border-border bg-background font-mono font-bold text-[10px] text-indigo-600 dark:text-indigo-400"
                >
                  <option value="AND">AND</option>
                  <option value="OR">OR</option>
                </select>
              )}

              <input
                type="text"
                placeholder="field.path (e.g. task.priority)"
                value={cond.field_path}
                onChange={(e) =>
                  updateCondition(idx, { field_path: e.target.value })
                }
                className="h-8 px-2.5 flex-1 rounded-lg border border-border bg-background font-mono text-xs focus:ring-1 focus:ring-indigo-500"
              />

              <select
                value={cond.operator}
                onChange={(e) =>
                  updateCondition(idx, {
                    operator: e.target.value as ConditionOperator,
                  })
                }
                className="h-8 px-2 rounded-lg border border-border bg-background text-xs font-medium"
              >
                {Object.entries(OPERATOR_LABELS).map(([op, label]) => (
                  <option key={op} value={op}>
                    {label}
                  </option>
                ))}
              </select>

              <input
                type="text"
                placeholder="Value (e.g. 0.7 or HIGH)"
                value={
                  typeof cond.expected_value === "object"
                    ? JSON.stringify(cond.expected_value)
                    : cond.expected_value ?? ""
                }
                onChange={(e) => {
                  let val: any = e.target.value;
                  try {
                    val = JSON.parse(e.target.value);
                  } catch {
                    // keep as string
                  }
                  updateCondition(idx, { expected_value: val });
                }}
                className="h-8 px-2.5 w-32 rounded-lg border border-border bg-background text-xs font-mono focus:ring-1 focus:ring-indigo-500"
              />

              <button
                type="button"
                onClick={() => removeCondition(idx)}
                className="p-1.5 rounded-lg text-muted-foreground hover:text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/40 transition-colors"
                title="Remove condition"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

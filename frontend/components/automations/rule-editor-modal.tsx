"use client";

import React, { useState } from "react";
import type { AutomationRule, TriggerType } from "@/types/automations";
import { TriggerSelector, TRIGGER_OPTIONS } from "./trigger-selector";
import { ConditionBuilder, ConditionRow } from "./condition-builder";
import { ActionPreviewCard, ACTION_PRESETS } from "./action-preview-card";
import { X, Save, Sparkles, Clock, Shield, Bell } from "lucide-react";
import { Button } from "@/components/ui/button";

interface RuleEditorModalProps {
  rule?: AutomationRule | null;
  isOpen: boolean;
  onClose: () => void;
  onSave: (payload: any) => Promise<void>;
}

export function RuleEditorModal({
  rule,
  isOpen,
  onClose,
  onSave,
}: RuleEditorModalProps) {
  if (!isOpen) return null;

  const [name, setName] = useState(rule?.name || "New Behavioral Rule");
  const [description, setDescription] = useState(rule?.description || "");
  const [triggerType, setTriggerType] = useState<TriggerType>(
    (rule?.triggers?.[0]?.trigger_type as TriggerType) || "FORGETTING_THRESHOLD_EXCEEDED"
  );
  const [conditions, setConditions] = useState<ConditionRow[]>(
    rule?.conditions?.map((c) => ({
      field_path: c.field_path,
      operator: c.operator as any,
      expected_value: c.expected_value,
      logical_operator: c.logical_operator as any,
      condition_group: c.condition_group,
    })) || [
      {
        field_path: "task.priority",
        operator: "IN_LIST",
        expected_value: ["HIGH", "CRITICAL"],
        logical_operator: "AND",
        condition_group: 0,
      },
    ]
  );
  const [actionIdentifier, setActionIdentifier] = useState(
    rule?.actions?.[0]?.action_identifier || "reminder:stage_context_warming"
  );
  const [cooldownMinutes, setCooldownMinutes] = useState(rule?.cooldown_minutes || 30);
  const [maxExecutionsPerDay, setMaxExecutionsPerDay] = useState(
    rule?.max_executions_per_day || 5
  );
  const [requiresApproval, setRequiresApproval] = useState(
    rule?.requires_approval !== undefined ? rule.requires_approval : true
  );
  const [quietHoursEnabled, setQuietHoursEnabled] = useState(
    rule?.quiet_hours?.enabled !== undefined ? rule.quiet_hours.enabled : true
  );
  const [isSaving, setIsSaving] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      const payload = {
        name,
        description,
        is_enabled: rule ? rule.is_enabled : true,
        priority: rule ? rule.priority : 10,
        cooldown_minutes: Number(cooldownMinutes),
        max_executions_per_day: Number(maxExecutionsPerDay),
        requires_approval: requiresApproval,
        risk_tier: ACTION_PRESETS[actionIdentifier]?.tier || "Tier 2",
        active_schedule: rule?.active_schedule || {
          days_of_week: [1, 2, 3, 4, 5],
          start_time: "09:00",
          end_time: "18:00",
          timezone: "UTC",
        },
        quiet_hours: {
          enabled: quietHoursEnabled,
          start_time: "22:00",
          end_time: "07:00",
          bypass_on_critical: false,
        },
        triggers: [
          {
            trigger_type: triggerType,
            parameters: {},
            is_authorized: true,
          },
        ],
        conditions: conditions.map((c) => ({
          condition_group: c.condition_group,
          logical_operator: c.logical_operator,
          field_path: c.field_path,
          operator: c.operator,
          expected_value: c.expected_value,
          min_evidence_observations: 1,
          confidence_threshold: 0.0,
        })),
        actions: [
          {
            action_order: 1,
            action_identifier: actionIdentifier,
            parameters_template: {},
            is_critical: true,
            is_reversible: ACTION_PRESETS[actionIdentifier]?.reversible ?? true,
            action_preview_template: {
              title: ACTION_PRESETS[actionIdentifier]?.title || actionIdentifier,
              description: ACTION_PRESETS[actionIdentifier]?.desc || "",
            },
          },
        ],
      };

      await onSave(payload);
      onClose();
    } catch (err) {
      console.error("Failed to save rule:", err);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-3xl max-h-[90vh] overflow-y-auto rounded-2xl border border-border/80 bg-card p-6 shadow-2xl space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border/70 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-indigo-600 text-white shadow-md shadow-indigo-500/20">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-foreground">
                {rule ? `Edit Rule: ${rule.name}` : "Create Automation Rule"}
              </h3>
              <p className="text-xs text-muted-foreground">
                Define deterministic behavioral triggers, conditions, and action contracts.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-muted-foreground hover:bg-muted transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Rule Metadata */}
          <div className="space-y-3">
            <div>
              <label className="text-xs font-semibold text-foreground block mb-1">
                Rule Name
              </label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Forgetting Risk Impending Warning"
                className="w-full h-9 px-3 rounded-xl border border-border bg-background text-sm focus:ring-1 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-foreground block mb-1">
                Description / Purpose
              </label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Brief summary of why this rule exists and when it triggers"
                className="w-full h-9 px-3 rounded-xl border border-border bg-background text-sm focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          </div>

          {/* Section 1: Trigger Selection */}
          <div className="space-y-2">
            <label className="text-xs font-semibold text-foreground block">
              1. Select Trigger Source
            </label>
            <TriggerSelector
              selected={triggerType}
              onSelect={(type) => {
                setTriggerType(type);
                const opt = TRIGGER_OPTIONS.find((t) => t.type === type);
                if (opt && conditions.length === 0) {
                  setConditions([
                    {
                      field_path: opt.defaultField,
                      operator: "GREATER_THAN",
                      expected_value: 0.7,
                      logical_operator: "AND",
                      condition_group: 0,
                    },
                  ]);
                }
              }}
            />
          </div>

          {/* Section 2: Condition Configuration */}
          <div className="space-y-2 pt-2 border-t border-border/60">
            <ConditionBuilder conditions={conditions} onChange={setConditions} />
          </div>

          {/* Section 3: Action Selection & Preview */}
          <div className="space-y-3 pt-2 border-t border-border/60">
            <label className="text-xs font-semibold text-foreground block">
              3. Configure Executable Action
            </label>
            <select
              value={actionIdentifier}
              onChange={(e) => setActionIdentifier(e.target.value)}
              className="w-full h-9 px-3 rounded-xl border border-border bg-background text-xs font-medium"
            >
              {Object.entries(ACTION_PRESETS).map(([id, info]) => (
                <option key={id} value={id}>
                  [{info.category}] {info.title}
                </option>
              ))}
            </select>

            <ActionPreviewCard
              actionIdentifier={actionIdentifier}
              requiresApproval={requiresApproval}
              riskTier={ACTION_PRESETS[actionIdentifier]?.tier || "Tier 2"}
              isReversible={ACTION_PRESETS[actionIdentifier]?.reversible ?? true}
            />
          </div>

          {/* Section 4: Safety & Throttle Controls */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2 border-t border-border/60 text-xs">
            <div>
              <label className="font-semibold text-foreground flex items-center gap-1 mb-1">
                <Clock className="h-3 w-3 text-indigo-500" /> Cooldown (mins)
              </label>
              <input
                type="number"
                min="0"
                max="1440"
                value={cooldownMinutes}
                onChange={(e) => setCooldownMinutes(Number(e.target.value))}
                className="w-full h-8 px-2.5 rounded-lg border border-border bg-background text-xs"
              />
            </div>

            <div>
              <label className="font-semibold text-foreground flex items-center gap-1 mb-1">
                <Shield className="h-3 w-3 text-indigo-500" /> Max / Day
              </label>
              <input
                type="number"
                min="1"
                max="100"
                value={maxExecutionsPerDay}
                onChange={(e) => setMaxExecutionsPerDay(Number(e.target.value))}
                className="w-full h-8 px-2.5 rounded-lg border border-border bg-background text-xs"
              />
            </div>

            <div className="flex flex-col justify-end">
              <label className="flex items-center gap-2 cursor-pointer h-8">
                <input
                  type="checkbox"
                  checked={requiresApproval}
                  onChange={(e) => setRequiresApproval(e.target.checked)}
                  className="rounded text-indigo-600 focus:ring-indigo-500"
                />
                <span className="font-semibold text-foreground">
                  Require Approval
                </span>
              </label>
            </div>
          </div>

          {/* Footer Actions */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-border/70">
            <Button type="button" variant="outline" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={isSaving}
              className="gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white"
            >
              <Save className="h-3.5 w-3.5" />
              {isSaving ? "Saving..." : rule ? "Update Rule" : "Create Rule"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

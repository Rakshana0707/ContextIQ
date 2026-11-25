"use client";

import React, { useEffect, useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { RuleList } from "@/components/automations/rule-list";
import { RuleEditorModal } from "@/components/automations/rule-editor-modal";
import { ExecutionHistoryTable } from "@/components/automations/execution-history-table";
import { ProactiveFeedList } from "@/components/proactive/proactive-feed-list";
import { WorkflowPlanList } from "@/components/workflows/workflow-plan-list";
import { WorkflowPreviewModal } from "@/components/workflows/workflow-preview-modal";
import { automationsApi } from "@/lib/api/services/automations";
import { proactiveApi } from "@/lib/api/services/proactive";
import { workflowsApi } from "@/lib/api/services/workflows";
import type { AutomationRule, AutomationExecution } from "@/types/automations";
import type { ProactiveFeedItem } from "@/types/proactive";
import type { WorkflowExecutionPlan } from "@/types/workflows";
import {
  Sparkles,
  Plus,
  Play,
  Layers,
  History,
  ShieldCheck,
  Zap,
  CheckCircle2,
  Clock,
  RefreshCw,
  Bell,
  GitBranch,
} from "lucide-react";
import { Button } from "@/components/ui/button";

export default function AutomationCenterPage() {
  const [rules, setRules] = useState<AutomationRule[]>([]);
  const [executions, setExecutions] = useState<AutomationExecution[]>([]);
  const [feedItems, setFeedItems] = useState<ProactiveFeedItem[]>([]);
  const [workflowPlans, setWorkflowPlans] = useState<WorkflowExecutionPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<AutomationRule | null>(null);

  // Workflow preview modal state
  const [selectedPlan, setSelectedPlan] = useState<WorkflowExecutionPlan | null>(null);
  const [isPlanModalOpen, setIsPlanModalOpen] = useState(false);

  const [activeTab, setActiveTab] = useState<"feed" | "workflows" | "rules" | "history">("workflows");

  // Dry run state
  const [dryRunLoading, setDryRunLoading] = useState(false);
  const [dryRunResult, setDryRunResult] = useState<any | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [rulesData, execData, feedData, plansData] = await Promise.all([
        automationsApi.listRules(),
        automationsApi.listExecutions(),
        proactiveApi.getFeed(),
        workflowsApi.listPlans(),
      ]);
      setRules(rulesData);
      setExecutions(execData);
      setFeedItems(feedData);
      setWorkflowPlans(plansData);
    } catch (err: any) {
      setError(err?.message || "Failed to load automation data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleToggle = async (id: string) => {
    try {
      const updated = await automationsApi.toggleRule(id);
      setRules((prev) => prev.map((r) => (r.id === id ? updated : r)));
    } catch (err) {
      console.error("Toggle error:", err);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this automation rule?")) return;
    try {
      await automationsApi.deleteRule(id);
      setRules((prev) => prev.filter((r) => r.id !== id));
    } catch (err) {
      console.error("Delete error:", err);
    }
  };

  const handleSaveRule = async (payload: any) => {
    if (editingRule) {
      const updated = await automationsApi.updateRule(editingRule.id, payload);
      setRules((prev) => prev.map((r) => (r.id === editingRule.id ? updated : r)));
    } else {
      const created = await automationsApi.createRule(payload);
      setRules((prev) => [created, ...prev]);
    }
    setIsModalOpen(false);
    setEditingRule(null);
  };

  const handleSimulateTrigger = async () => {
    setDryRunLoading(true);
    setDryRunResult(null);
    try {
      const res = await automationsApi.evaluateTrigger("FORGETTING_THRESHOLD_EXCEEDED", {
        forgetting_risk: { probability: 0.78 },
        task: { priority: "HIGH" },
      });
      setDryRunResult(res);
      const updatedExecs = await automationsApi.listExecutions();
      setExecutions(updatedExecs);
    } catch (err) {
      console.error("Dry run evaluation error:", err);
    } finally {
      setDryRunLoading(false);
    }
  };

  // Proactive Feed action handlers
  const handleApproveFeedItem = async (id: string) => {
    try {
      const updated = await proactiveApi.respondToFeedItem(id, "APPROVE");
      setFeedItems((prev) => prev.map((item) => (item.id === id ? updated : item)));
      const updatedExecs = await automationsApi.listExecutions();
      setExecutions(updatedExecs);
    } catch (err) {
      console.error("Approve feed item error:", err);
    }
  };

  const handleSnoozeFeedItem = async (id: string, minutes: number) => {
    try {
      const updated = await proactiveApi.respondToFeedItem(id, "SNOOZE", minutes);
      setFeedItems((prev) => prev.map((item) => (item.id === id ? updated : item)));
    } catch (err) {
      console.error("Snooze feed item error:", err);
    }
  };

  const handleDismissFeedItem = async (id: string) => {
    try {
      const updated = await proactiveApi.respondToFeedItem(id, "DISMISS");
      setFeedItems((prev) => prev.map((item) => (item.id === id ? updated : item)));
    } catch (err) {
      console.error("Dismiss feed item error:", err);
    }
  };

  const handleSimulateDetection = async (detectionType: string) => {
    try {
      await proactiveApi.simulateDetection(detectionType);
      const updatedFeed = await proactiveApi.getFeed();
      setFeedItems(updatedFeed);
    } catch (err) {
      console.error("Simulate detection error:", err);
    }
  };

  // Workflow Plan handlers
  const handleSynthesizeWorkflowPlan = async () => {
    try {
      const plan = await workflowsApi.planWorkflow({
        trigger_type: "FORGETTING_RISK_SPIKE",
        behavioral_context: {
          task_title: "Deep Behavioral Analytics Review",
          lapse_probability: 0.82,
          has_calendar_conflict: true,
          conflicting_event_id: "ext_cal_401",
        },
      });
      setWorkflowPlans((prev) => [plan, ...prev]);
      setSelectedPlan(plan);
      setIsPlanModalOpen(true);
    } catch (err) {
      console.error("Synthesize workflow error:", err);
    }
  };

  const handleApproveWorkflowPlan = async (planId: string) => {
    try {
      const updated = await workflowsApi.transitionPlan(planId, "APPROVED", "User approved via preview modal");
      setWorkflowPlans((prev) => prev.map((p) => (p.id === planId ? updated : p)));
      setIsPlanModalOpen(false);
    } catch (err) {
      console.error("Approve workflow error:", err);
    }
  };

  const handleRejectWorkflowPlan = async (planId: string) => {
    try {
      const updated = await workflowsApi.transitionPlan(planId, "CANCELLED", "User rejected via preview modal");
      setWorkflowPlans((prev) => prev.map((p) => (p.id === planId ? updated : p)));
      setIsPlanModalOpen(false);
    } catch (err) {
      console.error("Reject workflow error:", err);
    }
  };

  const activeCount = rules.filter((r) => r.is_enabled).length;
  const activeFeedCount = feedItems.filter((f) => f.status === "ACTIVE").length;
  const awaitingApprovalPlanCount = workflowPlans.filter((p) => p.status === "AWAITING_APPROVAL").length;

  return (
    <AppShell>
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Top Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border/80 pb-5">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-500">
                <Sparkles className="h-5 w-5" />
              </div>
              <div>
                <h1 className="text-xl font-extrabold text-foreground tracking-tight">
                  Automation & Workflow Planning Center
                </h1>
                <p className="text-xs text-muted-foreground">
                  Multi-step workflow planning, governed lifecycle orchestration, and proactive behavioral interventions.
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <Button
              variant="outline"
              size="sm"
              onClick={handleSimulateTrigger}
              disabled={dryRunLoading}
              className="gap-1.5 text-xs h-9"
            >
              <Play className="h-3.5 w-3.5 text-indigo-500" />
              {dryRunLoading ? "Evaluating..." : "Test Event Trigger"}
            </Button>

            <Button
              size="sm"
              onClick={() => {
                setEditingRule(null);
                setIsModalOpen(true);
              }}
              className="gap-1.5 text-xs h-9 bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm"
            >
              <Plus className="h-3.5 w-3.5" />
              New Rule
            </Button>
          </div>
        </div>

        {/* Metric Summary Ribbon */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-3.5 rounded-xl border border-border/80 bg-card/60 backdrop-blur-sm">
            <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-indigo-600 dark:text-indigo-400 block">
              Workflow Proposals
            </span>
            <div className="text-xl font-extrabold text-indigo-600 dark:text-indigo-400 mt-0.5">
              {awaitingApprovalPlanCount} Awaiting Review
            </div>
          </div>

          <div className="p-3.5 rounded-xl border border-border/80 bg-card/60 backdrop-blur-sm">
            <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-cyan-600 dark:text-cyan-400 block">
              Proactive Feed Alerts
            </span>
            <div className="text-xl font-extrabold text-cyan-600 dark:text-cyan-400 mt-0.5">
              {activeFeedCount}
            </div>
          </div>

          <div className="p-3.5 rounded-xl border border-border/80 bg-card/60 backdrop-blur-sm">
            <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-emerald-600 dark:text-emerald-400 block">
              Active Rules
            </span>
            <div className="text-xl font-extrabold text-emerald-600 dark:text-emerald-400 mt-0.5">
              {activeCount} / {rules.length}
            </div>
          </div>

          <div className="p-3.5 rounded-xl border border-border/80 bg-card/60 backdrop-blur-sm">
            <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-muted-foreground block">
              Safety Boundary
            </span>
            <div className="text-xs font-semibold text-foreground mt-1 flex items-center gap-1.5">
              <ShieldCheck className="h-4 w-4 text-emerald-500" /> Governed 13-State FSM
            </div>
          </div>
        </div>

        {/* Dry run live alert if triggered */}
        {dryRunResult && (
          <div className="p-4 rounded-xl border border-indigo-500/30 bg-indigo-50/60 dark:bg-indigo-950/30 text-xs space-y-2 animate-in fade-in">
            <div className="flex items-center justify-between font-bold text-indigo-700 dark:text-indigo-300">
              <span className="flex items-center gap-1.5">
                <CheckCircle2 className="h-4 w-4" /> Trigger Evaluated: {dryRunResult.trigger_type}
              </span>
              <span className="font-mono text-[10px]">
                Matched {dryRunResult.matched_rules_count} of {dryRunResult.evaluated_rules_count} rules
              </span>
            </div>
            <p className="text-muted-foreground">
              Event dispatched: <code>task.priority=HIGH, forgetting_risk.probability=0.78</code>.
              Matched rules generated proposed workflow plans awaiting user confirmation.
            </p>
          </div>
        )}

        {/* Tab Controls */}
        <div className="flex items-center justify-between border-b border-border/70">
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setActiveTab("workflows")}
              className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors ${
                activeTab === "workflows"
                  ? "border-indigo-600 text-indigo-600 dark:text-indigo-400 font-bold"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              <GitBranch className="h-3.5 w-3.5" />
              Workflow Plans ({workflowPlans.length})
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("feed")}
              className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors ${
                activeTab === "feed"
                  ? "border-cyan-600 text-cyan-600 dark:text-cyan-400 font-bold"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              <Bell className="h-3.5 w-3.5" />
              Proactive Feed ({activeFeedCount})
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("rules")}
              className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors ${
                activeTab === "rules"
                  ? "border-indigo-600 text-indigo-600 dark:text-indigo-400 font-bold"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              <Layers className="h-3.5 w-3.5" />
              Automation Rules ({rules.length})
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("history")}
              className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors ${
                activeTab === "history"
                  ? "border-indigo-600 text-indigo-600 dark:text-indigo-400 font-bold"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              <History className="h-3.5 w-3.5" />
              Execution & Audit History ({executions.length})
            </button>
          </div>

          <Button
            variant="ghost"
            size="sm"
            onClick={loadData}
            className="h-8 text-xs gap-1 text-muted-foreground"
          >
            <RefreshCw className="h-3 w-3" /> Refresh
          </Button>
        </div>

        {/* Content Body */}
        {loading ? (
          <div className="py-12 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
            <RefreshCw className="h-4 w-4 animate-spin text-indigo-500" />
            Loading automation and behavioral data...
          </div>
        ) : error ? (
          <div className="p-4 rounded-xl border border-rose-500/30 bg-rose-50/50 dark:bg-rose-950/20 text-xs text-rose-600 dark:text-rose-400">
            {error}
          </div>
        ) : activeTab === "workflows" ? (
          <WorkflowPlanList
            plans={workflowPlans}
            loading={loading}
            onRefresh={loadData}
            onSelectPlan={(plan) => {
              setSelectedPlan(plan);
              setIsPlanModalOpen(true);
            }}
            onSynthesize={handleSynthesizeWorkflowPlan}
          />
        ) : activeTab === "feed" ? (
          <ProactiveFeedList
            items={feedItems}
            loading={loading}
            onRefresh={loadData}
            onApprove={handleApproveFeedItem}
            onSnooze={handleSnoozeFeedItem}
            onDismiss={handleDismissFeedItem}
            onSimulate={handleSimulateDetection}
          />
        ) : activeTab === "rules" ? (
          <RuleList
            rules={rules}
            onToggle={handleToggle}
            onEdit={(r) => {
              setEditingRule(r);
              setIsModalOpen(true);
            }}
            onDelete={handleDelete}
          />
        ) : (
          <ExecutionHistoryTable executions={executions} />
        )}

        {/* Workflow Preview Modal */}
        <WorkflowPreviewModal
          plan={selectedPlan}
          isOpen={isPlanModalOpen}
          onClose={() => {
            setIsPlanModalOpen(false);
            setSelectedPlan(null);
          }}
          onApprove={handleApproveWorkflowPlan}
          onReject={handleRejectWorkflowPlan}
        />

        {/* Rule Editor Modal */}
        <RuleEditorModal
          rule={editingRule}
          isOpen={isModalOpen}
          onClose={() => {
            setIsModalOpen(false);
            setEditingRule(null);
          }}
          onSave={handleSaveRule}
        />
      </div>
    </AppShell>
  );
}

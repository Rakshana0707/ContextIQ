"use client";

import { useState, useEffect } from "react";
import {
  AlertCircle,
  ArrowRight,
  BrainCircuit,
  Calendar,
  CheckCircle2,
  Clock,
  Compass,
  CornerDownLeft,
  FileCheck,
  History,
  Layers,
  Play,
  RotateCcw,
  Shield,
  ShieldAlert,
  Sparkles,
  TrendingDown,
  TrendingUp,
  XCircle,
  Zap,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import type {
  ProposedWorkflow,
  SavedScenario,
  ScenarioCompareResponse,
  ScenarioSimulationResult,
  ScenarioType,
  WorkflowExecutionResponse,
  WorkflowRollbackResponse,
} from "@/types/simulation";
import {
  mockCompareResponse,
  mockProposedWorkflow,
  mockSavedScenarios,
  mockSimulationResult,
  simulationApi,
} from "@/lib/api/services/simulation";

const SCENARIO_OPTIONS: { type: ScenarioType; label: string; desc: string }[] = [
  {
    type: "SCHEDULE_FOCUS_SESSION",
    label: "Schedule Focus Session",
    desc: "Allocate a 60m unfragmented morning focus block with notifications silenced.",
  },
  {
    type: "ADD_RECOVERY_BUFFER",
    label: "Add Recovery Buffer",
    desc: "Insert 15m post-interruption buffer to mitigate resumption friction.",
  },
  {
    type: "MOVE_TASK_TIME",
    label: "Reschedule to Optimal Peak",
    desc: "Shift task to morning circadian focus window (09:00 - 10:00).",
  },
  {
    type: "REDUCE_NOTIFICATIONS",
    label: "Suppress Notifications",
    desc: "DND policy silencing low-priority pings during deep work.",
  },
  {
    type: "DECOMPOSE_TASK",
    label: "Decompose into Milestones",
    desc: "Split complex task into 3 distinct micro-deliverables.",
  },
];

export function BehavioralScenarioLab() {
  const [selectedScenarioType, setSelectedScenarioType] =
    useState<ScenarioType>("SCHEDULE_FOCUS_SESSION");
  const [simResult, setSimResult] = useState<ScenarioSimulationResult>(mockSimulationResult);
  const [savedScenarios, setSavedScenarios] = useState<SavedScenario[]>(mockSavedScenarios);
  const [compareData, setCompareData] = useState<ScenarioCompareResponse>(mockCompareResponse);
  const [workflow, setWorkflow] = useState<ProposedWorkflow>(mockProposedWorkflow);
  const [loading, setLoading] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"simulator" | "comparison" | "workflow">("simulator");

  const runSimulation = async (type: ScenarioType) => {
    setSelectedScenarioType(type);
    setLoading(true);
    setActionMessage(null);
    try {
      const result = await simulationApi.simulate(type);
      setSimResult(result);
    } catch (e) {
      console.error("Simulation failed:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleProposeWorkflow = async (scenarioId: string) => {
    setLoading(true);
    setActionMessage(null);
    try {
      const proposed = await simulationApi.proposeWorkflow(scenarioId);
      setWorkflow(proposed);
      setActiveTab("workflow");
      setActionMessage("Proposed workflow generated. Review steps and permissions below.");
    } catch (e) {
      console.error("Workflow proposal failed:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleApproveWorkflow = async (approved: boolean) => {
    setLoading(true);
    try {
      const updated = await simulationApi.approveWorkflow(workflow.id, approved);
      setWorkflow(updated);
      setActionMessage(
        approved
          ? "Workflow approved by user. Ready for idempotent execution."
          : "Workflow proposal was rejected/cancelled."
      );
    } catch (e) {
      console.error("Workflow approval failed:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleExecuteWorkflow = async () => {
    setLoading(true);
    try {
      const res: WorkflowExecutionResponse = await simulationApi.executeWorkflow(
        workflow.id,
        workflow.idempotency_key
      );
      setWorkflow((prev) => ({
        ...prev,
        status: res.status,
      }));
      setActionMessage(
        `Executed ${res.executed_actions_count} actions successfully. Reversible snapshot stored.`
      );
    } catch (e) {
      console.error("Workflow execution failed:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleRollbackWorkflow = async () => {
    setLoading(true);
    try {
      const res: WorkflowRollbackResponse = await simulationApi.rollbackWorkflow(workflow.id);
      setWorkflow((prev) => ({
        ...prev,
        status: res.status,
      }));
      setActionMessage(`Rollback complete: ${res.details}`);
    } catch (e) {
      console.error("Workflow rollback failed:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleActivatePlan = async (scenarioId: string) => {
    setLoading(true);
    try {
      await simulationApi.activatePlan(scenarioId);
      setSavedScenarios((prev) =>
        prev.map((s) => ({
          ...s,
          is_active_plan: s.id === scenarioId,
        }))
      );
      setActionMessage("Designated scenario as active behavioral target.");
    } catch (e) {
      console.error("Activate plan failed:", e);
    } finally {
      setLoading(false);
    }
  };

  const delta = simResult.counterfactual_delta;

  return (
    <Card className="border border-border/80 shadow-xs">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <BrainCircuit className="h-5 w-5 text-indigo-500" />
            <CardTitle className="text-lg font-semibold">
              Behavioral Digital Twin & Proposed Workflow Lab
            </CardTitle>
            <Badge variant="outline" className="border-indigo-400 text-indigo-700 dark:text-indigo-300">
              Phase 6.9
            </Badge>
          </div>
          <div className="flex items-center gap-1.5 bg-muted/60 p-1 rounded-lg text-xs">
            <button
              onClick={() => setActiveTab("simulator")}
              className={`px-3 py-1 rounded-md transition-colors ${
                activeTab === "simulator"
                  ? "bg-background text-foreground shadow-xs font-semibold"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Scenario Simulator
            </button>
            <button
              onClick={() => setActiveTab("comparison")}
              className={`px-3 py-1 rounded-md transition-colors ${
                activeTab === "comparison"
                  ? "bg-background text-foreground shadow-xs font-semibold"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Saved Scenarios ({savedScenarios.length})
            </button>
            <button
              onClick={() => setActiveTab("workflow")}
              className={`px-3 py-1 rounded-md transition-colors ${
                activeTab === "workflow"
                  ? "bg-background text-foreground shadow-xs font-semibold"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Proposed Workflow
            </button>
          </div>
        </div>
        <CardDescription className="text-xs text-muted-foreground">
          Model-based behavioral simulation with counterfactual delta analysis and safe, reversible multi-step workflow orchestration.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Epistemic disclaimer banner */}
        <div className="bg-indigo-50/70 dark:bg-indigo-950/20 border border-indigo-200 dark:border-indigo-900 rounded-lg p-3 text-xs text-indigo-900 dark:text-indigo-200 flex items-start gap-2.5">
          <Shield className="h-4 w-4 text-indigo-600 dark:text-indigo-400 mt-0.5 shrink-0" />
          <div className="space-y-1">
            <p className="font-medium">
              Simulation Safety Boundary & Model Approximation
            </p>
            <p className="text-[11px] leading-relaxed text-indigo-800 dark:text-indigo-300">
              The digital twin is a model-based approximation of observed behavior and does not modify user tasks or schedules during simulation. All proposed actions require explicit user approval, support idempotency, and provide full one-click rollback.
            </p>
          </div>
        </div>

        {/* Action feedback toast */}
        {actionMessage && (
          <div className="bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-200 text-xs p-2.5 rounded-md flex items-center justify-between">
            <span>{actionMessage}</span>
            <button onClick={() => setActionMessage(null)} className="text-xs hover:underline">
              Dismiss
            </button>
          </div>
        )}

        {/* TAB 1: SIMULATOR */}
        {activeTab === "simulator" && (
          <div className="space-y-4">
            {/* Scenario selector chips */}
            <div>
              <span className="text-xs font-medium text-muted-foreground block mb-1.5">
                Select Counterfactual Hypothesis:
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                {SCENARIO_OPTIONS.map((opt) => (
                  <button
                    key={opt.type}
                    onClick={() => runSimulation(opt.type)}
                    disabled={loading}
                    className={`text-left p-2.5 rounded-lg border text-xs transition-all ${
                      selectedScenarioType === opt.type
                        ? "border-primary bg-primary/5 ring-1 ring-primary"
                        : "border-border hover:bg-muted/50"
                    }`}
                  >
                    <div className="font-semibold text-foreground">{opt.label}</div>
                    <div className="text-[11px] text-muted-foreground line-clamp-2 mt-0.5">
                      {opt.desc}
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Counterfactual Metric Projection Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
              {/* Metric 1: Completion Likelihood */}
              <div className="p-3 bg-muted/30 border rounded-lg space-y-1">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>Task Completion</span>
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-bold">
                    {Math.round(simResult.simulated_metrics.completion_probability * 100)}%
                  </span>
                  <span
                    className={`text-xs font-medium flex items-center ${
                      delta.completion_probability_delta >= 0
                        ? "text-emerald-600 dark:text-emerald-400"
                        : "text-rose-600"
                    }`}
                  >
                    {delta.completion_probability_delta >= 0 ? (
                      <TrendingUp className="h-3 w-3 mr-0.5 inline" />
                    ) : (
                      <TrendingDown className="h-3 w-3 mr-0.5 inline" />
                    )}
                    {(delta.completion_probability_delta * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="text-[10px] text-muted-foreground">
                  Baseline: {Math.round(simResult.baseline_metrics.completion_probability * 100)}% (90% CI:{" "}
                  {Math.round(simResult.simulated_metrics.completion_probability_interval_lower * 100)}-
                  {Math.round(simResult.simulated_metrics.completion_probability_interval_upper * 100)}%)
                </div>
              </div>

              {/* Metric 2: Recovery Duration */}
              <div className="p-3 bg-muted/30 border rounded-lg space-y-1">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>Recovery Lag</span>
                  <Clock className="h-3.5 w-3.5 text-amber-500" />
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-bold">
                    {simResult.simulated_metrics.expected_recovery_duration_minutes.toFixed(1)}m
                  </span>
                  <span
                    className={`text-xs font-medium flex items-center ${
                      delta.recovery_duration_delta_minutes <= 0
                        ? "text-emerald-600 dark:text-emerald-400"
                        : "text-rose-600"
                    }`}
                  >
                    {delta.recovery_duration_delta_minutes <= 0 ? (
                      <TrendingDown className="h-3 w-3 mr-0.5 inline" />
                    ) : (
                      <TrendingUp className="h-3 w-3 mr-0.5 inline" />
                    )}
                    {delta.recovery_duration_delta_minutes.toFixed(1)}m
                  </span>
                </div>
                <div className="text-[10px] text-muted-foreground">
                  Baseline: {simResult.baseline_metrics.expected_recovery_duration_minutes.toFixed(1)}m (90% CI:{" "}
                  {simResult.simulated_metrics.recovery_duration_interval_lower.toFixed(1)}-
                  {simResult.simulated_metrics.recovery_duration_interval_upper.toFixed(1)}m)
                </div>
              </div>

              {/* Metric 3: Behavioral Friction (BFI) */}
              <div className="p-3 bg-muted/30 border rounded-lg space-y-1">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>Friction Index</span>
                  <TrendingDown className="h-3.5 w-3.5 text-blue-500" />
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-bold">
                    {Math.round(simResult.simulated_metrics.behavioral_friction_index)}
                  </span>
                  <span
                    className={`text-xs font-medium flex items-center ${
                      delta.friction_delta <= 0
                        ? "text-emerald-600 dark:text-emerald-400"
                        : "text-rose-600"
                    }`}
                  >
                    {delta.friction_delta <= 0 ? (
                      <TrendingDown className="h-3 w-3 mr-0.5 inline" />
                    ) : (
                      <TrendingUp className="h-3 w-3 mr-0.5 inline" />
                    )}
                    {delta.friction_delta.toFixed(1)} pts
                  </span>
                </div>
                <div className="text-[10px] text-muted-foreground">
                  Baseline: {Math.round(simResult.baseline_metrics.behavioral_friction_index)} / 100
                </div>
              </div>

              {/* Metric 4: Calendar Feasibility */}
              <div className="p-3 bg-muted/30 border rounded-lg space-y-1">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>Feasibility</span>
                  <Calendar className="h-3.5 w-3.5 text-purple-500" />
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-bold">
                    {Math.round(simResult.simulated_metrics.calendar_feasibility * 100)}%
                  </span>
                  <Badge variant="outline" className="text-[10px]">
                    High Fit
                  </Badge>
                </div>
                <div className="text-[10px] text-muted-foreground">
                  Notification Burden: {Math.round(simResult.simulated_metrics.notification_burden_score)}/100
                </div>
              </div>
            </div>

            {/* Assumptions & Model Metadata */}
            <div className="p-3 border rounded-lg bg-card space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold flex items-center gap-1.5">
                  <Sparkles className="h-3.5 w-3.5 text-indigo-500" />
                  Simulation Assumptions & Behavioral Model
                </span>
                <span className="text-[10px] text-muted-foreground font-mono">
                  {simResult.model_version} • {simResult.feature_version}
                </span>
              </div>
              <ul className="text-xs text-muted-foreground space-y-1 list-disc list-inside">
                {simResult.assumptions.map((assump, idx) => (
                  <li key={idx} className="leading-relaxed">
                    {assump}
                  </li>
                ))}
              </ul>
            </div>

            {/* Proposal CTA */}
            <div className="flex items-center justify-between pt-2">
              <p className="text-xs text-muted-foreground">
                Satisfied with this scenario projection? Generate a reversible workflow proposal for review.
              </p>
              <Button
                size="sm"
                className="gap-1.5 text-xs"
                onClick={() => handleProposeWorkflow("scen_mock_001")}
                disabled={loading}
              >
                <Play className="h-3.5 w-3.5" />
                Propose Workflow
              </Button>
            </div>
          </div>
        )}

        {/* TAB 2: SAVED SCENARIOS & COMPARISON */}
        {activeTab === "comparison" && (
          <div className="space-y-4">
            <div className="space-y-2">
              <span className="text-xs font-semibold text-foreground">
                Saved User Scenarios & Active Plans
              </span>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {savedScenarios.map((scen) => (
                  <div
                    key={scen.id}
                    className={`p-3 border rounded-lg space-y-2 transition-all ${
                      scen.is_active_plan
                        ? "border-emerald-500 bg-emerald-50/20 dark:bg-emerald-950/10"
                        : "bg-card"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="font-semibold text-xs text-foreground flex items-center gap-1.5">
                        {scen.title}
                        {scen.is_active_plan && (
                          <Badge className="bg-emerald-600 text-white text-[10px] py-0 px-1.5">
                            Active Plan
                          </Badge>
                        )}
                      </div>
                      <Badge variant="outline" className="text-[10px]">
                        {scen.scenario_type.replace(/_/g, " ")}
                      </Badge>
                    </div>

                    <p className="text-[11px] text-muted-foreground line-clamp-2">
                      {scen.hypothesis}
                    </p>

                    <div className="grid grid-cols-3 gap-2 py-1 border-t text-center text-xs">
                      <div>
                        <div className="text-[10px] text-muted-foreground">Completion</div>
                        <div className="font-semibold text-emerald-600 dark:text-emerald-400">
                          {Math.round(scen.simulated_metrics.completion_probability * 100)}%
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] text-muted-foreground">Recovery</div>
                        <div className="font-semibold">
                          {scen.simulated_metrics.expected_recovery_duration_minutes.toFixed(1)}m
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] text-muted-foreground">Friction</div>
                        <div className="font-semibold">
                          {Math.round(scen.simulated_metrics.behavioral_friction_index)}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center justify-between pt-1 text-xs">
                      {!scen.is_active_plan ? (
                        <Button
                          variant="outline"
                          size="sm"
                          className="text-[11px] h-7"
                          onClick={() => handleActivatePlan(scen.id)}
                          disabled={loading}
                        >
                          Set as Active Plan
                        </Button>
                      ) : (
                        <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-medium flex items-center gap-1">
                          <CheckCircle2 className="h-3 w-3" /> Targeted Strategy
                        </span>
                      )}
                      <Button
                        size="sm"
                        className="text-[11px] h-7 gap-1"
                        onClick={() => handleProposeWorkflow(scen.id)}
                        disabled={loading}
                      >
                        Propose Workflow
                        <ArrowRight className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Trade-off Matrix */}
            <div className="p-3 border rounded-lg bg-card space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold flex items-center gap-1.5">
                  <Compass className="h-3.5 w-3.5 text-primary" />
                  Scenario Trade-off Matrix & Recommendation
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                {compareData.recommendation_rationale}
              </p>
              <div className="space-y-1.5 pt-1">
                {compareData.scenarios.map((item, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between text-xs p-2 bg-muted/40 rounded-md"
                  >
                    <span className="font-medium text-foreground">{item.title}</span>
                    <div className="flex items-center gap-3">
                      <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                        +{(item.completion_probability_delta * 100).toFixed(0)}% Done
                      </span>
                      <span className="text-amber-600 dark:text-amber-400">
                        {item.recovery_minutes_delta.toFixed(1)}m Recovery
                      </span>
                      <span className="text-muted-foreground">
                        BFI {Math.round(item.behavioral_friction)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: WORKFLOW ORCHESTRATION */}
        {activeTab === "workflow" && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2 p-3 border rounded-lg bg-muted/20">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-sm text-foreground">{workflow.title}</span>
                  <Badge
                    variant={
                      workflow.status === "COMPLETED"
                        ? "default"
                        : workflow.status === "APPROVED"
                        ? "outline"
                        : workflow.status === "REVERTED"
                        ? "secondary"
                        : "outline"
                    }
                    className={`text-[10px] ${
                      workflow.status === "COMPLETED"
                        ? "bg-emerald-600 text-white"
                        : workflow.status === "APPROVED"
                        ? "border-emerald-500 text-emerald-700 dark:text-emerald-300"
                        : workflow.status === "REVERTED"
                        ? "border-amber-400 text-amber-700"
                        : ""
                    }`}
                  >
                    {workflow.status}
                  </Badge>
                </div>
                <div className="text-[11px] text-muted-foreground mt-0.5">
                  Est. duration: {workflow.estimated_total_duration_minutes}m • Reversible:{" "}
                  {workflow.is_reversible ? "Yes" : "No"} • Idempotency key:{" "}
                  <code className="text-[10px]">{workflow.idempotency_key.slice(0, 12)}...</code>
                </div>
              </div>

              {/* Action Buttons based on status */}
              <div className="flex items-center gap-2">
                {workflow.status === "PROPOSED" && (
                  <>
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-xs text-rose-600 h-8 gap-1"
                      onClick={() => handleApproveWorkflow(false)}
                      disabled={loading}
                    >
                      <XCircle className="h-3.5 w-3.5" /> Reject
                    </Button>
                    <Button
                      size="sm"
                      className="text-xs bg-emerald-600 hover:bg-emerald-700 text-white h-8 gap-1"
                      onClick={() => handleApproveWorkflow(true)}
                      disabled={loading}
                    >
                      <FileCheck className="h-3.5 w-3.5" /> Approve Proposal
                    </Button>
                  </>
                )}

                {workflow.status === "APPROVED" && (
                  <Button
                    size="sm"
                    className="text-xs h-8 gap-1"
                    onClick={handleExecuteWorkflow}
                    disabled={loading}
                  >
                    <Play className="h-3.5 w-3.5" /> Execute Workflow
                  </Button>
                )}

                {workflow.status === "COMPLETED" && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="text-xs border-amber-400 text-amber-700 dark:text-amber-300 h-8 gap-1"
                    onClick={handleRollbackWorkflow}
                    disabled={loading}
                  >
                    <RotateCcw className="h-3.5 w-3.5" /> Rollback / Undo All Actions
                  </Button>
                )}
              </div>
            </div>

            {/* Required Permissions */}
            <div className="text-xs text-muted-foreground flex items-center gap-2">
              <span className="font-medium text-foreground">Required Permissions:</span>
              <div className="flex flex-wrap gap-1">
                {workflow.required_permissions.map((perm) => (
                  <Badge key={perm} variant="secondary" className="text-[10px] font-mono">
                    {perm}
                  </Badge>
                ))}
              </div>
            </div>

            {/* Sequence of action previews */}
            <div className="space-y-2">
              <span className="text-xs font-semibold text-foreground">
                Action Execution Steps ({workflow.actions.length})
              </span>
              <div className="space-y-2">
                {workflow.actions.map((act) => (
                  <div
                    key={act.action_id}
                    className="p-3 border rounded-lg bg-card flex items-start justify-between text-xs gap-3"
                  >
                    <div className="flex items-start gap-2.5">
                      <div className="w-5 h-5 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-[10px] mt-0.5 shrink-0">
                        {act.sequence_order}
                      </div>
                      <div className="space-y-0.5">
                        <div className="font-semibold text-foreground flex items-center gap-2">
                          <span>{act.action_type.replace(/_/g, " ")}</span>
                          <span className="text-[10px] text-muted-foreground font-mono">
                            ({act.target_resource})
                          </span>
                        </div>
                        <p className="text-muted-foreground text-[11px]">{act.description}</p>
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <Badge variant="outline" className="text-[10px]">
                        {act.estimated_duration_minutes}m
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Audit Trail */}
            {workflow.audit_trail && workflow.audit_trail.length > 0 && (
              <div className="p-3 border rounded-lg bg-muted/20 space-y-1.5">
                <span className="text-xs font-semibold flex items-center gap-1.5 text-foreground">
                  <History className="h-3.5 w-3.5 text-muted-foreground" />
                  Audit Trail
                </span>
                <div className="space-y-1">
                  {workflow.audit_trail.map((entry, idx) => (
                    <div key={idx} className="text-[11px] text-muted-foreground font-mono">
                      <span className="text-foreground">{entry.action}</span>: {entry.details} (
                      {new Date(entry.timestamp).toLocaleTimeString()})
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

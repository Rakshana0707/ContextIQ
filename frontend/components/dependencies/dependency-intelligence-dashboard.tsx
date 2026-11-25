"use client";

import React, { useState, useEffect, useMemo } from "react";
import {
  GitFork,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  ArrowRight,
  ShieldAlert,
  Sparkles,
  Layers,
  Clock,
  Activity,
  RefreshCw,
  Plus,
  Search,
  Filter,
  Check,
  Zap,
} from "lucide-react";
import { taskDependencyApi } from "@/lib/api";
import type {
  DependencyGraphResponse,
  ImpactAnalysisResult,
  TaskDependency,
  TaskDependencyType,
  DependencyValidationStatus,
} from "@/types/task_dependency";

export function DependencyIntelligenceDashboard() {
  const [dependencies, setDependencies] = useState<TaskDependency[]>([]);
  const [graphData, setGraphData] = useState<DependencyGraphResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [discovering, setDiscovering] = useState(false);
  const [activeTab, setActiveTab] = useState<"LIST" | "GRAPH" | "IMPACT" | "CREATE">("LIST");

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedType, setSelectedType] = useState<string>("ALL");
  const [selectedStatus, setSelectedStatus] = useState<string>("ALL");

  // Impact Simulation State
  const [simTaskId, setSimTaskId] = useState<string>("");
  const [simDelayDays, setSimDelayDays] = useState<number>(3.0);
  const [simIsBlocked, setSimIsBlocked] = useState<boolean>(true);
  const [impactResult, setImpactResult] = useState<ImpactAnalysisResult | null>(null);
  const [simulating, setSimulating] = useState(false);

  // Manual Creation State
  const [createSrcId, setCreateSrcId] = useState("");
  const [createDstId, setCreateDstId] = useState("");
  const [createType, setCreateType] = useState<TaskDependencyType>("EXPLICIT_DEPENDENCY");
  const [createNotes, setCreateNotes] = useState("");
  const [creating, setCreating] = useState(false);

  // Detail Modal / Inspector
  const [inspectDep, setInspectDep] = useState<TaskDependency | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [deps, graph] = await Promise.all([
        taskDependencyApi.listDependencies(),
        taskDependencyApi.getDependencyGraph(),
      ]);
      setDependencies(deps);
      setGraphData(graph);
      if (deps.length > 0 && !simTaskId) {
        setSimTaskId(deps[0].source_task_id);
      }
    } catch (err) {
      console.error("Failed to load dependency intelligence", err);
    } finally {
      setLoading(false);
    }
  };

  const handleDiscover = async () => {
    setDiscovering(true);
    try {
      const res = await taskDependencyApi.discoverDependencies({
        lookback_days: 30,
        min_confidence: 0.4,
        include_temporal: true,
        include_project_goals: true,
        include_resource_conflicts: true,
      });
      setDependencies(res.dependencies);
      const graph = await taskDependencyApi.getDependencyGraph();
      setGraphData(graph);
    } catch (err) {
      console.error("Discovery error", err);
    } finally {
      setDiscovering(false);
    }
  };

  const handleConfirm = async (depId: string, action: "CONFIRM" | "REJECT" | "CONVERT_EXPLICIT", correctedType?: TaskDependencyType) => {
    try {
      const updated = await taskDependencyApi.confirmOrReviewDependency(depId, {
        action,
        corrected_type: correctedType,
      });
      setDependencies((prev) => prev.map((d) => (d.id === depId ? updated : d)));
      if (inspectDep?.id === depId) {
        setInspectDep(updated);
      }
    } catch (err) {
      console.error("Review action failed", err);
    }
  };

  const handleSimulateImpact = async () => {
    if (!simTaskId) return;
    setSimulating(true);
    try {
      const res = await taskDependencyApi.runImpactAnalysis({
        task_id: simTaskId,
        hypothetical_delay_days: simDelayDays,
        is_blocked: simIsBlocked,
      });
      setImpactResult(res);
    } catch (err) {
      console.error("Impact simulation failed", err);
    } finally {
      setSimulating(false);
    }
  };

  const handleCreateExplicit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createSrcId || !createDstId) return;
    setCreating(true);
    try {
      const newDep = await taskDependencyApi.createExplicitDependency({
        source_task_id: createSrcId,
        target_task_id: createDstId,
        dependency_type: createType,
        confidence: 1.0,
        notes: createNotes,
      });
      setDependencies((prev) => [newDep, ...prev]);
      setActiveTab("LIST");
      setCreateSrcId("");
      setCreateDstId("");
      setCreateNotes("");
    } catch (err) {
      console.error("Creation failed", err);
    } finally {
      setCreating(false);
    }
  };

  const filteredDependencies = useMemo(() => {
    return dependencies.filter((d) => {
      const matchesSearch =
        !searchQuery ||
        (d.source_task_title && d.source_task_title.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (d.target_task_title && d.target_task_title.toLowerCase().includes(searchQuery.toLowerCase())) ||
        d.dependency_type.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesType = selectedType === "ALL" || d.dependency_type === selectedType;
      const matchesStatus = selectedStatus === "ALL" || d.validation_status === selectedStatus;

      return matchesSearch && matchesType && matchesStatus;
    });
  }, [dependencies, searchQuery, selectedType, selectedStatus]);

  const potentialBlockersCount = useMemo(() => {
    return dependencies.filter((d) => d.dependency_type === "POTENTIAL_BLOCKER" && d.validation_status !== "REJECTED").length;
  }, [dependencies]);

  const explicitCount = useMemo(() => {
    return dependencies.filter((d) => !d.is_inferred).length;
  }, [dependencies]);

  const proposedCount = useMemo(() => {
    return dependencies.filter((d) => d.validation_status === "PROPOSED").length;
  }, [dependencies]);

  return (
    <div className="space-y-6">
      {/* Top Header & Analytics Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 bg-slate-900 border border-slate-800 rounded-xl text-white">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <GitFork className="h-6 w-6 text-indigo-400" />
            <h1 className="text-2xl font-bold tracking-tight">Cross-Task Dependency Intelligence</h1>
          </div>
          <p className="text-slate-400 text-sm max-w-2xl">
            Algorithmic discovery of latent bottlenecks, shared project synergies, repeated sequences, and cascading impact analysis.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleDiscover}
            disabled={discovering}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition shadow-md"
          >
            <Sparkles className={`h-4 w-4 ${discovering ? "animate-spin" : ""}`} />
            {discovering ? "Mining Relationships..." : "Discover Dependencies"}
          </button>
          <button
            onClick={() => setActiveTab("CREATE")}
            className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg text-sm font-medium transition"
          >
            <Plus className="h-4 w-4" />
            Declare Explicit
          </button>
        </div>
      </div>

      {/* KPI Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Total Discovered</span>
            <Layers className="h-4 w-4 text-indigo-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-white">{dependencies.length}</div>
          <div className="text-xs text-slate-400 mt-1">{explicitCount} explicit · {dependencies.length - explicitCount} inferred</div>
        </div>

        <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-amber-400 uppercase tracking-wider">Potential Blockers</span>
            <AlertTriangle className="h-4 w-4 text-amber-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-amber-300">{potentialBlockersCount}</div>
          <div className="text-xs text-slate-400 mt-1">Preceding uncompleted bottlenecks</div>
        </div>

        <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-purple-400 uppercase tracking-wider">Awaiting Review</span>
            <Activity className="h-4 w-4 text-purple-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-purple-300">{proposedCount}</div>
          <div className="text-xs text-slate-400 mt-1">Proposed hypotheses pending confirmation</div>
        </div>

        <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">Confirmed Active</span>
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-emerald-300">
            {dependencies.filter((d) => d.validation_status === "CONFIRMED" || d.validation_status === "CONVERTED_EXPLICIT").length}
          </div>
          <div className="text-xs text-slate-400 mt-1">Verified strategic relationships</div>
        </div>
      </div>

      {/* Tabs Navigation */}
      <div className="flex border-b border-slate-800 gap-6 text-sm font-medium">
        <button
          onClick={() => setActiveTab("LIST")}
          className={`pb-3 transition flex items-center gap-2 ${
            activeTab === "LIST"
              ? "text-indigo-400 border-b-2 border-indigo-500"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <Layers className="h-4 w-4" />
          Discovered Relationships ({dependencies.length})
        </button>
        <button
          onClick={() => setActiveTab("GRAPH")}
          className={`pb-3 transition flex items-center gap-2 ${
            activeTab === "GRAPH"
              ? "text-indigo-400 border-b-2 border-indigo-500"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <GitFork className="h-4 w-4" />
          Visual Graph Network
        </button>
        <button
          onClick={() => setActiveTab("IMPACT")}
          className={`pb-3 transition flex items-center gap-2 ${
            activeTab === "IMPACT"
              ? "text-indigo-400 border-b-2 border-indigo-500"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <ShieldAlert className="h-4 w-4" />
          Cascading Impact Simulator
        </button>
      </div>

      {/* TAB 1: RELATIONSHIPS LIST */}
      {activeTab === "LIST" && (
        <div className="space-y-4">
          {/* Filter Bar */}
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
              <input
                type="text"
                placeholder="Search tasks, dependency types, or notes..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-4 py-2 bg-slate-900 border border-slate-800 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
            </div>
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              <option value="ALL">All Types</option>
              <option value="POTENTIAL_BLOCKER">Potential Blocker</option>
              <option value="EXPLICIT_DEPENDENCY">Explicit Dependency</option>
              <option value="REPEATED_WORKFLOW">Repeated Workflow</option>
              <option value="RESOURCE_CONFLICT">Resource Conflict</option>
              <option value="SHARED_PROJECT">Shared Project</option>
              <option value="SHARED_GOAL">Shared Goal</option>
              <option value="TEMPORAL_ASSOCIATION">Temporal Association</option>
            </select>
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              <option value="ALL">All Statuses</option>
              <option value="PROPOSED">Proposed</option>
              <option value="CONFIRMED">Confirmed</option>
              <option value="CONVERTED_EXPLICIT">Converted Explicit</option>
              <option value="REJECTED">Rejected</option>
            </select>
          </div>

          {/* Cards List */}
          {loading ? (
            <div className="p-8 text-center text-slate-400">Loading dependency records...</div>
          ) : filteredDependencies.length === 0 ? (
            <div className="p-8 text-center text-slate-400 bg-slate-900 border border-slate-800 rounded-xl">
              No cross-task relationships match your search criteria. Click &quot;Discover Dependencies&quot; to mine from execution logs.
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3">
              {filteredDependencies.map((dep) => (
                <div
                  key={dep.id}
                  className={`p-4 bg-slate-900 border rounded-xl transition hover:border-slate-700 ${
                    dep.dependency_type === "POTENTIAL_BLOCKER"
                      ? "border-amber-900/60 bg-amber-950/10"
                      : "border-slate-800"
                  }`}
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    {/* Source and Target Tasks */}
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      <div className="flex-1 min-w-0">
                        <div className="text-xs text-slate-400 uppercase font-semibold">Source Task</div>
                        <div className="text-sm font-medium text-white truncate">
                          {dep.source_task_title || dep.source_task_id}
                        </div>
                        <span className="inline-block mt-1 text-[11px] px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                          {dep.source_task_status || "PENDING"}
                        </span>
                      </div>

                      <div className="flex flex-col items-center px-2">
                        <ArrowRight className="h-4 w-4 text-indigo-400" />
                        <span className="text-[10px] font-semibold text-indigo-300 mt-1 text-center whitespace-nowrap">
                          {dep.dependency_type.replace(/_/g, " ")}
                        </span>
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="text-xs text-slate-400 uppercase font-semibold">Target Task</div>
                        <div className="text-sm font-medium text-white truncate">
                          {dep.target_task_title || dep.target_task_id}
                        </div>
                        <span className="inline-block mt-1 text-[11px] px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                          {dep.target_task_status || "PENDING"}
                        </span>
                      </div>
                    </div>

                    {/* Metadata Badges & Action Buttons */}
                    <div className="flex items-center gap-3">
                      <div className="text-right">
                        <div className="text-xs text-slate-400">Confidence</div>
                        <div className="text-sm font-bold text-white">{(dep.confidence * 100).toFixed(0)}%</div>
                      </div>

                      {/* Epistemic Status Tag */}
                      <span
                        className={`text-xs px-2.5 py-1 rounded-full font-medium ${
                          dep.validation_status === "CONFIRMED"
                            ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                            : dep.validation_status === "CONVERTED_EXPLICIT"
                            ? "bg-indigo-950 text-indigo-300 border border-indigo-800"
                            : dep.validation_status === "REJECTED"
                            ? "bg-rose-950 text-rose-300 border border-rose-800"
                            : "bg-amber-950 text-amber-300 border border-amber-800"
                        }`}
                      >
                        {dep.validation_status}
                      </span>

                      {/* Quick Actions */}
                      <button
                        onClick={() => setInspectDep(dep)}
                        className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium transition"
                      >
                        Inspect Evidence
                      </button>

                      {dep.validation_status === "PROPOSED" && (
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => handleConfirm(dep.id, "CONFIRM")}
                            title="Confirm Relationship"
                            className="p-1.5 bg-emerald-900/50 hover:bg-emerald-800 text-emerald-300 rounded-md transition"
                          >
                            <Check className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => handleConfirm(dep.id, "REJECT")}
                            title="Reject Relationship"
                            className="p-1.5 bg-rose-900/50 hover:bg-rose-800 text-rose-300 rounded-md transition"
                          >
                            <XCircle className="h-4 w-4" />
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Supporting Rationale Bar */}
                  {dep.supporting_observations?.reason && (
                    <div className="mt-3 text-xs text-slate-400 bg-slate-950/50 px-3 py-1.5 rounded-md border border-slate-800/80">
                      <span className="font-semibold text-slate-300">Observation:</span> {dep.supporting_observations.reason}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: VISUAL GRAPH NETWORK */}
      {activeTab === "GRAPH" && (
        <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-white">Interactive Dependency Network</h2>
            <div className="text-xs text-slate-400 flex items-center gap-4">
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-indigo-500"></span> Explicit
              </span>
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-amber-500"></span> Blocker
              </span>
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-emerald-500"></span> Workflow
              </span>
            </div>
          </div>

          {/* Simple Visual representation of graph connections */}
          <div className="bg-slate-950 p-6 rounded-lg border border-slate-800 min-h-[300px]">
            {graphData?.nodes.length === 0 ? (
              <div className="text-center text-slate-500 py-12">No graph nodes active.</div>
            ) : (
              <div className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {graphData?.nodes
                    .filter((n) => n.entity_type === "TASK")
                    .map((node) => {
                      const outgoingEdges = graphData.edges.filter((e) => e.source === node.id);
                      return (
                        <div key={node.id} className="p-4 bg-slate-900 border border-slate-800 rounded-lg space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="text-xs px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 font-mono">
                              {node.entity_type}
                            </span>
                            <span className="text-[11px] text-slate-400">{node.status}</span>
                          </div>
                          <div className="text-sm font-semibold text-white">{node.label}</div>
                          {outgoingEdges.length > 0 && (
                            <div className="pt-2 border-t border-slate-800 space-y-1">
                              <span className="text-[11px] text-slate-400">Depends On / Blocks:</span>
                              {outgoingEdges.map((edge) => {
                                const targetNode = graphData.nodes.find((n) => n.id === edge.target);
                                return (
                                  <div key={edge.id} className="flex items-center gap-1 text-xs text-slate-300">
                                    <ArrowRight className="h-3 w-3 text-indigo-400" />
                                    <span className="font-medium text-amber-400">
                                      {edge.dependency_type.replace(/_/g, " ")}:
                                    </span>{" "}
                                    <span className="truncate">{targetNode?.label || edge.target}</span>
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      );
                    })}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: CASCADING IMPACT SIMULATOR */}
      {activeTab === "IMPACT" && (
        <div className="space-y-6">
          <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl space-y-4">
            <h2 className="text-base font-semibold text-white flex items-center gap-2">
              <ShieldAlert className="h-5 w-5 text-indigo-400" />
              Cascading Delay & Blocker Impact Simulator
            </h2>
            <p className="text-xs text-slate-400">
              Select a task to simulate how delays ripple through downstream deliverables, project health indicators, and strategic milestone commitments.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
              <div>
                <label className="text-xs font-semibold text-slate-400 uppercase">Focal Task</label>
                <select
                  value={simTaskId}
                  onChange={(e) => setSimTaskId(e.target.value)}
                  className="w-full mt-1.5 px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-white focus:outline-none focus:border-indigo-500"
                >
                  <option value="">Select a task...</option>
                  {dependencies.map((d) => (
                    <option key={d.source_task_id} value={d.source_task_id}>
                      {d.source_task_title || d.source_task_id}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-400 uppercase">Hypothetical Delay (Days)</label>
                <input
                  type="number"
                  min="0.5"
                  max="30"
                  step="0.5"
                  value={simDelayDays}
                  onChange={(e) => setSimDelayDays(parseFloat(e.target.value) || 1.0)}
                  className="w-full mt-1.5 px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="flex items-end">
                <button
                  onClick={handleSimulateImpact}
                  disabled={simulating || !simTaskId}
                  className="w-full px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition shadow-md flex items-center justify-center gap-2"
                >
                  <RefreshCw className={`h-4 w-4 ${simulating ? "animate-spin" : ""}`} />
                  {simulating ? "Simulating Cascade..." : "Run Ripple Simulation"}
                </button>
              </div>
            </div>
          </div>

          {/* Simulation Results Display */}
          {impactResult && (
            <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
                <div>
                  <span className="text-xs uppercase text-slate-400 font-semibold">Simulation Analysis</span>
                  <h3 className="text-lg font-bold text-white mt-1">Impact for &quot;{impactResult.focal_task_title}&quot;</h3>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className={`px-3 py-1 rounded-full text-xs font-bold ${
                      impactResult.impact_severity === "CRITICAL"
                        ? "bg-rose-950 text-rose-300 border border-rose-800"
                        : impactResult.impact_severity === "HIGH"
                        ? "bg-amber-950 text-amber-300 border border-amber-800"
                        : "bg-blue-950 text-blue-300 border border-blue-800"
                    }`}
                  >
                    {impactResult.impact_severity} SEVERITY
                  </span>
                  {impactResult.critical_path_risk && (
                    <span className="px-3 py-1 rounded-full text-xs font-bold bg-purple-950 text-purple-300 border border-purple-800 flex items-center gap-1">
                      <AlertTriangle className="h-3 w-3" /> CRITICAL PATH AT RISK
                    </span>
                  )}
                </div>
              </div>

              <p className="text-sm text-slate-300 bg-slate-950 p-4 rounded-lg border border-slate-800">
                {impactResult.analysis_summary}
              </p>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Affected Downstream Tasks */}
                <div className="p-4 bg-slate-950 rounded-lg border border-slate-800">
                  <h4 className="text-xs font-semibold text-slate-400 uppercase mb-3">
                    Downstream Tasks ({impactResult.total_downstream_tasks})
                  </h4>
                  {impactResult.downstream_tasks.length === 0 ? (
                    <div className="text-xs text-slate-500">No immediate downstream tasks affected.</div>
                  ) : (
                    <div className="space-y-2">
                      {impactResult.downstream_tasks.map((task) => (
                        <div key={task.task_id} className="p-2.5 bg-slate-900 rounded border border-slate-800 text-xs">
                          <div className="font-semibold text-white">{task.title}</div>
                          <div className="text-slate-400 mt-1 flex justify-between">
                            <span>Hop Distance: {task.hop_distance}</span>
                            <span className="text-amber-400">+{task.projected_delay_days}d projected</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Affected Milestones */}
                <div className="p-4 bg-slate-950 rounded-lg border border-slate-800">
                  <h4 className="text-xs font-semibold text-slate-400 uppercase mb-3">
                    Milestones Impacted ({impactResult.affected_milestones.length})
                  </h4>
                  {impactResult.affected_milestones.length === 0 ? (
                    <div className="text-xs text-slate-500">No project milestones affected.</div>
                  ) : (
                    <div className="space-y-2">
                      {impactResult.affected_milestones.map((m) => (
                        <div key={m.milestone_id} className="p-2.5 bg-slate-900 rounded border border-slate-800 text-xs">
                          <div className="font-semibold text-white">{m.title}</div>
                          <div className="text-slate-400 mt-1 flex justify-between">
                            <span>Due in: {m.days_until_due !== null ? `${m.days_until_due}d` : "N/A"}</span>
                            {m.at_risk && <span className="text-rose-400 font-bold">AT RISK</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Affected Projects & Goals */}
                <div className="p-4 bg-slate-950 rounded-lg border border-slate-800">
                  <h4 className="text-xs font-semibold text-slate-400 uppercase mb-3">
                    Strategic Scope Impact
                  </h4>
                  <div className="space-y-2 text-xs">
                    {impactResult.affected_projects.map((p) => (
                      <div key={p.project_id} className="p-2 bg-slate-900 rounded border border-slate-800">
                        <div className="text-white font-medium">{p.title}</div>
                        <div className="text-slate-400 mt-0.5">
                          Projected Health: <span className="text-amber-400">{p.projected_health_status}</span>
                        </div>
                      </div>
                    ))}
                    {impactResult.affected_goals.map((g) => (
                      <div key={g.goal_id} className="p-2 bg-slate-900 rounded border border-slate-800">
                        <div className="text-white font-medium">{g.title}</div>
                        <div className="text-slate-400 mt-0.5">
                          Goal Risk: <span className="text-purple-400 font-semibold">{g.risk_level}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 4: DECLARE EXPLICIT MODAL / FORM */}
      {activeTab === "CREATE" && (
        <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl space-y-4 max-w-xl mx-auto">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Plus className="h-5 w-5 text-indigo-400" />
            Declare Explicit Dependency
          </h2>
          <p className="text-xs text-slate-400">
            Define a verified architectural execution constraint between two tasks. This constraint will register in the Knowledge Graph.
          </p>

          <form onSubmit={handleCreateExplicit} className="space-y-4 pt-2">
            <div>
              <label className="text-xs font-semibold text-slate-400 uppercase">Source Task ID (Prerequisite / Blocker)</label>
              <input
                type="text"
                required
                placeholder="UUID or task title..."
                value={createSrcId}
                onChange={(e) => setCreateSrcId(e.target.value)}
                className="w-full mt-1.5 px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-white focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-400 uppercase">Target Task ID (Dependent)</label>
              <input
                type="text"
                required
                placeholder="UUID or task title..."
                value={createDstId}
                onChange={(e) => setCreateDstId(e.target.value)}
                className="w-full mt-1.5 px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-white focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-400 uppercase">Dependency Type</label>
              <select
                value={createType}
                onChange={(e) => setCreateType(e.target.value as TaskDependencyType)}
                className="w-full mt-1.5 px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-white focus:outline-none focus:border-indigo-500"
              >
                <option value="EXPLICIT_DEPENDENCY">Explicit Dependency</option>
                <option value="POTENTIAL_BLOCKER">Hard Execution Blocker</option>
                <option value="REPEATED_WORKFLOW">Sequential Workflow</option>
                <option value="SHARED_PROJECT">Shared Project Constraint</option>
              </select>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-400 uppercase">Architectural Notes</label>
              <textarea
                rows={2}
                placeholder="Rationale for explicit dependency..."
                value={createNotes}
                onChange={(e) => setCreateNotes(e.target.value)}
                className="w-full mt-1.5 px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-white focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setActiveTab("LIST")}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm font-medium transition"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={creating}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition shadow-md"
              >
                {creating ? "Declaring..." : "Create Explicit Dependency"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* DETAIL & EVIDENCE INSPECTION MODAL */}
      {inspectDep && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 max-w-lg w-full space-y-4 text-white shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="text-base font-bold flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-indigo-400" />
                Empirical Evidence & Epistemic Audit
              </h3>
              <button
                onClick={() => setInspectDep(null)}
                className="text-slate-400 hover:text-white transition"
              >
                <XCircle className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-3 text-sm">
              <div>
                <span className="text-xs font-semibold text-slate-400 uppercase">Relationship Type</span>
                <div className="font-bold text-indigo-400 mt-0.5">{inspectDep.dependency_type}</div>
              </div>

              <div>
                <span className="text-xs font-semibold text-slate-400 uppercase">Detection Method</span>
                <div className="text-slate-300 mt-0.5">{inspectDep.detection_method}</div>
              </div>

              <div>
                <span className="text-xs font-semibold text-slate-400 uppercase">Confidence Score</span>
                <div className="text-slate-300 mt-0.5">{(inspectDep.confidence * 100).toFixed(1)}% calibrated certainty</div>
              </div>

              <div>
                <span className="text-xs font-semibold text-slate-400 uppercase">Supporting Observations</span>
                <pre className="mt-1.5 p-3 bg-slate-950 rounded-lg text-xs font-mono text-slate-300 overflow-x-auto border border-slate-800 max-h-48">
                  {JSON.stringify(inspectDep.supporting_observations, null, 2)}
                </pre>
              </div>

              <div>
                <span className="text-xs font-semibold text-slate-400 uppercase">User Review Governance</span>
                <div className="mt-2 flex flex-wrap gap-2">
                  <button
                    onClick={() => handleConfirm(inspectDep.id, "CONFIRM")}
                    className="px-3 py-1.5 bg-emerald-700 hover:bg-emerald-600 text-white rounded-lg text-xs font-medium transition"
                  >
                    Confirm Valid
                  </button>
                  <button
                    onClick={() => handleConfirm(inspectDep.id, "CONVERT_EXPLICIT")}
                    className="px-3 py-1.5 bg-indigo-700 hover:bg-indigo-600 text-white rounded-lg text-xs font-medium transition"
                  >
                    Promote to Explicit Constraint
                  </button>
                  <button
                    onClick={() => handleConfirm(inspectDep.id, "REJECT")}
                    className="px-3 py-1.5 bg-rose-800 hover:bg-rose-700 text-white rounded-lg text-xs font-medium transition"
                  >
                    Reject Spurious
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

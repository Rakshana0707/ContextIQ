"use client";

import React, { useState, useEffect, useMemo } from "react";
import {
  TrendingUp,
  Calendar,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Sparkles,
  BarChart3,
  Layers,
  ArrowRight,
  ShieldAlert,
  HelpCircle,
  Play,
  RotateCcw,
  Sliders,
  Check,
  Zap,
} from "lucide-react";
import { projectForecastApi, goalProjectApi } from "@/lib/api";
import type {
  ForecastScenarioResult,
  ModelBenchmarkResult,
  ProjectForecast,
  ProjectForecastDashboardData,
} from "@/types/project_forecast";
import type { Project } from "@/types/goal_project";

export function ProjectForecastDashboard() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("project-1");
  const [dashboardData, setDashboardData] = useState<ProjectForecastDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [selectedModel, setSelectedModel] = useState<string>("ENSEMBLE_FORECASTER");

  // What-If Scenario State
  const [scenarioPrioritizeOverdue, setScenarioPrioritizeOverdue] = useState(false);
  const [scenarioFocusHours, setScenarioFocusHours] = useState<number>(3.0);
  const [scenarioResolveBlockers, setScenarioResolveBlockers] = useState(false);
  const [scenarioDeadlineExt, setScenarioDeadlineExt] = useState<number>(0);
  const [scenarioResult, setScenarioResult] = useState<ForecastScenarioResult | null>(null);
  const [simulatingScenario, setSimulatingScenario] = useState(false);

  // Benchmarks Modal
  const [benchmarks, setBenchmarks] = useState<ModelBenchmarkResult | null>(null);
  const [showBenchmarkModal, setShowBenchmarkModal] = useState(false);
  const [loadingBenchmark, setLoadingBenchmark] = useState(false);

  useEffect(() => {
    loadInitialData();
  }, []);

  useEffect(() => {
    if (selectedProjectId) {
      loadForecastData(selectedProjectId);
    }
  }, [selectedProjectId]);

  const loadInitialData = async () => {
    setLoading(true);
    try {
      const projList = await goalProjectApi.listProjects();
      setProjects(projList);
      if (projList.length > 0) {
        setSelectedProjectId(projList[0].id);
      } else {
        await loadForecastData("project-1");
      }
    } catch {
      await loadForecastData("project-1");
    } finally {
      setLoading(false);
    }
  };

  const loadForecastData = async (projId: string) => {
    try {
      const data = await projectForecastApi.getProjectForecastDashboard(projId);
      setDashboardData(data);
    } catch (err) {
      console.error("Failed to load forecast data", err);
    }
  };

  const handleGenerateForecast = async () => {
    if (!selectedProjectId) return;
    setGenerating(true);
    try {
      await projectForecastApi.generateProjectForecast(selectedProjectId, selectedModel);
      await loadForecastData(selectedProjectId);
    } catch (err) {
      console.error("Forecast generation failed", err);
    } finally {
      setGenerating(false);
    }
  };

  const handleRunScenario = async () => {
    if (!selectedProjectId) return;
    setSimulatingScenario(true);
    try {
      const res = await projectForecastApi.runScenarioSimulation({
        project_id: selectedProjectId,
        prioritize_overdue_tasks: scenarioPrioritizeOverdue,
        additional_focus_hours_per_week: scenarioFocusHours,
        resolve_blockers: scenarioResolveBlockers,
        deadline_extension_days: scenarioDeadlineExt,
      });
      setScenarioResult(res);
    } catch (err) {
      console.error("Scenario simulation failed", err);
    } finally {
      setSimulatingScenario(false);
    }
  };

  const handleOpenBenchmarks = async () => {
    setShowBenchmarkModal(true);
    if (!benchmarks) {
      setLoadingBenchmark(true);
      try {
        const b = await projectForecastApi.getModelBenchmarks();
        setBenchmarks(b);
      } catch (err) {
        console.error("Failed to load benchmarks", err);
      } finally {
        setLoadingBenchmark(false);
      }
    }
  };

  const forecast = dashboardData?.forecast;

  const formatDate = (isoStr?: string | null) => {
    if (!isoStr) return "N/A";
    return new Date(isoStr).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  return (
    <div className="space-y-6">
      {/* Top Banner & Project Selector */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 bg-slate-900 border border-slate-800 rounded-xl text-white">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <TrendingUp className="h-6 w-6 text-indigo-400" />
            <h1 className="text-2xl font-bold tracking-tight">Intelligent Project Progress Forecasting</h1>
          </div>
          <p className="text-slate-400 text-sm max-w-2xl">
            Probabilistic timeline estimation using historical task completion velocity, dependency blockers, and calibrated uncertainty bounds.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex flex-wrap items-center gap-3">
          {projects.length > 0 && (
            <select
              value={selectedProjectId}
              onChange={(e) => setSelectedProjectId(e.target.value)}
              className="px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title}
                </option>
              ))}
            </select>
          )}

          <select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            className="px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
          >
            <option value="ENSEMBLE_FORECASTER">Ensemble Forecaster (Recommended)</option>
            <option value="SURVIVAL_HAZARD">Weibull Survival Hazard</option>
            <option value="HISTORICAL_RATE">Empirical Completion Rate</option>
            <option value="RULE_BASED_VELOCITY">Linear Velocity Extrapolation</option>
          </select>

          <button
            onClick={handleGenerateForecast}
            disabled={generating}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition shadow-md"
          >
            <Sparkles className={`h-4 w-4 ${generating ? "animate-spin" : ""}`} />
            {generating ? "Forecasting..." : "Recalculate Forecast"}
          </button>

          <button
            onClick={handleOpenBenchmarks}
            className="flex items-center gap-1.5 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm font-medium border border-slate-700 transition"
          >
            <BarChart3 className="h-4 w-4" />
            Model Benchmarks
          </button>
        </div>
      </div>

      {/* Main KPI Statistics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* On-Time Probability */}
        <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">On-Time Probability</span>
            <CheckCircle2
              className={`h-5 w-5 ${
                (forecast?.on_time_probability ?? 0) >= 0.75
                  ? "text-emerald-400"
                  : (forecast?.on_time_probability ?? 0) >= 0.5
                  ? "text-amber-400"
                  : "text-rose-400"
              }`}
            />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span
              className={`text-3xl font-extrabold ${
                (forecast?.on_time_probability ?? 0) >= 0.75
                  ? "text-emerald-300"
                  : (forecast?.on_time_probability ?? 0) >= 0.5
                  ? "text-amber-300"
                  : "text-rose-300"
              }`}
            >
              {Math.round((forecast?.on_time_probability ?? 0.5) * 100)}%
            </span>
            <span className="text-xs font-semibold px-2 py-0.5 rounded bg-slate-800 text-slate-300">
              {forecast?.delay_risk_tier ?? "MODERATE"} RISK
            </span>
          </div>
          <div className="text-xs text-slate-400 mt-2">
            Target: {formatDate(forecast?.target_completion_date)}
          </div>
        </div>

        {/* Expected Completion Date */}
        <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-indigo-400 uppercase tracking-wider">Projected Delivery (P50)</span>
            <Calendar className="h-5 w-5 text-indigo-400" />
          </div>
          <div className="mt-3 text-2xl font-bold text-white">
            {formatDate(forecast?.estimated_completion_date)}
          </div>
          <div className="text-xs text-slate-400 mt-2">
            Remaining work: <span className="text-white font-medium">{forecast?.expected_remaining_workload_hours} hrs</span> ({forecast?.remaining_tasks_count} tasks)
          </div>
        </div>

        {/* Uncertainty Range */}
        <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-purple-400 uppercase tracking-wider">Uncertainty Bounds</span>
            <Clock className="h-5 w-5 text-purple-400" />
          </div>
          <div className="mt-3 text-lg font-bold text-white">
            ±{forecast?.uncertainty_spread_days} days
          </div>
          <div className="text-xs text-slate-400 mt-2 flex justify-between">
            <span>P10: {formatDate(forecast?.p10_completion_date)}</span>
            <span>P90: {formatDate(forecast?.p90_completion_date)}</span>
          </div>
        </div>

        {/* Velocity & Sufficiency */}
        <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Throughput Velocity</span>
            <Zap className="h-5 w-5 text-amber-400" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-white">
              {forecast?.current_velocity_tasks_per_week}
            </span>
            <span className="text-xs text-slate-400">/ {forecast?.required_velocity_tasks_per_week} tasks/wk req</span>
          </div>
          <div className="text-xs mt-2">
            <span
              className={`px-2 py-0.5 rounded font-medium text-[11px] ${
                dashboardData?.data_sufficiency === "DATA_SUFFICIENT"
                  ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                  : dashboardData?.data_sufficiency === "LIMITED_HISTORY_FALLBACK"
                  ? "bg-amber-950 text-amber-300 border border-amber-800"
                  : "bg-slate-800 text-slate-400"
              }`}
            >
              {dashboardData?.data_sufficiency?.replace(/_/g, " ")}
            </span>
          </div>
        </div>
      </div>

      {/* Probabilistic Timeline Runway Visualizer */}
      <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-white flex items-center gap-2">
            <Calendar className="h-5 w-5 text-indigo-400" />
            Timeline Forecast Runway (P10 - P50 - P90)
          </h2>
          <span className="text-xs text-slate-400 font-mono">Model: {forecast?.model_name}</span>
        </div>

        {/* Horizontal Track Bar */}
        <div className="bg-slate-950 p-6 rounded-lg border border-slate-800 space-y-6">
          <div className="relative pt-6 pb-2">
            {/* Base line */}
            <div className="h-2 bg-slate-800 rounded-full w-full"></div>

            {/* P10 to P90 Confidence Band */}
            <div
              className="absolute top-6 h-2 bg-indigo-500/40 rounded-full"
              style={{ left: "30%", width: "45%" }}
            ></div>

            {/* P50 Marker */}
            <div className="absolute top-4" style={{ left: "55%" }}>
              <div className="h-6 w-1 bg-indigo-400 mx-auto rounded"></div>
              <div className="text-[11px] font-bold text-indigo-300 mt-1 whitespace-nowrap text-center">
                P50 (Expected)
                <br />
                <span className="font-normal text-slate-400">{formatDate(forecast?.estimated_completion_date)}</span>
              </div>
            </div>

            {/* P10 Optimistic Marker */}
            <div className="absolute top-5" style={{ left: "30%" }}>
              <div className="h-4 w-1 bg-emerald-400 mx-auto rounded"></div>
              <div className="text-[10px] text-emerald-300 mt-2 whitespace-nowrap text-center">
                P10 (Optimistic)
                <br />
                <span className="text-slate-500">{formatDate(forecast?.p10_completion_date)}</span>
              </div>
            </div>

            {/* P90 Conservative Marker */}
            <div className="absolute top-5" style={{ left: "75%" }}>
              <div className="h-4 w-1 bg-purple-400 mx-auto rounded"></div>
              <div className="text-[10px] text-purple-300 mt-2 whitespace-nowrap text-center">
                P90 (Conservative)
                <br />
                <span className="text-slate-500">{formatDate(forecast?.p90_completion_date)}</span>
              </div>
            </div>

            {/* Target Deadline Marker */}
            <div className="absolute top-2" style={{ left: "68%" }}>
              <div className="h-8 w-1 bg-amber-400 mx-auto rounded dashed"></div>
              <div className="text-[11px] font-bold text-amber-300 mt-1 whitespace-nowrap text-center">
                Target Deadline
                <br />
                <span className="text-slate-400">{formatDate(forecast?.target_completion_date)}</span>
              </div>
            </div>
          </div>
          <div className="h-8"></div>
        </div>
      </div>

      {/* Major Delay Contributors & Milestone Predictions Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Major Delay Contributors */}
        <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl space-y-4">
          <h2 className="text-base font-semibold text-white flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-400" />
            Top Delay Contributors & Risk Attribution
          </h2>

          {dashboardData?.major_delay_contributors.length === 0 ? (
            <div className="text-xs text-slate-500 py-6 text-center">
              No significant delay drivers detected. Execution is currently on track.
            </div>
          ) : (
            <div className="space-y-3">
              {dashboardData?.major_delay_contributors.map((c, i) => (
                <div key={i} className="p-4 bg-slate-950 rounded-lg border border-slate-800 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-amber-400 font-mono">
                      {c.factor.replace(/_/g, " ")}
                    </span>
                    <span className="text-xs text-slate-400 font-semibold">
                      Impact: {(c.impact_score * 100).toFixed(0)}%
                    </span>
                  </div>
                  <p className="text-xs text-slate-300">{c.description}</p>
                  <div className="text-xs text-slate-400 pt-1 border-t border-slate-800/80">
                    <span className="font-semibold text-indigo-300">Recommendation:</span>{" "}
                    {c.remediation_suggestion}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Milestone Probabilistic Predictions */}
        <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl space-y-4">
          <h2 className="text-base font-semibold text-white flex items-center gap-2">
            <Layers className="h-5 w-5 text-indigo-400" />
            Milestone Completion Projections
          </h2>

          {dashboardData?.milestone_predictions.length === 0 ? (
            <div className="text-xs text-slate-500 py-6 text-center">
              No milestones defined for this project.
            </div>
          ) : (
            <div className="space-y-2.5">
              {dashboardData?.milestone_predictions.map((m) => (
                <div
                  key={m.milestone_id}
                  className="p-3 bg-slate-950 rounded-lg border border-slate-800 flex items-center justify-between text-xs"
                >
                  <div className="space-y-1">
                    <div className="font-semibold text-white flex items-center gap-2">
                      {m.is_completed && <Check className="h-3.5 w-3.5 text-emerald-400" />}
                      {m.title}
                    </div>
                    <div className="text-slate-400 flex items-center gap-3">
                      <span>Due: {formatDate(m.due_date)}</span>
                      <span>Projected: {formatDate(m.projected_completion_date)}</span>
                    </div>
                  </div>

                  <div className="text-right">
                    <div
                      className={`font-bold ${
                        m.on_time_probability >= 0.75
                          ? "text-emerald-400"
                          : m.on_time_probability >= 0.50
                          ? "text-amber-400"
                          : "text-rose-400"
                      }`}
                    >
                      {Math.round(m.on_time_probability * 100)}% On-Time
                    </div>
                    <span className="text-[10px] text-slate-500 uppercase">{m.risk_tier} RISK</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Interactive What-If Counterfactual Scenario Simulator */}
      <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-white flex items-center gap-2">
              <Sliders className="h-5 w-5 text-indigo-400" />
              What-If Counterfactual Scenario Simulator
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Simulate how operational interventions (adding focus hours, resolving blockers, prioritizing overdue work) lift on-time completion probability.
            </p>
          </div>
          <button
            onClick={handleRunScenario}
            disabled={simulatingScenario}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition shadow-md"
          >
            <Play className={`h-4 w-4 ${simulatingScenario ? "animate-spin" : ""}`} />
            {simulatingScenario ? "Simulating..." : "Run What-If Simulation"}
          </button>
        </div>

        {/* Simulator Controls */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 p-4 bg-slate-950 rounded-lg border border-slate-800">
          <label className="flex items-center gap-2.5 text-xs text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={scenarioPrioritizeOverdue}
              onChange={(e) => setScenarioPrioritizeOverdue(e.target.checked)}
              className="rounded bg-slate-800 border-slate-700 text-indigo-500 focus:ring-0"
            />
            Prioritize Overdue Tasks
          </label>

          <label className="flex items-center gap-2.5 text-xs text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={scenarioResolveBlockers}
              onChange={(e) => setScenarioResolveBlockers(e.target.checked)}
              className="rounded bg-slate-800 border-slate-700 text-indigo-500 focus:ring-0"
            />
            Resolve Active Blockers
          </label>

          <div className="space-y-1">
            <div className="flex justify-between text-xs text-slate-400">
              <span>+ Focus Hours/Wk:</span>
              <span className="font-bold text-white">{scenarioFocusHours}h</span>
            </div>
            <input
              type="range"
              min="0"
              max="15"
              step="1"
              value={scenarioFocusHours}
              onChange={(e) => setScenarioFocusHours(parseFloat(e.target.value))}
              className="w-full accent-indigo-500 h-1.5 bg-slate-800 rounded-lg"
            />
          </div>

          <div className="space-y-1">
            <div className="flex justify-between text-xs text-slate-400">
              <span>Extend Deadline:</span>
              <span className="font-bold text-white">{scenarioDeadlineExt}d</span>
            </div>
            <input
              type="range"
              min="0"
              max="30"
              step="3"
              value={scenarioDeadlineExt}
              onChange={(e) => setScenarioDeadlineExt(parseFloat(e.target.value))}
              className="w-full accent-indigo-500 h-1.5 bg-slate-800 rounded-lg"
            />
          </div>
        </div>

        {/* Counterfactual Results Comparison */}
        {scenarioResult && (
          <div className="p-5 bg-indigo-950/20 border border-indigo-900/50 rounded-xl space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-indigo-900/40">
              <div>
                <span className="text-xs uppercase text-indigo-400 font-semibold tracking-wider">Simulation Outcome</span>
                <div className="text-base font-bold text-white mt-0.5">
                  Lift: +{Math.round(scenarioResult.probability_lift * 100)}% On-Time Probability
                </div>
              </div>

              <div className="flex items-center gap-3">
                <span className="px-3 py-1 rounded-full text-xs font-bold bg-emerald-950 text-emerald-300 border border-emerald-800">
                  {scenarioResult.days_saved.toFixed(1)} Days Saved
                </span>
                <span className="px-3 py-1 rounded-full text-xs font-bold bg-slate-800 text-slate-300">
                  Risk: {scenarioResult.baseline_risk_tier} → {scenarioResult.scenario_risk_tier}
                </span>
              </div>
            </div>

            <p className="text-sm text-slate-200">{scenarioResult.scenario_summary}</p>

            {scenarioResult.recommended_interventions.length > 0 && (
              <div className="space-y-1.5 pt-2">
                <span className="text-xs font-semibold text-slate-400 uppercase">Recommended Interventions:</span>
                <ul className="list-disc list-inside text-xs text-slate-300 space-y-1">
                  {scenarioResult.recommended_interventions.map((rec, idx) => (
                    <li key={idx}>{rec}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Model Benchmark Evaluation Modal */}
      {showBenchmarkModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 max-w-2xl w-full space-y-4 text-white shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="text-base font-bold flex items-center gap-2">
                <BarChart3 className="h-5 w-5 text-indigo-400" />
                Model Benchmark & Evaluation Report
              </h3>
              <button
                onClick={() => setShowBenchmarkModal(false)}
                className="text-slate-400 hover:text-white transition"
              >
                ✕
              </button>
            </div>

            {loadingBenchmark ? (
              <div className="py-8 text-center text-slate-400">Loading benchmark metrics...</div>
            ) : benchmarks ? (
              <div className="space-y-4 text-xs">
                <p className="text-slate-300 bg-slate-950 p-3 rounded-lg border border-slate-800">
                  {benchmarks.benchmark_summary}
                </p>

                {/* Model Error Table */}
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-slate-800 text-slate-400 font-semibold">
                        <th className="py-2">Model</th>
                        <th className="py-2">MAE (Days)</th>
                        <th className="py-2">RMSE (Days)</th>
                        <th className="py-2">Brier Score</th>
                        <th className="py-2">P10-P90 Coverage</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {benchmarks.models_evaluated.map((m) => (
                        <tr key={m} className={m === benchmarks.recommended_model ? "text-indigo-300 font-bold" : "text-slate-300"}>
                          <td className="py-2 font-mono">{m.replace(/_/g, " ")}</td>
                          <td className="py-2">{benchmarks.mae_days_by_model[m]}d</td>
                          <td className="py-2">{benchmarks.rmse_days_by_model[m]}d</td>
                          <td className="py-2">{benchmarks.brier_score_by_model[m]}</td>
                          <td className="py-2">{Math.round((benchmarks.interval_coverage_p10_p90[m] || 0) * 100)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Horizon Performance */}
                <div className="pt-2">
                  <span className="font-semibold text-slate-400 uppercase">Horizon Analysis (Forecast Window)</span>
                  <div className="grid grid-cols-3 gap-3 mt-1.5">
                    {Object.entries(benchmarks.horizon_performance).map(([horizon, metrics]) => (
                      <div key={horizon} className="p-2.5 bg-slate-950 rounded border border-slate-800 text-center">
                        <div className="font-bold text-white">{horizon.replace("_", " ")}</div>
                        <div className="text-slate-400 mt-1">MAE: {metrics.MAE_days}d</div>
                        <div className="text-slate-400">Coverage: {Math.round(metrics.Coverage * 100)}%</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}

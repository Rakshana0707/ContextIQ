"use client";

import React, { useState, useEffect } from "react";
import {
  Search,
  TrendingUp,
  BrainCircuit,
  BarChart2,
  PieChart,
  LineChart,
  Table as TableIcon,
  Clock,
  ShieldCheck,
  Bookmark,
  BookmarkPlus,
  Download,
  AlertTriangle,
  HelpCircle,
  Sparkles,
  ChevronRight,
  Trash2,
  RefreshCw,
  ExternalLink,
  Target,
  ArrowUpRight,
} from "lucide-react";
import { analyticsWorkspaceApi } from "@/lib/api";
import type {
  AnalyticsQueryResponse,
  AnalyticsSuggestionItem,
  SavedAnalyticsQueryRead,
  DecisionRecommendation,
} from "@/types/analytics_workspace";

const CANONICAL_QUESTIONS = [
  "Which project consumed most of my productive time?",
  "Which goal has the greatest number of blocked tasks?",
  "Which project has the highest delay risk?",
  "What types of tasks do I postpone most often?",
  "How has my recovery duration changed?",
  "Which interventions have the strongest historical evidence?",
  "Which upcoming deadlines conflict with my current priorities?",
];

export function NaturalLanguageAnalyticsWorkspace() {
  const [queryInput, setQueryInput] = useState("");
  const [lookbackDays, setLookbackDays] = useState(30);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analyticsResult, setAnalyticsResult] = useState<AnalyticsQueryResponse | null>(null);
  const [suggestions, setSuggestions] = useState<AnalyticsSuggestionItem[]>([]);
  const [savedQueries, setSavedQueries] = useState<SavedAnalyticsQueryRead[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [saveTitle, setSaveTitle] = useState("");
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [showPlanDetails, setShowPlanDetails] = useState(false);

  useEffect(() => {
    loadInitialData();
  }, []);

  const loadInitialData = async () => {
    try {
      const [sugRes, savedRes] = await Promise.all([
        analyticsWorkspaceApi.getSuggestions(),
        analyticsWorkspaceApi.listSavedQueries(),
      ]);
      setSuggestions(sugRes);
      setSavedQueries(savedRes.queries);
    } catch {
      // offline / fallback
    }
  };

  const handleExecuteQuery = async (queryToRun?: string) => {
    const q = (queryToRun || queryInput).trim();
    if (!q) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await analyticsWorkspaceApi.executeQuery({
        query: q,
        lookback_days: lookbackDays,
      });
      setAnalyticsResult(res);
      setQueryInput(q);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to execute query";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveQuery = async () => {
    if (!saveTitle.trim() || !analyticsResult) return;
    setIsSaving(true);
    try {
      await analyticsWorkspaceApi.saveQuery({
        title: saveTitle.trim(),
        query_text: analyticsResult.query,
        target_domain: analyticsResult.plan.target_domain,
        plan_snapshot: {
          lookback_days: analyticsResult.time_range?.lookback_days || lookbackDays,
        },
      });
      setShowSaveDialog(false);
      setSaveTitle("");
      const updated = await analyticsWorkspaceApi.listSavedQueries();
      setSavedQueries(updated.queries);
    } catch (err: unknown) {
      alert("Failed to save query");
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteSavedQuery = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await analyticsWorkspaceApi.deleteSavedQuery(id);
      setSavedQueries((prev) => prev.filter((item) => item.id !== id));
    } catch {
      alert("Failed to delete saved query");
    }
  };

  const handleExportCSV = () => {
    if (!analyticsResult?.supporting_records?.length) return;
    const records = analyticsResult.supporting_records;
    const headers = Object.keys(records[0]);
    const csvContent = [
      headers.join(","),
      ...records.map((r) =>
        headers.map((h) => JSON.stringify(r[h] ?? "")).join(",")
      ),
    ].join("\n");

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `analytics_export_${Date.now()}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleExportJSON = () => {
    if (!analyticsResult) return;
    const blob = new Blob([JSON.stringify(analyticsResult, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `analytics_result_${Date.now()}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-border">
        <div>
          <div className="flex items-center gap-2">
            <TrendingUp className="h-6 w-6 text-primary" />
            <h1 className="text-2xl font-bold tracking-tight">Analytics Workspace</h1>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Natural-language productivity analytics, cross-project synthesis & decision intelligence.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-3 py-1 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 rounded-md text-xs font-medium border border-emerald-500/20">
            <ShieldCheck className="h-4 w-4" />
            <span>AST Query Safety (No Raw SQL)</span>
          </div>
        </div>
      </div>

      {/* Main Grid: Query Interface + Saved Queries */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Left Column: Query Console (3 cols) */}
        <div className="lg:col-span-3 space-y-6">
          {/* Query Input Card */}
          <div className="p-4 sm:p-5 rounded-xl border border-border bg-card shadow-sm space-y-4">
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Ask any cross-project productivity or behavioral question..."
                  value={queryInput}
                  onChange={(e) => setQueryInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleExecuteQuery()}
                  className="w-full pl-9 pr-4 py-2 text-sm bg-background border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary"
                />
              </div>
              <div className="flex items-center gap-2">
                <select
                  value={lookbackDays}
                  onChange={(e) => setLookbackDays(Number(e.target.value))}
                  className="px-3 py-2 text-sm bg-background border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/40 text-foreground"
                >
                  <option value={7}>Last 7 Days</option>
                  <option value={14}>Last 14 Days</option>
                  <option value={30}>Last 30 Days</option>
                  <option value={90}>Last 90 Days</option>
                  <option value={180}>Last 6 Months</option>
                  <option value={365}>Last 1 Year</option>
                </select>
                <button
                  onClick={() => handleExecuteQuery()}
                  disabled={isLoading || !queryInput.trim()}
                  className="px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50 flex items-center gap-1.5 shrink-0"
                >
                  {isLoading ? (
                    <RefreshCw className="h-4 w-4 animate-spin" />
                  ) : (
                    <Sparkles className="h-4 w-4" />
                  )}
                  <span>Analyze</span>
                </button>
              </div>
            </div>

            {/* Canonical Suggestion Chips */}
            <div className="space-y-2 pt-1 border-t border-border/50">
              <div className="flex items-center justify-between text-xs text-muted-foreground font-medium">
                <span>Canonical Cross-Project Inquiries</span>
                <span>Click to analyze</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {CANONICAL_QUESTIONS.map((q, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      setQueryInput(q);
                      handleExecuteQuery(q);
                    }}
                    className="text-xs px-2.5 py-1 rounded-md bg-secondary/60 hover:bg-secondary text-secondary-foreground border border-border/60 transition-colors text-left"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Error Banner */}
          {error && (
            <div className="p-4 rounded-xl border border-destructive/20 bg-destructive/10 text-destructive flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-sm">Query Execution Blocked</p>
                <p className="text-xs mt-0.5">{error}</p>
              </div>
            </div>
          )}

          {/* Results Workspace */}
          {analyticsResult && (
            <div className="space-y-6">
              {/* Summary Answer Card */}
              <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border/60 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="px-2.5 py-0.5 text-xs font-semibold rounded bg-primary/10 text-primary uppercase tracking-wide">
                      {analyticsResult.plan.target_domain}
                    </span>
                    <span className="text-xs text-muted-foreground flex items-center gap-1">
                      <Clock className="h-3.5 w-3.5" />
                      {analyticsResult.time_range?.label || `${lookbackDays} Days`}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setShowSaveDialog(true)}
                      className="px-2.5 py-1 text-xs border border-border rounded-md hover:bg-secondary flex items-center gap-1 text-muted-foreground hover:text-foreground transition-colors"
                    >
                      <BookmarkPlus className="h-3.5 w-3.5" />
                      <span>Save Query</span>
                    </button>
                    <button
                      onClick={handleExportCSV}
                      disabled={!analyticsResult.supporting_records?.length}
                      className="px-2.5 py-1 text-xs border border-border rounded-md hover:bg-secondary flex items-center gap-1 text-muted-foreground hover:text-foreground transition-colors disabled:opacity-40"
                    >
                      <Download className="h-3.5 w-3.5" />
                      <span>CSV</span>
                    </button>
                    <button
                      onClick={handleExportJSON}
                      className="px-2.5 py-1 text-xs border border-border rounded-md hover:bg-secondary flex items-center gap-1 text-muted-foreground hover:text-foreground transition-colors"
                    >
                      <Download className="h-3.5 w-3.5" />
                      <span>JSON</span>
                    </button>
                  </div>
                </div>

                <div className="text-base text-foreground font-medium leading-relaxed">
                  {analyticsResult.summary_answer}
                </div>

                {/* Query Plan Toggle */}
                <div className="border border-border/60 rounded-lg p-3 bg-secondary/20">
                  <button
                    onClick={() => setShowPlanDetails(!showPlanDetails)}
                    className="flex items-center justify-between w-full text-xs font-medium text-muted-foreground hover:text-foreground"
                  >
                    <span className="flex items-center gap-1.5">
                      <BrainCircuit className="h-3.5 w-3.5 text-primary" />
                      <span>Structured Query Plan (AST Execution Verified)</span>
                    </span>
                    <span>{showPlanDetails ? "Hide Plan" : "View Plan"}</span>
                  </button>
                  {showPlanDetails && (
                    <div className="mt-2.5 pt-2 border-t border-border/40 grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                      <div>
                        <span className="text-muted-foreground block">Entity:</span>
                        <span className="font-mono">{analyticsResult.plan.entity}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground block">Aggregation:</span>
                        <span className="font-mono">{analyticsResult.plan.aggregation}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground block">Sort:</span>
                        <span className="font-mono">{analyticsResult.plan.sort_order}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground block">AST Valid:</span>
                        <span className="text-emerald-500 font-medium">True (User-Scoped)</span>
                      </div>
                      <div className="col-span-2 sm:col-span-4 mt-1 text-[11px] text-muted-foreground font-mono">
                        Rationale: {analyticsResult.plan.planning_rationale}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Visual Analytics Spec Rendering */}
              {analyticsResult.visualization && (
                <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-4">
                  <div className="flex items-center justify-between border-b border-border/60 pb-3">
                    <div className="flex items-center gap-2">
                      {analyticsResult.visualization.chart_type === "BAR" && (
                        <BarChart2 className="h-5 w-5 text-primary" />
                      )}
                      {analyticsResult.visualization.chart_type === "PIE" && (
                        <PieChart className="h-5 w-5 text-primary" />
                      )}
                      {analyticsResult.visualization.chart_type === "LINE" && (
                        <LineChart className="h-5 w-5 text-primary" />
                      )}
                      {analyticsResult.visualization.chart_type === "TABLE" && (
                        <TableIcon className="h-5 w-5 text-primary" />
                      )}
                      <h3 className="font-semibold text-sm">
                        {analyticsResult.visualization.title}
                      </h3>
                    </div>
                    <span className="text-xs text-muted-foreground">
                      Type: {analyticsResult.visualization.chart_type}
                    </span>
                  </div>

                  {/* Render Visual Chart */}
                  <div className="py-2">
                    {renderVisualizationChart(analyticsResult.visualization)}
                  </div>

                  {/* Calculation Details */}
                  {analyticsResult.calculation_details &&
                    Object.keys(analyticsResult.calculation_details).length > 0 && (
                      <div className="pt-3 border-t border-border/60">
                        <div className="text-xs font-medium text-muted-foreground mb-2">
                          Calculation Details
                        </div>
                        <div className="flex flex-wrap gap-3">
                          {Object.entries(analyticsResult.calculation_details).map(
                            ([key, val]) => (
                              <div
                                key={key}
                                className="px-3 py-1.5 rounded-lg bg-secondary/40 border border-border/50 text-xs"
                              >
                                <span className="text-muted-foreground capitalize mr-1.5">
                                  {key.replace(/_/g, " ")}:
                                </span>
                                <span className="font-semibold text-foreground">
                                  {typeof val === "number"
                                    ? Number.isInteger(val)
                                      ? val
                                      : val.toFixed(2)
                                    : String(val)}
                                </span>
                              </div>
                            )
                          )}
                        </div>
                      </div>
                    )}
                </div>
              )}

              {/* Decision Support Recommendations */}
              {analyticsResult.suggested_decisions &&
                analyticsResult.suggested_decisions.length > 0 && (
                  <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-4">
                    <div className="flex items-center gap-2 border-b border-border/60 pb-3">
                      <Target className="h-5 w-5 text-primary" />
                      <h3 className="font-semibold text-sm">
                        Cross-Project Decision Recommendations
                      </h3>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {analyticsResult.suggested_decisions.map(
                        (rec: DecisionRecommendation, idx: number) => (
                          <div
                            key={idx}
                            className="p-3.5 rounded-lg border border-border bg-background/50 hover:bg-background transition-colors space-y-2 flex flex-col justify-between"
                          >
                            <div className="space-y-1.5">
                              <div className="flex items-center justify-between">
                                <span className="font-semibold text-sm text-foreground">
                                  {rec.target_title}
                                </span>
                                <span className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary font-medium">
                                  Rank #{rec.rank} (Score: {(rec.score * 100).toFixed(0)}%)
                                </span>
                              </div>
                              <p className="text-xs text-muted-foreground">{rec.rationale}</p>
                            </div>
                            <div className="pt-2 border-t border-border/40 text-xs text-emerald-600 dark:text-emerald-400 font-medium flex items-center gap-1.5">
                              <ArrowUpRight className="h-3.5 w-3.5 shrink-0" />
                              <span>{rec.suggested_action}</span>
                            </div>
                          </div>
                        )
                      )}
                    </div>
                  </div>
                )}

              {/* Supporting Records Table */}
              {analyticsResult.supporting_records &&
                analyticsResult.supporting_records.length > 0 && (
                  <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-4">
                    <div className="flex items-center justify-between border-b border-border/60 pb-3">
                      <h3 className="font-semibold text-sm">Supporting Records Evidence</h3>
                      <span className="text-xs text-muted-foreground">
                        {analyticsResult.supporting_records.length} records retrieved
                      </span>
                    </div>
                    <div className="overflow-x-auto max-h-72">
                      <table className="w-full text-xs text-left">
                        <thead className="bg-secondary/40 text-muted-foreground uppercase sticky top-0">
                          <tr>
                            {Object.keys(analyticsResult.supporting_records[0]).map((h) => (
                              <th key={h} className="px-3 py-2 font-medium">
                                {h.replace(/_/g, " ")}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border/40">
                          {analyticsResult.supporting_records.map((row, i) => (
                            <tr key={i} className="hover:bg-secondary/20 transition-colors">
                              {Object.keys(analyticsResult.supporting_records[0]).map((h) => (
                                <td key={h} className="px-3 py-2 font-mono text-foreground">
                                  {formatTableCell(row[h])}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

              {/* Limitations & Epistemic Disclaimer */}
              <div className="space-y-3">
                {analyticsResult.limitations && analyticsResult.limitations.length > 0 && (
                  <div className="p-3.5 rounded-lg border border-border/60 bg-secondary/20 text-xs space-y-1">
                    <div className="font-medium text-foreground flex items-center gap-1.5">
                      <HelpCircle className="h-3.5 w-3.5 text-muted-foreground" />
                      <span>Analytical Limitations & Data Bounds:</span>
                    </div>
                    <ul className="list-disc pl-5 text-muted-foreground space-y-0.5">
                      {analyticsResult.limitations.map((lim, i) => (
                        <li key={i}>{lim}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="p-3 rounded-lg border border-border/40 bg-muted/20 text-[11px] text-muted-foreground flex items-start gap-2">
                  <ShieldCheck className="h-4 w-4 shrink-0 text-primary mt-0.5" />
                  <span>
                    {analyticsResult.epistemic_disclaimer ||
                      "ContextIQ natural-language analytics are computed deterministically from verified user records. Observational correlations do not constitute singular causal proof."}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Saved Queries & Domain Catalog (1 col) */}
        <div className="space-y-6">
          {/* Saved Queries */}
          <div className="p-4 rounded-xl border border-border bg-card shadow-sm space-y-3">
            <div className="flex items-center justify-between border-b border-border/60 pb-2">
              <div className="flex items-center gap-1.5 text-sm font-semibold">
                <Bookmark className="h-4 w-4 text-primary" />
                <span>Saved Queries</span>
              </div>
              <span className="text-xs text-muted-foreground">{savedQueries.length}</span>
            </div>

            {savedQueries.length === 0 ? (
              <p className="text-xs text-muted-foreground py-2 text-center">
                No saved queries yet. Run any query and click &quot;Save Query&quot; to bookmark.
              </p>
            ) : (
              <div className="space-y-2 max-h-80 overflow-y-auto">
                {savedQueries.map((sq) => (
                  <div
                    key={sq.id}
                    onClick={() => {
                      setQueryInput(sq.query_text);
                      const days = sq.plan_snapshot?.lookback_days || 30;
                      setLookbackDays(days);
                      handleExecuteQuery(sq.query_text);
                    }}
                    className="p-2.5 rounded-lg border border-border bg-background hover:bg-secondary/40 cursor-pointer transition-colors space-y-1 text-xs group"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-foreground group-hover:text-primary transition-colors">
                        {sq.title}
                      </span>
                      <button
                        onClick={(e) => handleDeleteSavedQuery(sq.id, e)}
                        className="opacity-0 group-hover:opacity-100 hover:text-destructive transition-opacity"
                        title="Delete saved query"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    <p className="text-muted-foreground text-[11px] truncate">
                      {sq.query_text}
                    </p>
                    <div className="flex items-center justify-between text-[10px] text-muted-foreground pt-1">
                      <span>{sq.target_domain}</span>
                      <span>{sq.plan_snapshot?.lookback_days || 30}d</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Domain Intelligence Catalog */}
          <div className="p-4 rounded-xl border border-border bg-card shadow-sm space-y-3">
            <div className="flex items-center gap-1.5 text-sm font-semibold border-b border-border/60 pb-2">
              <BrainCircuit className="h-4 w-4 text-primary" />
              <span>Available Domains</span>
            </div>
            <div className="space-y-2 text-xs">
              <div className="p-2 rounded bg-secondary/30">
                <div className="font-medium text-foreground">Time Allocation</div>
                <div className="text-[11px] text-muted-foreground">
                  Task checkpoints, duration, focus hours by project.
                </div>
              </div>
              <div className="p-2 rounded bg-secondary/30">
                <div className="font-medium text-foreground">Blocker Intelligence</div>
                <div className="text-[11px] text-muted-foreground">
                  Task dependencies, blocked milestones, goal risks.
                </div>
              </div>
              <div className="p-2 rounded bg-secondary/30">
                <div className="font-medium text-foreground">Forecast Delay Risk</div>
                <div className="text-[11px] text-muted-foreground">
                  Predictive progress models & milestone delay probabilities.
                </div>
              </div>
              <div className="p-2 rounded bg-secondary/30">
                <div className="font-medium text-foreground">Task Postponements</div>
                <div className="text-[11px] text-muted-foreground">
                  Behavioral events, postponed tasks, priority patterns.
                </div>
              </div>
              <div className="p-2 rounded bg-secondary/30">
                <div className="font-medium text-foreground">Recovery Durations</div>
                <div className="text-[11px] text-muted-foreground">
                  Post-interruption lag trends and efficiency scoring.
                </div>
              </div>
              <div className="p-2 rounded bg-secondary/30">
                <div className="font-medium text-foreground">Intervention Evidence</div>
                <div className="text-[11px] text-muted-foreground">
                  Causal acceptance, feedback rates, recommendation scores.
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Save Query Modal */}
      {showSaveDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-xl border border-border bg-card p-5 shadow-lg space-y-4">
            <h3 className="text-base font-semibold text-foreground">Save Query Bookmark</h3>
            <p className="text-xs text-muted-foreground">
              Save this natural-language inquiry to your personal dashboard for one-click re-runs.
            </p>
            <div className="space-y-2">
              <label className="text-xs font-medium text-foreground">Bookmark Title</label>
              <input
                type="text"
                placeholder="e.g. Weekly Delay Risk Review"
                value={saveTitle}
                onChange={(e) => setSaveTitle(e.target.value)}
                className="w-full px-3 py-2 text-sm bg-background border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/40"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowSaveDialog(false)}
                className="px-3 py-1.5 text-xs border border-border rounded-lg hover:bg-secondary"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveQuery}
                disabled={isSaving || !saveTitle.trim()}
                className="px-3 py-1.5 text-xs bg-primary text-primary-foreground font-medium rounded-lg hover:bg-primary/90 disabled:opacity-50"
              >
                {isSaving ? "Saving..." : "Save Bookmark"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function formatTableCell(val: unknown): string {
  if (val === null || val === undefined) return "-";
  if (typeof val === "boolean") return val ? "Yes" : "No";
  if (typeof val === "number") {
    return Number.isInteger(val) ? String(val) : val.toFixed(2);
  }
  return String(val);
}

function renderVisualizationChart(spec: AnalyticsQueryResponse["visualization"]) {
  if (!spec || !spec.series || spec.series.length === 0) {
    return (
      <div className="p-4 text-center text-xs text-muted-foreground">
        No chart data available for this query.
      </div>
    );
  }

  const { chart_type, series } = spec;

  if (chart_type === "BAR") {
    const maxVal = Math.max(...series.map((d) => d.value || 0), 1);
    return (
      <div className="space-y-2.5">
        {series.map((d, i) => {
          const pct = Math.min(100, Math.max(5, (d.value / maxVal) * 100));
          return (
            <div key={i} className="space-y-1 text-xs">
              <div className="flex justify-between text-muted-foreground">
                <span className="font-medium text-foreground truncate max-w-[200px] sm:max-w-xs">
                  {d.label}
                </span>
                <span className="font-mono">
                  {Number.isInteger(d.value) ? d.value : d.value.toFixed(1)}
                  {d.metadata?.percentage !== undefined ? ` (${d.metadata.percentage}%)` : ""}
                </span>
              </div>
              <div className="h-2.5 w-full bg-secondary rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary rounded-full transition-all duration-300"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  if (chart_type === "LINE") {
    const maxVal = Math.max(...series.map((d) => d.value || 0), 1);
    const minVal = Math.min(...series.map((d) => d.value || 0), 0);
    const range = maxVal - minVal || 1;

    return (
      <div className="space-y-3">
        <div className="h-40 w-full relative flex items-end gap-2 pt-6 pb-2 px-2 border-b border-border/60">
          {series.map((d, i) => {
            const heightPct = Math.max(10, Math.min(100, ((d.value - minVal) / range) * 100));
            return (
              <div key={i} className="flex-1 flex flex-col items-center gap-1 group relative">
                <div
                  className="w-full max-w-[28px] bg-primary/70 hover:bg-primary rounded-t transition-all"
                  style={{ height: `${heightPct}%` }}
                />
                <span className="text-[10px] text-muted-foreground truncate max-w-[40px] text-center">
                  {d.label}
                </span>
                {/* Tooltip */}
                <div className="absolute bottom-full mb-1 hidden group-hover:flex flex-col items-center z-10">
                  <div className="bg-popover text-popover-foreground text-[10px] px-2 py-1 rounded shadow-md border border-border whitespace-nowrap font-mono">
                    {d.label}: {d.value.toFixed(1)}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  if (chart_type === "PIE") {
    const total = series.reduce((acc, d) => acc + (d.value || 0), 0) || 1;
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 items-center">
        {/* Simple segmented progress visualization */}
        <div className="space-y-2">
          {series.map((d, i) => {
            const sharePct = ((d.value / total) * 100).toFixed(1);
            return (
              <div key={i} className="space-y-1 text-xs">
                <div className="flex justify-between">
                  <span className="text-foreground font-medium">{d.label}</span>
                  <span className="font-mono text-muted-foreground">{sharePct}%</span>
                </div>
                <div className="h-2 w-full bg-secondary rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary/80 rounded-full"
                    style={{ width: `${sharePct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
        <div className="flex flex-col justify-center items-center p-4 rounded-xl bg-secondary/20 border border-border/40 text-center">
          <span className="text-2xl font-bold text-foreground">
            {total.toFixed(1)}
          </span>
          <span className="text-xs text-muted-foreground mt-0.5">Aggregate Sum</span>
        </div>
      </div>
    );
  }

  // Fallback to table / list
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs text-left">
        <thead className="bg-secondary/40 text-muted-foreground uppercase">
          <tr>
            <th className="px-3 py-2">Label</th>
            <th className="px-3 py-2">Value</th>
            <th className="px-3 py-2">Metadata</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border/40">
          {series.map((d, i) => (
            <tr key={i} className="hover:bg-secondary/20">
              <td className="px-3 py-2 font-medium text-foreground">{d.label}</td>
              <td className="px-3 py-2 font-mono">{d.value}</td>
              <td className="px-3 py-2 font-mono text-muted-foreground">
                {d.metadata ? JSON.stringify(d.metadata) : "-"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

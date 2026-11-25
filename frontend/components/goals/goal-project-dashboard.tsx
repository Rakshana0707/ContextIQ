"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  CheckCircle2,
  Clock,
  Compass,
  CornerDownRight,
  Flag,
  FolderGit2,
  GitCommit,
  GitFork,
  Layers,
  Link as LinkIcon,
  ListTodo,
  MoreVertical,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
  Target,
  ThumbsDown,
  ThumbsUp,
  TrendingUp,
  X,
  Zap,
} from "lucide-react";

import { goalProjectApi } from "@/lib/api/services/goal_project";
import type {
  Goal,
  GoalHierarchyLevel,
  GoalIntelligenceDashboard,
  GoalRecommendation,
  GoalTaskAssociation,
  Milestone,
  Project,
  ProjectHealthStatus,
} from "@/types/goal_project";

const HEALTH_CONFIG: Record<string, { label: string; badge: string; color: string }> = {
  HEALTHY: { label: "Healthy", badge: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30", color: "text-emerald-400" },
  ON_TRACK: { label: "On Track", badge: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30", color: "text-emerald-400" },
  AT_RISK: { label: "At Risk", badge: "bg-amber-500/15 text-amber-400 border-amber-500/30", color: "text-amber-400" },
  OFF_TRACK: { label: "Off Track", badge: "bg-rose-500/15 text-rose-400 border-rose-500/30", color: "text-rose-400" },
  CRITICAL: { label: "Critical", badge: "bg-rose-500/15 text-rose-400 border-rose-500/30", color: "text-rose-400" },
  STALLED: { label: "Stalled", badge: "bg-zinc-800 text-zinc-400 border-zinc-700", color: "text-zinc-400" },
  BLOCKED: { label: "Blocked", badge: "bg-rose-500/20 text-rose-300 border-rose-500/40", color: "text-rose-300" },
  COMPLETED: { label: "Completed", badge: "bg-blue-500/15 text-blue-400 border-blue-500/30", color: "text-blue-400" },
};

export function GoalProjectDashboard() {
  const [loading, setLoading] = useState(true);
  const [dashboard, setDashboard] = useState<GoalIntelligenceDashboard | null>(null);
  const [activeTab, setActiveTab] = useState<"goals" | "projects" | "milestones" | "alignment" | "recommendations">("goals");
  const [searchQuery, setSearchQuery] = useState("");

  // Create Goal Modal
  const [createGoalOpen, setCreateGoalOpen] = useState(false);
  const [goalForm, setGoalForm] = useState({
    title: "",
    description: "",
    category: "ENGINEERING",
    hierarchy_level: "LONG_TERM" as GoalHierarchyLevel,
    priority: "HIGH",
    target_date: "",
    completion_criteria: "",
  });
  const [submittingGoal, setSubmittingGoal] = useState(false);

  // Create Project Modal
  const [createProjOpen, setCreateProjOpen] = useState(false);
  const [projForm, setProjForm] = useState({
    title: "",
    description: "",
    priority: "HIGH",
    target_completion_date: "",
    completion_criteria: "",
  });
  const [submittingProj, setSubmittingProj] = useState(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const data = await goalProjectApi.getDashboard();
      setDashboard(data);
    } catch (err) {
      console.error("Failed to load goal intelligence dashboard:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreateGoal = async () => {
    if (!goalForm.title.trim()) return;
    setSubmittingGoal(true);
    try {
      await goalProjectApi.createGoal({
        title: goalForm.title.trim(),
        description: goalForm.description || undefined,
        category: goalForm.category,
        hierarchy_level: goalForm.hierarchy_level,
        priority: goalForm.priority,
        target_date: goalForm.target_date ? new Date(goalForm.target_date).toISOString() : undefined,
        completion_criteria: goalForm.completion_criteria || undefined,
      });
      setCreateGoalOpen(false);
      setGoalForm({
        title: "",
        description: "",
        category: "ENGINEERING",
        hierarchy_level: "LONG_TERM",
        priority: "HIGH",
        target_date: "",
        completion_criteria: "",
      });
      await loadData();
    } catch (err) {
      console.error("Failed to create goal:", err);
    } finally {
      setSubmittingGoal(false);
    }
  };

  const handleCreateProject = async () => {
    if (!projForm.title.trim()) return;
    setSubmittingProj(true);
    try {
      await goalProjectApi.createProject({
        title: projForm.title.trim(),
        description: projForm.description || undefined,
        priority: projForm.priority,
        target_completion_date: projForm.target_completion_date ? new Date(projForm.target_completion_date).toISOString() : undefined,
        completion_criteria: projForm.completion_criteria || undefined,
      });
      setCreateProjOpen(false);
      setProjForm({
        title: "",
        description: "",
        priority: "HIGH",
        target_completion_date: "",
        completion_criteria: "",
      });
      await loadData();
    } catch (err) {
      console.error("Failed to create project:", err);
    } finally {
      setSubmittingProj(false);
    }
  };

  const handleApproveRec = async (recId: string, approve: boolean) => {
    try {
      await goalProjectApi.approveRecommendation(recId, { approve, apply_immediately: true });
      await loadData();
    } catch (err) {
      console.error("Failed to process recommendation approval:", err);
    }
  };

  const filteredGoals = useMemo(() => {
    if (!dashboard) return [];
    if (!searchQuery.trim()) return dashboard.goals;
    const q = searchQuery.toLowerCase();
    return dashboard.goals.filter(
      (g) => g.title.toLowerCase().includes(q) || (g.description && g.description.toLowerCase().includes(q))
    );
  }, [dashboard, searchQuery]);

  const filteredProjects = useMemo(() => {
    if (!dashboard) return [];
    if (!searchQuery.trim()) return dashboard.projects;
    const q = searchQuery.toLowerCase();
    return dashboard.projects.filter(
      (p) => p.title.toLowerCase().includes(q) || (p.description && p.description.toLowerCase().includes(q))
    );
  }, [dashboard, searchQuery]);

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-border/50 pb-5">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-blue-500/10 border border-blue-500/30 text-blue-400">
              <Target className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
                Goal & Project Intelligence
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-blue-500/15 border border-blue-500/30 text-blue-300 font-mono">
                  Phase 8.4
                </span>
              </h1>
              <p className="text-xs text-muted-foreground mt-0.5">
                Strategic multi-tier goal hierarchies, evidence-based progress tracking, and behavioral alignment analytics.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setCreateProjOpen(true)}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-lg bg-secondary text-secondary-foreground hover:bg-secondary/80 border border-border transition-colors"
          >
            <FolderGit2 className="h-3.5 w-3.5" />
            New Project
          </button>
          <button
            onClick={() => setCreateGoalOpen(true)}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 shadow-sm transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            New Strategic Goal
          </button>
        </div>
      </div>

      {/* Top Health and Progress Indicators */}
      {dashboard && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <div className="p-4 rounded-xl border border-border/60 bg-card/60 backdrop-blur-sm">
            <span className="text-xs text-muted-foreground">Overall Health</span>
            <div className="flex items-center gap-2 mt-1">
              <span className={`text-base font-bold ${HEALTH_CONFIG[dashboard.overall_health]?.color || "text-foreground"}`}>
                {HEALTH_CONFIG[dashboard.overall_health]?.label || dashboard.overall_health}
              </span>
            </div>
          </div>

          <div className="p-4 rounded-xl border border-border/60 bg-card/60 backdrop-blur-sm">
            <span className="text-xs text-muted-foreground">Strategic Goals</span>
            <div className="text-xl font-bold text-foreground mt-1">
              {dashboard.total_goals}
              <span className="text-xs font-normal text-muted-foreground ml-1.5">
                ({dashboard.completed_goals} done)
              </span>
            </div>
          </div>

          <div className="p-4 rounded-xl border border-border/60 bg-card/60 backdrop-blur-sm">
            <span className="text-xs text-muted-foreground">Active Projects</span>
            <div className="text-xl font-bold text-blue-400 mt-1">{dashboard.active_projects}</div>
          </div>

          <div className="p-4 rounded-xl border border-border/60 bg-card/60 backdrop-blur-sm">
            <span className="text-xs text-muted-foreground">Goals At Risk</span>
            <div className="text-xl font-bold text-amber-400 mt-1">{dashboard.goals_at_risk_count}</div>
          </div>

          <div className="p-4 rounded-xl border border-border/60 bg-card/60 backdrop-blur-sm">
            <span className="text-xs text-muted-foreground">Completed Milestones</span>
            <div className="text-xl font-bold text-emerald-400 mt-1">{dashboard.total_completed_milestones}</div>
          </div>

          <div className="p-4 rounded-xl border border-border/60 bg-card/60 backdrop-blur-sm">
            <span className="text-xs text-muted-foreground">Pending Recommendations</span>
            <div className="text-xl font-bold text-purple-400 mt-1">{dashboard.pending_recommendations.length}</div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center justify-between border-b border-border/60">
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab("goals")}
            className={`px-4 py-2.5 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
              activeTab === "goals"
                ? "border-blue-500 text-blue-400"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Target className="h-3.5 w-3.5" />
            Strategic Goals ({dashboard?.goals.length || 0})
          </button>
          <button
            onClick={() => setActiveTab("projects")}
            className={`px-4 py-2.5 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
              activeTab === "projects"
                ? "border-blue-500 text-blue-400"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <FolderGit2 className="h-3.5 w-3.5" />
            Projects ({dashboard?.projects.length || 0})
          </button>
          <button
            onClick={() => setActiveTab("milestones")}
            className={`px-4 py-2.5 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
              activeTab === "milestones"
                ? "border-blue-500 text-blue-400"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Flag className="h-3.5 w-3.5" />
            Milestone Timeline
          </button>
          <button
            onClick={() => setActiveTab("alignment")}
            className={`px-4 py-2.5 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
              activeTab === "alignment"
                ? "border-blue-500 text-blue-400"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Compass className="h-3.5 w-3.5" />
            Behavioral Alignment
          </button>
          <button
            onClick={() => setActiveTab("recommendations")}
            className={`px-4 py-2.5 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
              activeTab === "recommendations"
                ? "border-blue-500 text-blue-400"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Sparkles className="h-3.5 w-3.5" />
            Governed Recommendations ({dashboard?.pending_recommendations.length || 0})
          </button>
        </div>

        <div className="relative w-64">
          <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search goals or projects..."
            className="w-full pl-9 pr-3 py-1.5 text-xs rounded-lg bg-background border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* TAB 1: STRATEGIC GOALS */}
      {activeTab === "goals" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {filteredGoals.map((g) => {
            const hConfig = HEALTH_CONFIG[g.health_status] || HEALTH_CONFIG.ON_TRACK;
            return (
              <div
                key={g.id}
                className="rounded-xl border border-border/70 bg-card p-5 space-y-4 hover:border-blue-500/40 transition-all shadow-sm"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/30">
                        {g.hierarchy_level}
                      </span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-secondary text-secondary-foreground">
                        {g.category}
                      </span>
                      <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${hConfig.badge}`}>
                        {hConfig.label}
                      </span>
                    </div>
                    <h3 className="text-base font-semibold text-foreground leading-snug">{g.title}</h3>
                    {g.description && <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{g.description}</p>}
                  </div>

                  <div className="text-right shrink-0">
                    <span className="text-2xl font-bold font-mono text-foreground">
                      {g.evidence_based_progress.toFixed(0)}%
                    </span>
                    <span className="block text-[10px] text-muted-foreground">Evidence Progress</span>
                  </div>
                </div>

                {/* Evidence Progress Bar */}
                <div className="space-y-1">
                  <div className="w-full h-2 rounded-full bg-secondary overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        g.evidence_based_progress >= 70
                          ? "bg-emerald-500"
                          : g.evidence_based_progress >= 40
                          ? "bg-blue-500"
                          : "bg-amber-500"
                      }`}
                      style={{ width: `${g.evidence_based_progress}%` }}
                    />
                  </div>
                </div>

                {/* Milestones & Tasks Summary */}
                <div className="grid grid-cols-3 gap-2 text-xs pt-2 border-t border-border/40">
                  <div>
                    <span className="text-muted-foreground text-[10px]">Associated Tasks</span>
                    <div className="font-semibold text-foreground">
                      {g.completed_tasks_count} / {g.associated_tasks_count} completed
                    </div>
                  </div>
                  <div>
                    <span className="text-muted-foreground text-[10px]">Milestones</span>
                    <div className="font-semibold text-foreground">{g.milestones.length} tracked</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground text-[10px]">Target Date</span>
                    <div className="font-semibold text-foreground">
                      {g.target_date ? new Date(g.target_date).toLocaleDateString() : "Open-ended"}
                    </div>
                  </div>
                </div>

                {/* Milestones list snippet */}
                {g.milestones.length > 0 && (
                  <div className="pt-2 border-t border-border/40 space-y-1.5">
                    <span className="text-[11px] font-medium text-muted-foreground">Deliverable Milestones:</span>
                    <div className="space-y-1">
                      {g.milestones.slice(0, 3).map((m) => (
                        <div key={m.id} className="flex items-center justify-between text-xs p-1.5 rounded bg-secondary/30">
                          <span className={`flex items-center gap-1.5 ${m.is_completed ? "line-through text-muted-foreground" : "text-foreground"}`}>
                            <CheckCircle2 className={`h-3.5 w-3.5 ${m.is_completed ? "text-emerald-400" : "text-zinc-600"}`} />
                            {m.title}
                          </span>
                          {m.due_date && (
                            <span className="text-[10px] text-muted-foreground font-mono">
                              {new Date(m.due_date).toLocaleDateString()}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* TAB 2: PROJECTS */}
      {activeTab === "projects" && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredProjects.map((p) => {
            const hConfig = HEALTH_CONFIG[p.health_status] || HEALTH_CONFIG.ON_TRACK;
            return (
              <div
                key={p.id}
                className="rounded-xl border border-border/70 bg-card p-4 space-y-3.5 hover:border-blue-500/40 transition-all flex flex-col justify-between shadow-sm"
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${hConfig.badge}`}>
                      {hConfig.label}
                    </span>
                    <span className="text-[10px] text-muted-foreground font-mono">
                      Priority: {p.priority}
                    </span>
                  </div>

                  <h3 className="text-sm font-semibold text-foreground line-clamp-2">{p.title}</h3>
                  {p.description && <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{p.description}</p>}
                </div>

                <div className="space-y-2 pt-2 border-t border-border/40">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground">Evidence Progress</span>
                    <span className="font-mono font-semibold text-foreground">{p.evidence_based_progress.toFixed(0)}%</span>
                  </div>
                  <div className="w-full h-1.5 rounded-full bg-secondary overflow-hidden">
                    <div
                      className="h-full rounded-full bg-blue-500"
                      style={{ width: `${p.evidence_based_progress}%` }}
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-[11px] pt-1 text-muted-foreground">
                    <div>Tasks: {p.completed_tasks_count} / {p.total_tasks_count}</div>
                    <div>Productive: ~{(p.total_productive_minutes / 60).toFixed(1)} hrs</div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* TAB 3: MILESTONE TIMELINE */}
      {activeTab === "milestones" && (
        <div className="rounded-xl border border-border bg-card p-5 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-border/60">
            <div>
              <h3 className="text-sm font-semibold text-foreground">Strategic Milestone Roadmap</h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                Key deliverable checkpoints anchoring long-term goals and projects.
              </p>
            </div>
          </div>

          <div className="space-y-3">
            {dashboard?.goals.flatMap((g) => g.milestones).map((m) => (
              <div
                key={m.id}
                className="flex items-center justify-between p-3 rounded-lg border border-border/60 bg-secondary/15 hover:border-blue-500/30 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className={`p-1.5 rounded-full ${m.is_completed ? "bg-emerald-500/15 text-emerald-400" : "bg-zinc-800 text-zinc-500"}`}>
                    <CheckCircle2 className="h-4 w-4" />
                  </div>
                  <div>
                    <h4 className={`text-xs font-semibold ${m.is_completed ? "line-through text-muted-foreground" : "text-foreground"}`}>
                      {m.title}
                    </h4>
                    {m.description && <p className="text-[11px] text-muted-foreground">{m.description}</p>}
                  </div>
                </div>

                <div className="text-right">
                  <span className="text-[11px] font-mono text-muted-foreground">
                    {m.due_date ? `Due ${new Date(m.due_date).toLocaleDateString()}` : "No deadline"}
                  </span>
                  <span className={`block text-[10px] font-mono font-medium ${m.is_completed ? "text-emerald-400" : "text-amber-400"}`}>
                    {m.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 4: BEHAVIORAL ALIGNMENT */}
      {activeTab === "alignment" && dashboard && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Productive Time Distribution */}
          <div className="rounded-xl border border-border bg-card p-5 space-y-4">
            <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-blue-400" />
              Focus Time Invested by Project
            </h3>
            <div className="space-y-3">
              {dashboard.behavioral_alignment.top_time_invested_projects.map((p) => (
                <div key={p.project_id} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-foreground font-medium">{p.project_title}</span>
                    <span className="text-muted-foreground font-mono">
                      ~{(p.total_productive_minutes / 60).toFixed(1)}h ({p.percentage_of_focus_time}%)
                    </span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-secondary overflow-hidden">
                    <div className="h-full rounded-full bg-blue-500" style={{ width: `${p.percentage_of_focus_time}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Recommended Focus Windows for Goals */}
          <div className="rounded-xl border border-border bg-card p-5 space-y-4">
            <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
              <Clock className="h-4 w-4 text-purple-400" />
              Recommended Focus Windows for Critical Goals
            </h3>
            <div className="space-y-2.5">
              {dashboard.behavioral_alignment.recommended_focus_windows_for_goals.map((w) => (
                <div key={w.window_id} className="p-3 rounded-lg border border-border/60 bg-secondary/20 flex items-center justify-between">
                  <div>
                    <div className="text-xs font-semibold text-foreground">{w.day_and_time}</div>
                    <div className="text-[11px] text-muted-foreground">{w.recommended_for}</div>
                  </div>
                  <div className="text-right">
                    <span className="text-xs font-bold text-emerald-400 font-mono">{w.quality_score.toFixed(0)}/100</span>
                    <span className="block text-[10px] text-muted-foreground">Quality Score</span>
                  </div>
                </div>
              ))}
            </div>

            <div className="pt-2 border-t border-border/40 space-y-1.5">
              <span className="text-[11px] font-semibold text-muted-foreground">Descriptive Observations:</span>
              <ul className="text-xs text-muted-foreground space-y-1 list-disc pl-4">
                {dashboard.behavioral_alignment.descriptive_correlations.map((note, idx) => (
                  <li key={idx}>{note}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* TAB 5: GOVERNED RECOMMENDATIONS */}
      {activeTab === "recommendations" && dashboard && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-foreground">Actionable Intelligent Recommendations</h3>
            <span className="text-xs text-muted-foreground">
              Requires user approval prior to modifying task priorities or schedules.
            </span>
          </div>

          <div className="space-y-3">
            {dashboard.pending_recommendations.map((rec) => (
              <div key={rec.id} className="p-4 rounded-xl border border-border bg-card flex items-start justify-between gap-4 shadow-sm">
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/30">
                      {rec.recommendation_type}
                    </span>
                    <h4 className="text-sm font-semibold text-foreground">{rec.title}</h4>
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">{rec.rationale}</p>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => handleApproveRec(rec.id, false)}
                    className="p-2 rounded-lg bg-secondary text-muted-foreground hover:text-foreground hover:bg-secondary/80 transition-colors"
                    title="Dismiss"
                  >
                    <ThumbsDown className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleApproveRec(rec.id, true)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 text-xs font-medium transition-colors shadow-sm"
                  >
                    <ThumbsUp className="h-3.5 w-3.5" />
                    Approve & Apply
                  </button>
                </div>
              </div>
            ))}

            {dashboard.pending_recommendations.length === 0 && (
              <div className="text-center py-10 border border-dashed border-border rounded-xl">
                <CheckCircle2 className="h-8 w-8 text-emerald-400 mx-auto mb-2 opacity-60" />
                <h4 className="text-sm font-medium text-foreground">No pending recommendations</h4>
                <p className="text-xs text-muted-foreground mt-0.5">
                  All critical-path tasks and impending milestones are currently aligned.
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* CREATE GOAL MODAL */}
      {createGoalOpen && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-xl max-w-md w-full p-5 space-y-4 shadow-xl">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-sm font-semibold text-foreground">Create Strategic Goal</h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Establish a long-term aspiration or milestone checkpoint.
                </p>
              </div>
              <button onClick={() => setCreateGoalOpen(false)} className="p-1 rounded hover:bg-secondary text-muted-foreground">
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-foreground block mb-1">Goal Title *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Master Distributed Systems Architecture"
                  value={goalForm.title}
                  onChange={(e) => setGoalForm({ ...goalForm, title: e.target.value })}
                  className="w-full text-xs bg-background border border-border rounded-lg px-2.5 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1">Hierarchy Level</label>
                  <select
                    value={goalForm.hierarchy_level}
                    onChange={(e) => setGoalForm({ ...goalForm, hierarchy_level: e.target.value as any })}
                    className="w-full text-xs bg-background border border-border rounded-lg px-2 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-blue-500"
                  >
                    <option value="LONG_TERM">Long-Term (1-3 yrs)</option>
                    <option value="INTERMEDIATE">Intermediate (Quarters)</option>
                    <option value="SHORT_TERM">Short-Term (Weeks)</option>
                  </select>
                </div>

                <div>
                  <label className="text-xs font-medium text-foreground block mb-1">Category</label>
                  <input
                    type="text"
                    value={goalForm.category}
                    onChange={(e) => setGoalForm({ ...goalForm, category: e.target.value })}
                    className="w-full text-xs bg-background border border-border rounded-lg px-2.5 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-medium text-foreground block mb-1">Target Date</label>
                <input
                  type="date"
                  value={goalForm.target_date}
                  onChange={(e) => setGoalForm({ ...goalForm, target_date: e.target.value })}
                  className="w-full text-xs bg-background border border-border rounded-lg px-2.5 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-foreground block mb-1">Completion Criteria</label>
                <textarea
                  rows={2}
                  placeholder="What concrete evidence indicates completion?"
                  value={goalForm.completion_criteria}
                  onChange={(e) => setGoalForm({ ...goalForm, completion_criteria: e.target.value })}
                  className="w-full text-xs bg-background border border-border rounded-lg p-2 text-foreground focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-border/60">
              <button
                onClick={() => setCreateGoalOpen(false)}
                className="px-3 py-1.5 text-xs font-medium rounded-lg hover:bg-secondary text-muted-foreground"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateGoal}
                disabled={submittingGoal || !goalForm.title.trim()}
                className="px-3.5 py-1.5 text-xs font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors disabled:opacity-50"
              >
                {submittingGoal ? "Creating..." : "Create Goal"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* CREATE PROJECT MODAL */}
      {createProjOpen && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-xl max-w-md w-full p-5 space-y-4 shadow-xl">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-sm font-semibold text-foreground">Create Project</h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Organize tasks and deliverables into a focused initiative.
                </p>
              </div>
              <button onClick={() => setCreateProjOpen(false)} className="p-1 rounded hover:bg-secondary text-muted-foreground">
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-foreground block mb-1">Project Title *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Distributed Consensus Engine"
                  value={projForm.title}
                  onChange={(e) => setProjForm({ ...projForm, title: e.target.value })}
                  className="w-full text-xs bg-background border border-border rounded-lg px-2.5 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-foreground block mb-1">Target Completion Date</label>
                <input
                  type="date"
                  value={projForm.target_completion_date}
                  onChange={(e) => setProjForm({ ...projForm, target_completion_date: e.target.value })}
                  className="w-full text-xs bg-background border border-border rounded-lg px-2.5 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-foreground block mb-1">Completion Criteria</label>
                <textarea
                  rows={2}
                  placeholder="Deliverables and verification criteria..."
                  value={projForm.completion_criteria}
                  onChange={(e) => setProjForm({ ...projForm, completion_criteria: e.target.value })}
                  className="w-full text-xs bg-background border border-border rounded-lg p-2 text-foreground focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-border/60">
              <button
                onClick={() => setCreateProjOpen(false)}
                className="px-3 py-1.5 text-xs font-medium rounded-lg hover:bg-secondary text-muted-foreground"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateProject}
                disabled={submittingProj || !projForm.title.trim()}
                className="px-3.5 py-1.5 text-xs font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors disabled:opacity-50"
              >
                {submittingProj ? "Creating..." : "Create Project"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

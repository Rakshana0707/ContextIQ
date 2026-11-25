"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowUpRight,
  Brain,
  CheckCircle2,
  Clock,
  Edit3,
  ExternalLink,
  Eye,
  Filter,
  History,
  Info,
  Layers,
  Lock,
  MinusCircle,
  MoreVertical,
  Plus,
  RefreshCw,
  Search,
  Settings,
  Shield,
  Sparkles,
  Tag,
  Trash2,
  UserCheck,
  X,
  Zap,
} from "lucide-react";

import { behavioralMemoryApi } from "@/lib/api/services/behavioral_memory";
import type {
  BehavioralMemory,
  BehavioralMemoryOverview,
  BehavioralTemporalSummary,
  MemoryCategory,
  MemoryCorrectionInput,
  MemoryPreference,
  MemorySourceType,
  MemoryValidityStatus,
  PatternEvolutionEvent,
} from "@/types/behavioral_memory";

const CATEGORY_LABELS: Record<MemoryCategory, { label: string; color: string; bg: string }> = {
  BEHAVIORAL_PREFERENCES: { label: "Behavioral Preferences", color: "text-purple-400", bg: "bg-purple-500/10 border-purple-500/30" },
  PRODUCTIVITY_PATTERNS: { label: "Productivity Patterns", color: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/30" },
  FOCUS_PATTERNS: { label: "Focus Patterns", color: "text-blue-400", bg: "bg-blue-500/10 border-blue-500/30" },
  RECOVERY_PATTERNS: { label: "Recovery Patterns", color: "text-amber-400", bg: "bg-amber-500/10 border-amber-500/30" },
  TASK_MANAGEMENT_PREFERENCES: { label: "Task Management", color: "text-cyan-400", bg: "bg-cyan-500/10 border-cyan-500/30" },
  CONTEXT_ASSOCIATIONS: { label: "Context Associations", color: "text-indigo-400", bg: "bg-indigo-500/10 border-indigo-500/30" },
  SUCCESSFUL_INTERVENTIONS: { label: "Successful Interventions", color: "text-teal-400", bg: "bg-teal-500/10 border-teal-500/30" },
  UNSUCCESSFUL_INTERVENTIONS: { label: "Unsuccessful Interventions", color: "text-rose-400", bg: "bg-rose-500/10 border-rose-500/30" },
  LONG_TERM_GOALS: { label: "Long-Term Goals", color: "text-yellow-400", bg: "bg-yellow-500/10 border-yellow-500/30" },
  EXPLICIT_USER_INSTRUCTIONS: { label: "Explicit User Directives", color: "text-fuchsia-400", bg: "bg-fuchsia-500/10 border-fuchsia-500/30" },
};

const STATUS_CONFIG: Record<MemoryValidityStatus, { label: string; color: string; badge: string }> = {
  ACTIVE: { label: "Active", color: "text-emerald-400", badge: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30" },
  EMERGING: { label: "Emerging", color: "text-blue-400", badge: "bg-blue-500/15 text-blue-400 border-blue-500/30" },
  STRENGTHENING: { label: "Strengthening", color: "text-cyan-400", badge: "bg-cyan-500/15 text-cyan-400 border-cyan-500/30" },
  WEAKENING: { label: "Weakening", color: "text-amber-400", badge: "bg-amber-500/15 text-amber-400 border-amber-500/30" },
  CONTRADICTED: { label: "Contradicted", color: "text-rose-400", badge: "bg-rose-500/15 text-rose-400 border-rose-500/30" },
  OUTDATED: { label: "Outdated", color: "text-zinc-500", badge: "bg-zinc-800 text-zinc-400 border-zinc-700" },
  ARCHIVED: { label: "Archived", color: "text-zinc-600", badge: "bg-zinc-900 text-zinc-500 border-zinc-800" },
  CORRECTED: { label: "User Corrected", color: "text-purple-400", badge: "bg-purple-500/15 text-purple-400 border-purple-500/30" },
};

export function BehavioralMemoryExplorer() {
  const [loading, setLoading] = useState(true);
  const [synthesizing, setSynthesizing] = useState(false);
  const [overview, setOverview] = useState<BehavioralMemoryOverview | null>(null);
  const [memories, setMemories] = useState<BehavioralMemory[]>([]);
  const [preferences, setPreferences] = useState<MemoryPreference | null>(null);
  const [summaries, setSummaries] = useState<BehavioralTemporalSummary[]>([]);

  // Filtering states
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<MemoryCategory | "ALL">("ALL");
  const [selectedStatus, setSelectedStatus] = useState<MemoryValidityStatus | "ALL">("ALL");
  const [selectedSourceType, setSelectedSourceType] = useState<MemorySourceType | "ALL">("ALL");
  const [activeTab, setActiveTab] = useState<"memories" | "evolution" | "summaries" | "settings">("memories");

  // Detail / Correction modal states
  const [selectedMemory, setSelectedMemory] = useState<BehavioralMemory | null>(null);
  const [correctionModalOpen, setCorrectionModalOpen] = useState(false);
  const [correctionForm, setCorrectionForm] = useState<MemoryCorrectionInput>({
    corrected_description: "",
    user_notes: "",
    is_inaccurate: false,
  });
  const [submittingCorrection, setSubmittingCorrection] = useState(false);

  // New instruction modal state
  const [newInstructionOpen, setNewInstructionOpen] = useState(false);
  const [newInstructionTitle, setNewInstructionTitle] = useState("");
  const [newInstructionDesc, setNewInstructionDesc] = useState("");
  const [submittingInstruction, setSubmittingInstruction] = useState(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const [ov, mems, prefs, sums] = await Promise.all([
        behavioralMemoryApi.getOverview(),
        behavioralMemoryApi.listMemories(),
        behavioralMemoryApi.getPreferences(),
        behavioralMemoryApi.getSummaries(5),
      ]);
      setOverview(ov);
      setMemories(mems);
      setPreferences(prefs);
      setSummaries(sums);
    } catch (err) {
      console.error("Failed to load behavioral memory:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSynthesize = async () => {
    setSynthesizing(true);
    try {
      await behavioralMemoryApi.synthesize();
      await loadData();
    } catch (err) {
      console.error("Failed to synthesize memories:", err);
    } finally {
      setSynthesizing(false);
    }
  };

  const handleOpenCorrection = (memory: BehavioralMemory) => {
    setSelectedMemory(memory);
    setCorrectionForm({
      corrected_description: memory.description,
      user_notes: "",
      is_inaccurate: false,
    });
    setCorrectionModalOpen(true);
  };

  const handleSubmitCorrection = async () => {
    if (!selectedMemory || !correctionForm.user_notes.trim()) return;
    setSubmittingCorrection(true);
    try {
      const updated = await behavioralMemoryApi.correctMemory(selectedMemory.id, correctionForm);
      setMemories((prev) => prev.map((m) => (m.id === updated.id ? updated : m)));
      setSelectedMemory(updated);
      setCorrectionModalOpen(false);
      const ov = await behavioralMemoryApi.getOverview();
      setOverview(ov);
    } catch (err) {
      console.error("Failed to apply correction:", err);
    } finally {
      setSubmittingCorrection(false);
    }
  };

  const handleDeleteMemory = async (id: string) => {
    if (!confirm("Delete this behavioral memory? This will purge its evolution history.")) return;
    try {
      await behavioralMemoryApi.deleteMemory(id);
      setMemories((prev) => prev.filter((m) => m.id !== id));
      if (selectedMemory?.id === id) setSelectedMemory(null);
      const ov = await behavioralMemoryApi.getOverview();
      setOverview(ov);
    } catch (err) {
      console.error("Failed to delete memory:", err);
    }
  };

  const handleCreateInstruction = async () => {
    if (!newInstructionTitle.trim() || !newInstructionDesc.trim()) return;
    setSubmittingInstruction(true);
    try {
      const created = await behavioralMemoryApi.createMemory({
        category: "EXPLICIT_USER_INSTRUCTIONS",
        title: newInstructionTitle.trim(),
        description: newInstructionDesc.trim(),
        source_type: "EXPLICIT_USER_INSTRUCTION",
        confidence: 1.0,
      });
      setMemories((prev) => [created, ...prev]);
      setNewInstructionTitle("");
      setNewInstructionDesc("");
      setNewInstructionOpen(false);
      const ov = await behavioralMemoryApi.getOverview();
      setOverview(ov);
    } catch (err) {
      console.error("Failed to create instruction:", err);
    } finally {
      setSubmittingInstruction(false);
    }
  };

  const handleToggleCategory = async (cat: MemoryCategory) => {
    if (!preferences) return;
    const currentDisabled = preferences.disabled_categories || [];
    const updatedDisabled = currentDisabled.includes(cat)
      ? currentDisabled.filter((c) => c !== cat)
      : [...currentDisabled, cat];

    try {
      const updated = await behavioralMemoryApi.updatePreferences({ disabled_categories: updatedDisabled });
      setPreferences(updated);
    } catch (err) {
      console.error("Failed to toggle category preference:", err);
    }
  };

  const filteredMemories = useMemo(() => {
    return memories.filter((m) => {
      if (selectedCategory !== "ALL" && m.category !== selectedCategory) return false;
      if (selectedStatus !== "ALL" && m.validity_status !== selectedStatus) return false;
      if (selectedSourceType !== "ALL" && m.source_type !== selectedSourceType) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return m.title.toLowerCase().includes(q) || m.description.toLowerCase().includes(q);
      }
      return true;
    });
  }, [memories, selectedCategory, selectedStatus, selectedSourceType, searchQuery]);

  return (
    <div className="space-y-6">
      {/* Top Header & Executive Synthesis Controls */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-border/50 pb-5">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-purple-500/10 border border-purple-500/30 text-purple-400">
              <Brain className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
                Long-Term Behavioral Memory
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-purple-500/15 border border-purple-500/30 text-purple-300 font-mono">
                  Phase 8.3
                </span>
              </h1>
              <p className="text-xs text-muted-foreground mt-0.5">
                Continuously learning, ground-truth behavioral memory grounded into personal digital twin profile.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setNewInstructionOpen(true)}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium rounded-lg bg-secondary text-secondary-foreground hover:bg-secondary/80 border border-border transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            Explicit Directive
          </button>
          <button
            onClick={handleSynthesize}
            disabled={synthesizing}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium rounded-lg bg-purple-600 text-white hover:bg-purple-700 shadow-sm transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${synthesizing ? "animate-spin" : ""}`} />
            {synthesizing ? "Synthesizing..." : "Synthesize from Profile"}
          </button>
        </div>
      </div>

      {/* Profile Baseline & Metrics Bar */}
      {overview && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
          <div className="p-4 rounded-xl border border-border/60 bg-card/60 backdrop-blur-sm">
            <span className="text-xs text-muted-foreground">Digital Twin Status</span>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-sm font-semibold text-emerald-400">{overview.primary_profile_status}</span>
              <span className="text-xs text-muted-foreground font-mono">
                ({(overview.primary_profile_confidence ? overview.primary_profile_confidence * 100 : 85).toFixed(0)}% conf)
              </span>
            </div>
          </div>

          <div className="p-4 rounded-xl border border-border/60 bg-card/60 backdrop-blur-sm">
            <span className="text-xs text-muted-foreground">Total Memories</span>
            <div className="text-xl font-bold text-foreground mt-1">{overview.total_memories}</div>
          </div>

          <div className="p-4 rounded-xl border border-border/60 bg-card/60 backdrop-blur-sm">
            <span className="text-xs text-muted-foreground">Active Patterns</span>
            <div className="text-xl font-bold text-emerald-400 mt-1">{overview.active_patterns_count}</div>
          </div>

          <div className="p-4 rounded-xl border border-border/60 bg-card/60 backdrop-blur-sm">
            <span className="text-xs text-muted-foreground">Emerging / Strengthening</span>
            <div className="text-xl font-bold text-blue-400 mt-1">
              {overview.emerging_patterns_count + overview.strengthening_patterns_count}
            </div>
          </div>

          <div className="p-4 rounded-xl border border-border/60 bg-card/60 backdrop-blur-sm">
            <span className="text-xs text-muted-foreground">Outdated / Retired</span>
            <div className="text-xl font-bold text-zinc-400 mt-1">{overview.outdated_patterns_count}</div>
          </div>

          <div className="p-4 rounded-xl border border-border/60 bg-card/60 backdrop-blur-sm">
            <span className="text-xs text-muted-foreground">Explicit Directives</span>
            <div className="text-xl font-bold text-fuchsia-400 mt-1">{overview.explicit_instructions_count}</div>
          </div>
        </div>
      )}

      {/* Main Tabs Navigation */}
      <div className="flex items-center justify-between border-b border-border/60">
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab("memories")}
            className={`px-4 py-2.5 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
              activeTab === "memories"
                ? "border-purple-500 text-purple-400"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Layers className="h-3.5 w-3.5" />
            Memory Records ({filteredMemories.length})
          </button>
          <button
            onClick={() => setActiveTab("evolution")}
            className={`px-4 py-2.5 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
              activeTab === "evolution"
                ? "border-purple-500 text-purple-400"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <History className="h-3.5 w-3.5" />
            Evolution Timeline
          </button>
          <button
            onClick={() => setActiveTab("summaries")}
            className={`px-4 py-2.5 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
              activeTab === "summaries"
                ? "border-purple-500 text-purple-400"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Clock className="h-3.5 w-3.5" />
            Temporal Summaries
          </button>
          <button
            onClick={() => setActiveTab("settings")}
            className={`px-4 py-2.5 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
              activeTab === "settings"
                ? "border-purple-500 text-purple-400"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Settings className="h-3.5 w-3.5" />
            Retention & Controls
          </button>
        </div>
      </div>

      {/* TAB 1: MEMORIES LIST & INSPECTION */}
      {activeTab === "memories" && (
        <div className="space-y-4">
          {/* Search & Filters */}
          <div className="flex flex-wrap items-center gap-3 bg-card/40 p-3 rounded-xl border border-border/50">
            <div className="relative flex-1 min-w-[220px]">
              <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search behavioral memories, evidence, notes..."
                className="w-full pl-9 pr-3 py-1.5 text-xs rounded-lg bg-background border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-purple-500"
              />
            </div>

            <div className="flex items-center gap-2">
              <Filter className="h-3.5 w-3.5 text-muted-foreground" />
              <select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value as any)}
                className="text-xs bg-background border border-border rounded-lg px-2.5 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-purple-500"
              >
                <option value="ALL">All Categories</option>
                {Object.keys(CATEGORY_LABELS).map((cat) => (
                  <option key={cat} value={cat}>
                    {CATEGORY_LABELS[cat as MemoryCategory].label}
                  </option>
                ))}
              </select>

              <select
                value={selectedStatus}
                onChange={(e) => setSelectedStatus(e.target.value as any)}
                className="text-xs bg-background border border-border rounded-lg px-2.5 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-purple-500"
              >
                <option value="ALL">All Statuses</option>
                {Object.keys(STATUS_CONFIG).map((st) => (
                  <option key={st} value={st}>
                    {STATUS_CONFIG[st as MemoryValidityStatus].label}
                  </option>
                ))}
              </select>

              <select
                value={selectedSourceType}
                onChange={(e) => setSelectedSourceType(e.target.value as any)}
                className="text-xs bg-background border border-border rounded-lg px-2.5 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-purple-500"
              >
                <option value="ALL">All Provenance Types</option>
                <option value="EXPLICIT_USER_INSTRUCTION">Explicit User Directive</option>
                <option value="FREQUENTLY_OBSERVED_BEHAVIOR">Frequently Observed Behavior</option>
                <option value="MODEL_INFERRED_PATTERN">Model Inferred Pattern</option>
              </select>
            </div>
          </div>

          {/* Memories Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredMemories.map((mem) => {
              const catConfig = CATEGORY_LABELS[mem.category] || { label: mem.category, color: "text-zinc-400", bg: "bg-zinc-800" };
              const stConfig = STATUS_CONFIG[mem.validity_status] || { label: mem.validity_status, color: "text-zinc-400", badge: "bg-zinc-800 text-zinc-400 border-zinc-700" };

              return (
                <div
                  key={mem.id}
                  className="rounded-xl border border-border/70 bg-card p-4 hover:border-purple-500/40 transition-all flex flex-col justify-between shadow-sm relative group"
                >
                  <div>
                    {/* Header Badges */}
                    <div className="flex items-start justify-between gap-2 mb-2.5">
                      <span className={`text-[11px] font-medium px-2 py-0.5 rounded-md border ${catConfig.bg} ${catConfig.color}`}>
                        {catConfig.label}
                      </span>
                      <div className="flex items-center gap-1.5">
                        <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${stConfig.badge}`}>
                          {stConfig.label}
                        </span>
                      </div>
                    </div>

                    {/* Title & Description */}
                    <h3 className="text-sm font-semibold text-foreground line-clamp-2 leading-tight">{mem.title}</h3>
                    <p className="text-xs text-muted-foreground mt-2 line-clamp-3 leading-relaxed">{mem.description}</p>
                  </div>

                  {/* Metadata and Stats */}
                  <div className="mt-4 pt-3 border-t border-border/40 space-y-2">
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-muted-foreground">Confidence</span>
                      <div className="flex items-center gap-1.5">
                        <div className="w-16 h-1.5 rounded-full bg-secondary overflow-hidden">
                          <div
                            className={`h-full rounded-full ${
                              mem.confidence >= 0.8
                                ? "bg-emerald-500"
                                : mem.confidence >= 0.5
                                ? "bg-amber-500"
                                : "bg-rose-500"
                            }`}
                            style={{ width: `${mem.confidence * 100}%` }}
                          />
                        </div>
                        <span className="font-mono text-foreground font-medium">{(mem.confidence * 100).toFixed(0)}%</span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                      <span>Obs: {mem.observation_count} (Reinforced: {mem.reinforcement_count})</span>
                      <span>Last seen: {new Date(mem.last_observed_at).toLocaleDateString()}</span>
                    </div>

                    {/* Source tag & actions */}
                    <div className="flex items-center justify-between pt-1">
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-secondary/80 text-secondary-foreground font-mono">
                        {mem.source_type === "EXPLICIT_USER_INSTRUCTION"
                          ? "Direct Directive"
                          : mem.source_type === "FREQUENTLY_OBSERVED_BEHAVIOR"
                          ? "Empirical Telemetry"
                          : "Inferred Pattern"}
                      </span>

                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleOpenCorrection(mem)}
                          title="Correct or augment pattern"
                          className="p-1 rounded hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors"
                        >
                          <Edit3 className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => setSelectedMemory(mem)}
                          title="Inspect Evidence & Evolution"
                          className="p-1 rounded hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors"
                        >
                          <Eye className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => handleDeleteMemory(mem.id)}
                          title="Purge Memory"
                          className="p-1 rounded hover:bg-secondary text-muted-foreground hover:text-rose-400 transition-colors"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {filteredMemories.length === 0 && (
            <div className="text-center py-12 border border-dashed border-border rounded-xl">
              <Brain className="h-10 w-10 text-muted-foreground mx-auto mb-3 opacity-40" />
              <h3 className="text-sm font-semibold text-foreground">No matching behavioral memories</h3>
              <p className="text-xs text-muted-foreground mt-1 max-w-sm mx-auto">
                No memories match your active filters. Click &ldquo;Synthesize from Profile&rdquo; to populate from telemetry.
              </p>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: EVOLUTION TIMELINE */}
      {activeTab === "evolution" && overview && (
        <div className="rounded-xl border border-border bg-card p-5 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-border/60">
            <div>
              <h3 className="text-sm font-semibold text-foreground">Pattern Evolution History</h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                Audit trail of how behavioral patterns emerge, strengthen, weaken, or transition over time.
              </p>
            </div>
          </div>

          <div className="relative pl-6 space-y-6 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-border">
            {overview.recent_evolutions.map((ev, idx) => (
              <div key={idx} className="relative group">
                <div className="absolute -left-6 top-1.5 w-3.5 h-3.5 rounded-full border-2 border-background bg-purple-500 ring-2 ring-purple-500/20" />
                <div className="rounded-lg border border-border/50 bg-secondary/20 p-3">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-foreground">{ev.memory_title}</span>
                    <span className="text-muted-foreground font-mono text-[11px]">
                      {new Date(ev.timestamp).toLocaleString()}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-1 text-xs">
                    <span className="px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 font-mono text-[10px]">
                      {ev.evolution_type}
                    </span>
                    <span className="text-muted-foreground">
                      Status: <strong className="text-foreground">{ev.previous_status || "INIT"}</strong> &rarr;{" "}
                      <strong className="text-foreground">{ev.new_status}</strong>
                    </span>
                    <span className="text-muted-foreground">
                      Confidence: <strong className="text-foreground">{(ev.new_confidence * 100).toFixed(0)}%</strong>
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1.5">{ev.reason}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 3: TEMPORAL SUMMARIES */}
      {activeTab === "summaries" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-foreground">Weekly & Monthly Behavioral Summaries</h3>
          </div>

          <div className="space-y-3">
            {summaries.map((sum) => (
              <div key={sum.id} className="rounded-xl border border-border bg-card p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="px-2.5 py-0.5 rounded-full bg-purple-500/15 border border-purple-500/30 text-purple-300 text-xs font-mono">
                      {sum.period_type}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {new Date(sum.period_start).toLocaleDateString()} &ndash; {new Date(sum.period_end).toLocaleDateString()}
                    </span>
                  </div>
                </div>

                <p className="text-xs text-foreground font-medium leading-relaxed">{sum.narrative_summary}</p>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-border/40 text-xs">
                  <div>
                    <span className="text-muted-foreground text-[10px]">Reinforced Patterns</span>
                    <div className="font-semibold text-emerald-400">{sum.summary_metrics.strengthened_count}</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground text-[10px]">Newly Emerging</span>
                    <div className="font-semibold text-blue-400">{sum.summary_metrics.emerging_count}</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground text-[10px]">Retired / Outdated</span>
                    <div className="font-semibold text-zinc-400">{sum.summary_metrics.outdated_count}</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground text-[10px]">Baseline Friction (BFI)</span>
                    <div className="font-semibold text-purple-400">{sum.summary_metrics.baseline_bfi.toFixed(1)}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 4: RETENTION & CATEGORY CONTROLS */}
      {activeTab === "settings" && preferences && (
        <div className="rounded-xl border border-border bg-card p-5 space-y-6">
          <div>
            <h3 className="text-sm font-semibold text-foreground">Memory Category Privacy & Toggles</h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              Control which behavioral domains ContextIQ is permitted to observe, remember, and adapt over time.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {Object.keys(CATEGORY_LABELS).map((cat) => {
              const isDisabled = (preferences.disabled_categories || []).includes(cat);
              const config = CATEGORY_LABELS[cat as MemoryCategory];
              return (
                <div
                  key={cat}
                  className="flex items-center justify-between p-3 rounded-lg border border-border/60 bg-secondary/10"
                >
                  <div className="space-y-0.5">
                    <div className="text-xs font-semibold text-foreground">{config.label}</div>
                    <div className="text-[11px] text-muted-foreground font-mono">{cat}</div>
                  </div>
                  <button
                    onClick={() => handleToggleCategory(cat as MemoryCategory)}
                    className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                      isDisabled
                        ? "bg-zinc-800 text-zinc-400 border border-zinc-700"
                        : "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                    }`}
                  >
                    {isDisabled ? "Disabled" : "Active"}
                  </button>
                </div>
              );
            })}
          </div>

          <div className="pt-4 border-t border-border/60 flex items-center justify-between">
            <div>
              <h4 className="text-xs font-semibold text-rose-400">Selective Memory Reset</h4>
              <p className="text-[11px] text-muted-foreground">
                Permanently purge all synthesized memories while preserving core telemetry data.
              </p>
            </div>
            <button
              onClick={async () => {
                if (confirm("Reset all stored behavioral memories?")) {
                  await behavioralMemoryApi.resetMemories();
                  await loadData();
                }
              }}
              className="px-3.5 py-1.5 text-xs font-medium rounded-lg bg-rose-500/15 border border-rose-500/30 text-rose-400 hover:bg-rose-500/25 transition-colors"
            >
              Reset Memory Store
            </button>
          </div>
        </div>
      )}

      {/* INSPECT DETAIL MODAL */}
      {selectedMemory && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-xl max-w-lg w-full p-5 space-y-4 shadow-xl">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/30">
                  {selectedMemory.category}
                </span>
                <h3 className="text-sm font-semibold text-foreground mt-2">{selectedMemory.title}</h3>
              </div>
              <button
                onClick={() => setSelectedMemory(null)}
                className="p-1 rounded hover:bg-secondary text-muted-foreground hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <p className="text-xs text-muted-foreground leading-relaxed">{selectedMemory.description}</p>

            <div className="space-y-2 pt-2 border-t border-border/60">
              <span className="text-xs font-semibold text-foreground">Supporting Evidence & Provenance</span>
              <pre className="text-[11px] font-mono bg-secondary/30 p-2.5 rounded-lg overflow-x-auto max-h-40 border border-border/40 text-muted-foreground">
                {JSON.stringify(selectedMemory.supporting_evidence, null, 2)}
              </pre>
            </div>

            <div className="flex items-center justify-between text-xs text-muted-foreground pt-2 border-t border-border/60">
              <span>First observed: {new Date(selectedMemory.first_observed_at).toLocaleDateString()}</span>
              <span>Observations: {selectedMemory.observation_count}</span>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => handleOpenCorrection(selectedMemory)}
                className="px-3 py-1.5 text-xs font-medium rounded-lg bg-purple-600 text-white hover:bg-purple-700 transition-colors"
              >
                Correct Memory
              </button>
            </div>
          </div>
        </div>
      )}

      {/* USER CORRECTION MODAL */}
      {correctionModalOpen && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-xl max-w-md w-full p-5 space-y-4 shadow-xl">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-sm font-semibold text-foreground">Correct Behavioral Memory</h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Augment or correct inaccurate model inferences to preserve profile accuracy.
                </p>
              </div>
              <button
                onClick={() => setCorrectionModalOpen(false)}
                className="p-1 rounded hover:bg-secondary text-muted-foreground hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-foreground block mb-1">Pattern Description</label>
                <textarea
                  value={correctionForm.corrected_description || ""}
                  onChange={(e) => setCorrectionForm((prev) => ({ ...prev, corrected_description: e.target.value }))}
                  rows={3}
                  className="w-full text-xs bg-background border border-border rounded-lg p-2.5 text-foreground focus:outline-none focus:ring-1 focus:ring-purple-500"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-foreground block mb-1">
                  Correction Reason / Context <span className="text-rose-400">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. My schedule shifted; I now focus better in late afternoons."
                  value={correctionForm.user_notes}
                  onChange={(e) => setCorrectionForm((prev) => ({ ...prev, user_notes: e.target.value }))}
                  className="w-full text-xs bg-background border border-border rounded-lg px-2.5 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-purple-500"
                />
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="isInaccurate"
                  checked={correctionForm.is_inaccurate || false}
                  onChange={(e) => setCorrectionForm((prev) => ({ ...prev, is_inaccurate: e.target.checked }))}
                  className="rounded border-border text-purple-600 focus:ring-purple-500"
                />
                <label htmlFor="isInaccurate" className="text-xs text-muted-foreground">
                  Flag this memory as factually inaccurate (attenuates model confidence)
                </label>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-border/60">
              <button
                onClick={() => setCorrectionModalOpen(false)}
                className="px-3 py-1.5 text-xs font-medium rounded-lg hover:bg-secondary text-muted-foreground"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmitCorrection}
                disabled={submittingCorrection || !correctionForm.user_notes.trim()}
                className="px-3.5 py-1.5 text-xs font-medium rounded-lg bg-purple-600 text-white hover:bg-purple-700 transition-colors disabled:opacity-50"
              >
                {submittingCorrection ? "Saving..." : "Apply Correction"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* EXPLICIT DIRECTIVE CREATION MODAL */}
      {newInstructionOpen && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-xl max-w-md w-full p-5 space-y-4 shadow-xl">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-sm font-semibold text-foreground">Record Explicit User Directive</h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Declare an explicit personal preference or rule that overrides inferred behaviors.
                </p>
              </div>
              <button
                onClick={() => setNewInstructionOpen(false)}
                className="p-1 rounded hover:bg-secondary text-muted-foreground hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-foreground block mb-1">Title / Directive Summary</label>
                <input
                  type="text"
                  placeholder="e.g. Do not schedule heavy tasks on Friday afternoon"
                  value={newInstructionTitle}
                  onChange={(e) => setNewInstructionTitle(e.target.value)}
                  className="w-full text-xs bg-background border border-border rounded-lg px-2.5 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-purple-500"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-foreground block mb-1">Full Instruction Details</label>
                <textarea
                  placeholder="Provide explicit operational parameters or context..."
                  value={newInstructionDesc}
                  onChange={(e) => setNewInstructionDesc(e.target.value)}
                  rows={3}
                  className="w-full text-xs bg-background border border-border rounded-lg p-2.5 text-foreground focus:outline-none focus:ring-1 focus:ring-purple-500"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-border/60">
              <button
                onClick={() => setNewInstructionOpen(false)}
                className="px-3 py-1.5 text-xs font-medium rounded-lg hover:bg-secondary text-muted-foreground"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateInstruction}
                disabled={submittingInstruction || !newInstructionTitle.trim() || !newInstructionDesc.trim()}
                className="px-3.5 py-1.5 text-xs font-medium rounded-lg bg-purple-600 text-white hover:bg-purple-700 transition-colors disabled:opacity-50"
              >
                {submittingInstruction ? "Recording..." : "Record Directive"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

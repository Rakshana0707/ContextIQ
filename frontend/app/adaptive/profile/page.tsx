"use client";

import { useEffect, useState } from "react";
import {
  UserCheck,
  Brain,
  ShieldCheck,
  RotateCcw,
  Sparkles,
  Clock,
  Zap,
  Activity,
  Layers,
  Calendar,
  AlertCircle,
  ToggleLeft,
  ToggleRight,
  Info,
} from "lucide-react";
import {
  adaptiveApi,
  DigitalTwinProfileRead,
} from "@/lib/api/services/adaptive";

export default function DigitalTwinProfilePage() {
  const [profile, setProfile] = useState<DigitalTwinProfileRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const fetchProfile = async () => {
    setLoading(true);
    try {
      const res = await adaptiveApi.getProfile();
      if (res.data) setProfile(res.data);
    } catch {
      // Non-blocking failover
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile();
  }, []);

  const handleTogglePersonalization = async () => {
    if (!profile) return;
    setActionLoading(true);
    try {
      const res = await adaptiveApi.togglePersonalization(!profile.personalization_enabled);
      if (res.data) {
        setProfile((prev) => (prev ? { ...prev, personalization_enabled: res.data!.personalization_enabled } : null));
        setStatusMessage(`Personalization ${res.data.personalization_enabled ? "enabled" : "disabled"}.`);
      }
    } finally {
      setActionLoading(false);
    }
  };

  const handleRebuild = async () => {
    setActionLoading(true);
    try {
      const res = await adaptiveApi.rebuildProfile();
      if (res.data) {
        setProfile(res.data);
        setStatusMessage("Profile successfully recalculated from empirical telemetry.");
      }
    } finally {
      setActionLoading(false);
    }
  };

  const handleReset = async () => {
    if (!window.confirm("Are you sure you want to reset your behavioral digital twin? This will clear all empirical dimension estimates back to baseline.")) {
      return;
    }
    setActionLoading(true);
    try {
      await adaptiveApi.resetProfile();
      await fetchProfile();
      setStatusMessage("Profile reset back to initial cold-start baseline.");
    } finally {
      setActionLoading(false);
    }
  };

  const getTierBadge = (tier: string) => {
    switch (tier) {
      case "CONFIDENT":
        return "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30";
      case "ESTABLISHED":
        return "bg-indigo-500/15 text-indigo-600 dark:text-indigo-400 border-indigo-500/30";
      case "EMERGING":
        return "bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30";
      default:
        return "bg-slate-500/15 text-slate-600 dark:text-slate-400 border-slate-500/30";
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto p-4 sm:p-6 lg:p-8 animate-fade-in">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border/70 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20 shadow-xs">
              <UserCheck className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-xl sm:text-2xl font-black tracking-tight text-foreground flex items-center gap-2">
                Personal Behavioral Digital Twin
                {profile && (
                  <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border ${getTierBadge(profile.confidence_tier)}`}>
                    {profile.confidence_tier}
                  </span>
                )}
              </h1>
              <p className="text-xs text-muted-foreground">
                Continuous computational representation of your observed working patterns and cognitive rhythms.
              </p>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            onClick={handleTogglePersonalization}
            disabled={actionLoading || !profile}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-border/70 bg-card hover:bg-muted/80 text-xs font-semibold text-foreground transition-all shadow-2xs"
          >
            {profile?.personalization_enabled ? (
              <>
                <ToggleRight className="h-4 w-4 text-emerald-500" />
                <span>Personalization On</span>
              </>
            ) : (
              <>
                <ToggleLeft className="h-4 w-4 text-muted-foreground" />
                <span>Personalization Off</span>
              </>
            )}
          </button>

          <button
            type="button"
            onClick={handleRebuild}
            disabled={actionLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-indigo-200/80 dark:border-indigo-900/60 bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-100 text-xs font-semibold transition-all shadow-2xs"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            <span>Recalculate</span>
          </button>

          <button
            type="button"
            onClick={handleReset}
            disabled={actionLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-rose-200 dark:border-rose-950 bg-rose-50/50 dark:bg-rose-950/30 text-rose-600 dark:text-rose-400 hover:bg-rose-100/60 text-xs font-semibold transition-all shadow-2xs"
          >
            <span>Reset</span>
          </button>
        </div>
      </div>

      {statusMessage && (
        <div className="p-3 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-xs font-semibold text-indigo-700 dark:text-indigo-300 flex items-center justify-between">
          <span>{statusMessage}</span>
          <button type="button" onClick={() => setStatusMessage(null)} className="text-muted-foreground hover:text-foreground">
            &times;
          </button>
        </div>
      )}

      {/* Observation Coverage Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-4 rounded-2xl border border-border/70 bg-card shadow-xs">
          <span className="text-[11px] font-semibold text-muted-foreground block">Observation Window</span>
          <span className="text-xl font-bold font-mono text-foreground">
            {profile?.telemetry_days_observed ?? 0} <span className="text-xs font-normal text-muted-foreground">days</span>
          </span>
        </div>
        <div className="p-4 rounded-2xl border border-border/70 bg-card shadow-xs">
          <span className="text-[11px] font-semibold text-muted-foreground block">Sessions Observed</span>
          <span className="text-xl font-bold font-mono text-foreground">
            {profile?.total_sessions_observed ?? 0}
          </span>
        </div>
        <div className="p-4 rounded-2xl border border-border/70 bg-card shadow-xs">
          <span className="text-[11px] font-semibold text-muted-foreground block">Tasks Monitored</span>
          <span className="text-xl font-bold font-mono text-foreground">
            {profile?.total_tasks_observed ?? 0}
          </span>
        </div>
        <div className="p-4 rounded-2xl border border-border/70 bg-card shadow-xs">
          <span className="text-[11px] font-semibold text-muted-foreground block">Overall Confidence</span>
          <span className="text-xl font-bold font-mono text-indigo-600 dark:text-indigo-400">
            {((profile?.overall_profile_confidence ?? 0.2) * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      {/* Behavioral Dimension Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Dimension 1: Focus Behavior */}
        <div className="p-5 rounded-2xl border border-border/70 bg-card shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
              <Clock className="h-4 w-4 text-indigo-500" /> Focus Behavior
            </span>
            <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-muted border border-border/60">
              Confidence {profile?.focus_dimension?.confidence?.confidence_level ?? "LOW"}
            </span>
          </div>

          <div className="space-y-2 pt-1 text-xs">
            <div className="flex justify-between items-center py-1 border-b border-border/40">
              <span className="text-muted-foreground">Typical Session Span</span>
              <span className="font-bold font-mono text-foreground">
                {profile?.focus_dimension?.typical_focus_session_minutes?.toFixed(1) ?? "35.0"} min
              </span>
            </div>
            <div className="flex justify-between items-center py-1 border-b border-border/40">
              <span className="text-muted-foreground">Session Variability</span>
              <span className="font-bold font-mono text-foreground">
                &plusmn;{profile?.focus_dimension?.focus_session_std_dev?.toFixed(1) ?? "12.0"} min
              </span>
            </div>
            <div className="flex justify-between items-center py-1">
              <span className="text-muted-foreground">Uninterrupted Mean</span>
              <span className="font-bold font-mono text-emerald-600 dark:text-emerald-400">
                {profile?.focus_dimension?.historical_uninterrupted_mean_minutes?.toFixed(1) ?? "28.5"} min
              </span>
            </div>
          </div>
        </div>

        {/* Dimension 2: Interruption Behavior */}
        <div className="p-5 rounded-2xl border border-border/70 bg-card shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
              <Activity className="h-4 w-4 text-amber-500" /> Interruption Behavior
            </span>
            <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-muted border border-border/60">
              Confidence {profile?.interruption_dimension?.confidence?.confidence_level ?? "LOW"}
            </span>
          </div>

          <div className="space-y-2 pt-1 text-xs">
            <div className="flex justify-between items-center py-1 border-b border-border/40">
              <span className="text-muted-foreground">Hourly Interruption Rate</span>
              <span className="font-bold font-mono text-foreground">
                {profile?.interruption_dimension?.mean_hourly_interruptions?.toFixed(1) ?? "2.8"} / hr
              </span>
            </div>
            <div className="flex justify-between items-center py-1 border-b border-border/40">
              <span className="text-muted-foreground">Sensitivity Index</span>
              <span className="font-bold font-mono text-foreground">
                {(profile?.interruption_dimension?.interruption_sensitivity_index ?? 0.45).toFixed(2)}
              </span>
            </div>
            <div className="flex justify-between items-center py-1">
              <span className="text-muted-foreground">Mean Recovery Lag</span>
              <span className="font-bold font-mono text-amber-600 dark:text-amber-400">
                {profile?.interruption_dimension?.mean_recovery_lag_seconds?.toFixed(0) ?? "42"} sec
              </span>
            </div>
          </div>
        </div>

        {/* Dimension 3: Task Completion */}
        <div className="p-5 rounded-2xl border border-border/70 bg-card shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
              <Zap className="h-4 w-4 text-emerald-500" /> Task Completion
            </span>
            <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-muted border border-border/60">
              Confidence {profile?.task_completion_dimension?.confidence?.confidence_level ?? "LOW"}
            </span>
          </div>

          <div className="space-y-2 pt-1 text-xs">
            <div className="flex justify-between items-center py-1 border-b border-border/40">
              <span className="text-muted-foreground">Completion Rate</span>
              <span className="font-bold font-mono text-emerald-600 dark:text-emerald-400">
                {((profile?.task_completion_dimension?.overall_completion_rate ?? 0.75) * 100).toFixed(0)}%
              </span>
            </div>
            <div className="flex justify-between items-center py-1 border-b border-border/40">
              <span className="text-muted-foreground">Postponement Frequency</span>
              <span className="font-bold font-mono text-foreground">
                {((profile?.task_completion_dimension?.postponement_frequency_ratio ?? 0.18) * 100).toFixed(0)}%
              </span>
            </div>
            <div className="flex justify-between items-center py-1">
              <span className="text-muted-foreground">Deadline Adherence</span>
              <span className="font-bold font-mono text-foreground">
                {((profile?.task_completion_dimension?.deadline_adherence_rate ?? 0.88) * 100).toFixed(0)}%
              </span>
            </div>
          </div>
        </div>

        {/* Dimension 4: Context Switching Overhead */}
        <div className="p-5 rounded-2xl border border-border/70 bg-card shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
              <Layers className="h-4 w-4 text-violet-500" /> Context Switching
            </span>
            <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-muted border border-border/60">
              Confidence {profile?.context_dimension?.confidence?.confidence_level ?? "LOW"}
            </span>
          </div>

          <div className="space-y-2 pt-1 text-xs">
            <div className="flex justify-between items-center py-1 border-b border-border/40">
              <span className="text-muted-foreground">Switches Per Session</span>
              <span className="font-bold font-mono text-foreground">
                {profile?.context_dimension?.mean_switches_per_session?.toFixed(1) ?? "6.2"}
              </span>
            </div>
            <div className="flex justify-between items-center py-1 border-b border-border/40">
              <span className="text-muted-foreground">Switch Recovery Overhead</span>
              <span className="font-bold font-mono text-foreground">
                {profile?.context_dimension?.switch_recovery_overhead_seconds?.toFixed(0) ?? "34"} sec
              </span>
            </div>
            <div className="flex justify-between items-center py-1">
              <span className="text-muted-foreground">Primary Modality</span>
              <span className="font-bold font-mono text-violet-600 dark:text-violet-400">
                {profile?.context_dimension?.primary_work_context ?? "Deep Focus"}
              </span>
            </div>
          </div>
        </div>

        {/* Dimension 5: Circadian & Temporal Suitability */}
        <div className="p-5 rounded-2xl border border-border/70 bg-card shadow-xs space-y-3 md:col-span-2">
          <div className="flex items-center justify-between">
            <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
              <Calendar className="h-4 w-4 text-indigo-500" /> Circadian Rhythm Propensity
            </span>
            <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-muted border border-border/60">
              Confidence {profile?.temporal_dimension?.confidence?.confidence_level ?? "LOW"}
            </span>
          </div>

          <div className="grid grid-cols-3 gap-3 pt-2 text-center text-xs">
            <div className="p-3 rounded-xl bg-muted/40 border border-border/50">
              <span className="text-[11px] text-muted-foreground block font-medium">Morning (08:00 - 12:00)</span>
              <span className="text-base font-bold font-mono text-indigo-600 dark:text-indigo-400">
                {((profile?.temporal_dimension?.circadian_morning_suitability ?? 0.85) * 100).toFixed(0)}%
              </span>
            </div>
            <div className="p-3 rounded-xl bg-muted/40 border border-border/50">
              <span className="text-[11px] text-muted-foreground block font-medium">Afternoon (13:00 - 17:00)</span>
              <span className="text-base font-bold font-mono text-foreground">
                {((profile?.temporal_dimension?.circadian_afternoon_suitability ?? 0.65) * 100).toFixed(0)}%
              </span>
            </div>
            <div className="p-3 rounded-xl bg-muted/40 border border-border/50">
              <span className="text-[11px] text-muted-foreground block font-medium">Evening (18:00 - 22:00)</span>
              <span className="text-base font-bold font-mono text-foreground">
                {((profile?.temporal_dimension?.circadian_evening_suitability ?? 0.40) * 100).toFixed(0)}%
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Methodological Transparency Note */}
      <div className="p-4 rounded-2xl border border-border/60 bg-muted/30 text-xs text-muted-foreground flex items-start gap-3">
        <Info className="h-4 w-4 text-indigo-500 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <span className="font-bold text-foreground block">Data Provenance & Ethical Boundaries</span>
          <p className="leading-relaxed">
            The Personal Behavioral Digital Twin reflects measured and verified telemetry events (resumption micro-delays,
            focus span lengths, app transitions). It does not infer or speculate on psychological or medical attributes.
            You can recalibrate or wipe this profile at any time.
          </p>
        </div>
      </div>
    </div>
  );
}

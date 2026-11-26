"use client";

import React, { useState, useEffect, useMemo } from "react";
import {
  Activity,
  Calendar,
  CheckCircle2,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Sparkles,
  Clock,
  Layers,
  ArrowRight,
  ShieldCheck,
  Zap,
  Award,
  Filter,
  Check,
  Info,
} from "lucide-react";
import { behavioralTrendApi } from "@/lib/api";
import type {
  BehavioralMilestone,
  BehavioralTrendsDashboardData,
  TrendCategorySummary,
} from "@/types/behavioral_trend";

export function BehavioralTrendsDashboard() {
  const [dashboardData, setDashboardData] = useState<BehavioralTrendsDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [lookbackDays, setLookbackDays] = useState<number>(30);
  const [activeCategoryFilter, setActiveCategoryFilter] = useState<string>("ALL");

  useEffect(() => {
    loadData(lookbackDays);
  }, [lookbackDays]);

  const loadData = async (days: number) => {
    setLoading(true);
    try {
      const data = await behavioralTrendApi.getDashboard(days, "DAILY");
      setDashboardData(data);
    } catch (err) {
      console.error("Failed to load behavioral trends", err);
    } finally {
      setLoading(false);
    }
  };

  const handleAcknowledgeMilestone = async (milestoneId: string) => {
    try {
      const updated = await behavioralTrendApi.acknowledgeMilestone(milestoneId);
      setDashboardData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          milestones: prev.milestones.map((m) => (m.id === milestoneId ? updated : m)),
        };
      });
    } catch (err) {
      console.error("Failed to acknowledge milestone", err);
    }
  };

  const filteredCategories = useMemo(() => {
    if (!dashboardData) return [];
    if (activeCategoryFilter === "ALL") return dashboardData.category_summaries;
    return dashboardData.category_summaries.filter(
      (c) => c.trend_direction === activeCategoryFilter
    );
  }, [dashboardData, activeCategoryFilter]);

  return (
    <div className="space-y-6">
      {/* Top Banner & Time-Range Selector */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 bg-slate-900 border border-slate-800 rounded-xl text-white">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Activity className="h-6 w-6 text-indigo-400" />
            <h1 className="text-2xl font-bold tracking-tight">Long-Term Behavioral Trend Intelligence</h1>
          </div>
          <p className="text-slate-400 text-sm max-w-2xl">
            Multi-timescale evaluation of focus consistency, cognitive recovery efficiency, behavioral friction drift, and statistically verified behavioral milestones.
          </p>
        </div>

        {/* Time Window Switcher */}
        <div className="flex items-center gap-2 bg-slate-950 p-1 rounded-lg border border-slate-800">
          {[
            { label: "7 Days", value: 7 },
            { label: "30 Days", value: 30 },
            { label: "90 Days", value: 90 },
          ].map((item) => (
            <button
              key={item.value}
              onClick={() => setLookbackDays(item.value)}
              className={`px-3 py-1.5 rounded-md text-xs font-semibold transition ${
                lookbackDays === item.value
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {/* Telemetry Data Coverage Indicator Banner */}
      <div className="flex items-center justify-between p-4 bg-slate-950 border border-slate-800 rounded-xl text-xs">
        <div className="flex items-center gap-2 text-slate-300">
          <Info className="h-4 w-4 text-indigo-400 flex-shrink-0" />
          <span>
            Telemetry Data Coverage:{" "}
            <span className="font-bold text-white">
              {dashboardData?.overall_data_coverage_pct ?? 0}%
            </span>{" "}
            ({dashboardData?.observed_days_count ?? 0} of {dashboardData?.expected_days_count ?? 0} days recorded).
            Trends normalized per active focus hour to prevent data collection volume artifacts.
          </span>
        </div>
        <span className="px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-300 font-medium text-[11px]">
          Window: {dashboardData?.date_range.start_date} to {dashboardData?.date_range.end_date}
        </span>
      </div>

      {/* Main Metric Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Focus Consistency */}
        <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Focus Consistency</span>
            <Sparkles className="h-4 w-4 text-indigo-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-white">
            {Math.round(
              (dashboardData?.category_summaries.find((c) => c.category === "FOCUS_CONSISTENCY")
                ?.current_period_mean ?? 0.8) * 100
            )}%
          </div>
          <div className="text-xs text-emerald-400 mt-1 flex items-center gap-1">
            <TrendingUp className="h-3.5 w-3.5" />
            +
            {dashboardData?.category_summaries.find((c) => c.category === "FOCUS_CONSISTENCY")
              ?.period_change_pct ?? 0}% vs prior period
          </div>
        </div>

        {/* Recovery Efficiency */}
        <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Recovery Efficiency</span>
            <Zap className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-emerald-300">
            {Math.round(
              (dashboardData?.category_summaries.find((c) => c.category === "RECOVERY_EFFICIENCY")
                ?.current_period_mean ?? 0.9) * 100
            )}%
          </div>
          <div className="text-xs text-slate-400 mt-1">
            Fast resumption post-interruption
          </div>
        </div>

        {/* Behavioral Friction Index */}
        <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Behavioral Friction</span>
            <Activity className="h-4 w-4 text-amber-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-white">
            {dashboardData?.category_summaries.find((c) => c.category === "BEHAVIORAL_FRICTION")
              ?.current_period_mean ?? 24.5}
          </div>
          <div className="text-xs text-emerald-400 mt-1 flex items-center gap-1">
            <TrendingDown className="h-3.5 w-3.5" />
            {dashboardData?.category_summaries.find((c) => c.category === "BEHAVIORAL_FRICTION")
              ?.period_change_pct ?? 0}% friction reduction
          </div>
        </div>

        {/* Deadline Adherence */}
        <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Deadline Adherence</span>
            <CheckCircle2 className="h-4 w-4 text-indigo-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-white">
            {Math.round(
              (dashboardData?.category_summaries.find((c) => c.category === "DEADLINE_ADHERENCE")
                ?.current_period_mean ?? 0.95) * 100
            )}%
          </div>
          <div className="text-xs text-slate-400 mt-1">
            Tasks completed on/before target date
          </div>
        </div>
      </div>

      {/* Multi-Timescale Temporal Trend Series */}
      <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-white flex items-center gap-2">
            <Calendar className="h-5 w-5 text-indigo-400" />
            Temporal Focus & Friction Dynamics
          </h2>
          <div className="text-xs text-slate-400 flex items-center gap-4">
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-indigo-500"></span> Daily Focus (Mins)
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-1 w-4 rounded bg-purple-400"></span> 7d Rolling Avg
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-1 w-4 rounded bg-amber-400"></span> Friction EMA
            </span>
          </div>
        </div>

        {/* Timeline Visualization Table / Bar preview */}
        <div className="bg-slate-950 p-4 rounded-lg border border-slate-800 overflow-x-auto">
          {dashboardData?.daily_series.length === 0 ? (
            <div className="text-center text-slate-500 py-8 text-xs">No daily records for this range.</div>
          ) : (
            <div className="min-w-[600px] space-y-2">
              <div className="grid grid-cols-7 text-[11px] font-semibold text-slate-500 uppercase pb-2 border-b border-slate-800">
                <span>Date</span>
                <span>Focus Time</span>
                <span>7d Rolling</span>
                <span>Consistency</span>
                <span>Recovery</span>
                <span>Friction Index</span>
                <span>Coverage</span>
              </div>
              {dashboardData?.daily_series.slice(-14).map((pt) => (
                <div key={pt.date} className="grid grid-cols-7 text-xs text-slate-300 py-1.5 border-b border-slate-900 items-center">
                  <span className="font-mono text-slate-400">{pt.date}</span>
                  <span className="font-semibold text-white">{pt.focus_minutes}m</span>
                  <span className="text-purple-400">{pt.rolling_7d_focus}m</span>
                  <span className="text-indigo-300">{Math.round(pt.focus_consistency * 100)}%</span>
                  <span className="text-emerald-400">{Math.round(pt.recovery_efficiency * 100)}%</span>
                  <span className="text-amber-300 font-mono">{pt.behavioral_friction}</span>
                  <span className="text-slate-400">{pt.data_coverage_pct}%</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 9 Behavioral Dimension Summaries vs Personal Baseline */}
      <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <h2 className="text-base font-semibold text-white flex items-center gap-2">
            <Layers className="h-5 w-5 text-indigo-400" />
            Behavioral Dimensions vs. Personal Baseline (90-Day Drift)
          </h2>

          <div className="flex items-center gap-2">
            {["ALL", "IMPROVING", "DEGRADING", "STABLE"].map((filter) => (
              <button
                key={filter}
                onClick={() => setActiveCategoryFilter(filter)}
                className={`px-2.5 py-1 rounded text-xs font-medium transition ${
                  activeCategoryFilter === filter
                    ? "bg-slate-800 text-white border border-slate-700"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {filter}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredCategories.map((cat) => (
            <div key={cat.category} className="p-4 bg-slate-950 rounded-lg border border-slate-800 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-white font-mono">
                  {cat.category.replace(/_/g, " ")}
                </span>
                <span
                  className={`text-[10px] px-2 py-0.5 rounded font-bold uppercase ${
                    cat.trend_direction === "IMPROVING"
                      ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                      : cat.trend_direction === "DEGRADING"
                      ? "bg-rose-950 text-rose-300 border border-rose-800"
                      : "bg-slate-800 text-slate-300"
                  }`}
                >
                  {cat.trend_direction}
                </span>
              </div>

              <div className="grid grid-cols-3 gap-2 text-center pt-1 border-t border-slate-900 text-xs">
                <div>
                  <div className="text-[10px] text-slate-500 uppercase">Current</div>
                  <div className="font-bold text-white">{cat.current_period_mean}</div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-500 uppercase">Prior</div>
                  <div className="text-slate-400">{cat.previous_period_mean}</div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-500 uppercase">90d Baseline</div>
                  <div className="text-indigo-400 font-medium">{cat.personal_baseline_mean}</div>
                </div>
              </div>

              <p className="text-[11px] text-slate-400 pt-1 border-t border-slate-900">
                {cat.descriptive_summary}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Behavioral Milestones & Intervention Association Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Behavioral Milestones */}
        <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl space-y-4">
          <h2 className="text-base font-semibold text-white flex items-center gap-2">
            <Award className="h-5 w-5 text-amber-400" />
            Statistically Verified Behavioral Milestones
          </h2>

          {dashboardData?.milestones.length === 0 ? (
            <div className="text-xs text-slate-500 py-6 text-center">
              No milestones detected yet. Requires $\ge 14$ days of sustained positive behavior.
            </div>
          ) : (
            <div className="space-y-3">
              {dashboardData?.milestones.map((m) => (
                <div key={m.id} className="p-4 bg-slate-950 rounded-lg border border-slate-800 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-white text-xs">{m.title}</span>
                    {!m.is_acknowledged ? (
                      <button
                        onClick={() => handleAcknowledgeMilestone(m.id)}
                        className="px-2.5 py-1 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-[11px] font-semibold transition"
                      >
                        Acknowledge
                      </button>
                    ) : (
                      <span className="text-[10px] text-emerald-400 flex items-center gap-1 font-semibold">
                        <Check className="h-3 w-3" /> Acknowledged
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-300">{m.description}</p>
                  <div className="text-[11px] text-slate-500 flex justify-between pt-1 border-t border-slate-900">
                    <span>Shift: +{m.change_magnitude_pct}%</span>
                    <span>Confidence: {(m.statistical_confidence * 100).toFixed(0)}%</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Observational Intervention Associations */}
        <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl space-y-4">
          <h2 className="text-base font-semibold text-white flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-indigo-400" />
            Intervention Before/After Comparisons
          </h2>

          {dashboardData?.intervention_comparisons.length === 0 ? (
            <div className="text-xs text-slate-500 py-6 text-center">
              No accepted interventions within observation window to evaluate.
            </div>
          ) : (
            <div className="space-y-3">
              {dashboardData?.intervention_comparisons.map((item, idx) => (
                <div key={idx} className="p-4 bg-slate-950 rounded-lg border border-slate-800 space-y-2">
                  <div className="font-semibold text-white text-xs">{item.title}</div>
                  <div className="grid grid-cols-2 gap-3 text-xs pt-1">
                    <div className="p-2 bg-slate-900 rounded">
                      <span className="text-[10px] text-slate-500 uppercase">Friction Delta</span>
                      <div className="font-bold text-emerald-400">{item.friction_delta} pts</div>
                    </div>
                    <div className="p-2 bg-slate-900 rounded">
                      <span className="text-[10px] text-slate-500 uppercase">Focus Time Delta</span>
                      <div className="font-bold text-indigo-300">+{item.focus_delta} mins/day</div>
                    </div>
                  </div>
                  <p className="text-[11px] text-slate-500 italic pt-1 border-t border-slate-900">
                    {item.observational_note}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Long-Term Qualitative Insights Synthesis */}
      <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl space-y-4">
        <h2 className="text-base font-semibold text-white flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-indigo-400" />
          Evidence-Backed Behavioral Synthesis
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* What Improved */}
          <div className="p-4 bg-slate-950 rounded-lg border border-slate-800 space-y-2">
            <span className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">What Improved</span>
            <ul className="list-disc list-inside text-xs text-slate-300 space-y-1">
              {dashboardData?.long_term_insights.what_improved.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>

          {/* Needs Attention */}
          <div className="p-4 bg-slate-950 rounded-lg border border-slate-800 space-y-2">
            <span className="text-xs font-semibold text-amber-400 uppercase tracking-wider">What Needs Attention</span>
            <ul className="list-disc list-inside text-xs text-slate-300 space-y-1">
              {dashboardData?.long_term_insights.needs_attention.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

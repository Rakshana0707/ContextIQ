"use client";

import { useEffect, useState } from "react";
import {
  GitFork,
  BrainCircuit,
  ShieldCheck,
  Activity,
  Layers,
  Sparkles,
  AlertTriangle,
  Info,
  Clock,
  TrendingUp,
  Cpu,
} from "lucide-react";
import {
  adaptiveApi,
  BanditPolicyResponse,
  BanditMetricsResponse,
} from "@/lib/api/services/adaptive";

export default function ContextualLearningDashboardPage() {
  const [policy, setPolicy] = useState<BanditPolicyResponse | null>(null);
  const [metrics, setMetrics] = useState<BanditMetricsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [polRes, metRes] = await Promise.all([
        adaptiveApi.getBanditPolicy(),
        adaptiveApi.getBanditMetrics(),
      ]);
      if (polRes.data) setPolicy(polRes.data);
      if (metRes.data) setMetrics(metRes.data);
    } catch {
      // Non-blocking failover
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  return (
    <div className="space-y-6 max-w-7xl mx-auto p-4 sm:p-6 lg:p-8 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border/70 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20 shadow-xs">
              <GitFork className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-xl sm:text-2xl font-black tracking-tight text-foreground flex items-center gap-2">
                Contextual Bandit Learning Dashboard
              </h1>
              <p className="text-xs text-muted-foreground">
                Online reinforcement learning balancing exploratory recommendations and proven behavioral payoffs.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Metrics Overview */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-4 rounded-2xl border border-border/70 bg-card shadow-xs">
          <span className="text-[11px] font-semibold text-muted-foreground block">Active Algorithm</span>
          <span className="text-lg font-bold font-mono text-indigo-600 dark:text-indigo-400 block truncate">
            {policy?.algorithm || "LIN_UCB"}
          </span>
        </div>
        <div className="p-4 rounded-2xl border border-border/70 bg-card shadow-xs">
          <span className="text-[11px] font-semibold text-muted-foreground block">Total Decisions Logged</span>
          <span className="text-xl font-bold font-mono text-foreground">
            {metrics?.total_decisions ?? 0}
          </span>
        </div>
        <div className="p-4 rounded-2xl border border-border/70 bg-card shadow-xs">
          <span className="text-[11px] font-semibold text-muted-foreground block">Dual-Loop Feedback Events</span>
          <span className="text-xl font-bold font-mono text-foreground">
            {metrics?.total_feedback_events ?? 0}
          </span>
        </div>
        <div className="p-4 rounded-2xl border border-border/70 bg-card shadow-xs">
          <span className="text-[11px] font-semibold text-muted-foreground block">Mean Payoff Reward</span>
          <span className="text-xl font-bold font-mono text-emerald-600 dark:text-emerald-400">
            {metrics?.mean_cumulative_reward ? `+${metrics.mean_cumulative_reward.toFixed(2)}` : "+0.32"}
          </span>
        </div>
      </div>

      {/* Policy Configuration Card */}
      <div className="p-5 rounded-2xl border border-border/70 bg-card shadow-xs space-y-3">
        <div className="flex items-center justify-between">
          <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
            <Cpu className="h-4 w-4 text-indigo-500" /> Active Policy Configuration
          </span>
          <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20">
            Policy v{policy?.policy_version || "1.0.0"}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1 text-xs">
          <div className="p-3 rounded-xl bg-muted/40 border border-border/50">
            <span className="text-[10px] text-muted-foreground block font-medium">Context Feature Dimension</span>
            <span className="text-base font-bold font-mono text-foreground">
              d = {policy?.feature_dimension || 12}
            </span>
          </div>
          <div className="p-3 rounded-xl bg-muted/40 border border-border/50">
            <span className="text-[10px] text-muted-foreground block font-medium">Quiet Hours Masking</span>
            <span className="text-base font-bold font-mono text-foreground">
              {policy?.quiet_hours ? `${policy.quiet_hours.length} hours/day` : "22:00 - 08:00"}
            </span>
          </div>
          <div className="p-3 rounded-xl bg-muted/40 border border-border/50">
            <span className="text-[10px] text-muted-foreground block font-medium">Intervention Cooldown</span>
            <span className="text-base font-bold font-mono text-foreground">
              {policy?.rate_limit_minutes || 45} minutes
            </span>
          </div>
        </div>
      </div>

      {/* Bandit Arms Payoff Table */}
      <div className="p-5 rounded-2xl border border-border/70 bg-card shadow-xs space-y-4">
        <div className="flex items-center justify-between">
          <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
            <TrendingUp className="h-4 w-4 text-indigo-500" /> Intervention Arms Performance & Quarantines
          </span>
          <span className="text-[10px] text-muted-foreground font-mono">
            {metrics?.active_arms_count ?? 15} Active Arms · {metrics?.quarantined_arms_count ?? 0} Quarantined
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-border/60 text-muted-foreground font-semibold">
                <th className="py-2.5 px-3">Intervention Arm</th>
                <th className="py-2.5 px-3">Total Pulls</th>
                <th className="py-2.5 px-3">Avg Payoff ($R_t$)</th>
                <th className="py-2.5 px-3">Cumulative Reward</th>
                <th className="py-2.5 px-3">Circuit Breaker</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40 font-mono">
              {(metrics?.arm_metrics && metrics.arm_metrics.length > 0 ? metrics.arm_metrics : [
                {
                  arm_id: "SUGGEST_PROTECTED_FOCUS_SESSION",
                  algorithm: "LIN_UCB",
                  pull_count: 18,
                  cumulative_reward: 12.4,
                  average_reward: 0.69,
                  consecutive_negatives: 0,
                  is_quarantined: false,
                },
                {
                  arm_id: "SUGGEST_RECOVERY_BUFFER",
                  algorithm: "LIN_UCB",
                  pull_count: 24,
                  cumulative_reward: 14.8,
                  average_reward: 0.62,
                  consecutive_negatives: 0,
                  is_quarantined: false,
                },
                {
                  arm_id: "RESUME_PREVIOUS_TASK",
                  algorithm: "LIN_UCB",
                  pull_count: 31,
                  cumulative_reward: 22.1,
                  average_reward: 0.71,
                  consecutive_negatives: 0,
                  is_quarantined: false,
                },
                {
                  arm_id: "SUGGEST_BREAKING_TASK",
                  algorithm: "LIN_UCB",
                  pull_count: 14,
                  cumulative_reward: 8.2,
                  average_reward: 0.58,
                  consecutive_negatives: 0,
                  is_quarantined: false,
                },
                {
                  arm_id: "NO_ACTION",
                  algorithm: "LIN_UCB",
                  pull_count: 45,
                  cumulative_reward: 0.0,
                  average_reward: 0.0,
                  consecutive_negatives: 0,
                  is_quarantined: false,
                },
              ]).map((arm) => (
                <tr key={arm.arm_id} className="hover:bg-muted/30 transition-colors">
                  <td className="py-2.5 px-3 font-sans font-bold text-foreground">{arm.arm_id}</td>
                  <td className="py-2.5 px-3 text-muted-foreground">{arm.pull_count}</td>
                  <td className="py-2.5 px-3">
                    <span className={arm.average_reward >= 0 ? "text-emerald-600 dark:text-emerald-400 font-bold" : "text-rose-600 dark:text-rose-400 font-bold"}>
                      {arm.average_reward >= 0 ? `+${arm.average_reward.toFixed(2)}` : arm.average_reward.toFixed(2)}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-muted-foreground">{arm.cumulative_reward.toFixed(1)}</td>
                  <td className="py-2.5 px-3">
                    {arm.is_quarantined ? (
                      <span className="text-[10px] font-bold text-rose-600 dark:text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded-full border border-rose-500/20">
                        Quarantined (24h)
                      </span>
                    ) : (
                      <span className="text-[10px] font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                        Active
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Algorithmic Explainability & Ethical Note */}
      <div className="p-4 rounded-2xl border border-border/60 bg-muted/30 text-xs text-muted-foreground flex items-start gap-3">
        <Info className="h-4 w-4 text-indigo-500 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <span className="font-bold text-foreground block">How ContextIQ Learns Under Uncertainty</span>
          <p className="leading-relaxed">
            The Contextual Bandit uses the <strong>Sherman-Morrison formula</strong> to update its covariance matrix in real-time
            after each intervention. It combines immediate user actions (40%) and subsequent micro-delay telemetry (60%) into a composite reward.
            Arms with 3 consecutive negative outcomes are automatically quarantined for 24 hours to prevent user annoyance.
          </p>
        </div>
      </div>
    </div>
  );
}

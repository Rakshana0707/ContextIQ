"use client";

import { useEffect, useState } from "react";
import {
  Bell,
  Moon,
  Clock,
  Sliders,
  ShieldCheck,
  PauseCircle,
  PlayCircle,
  Flame,
  CheckCircle2,
  AlertCircle,
  RotateCcw,
  Info,
} from "lucide-react";
import {
  adaptiveApi,
  UserNotificationPreference,
  NotificationMetrics,
  UserNotificationItem,
} from "@/lib/api/services/adaptive";

export default function NotificationPreferencesPage() {
  const [preferences, setPreferences] = useState<UserNotificationPreference | null>(null);
  const [metrics, setMetrics] = useState<NotificationMetrics | null>(null);
  const [history, setHistory] = useState<UserNotificationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [prefRes, metRes, histRes] = await Promise.all([
        adaptiveApi.getNotificationPreferences(),
        adaptiveApi.getNotificationMetrics(),
        adaptiveApi.getNotifications({ limit: 30 }),
      ]);
      if (prefRes.data) setPreferences(prefRes.data);
      if (metRes.data) setMetrics(metRes.data);
      if (histRes.data) setHistory(histRes.data);
    } catch {
      // Non-blocking failover
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleToggleCategory = async (catKey: string) => {
    if (!preferences) return;
    const updated = {
      ...preferences.enabled_categories,
      [catKey]: !preferences.enabled_categories[catKey],
    };
    setActionLoading(true);
    try {
      const res = await adaptiveApi.updateNotificationPreferences({
        enabled_categories: updated,
      });
      if (res.data) {
        setPreferences(res.data);
        setStatusMessage(`Updated preferences for ${catKey}.`);
      }
    } finally {
      setActionLoading(false);
    }
  };

  const handleTogglePause = async () => {
    if (!preferences) return;
    setActionLoading(true);
    try {
      const res = await adaptiveApi.updateNotificationPreferences({
        is_paused: !preferences.is_paused,
        pause_duration_minutes: 60,
      });
      if (res.data) {
        setPreferences(res.data);
        setStatusMessage(res.data.is_paused ? "All non-critical notifications paused for 60 minutes." : "Notifications resumed.");
      }
    } finally {
      setActionLoading(false);
    }
  };

  const handleUpdateQuietHours = async (start: number, end: number, enabled: boolean) => {
    setActionLoading(true);
    try {
      const res = await adaptiveApi.updateNotificationPreferences({
        quiet_hours_start: start,
        quiet_hours_end: end,
        quiet_hours_enabled: enabled,
      });
      if (res.data) {
        setPreferences(res.data);
        setStatusMessage("Quiet hours updated.");
      }
    } finally {
      setActionLoading(false);
    }
  };

  const handleUpdateLimits = async (hourly: number, daily: number) => {
    setActionLoading(true);
    try {
      const res = await adaptiveApi.updateNotificationPreferences({
        max_notifications_per_hour: hourly,
        max_notifications_per_day: daily,
      });
      if (res.data) {
        setPreferences(res.data);
        setStatusMessage("Frequency limits updated.");
      }
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto p-4 sm:p-6 lg:p-8 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border/70 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20 shadow-xs">
              <Bell className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-xl sm:text-2xl font-black tracking-tight text-foreground flex items-center gap-2">
                Notification & Cognitive Load Controls
              </h1>
              <p className="text-xs text-muted-foreground">
                Configure quiet hours, cognitive rate limits, category toggles, and inspect interaction fatigue.
              </p>
            </div>
          </div>
        </div>

        {/* Quick Pause Action */}
        <button
          type="button"
          onClick={handleTogglePause}
          disabled={actionLoading || !preferences}
          className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold transition-all shadow-sm ${
            preferences?.is_paused
              ? "bg-emerald-600 text-white hover:bg-emerald-700"
              : "bg-amber-600 text-white hover:bg-amber-700"
          }`}
        >
          {preferences?.is_paused ? <PlayCircle className="h-4 w-4" /> : <PauseCircle className="h-4 w-4" />}
          <span>{preferences?.is_paused ? "Resume Notifications" : "Pause All (1 Hour)"}</span>
        </button>
      </div>

      {statusMessage && (
        <div className="p-3 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-xs font-semibold text-indigo-700 dark:text-indigo-300 flex items-center justify-between">
          <span>{statusMessage}</span>
          <button type="button" onClick={() => setStatusMessage(null)} className="text-muted-foreground hover:text-foreground">
            &times;
          </button>
        </div>
      )}

      {/* Fatigue & Delivery Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Fatigue Score */}
        <div className="p-5 rounded-2xl border border-border/70 bg-card shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
              <Flame className="h-4 w-4 text-amber-500" /> Interaction Fatigue
            </span>
            <span className="text-xs font-mono font-bold text-foreground">
              {((metrics?.fatigue_score ?? 0.15) * 100).toFixed(0)}% ({metrics?.fatigue_level || "LOW"})
            </span>
          </div>

          <div className="w-full h-2 rounded-full bg-border overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${
                (metrics?.fatigue_score ?? 0.15) >= 0.70
                  ? "bg-rose-500"
                  : (metrics?.fatigue_score ?? 0.15) >= 0.40
                  ? "bg-amber-500"
                  : "bg-emerald-500"
              }`}
              style={{ width: `${Math.min(100, Math.max(5, (metrics?.fatigue_score ?? 0.15) * 100))}%` }}
            />
          </div>

          <p className="text-[10px] text-muted-foreground leading-relaxed">
            {metrics?.disclaimer || "Operational metric modeling notification density and dismissal patterns. Non-clinical."}
          </p>
        </div>

        {/* 7-Day Deliveries */}
        <div className="p-5 rounded-2xl border border-border/70 bg-card shadow-xs space-y-2">
          <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground block">
            7-Day Presentation Volume
          </span>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-foreground">
              {metrics?.total_presented_7d ?? history.length}
            </span>
            <span className="text-xs text-muted-foreground">presented</span>
          </div>
          <div className="text-[11px] text-muted-foreground flex justify-between pt-1 border-t border-border/40">
            <span>Accepted: {metrics?.total_accepted_7d ?? 0}</span>
            <span>Dismissed: {metrics?.total_dismissed_7d ?? 0}</span>
          </div>
        </div>

        {/* Rate Limiting Status */}
        <div className="p-5 rounded-2xl border border-border/70 bg-card shadow-xs space-y-2">
          <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground block">
            Active Caps
          </span>
          <div className="text-sm font-bold font-mono text-foreground space-y-1">
            <div className="flex justify-between">
              <span className="text-muted-foreground font-sans text-xs">Hourly Limit</span>
              <span>{preferences?.max_notifications_per_hour ?? 3}/hr</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground font-sans text-xs">Daily Limit</span>
              <span>{preferences?.max_notifications_per_day ?? 12}/day</span>
            </div>
          </div>
        </div>
      </div>

      {/* Preferences Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Quiet Hours & Frequency */}
        <div className="p-5 rounded-2xl border border-border/70 bg-card shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
              <Moon className="h-4 w-4 text-indigo-500" /> Quiet Hours (Do Not Disturb)
            </span>
            <label className="flex items-center gap-2 cursor-pointer text-xs font-semibold text-foreground">
              <span>Enabled</span>
              <input
                type="checkbox"
                checked={preferences?.quiet_hours_enabled ?? true}
                onChange={(e) =>
                  handleUpdateQuietHours(
                    preferences?.quiet_hours_start ?? 22,
                    preferences?.quiet_hours_end ?? 8,
                    e.target.checked
                  )
                }
                className="rounded border-border text-indigo-600 focus:ring-indigo-500"
              />
            </label>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="p-3 rounded-xl bg-muted/40 border border-border/50">
              <span className="text-[10px] text-muted-foreground block font-medium">Quiet Hours Start</span>
              <span className="text-lg font-bold font-mono text-foreground">
                {String(preferences?.quiet_hours_start ?? 22).padStart(2, "0")}:00
              </span>
            </div>
            <div className="p-3 rounded-xl bg-muted/40 border border-border/50">
              <span className="text-[10px] text-muted-foreground block font-medium">Quiet Hours End</span>
              <span className="text-lg font-bold font-mono text-foreground">
                {String(preferences?.quiet_hours_end ?? 8).padStart(2, "0")}:00
              </span>
            </div>
          </div>

          <p className="text-[11px] text-muted-foreground leading-relaxed">
            During quiet hours, routine interventions are silently collected in the notification center.
            <strong> Critical deadline warnings (&lt; 2h remaining) always bypass quiet hours.</strong>
          </p>
        </div>

        {/* Category Toggles (User Sovereignty) */}
        <div className="p-5 rounded-2xl border border-border/70 bg-card shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
              <Sliders className="h-4 w-4 text-indigo-500" /> Category Toggles (User Sovereignty)
            </span>
          </div>

          <div className="space-y-1.5 text-xs">
            {preferences &&
              Object.entries(preferences.enabled_categories).map(([catKey, isEnabled]) => (
                <label
                  key={catKey}
                  className="flex items-center justify-between p-2.5 rounded-xl bg-muted/30 border border-border/50 cursor-pointer hover:bg-muted/50 transition-colors"
                >
                  <div>
                    <span className="font-semibold text-foreground block text-xs">
                      {catKey.replace(/_/g, " ").toLowerCase()}
                    </span>
                  </div>
                  <input
                    type="checkbox"
                    checked={isEnabled}
                    onChange={() => handleToggleCategory(catKey)}
                    className="rounded border-border text-indigo-600 focus:ring-indigo-500"
                  />
                </label>
              ))}
          </div>
        </div>
      </div>

      {/* Notification Delivery History Log */}
      <div className="p-5 rounded-2xl border border-border/70 bg-card shadow-xs space-y-3">
        <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
          Recent Notification Delivery Log
        </h3>

        {history.length === 0 ? (
          <p className="text-xs text-muted-foreground py-4 text-center">No recent notification history.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-border/60 text-muted-foreground font-semibold">
                  <th className="py-2 px-3">Timestamp</th>
                  <th className="py-2 px-3">Title</th>
                  <th className="py-2 px-3">Category</th>
                  <th className="py-2 px-3">Priority</th>
                  <th className="py-2 px-3">Strategy</th>
                  <th className="py-2 px-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40 font-mono">
                {history.slice(0, 15).map((item) => (
                  <tr key={item.id} className="hover:bg-muted/30">
                    <td className="py-2 px-3 text-muted-foreground">
                      {new Date(item.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </td>
                    <td className="py-2 px-3 font-sans font-bold text-foreground">{item.title}</td>
                    <td className="py-2 px-3 text-[10px] text-muted-foreground">{item.category}</td>
                    <td className="py-2 px-3 text-[10px] uppercase font-bold">{item.priority}</td>
                    <td className="py-2 px-3 text-[10px] text-indigo-600 dark:text-indigo-400">
                      {item.delivery_strategy}
                    </td>
                    <td className="py-2 px-3 text-[10px]">
                      {item.is_dismissed ? "Dismissed" : item.is_read ? "Read" : item.is_delivered ? "Delivered" : "Deferred"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

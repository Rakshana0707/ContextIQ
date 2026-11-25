"use client";

import { useEffect, useState, useRef } from "react";
import {
  Bell,
  Check,
  X,
  Sliders,
  Activity,
  Moon,
  Clock,
  ShieldAlert,
  Flame,
  PauseCircle,
  PlayCircle,
  Sparkles,
} from "lucide-react";
import {
  adaptiveApi,
  UserNotificationItem,
  UserNotificationPreference,
  NotificationMetrics,
} from "@/lib/api/services/adaptive";

export function NotificationCenter() {
  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<"notifications" | "preferences" | "metrics">("notifications");
  const [notifications, setNotifications] = useState<UserNotificationItem[]>([]);
  const [preferences, setPreferences] = useState<UserNotificationPreference | null>(null);
  const [metrics, setMetrics] = useState<NotificationMetrics | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [filterUnread, setFilterUnread] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  const fetchNotifications = async () => {
    setIsLoading(true);
    try {
      const res = await adaptiveApi.getNotifications({ unread_only: filterUnread, limit: 30 });
      if (res.data) setNotifications(res.data);
    } catch {
      // Non-blocking failover
    } finally {
      setIsLoading(false);
    }
  };

  const fetchPreferencesAndMetrics = async () => {
    try {
      const [prefRes, metRes] = await Promise.all([
        adaptiveApi.getNotificationPreferences(),
        adaptiveApi.getNotificationMetrics(),
      ]);
      if (prefRes.data) setPreferences(prefRes.data);
      if (metRes.data) setMetrics(metRes.data);
    } catch {
      // Failover gracefully
    }
  };

  useEffect(() => {
    fetchNotifications();
    fetchPreferencesAndMetrics();
    const interval = setInterval(() => {
      fetchNotifications();
    }, 45000);
    return () => clearInterval(interval);
  }, [filterUnread]);

  // Close when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  const handleAcknowledge = async (id: string) => {
    try {
      await adaptiveApi.acknowledgeNotification(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
      fetchPreferencesAndMetrics();
    } catch {
      // Ignore
    }
  };

  const handleDismiss = async (id: string) => {
    try {
      await adaptiveApi.dismissNotification(id, "Dismissed via UI tray", 2);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_dismissed: true } : n))
      );
      fetchPreferencesAndMetrics();
    } catch {
      // Ignore
    }
  };

  const handleToggleCategory = async (categoryKey: string) => {
    if (!preferences) return;
    const updated = {
      ...preferences.enabled_categories,
      [categoryKey]: !preferences.enabled_categories[categoryKey],
    };
    try {
      const res = await adaptiveApi.updateNotificationPreferences({
        enabled_categories: updated,
      });
      if (res.data) setPreferences(res.data);
    } catch {
      // Ignore
    }
  };

  const handleTogglePause = async () => {
    if (!preferences) return;
    try {
      const res = await adaptiveApi.updateNotificationPreferences({
        is_paused: !preferences.is_paused,
        pause_duration_minutes: 60,
      });
      if (res.data) setPreferences(res.data);
    } catch {
      // Ignore
    }
  };

  const unreadCount = notifications.filter((n) => !n.is_read && !n.is_dismissed).length;

  const getPriorityBadgeClass = (priority: string) => {
    switch (priority) {
      case "CRITICAL":
        return "bg-rose-500/15 text-rose-600 dark:text-rose-400 border-rose-500/30";
      case "HIGH":
        return "bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30";
      case "MEDIUM":
        return "bg-indigo-500/15 text-indigo-600 dark:text-indigo-400 border-indigo-500/30";
      default:
        return "bg-muted text-muted-foreground border-border/50";
    }
  };

  return (
    <div className="relative" ref={panelRef}>
      {/* Trigger Bell Button */}
      <button
        type="button"
        onClick={() => {
          setIsOpen((prev) => !prev);
          if (!isOpen) {
            fetchNotifications();
            fetchPreferencesAndMetrics();
          }
        }}
        className="relative flex items-center justify-center h-8 w-8 rounded-full border border-border/80 bg-background/80 hover:bg-muted text-foreground transition-all shadow-2xs"
        title="Cognitive Notification Center"
        aria-label="Notification Center"
      >
        <Bell className="h-4 w-4" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 flex h-4 min-w-[16px] px-1 items-center justify-center rounded-full bg-rose-500 text-[10px] font-bold text-white shadow-xs">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {/* Popover Panel */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-96 max-w-[calc(100vw-2rem)] rounded-2xl border border-border/80 bg-background/95 backdrop-blur-xl shadow-xl z-50 animate-fade-in flex flex-col overflow-hidden max-h-[580px]">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-border/60 bg-muted/40">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-indigo-500" />
              <span className="font-bold text-xs text-foreground">Cognitive Shield Center</span>
            </div>
            {preferences?.is_paused ? (
              <span className="text-[10px] font-semibold text-amber-600 dark:text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/20 flex items-center gap-1">
                <PauseCircle className="h-3 w-3" /> Paused
              </span>
            ) : metrics?.active_quiet_hours ? (
              <span className="text-[10px] font-semibold text-indigo-600 dark:text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded-full border border-indigo-500/20 flex items-center gap-1">
                <Moon className="h-3 w-3" /> Quiet Hours
              </span>
            ) : (
              <span className="text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                Active
              </span>
            )}
          </div>

          {/* Navigation Tabs */}
          <div className="flex items-center border-b border-border/50 bg-muted/20 px-3 py-1.5 gap-1 text-xs">
            <button
              type="button"
              onClick={() => setActiveTab("notifications")}
              className={`px-3 py-1 rounded-lg font-semibold transition-all ${
                activeTab === "notifications"
                  ? "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Notifications ({notifications.filter((n) => !n.is_dismissed).length})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("preferences")}
              className={`px-3 py-1 rounded-lg font-semibold transition-all flex items-center gap-1 ${
                activeTab === "preferences"
                  ? "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Sliders className="h-3 w-3" /> Controls
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("metrics")}
              className={`px-3 py-1 rounded-lg font-semibold transition-all flex items-center gap-1 ${
                activeTab === "metrics"
                  ? "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Activity className="h-3 w-3" /> Fatigue
            </button>
          </div>

          {/* Content Area */}
          <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
            {activeTab === "notifications" && (
              <>
                <div className="flex items-center justify-between text-[11px] text-muted-foreground pb-1">
                  <label className="flex items-center gap-1.5 cursor-pointer font-medium">
                    <input
                      type="checkbox"
                      checked={filterUnread}
                      onChange={(e) => setFilterUnread(e.target.checked)}
                      className="rounded border-border"
                    />
                    Unread only
                  </label>
                  <span>{unreadCount} pending action</span>
                </div>

                {isLoading && notifications.length === 0 ? (
                  <div className="py-8 text-center text-xs text-muted-foreground">Loading notifications...</div>
                ) : notifications.filter((n) => !n.is_dismissed).length === 0 ? (
                  <div className="py-10 text-center space-y-2">
                    <div className="flex h-10 w-10 mx-auto items-center justify-center rounded-full bg-emerald-500/10 text-emerald-500">
                      <Check className="h-5 w-5" />
                    </div>
                    <p className="text-xs font-semibold text-foreground">All Clear!</p>
                    <p className="text-[11px] text-muted-foreground max-w-[200px] mx-auto">
                      No disruptive interruptions. Focus momentum protected.
                    </p>
                  </div>
                ) : (
                  notifications
                    .filter((n) => !n.is_dismissed)
                    .map((item) => (
                      <div
                        key={item.id}
                        className={`p-3 rounded-xl border transition-all text-xs space-y-1.5 ${
                          item.is_read
                            ? "bg-muted/30 border-border/60 opacity-80"
                            : "bg-card border-indigo-500/30 shadow-xs"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span
                            className={`text-[9px] font-bold px-1.5 py-0.5 rounded border uppercase ${getPriorityBadgeClass(
                              item.priority
                            )}`}
                          >
                            {item.priority}
                          </span>
                          <span className="text-[10px] text-muted-foreground font-mono">
                            {new Date(item.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                          </span>
                        </div>

                        <div>
                          <h4 className="font-bold text-foreground text-xs leading-tight">{item.title}</h4>
                          <p className="text-[11px] text-muted-foreground mt-0.5 leading-relaxed">{item.message}</p>
                        </div>

                        <div className="flex items-center justify-between pt-1 border-t border-border/40">
                          <span className="text-[10px] font-mono text-muted-foreground">
                            {item.delivery_strategy.toLowerCase().replace(/_/g, " ")}
                          </span>
                          <div className="flex items-center gap-1.5">
                            {!item.is_read && (
                              <button
                                type="button"
                                onClick={() => handleAcknowledge(item.id)}
                                className="px-2 py-0.5 rounded-md bg-indigo-50 dark:bg-indigo-950/60 hover:bg-indigo-100 text-indigo-600 dark:text-indigo-400 font-semibold text-[10px] flex items-center gap-1 transition-colors"
                              >
                                <Check className="h-3 w-3" /> Acknowledge
                              </button>
                            )}
                            <button
                              type="button"
                              onClick={() => handleDismiss(item.id)}
                              className="p-1 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                              title="Dismiss"
                            >
                              <X className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </div>
                      </div>
                    ))
                )}
              </>
            )}

            {activeTab === "preferences" && preferences && (
              <div className="space-y-3 text-xs">
                {/* Pause Button */}
                <div className="p-3 rounded-xl border border-border/70 bg-muted/30 flex items-center justify-between">
                  <div>
                    <span className="font-bold text-foreground block">Pause Notifications</span>
                    <span className="text-[10px] text-muted-foreground">
                      {preferences.is_paused ? "Currently paused for 60 min" : "Temporarily pause all non-critical alerts"}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={handleTogglePause}
                    className={`px-3 py-1 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 ${
                      preferences.is_paused
                        ? "bg-emerald-600 text-white hover:bg-emerald-700"
                        : "bg-amber-600 text-white hover:bg-amber-700"
                    }`}
                  >
                    {preferences.is_paused ? <PlayCircle className="h-3.5 w-3.5" /> : <PauseCircle className="h-3.5 w-3.5" />}
                    {preferences.is_paused ? "Resume" : "Pause 1h"}
                  </button>
                </div>

                {/* Quiet Hours */}
                <div className="p-3 rounded-xl border border-border/70 bg-muted/30 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-foreground flex items-center gap-1.5">
                      <Moon className="h-3.5 w-3.5 text-indigo-500" /> Quiet Hours
                    </span>
                    <span className="text-[11px] font-mono text-muted-foreground">
                      {String(preferences.quiet_hours_start).padStart(2, "0")}:00 –{" "}
                      {String(preferences.quiet_hours_end).padStart(2, "0")}:00
                    </span>
                  </div>
                  <p className="text-[10px] text-muted-foreground">
                    Only critical deadline reminders will notify you during quiet hours.
                  </p>
                </div>

                {/* Frequency Caps */}
                <div className="p-3 rounded-xl border border-border/70 bg-muted/30 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-foreground flex items-center gap-1.5">
                      <Clock className="h-3.5 w-3.5 text-indigo-500" /> Hourly & Daily Caps
                    </span>
                    <span className="text-[11px] font-mono text-muted-foreground">
                      Max {preferences.max_notifications_per_hour}/hr · {preferences.max_notifications_per_day}/day
                    </span>
                  </div>
                </div>

                {/* Category Toggles */}
                <div className="space-y-1.5 pt-1">
                  <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block">
                    Enabled Categories
                  </span>
                  {Object.entries(preferences.enabled_categories).map(([catKey, isEnabled]) => (
                    <label
                      key={catKey}
                      className="flex items-center justify-between p-2 rounded-lg bg-card border border-border/50 cursor-pointer hover:bg-muted/40 transition-colors"
                    >
                      <span className="text-[11px] font-medium text-foreground">
                        {catKey.replace(/_/g, " ").toLowerCase()}
                      </span>
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
            )}

            {activeTab === "metrics" && metrics && (
              <div className="space-y-3 text-xs">
                {/* Fatigue Gauge */}
                <div className="p-3 rounded-xl border border-border/70 bg-muted/30 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-foreground flex items-center gap-1.5">
                      <Flame className="h-3.5 w-3.5 text-amber-500" /> Cognitive Fatigue Score
                    </span>
                    <span className="text-xs font-mono font-bold text-foreground">
                      {(metrics.fatigue_score * 100).toFixed(0)}% ({metrics.fatigue_level})
                    </span>
                  </div>

                  {/* Progress bar */}
                  <div className="w-full h-2 rounded-full bg-border overflow-hidden">
                    <div
                      className={`h-full transition-all rounded-full ${
                        metrics.fatigue_score >= 0.70
                          ? "bg-rose-500"
                          : metrics.fatigue_score >= 0.40
                          ? "bg-amber-500"
                          : "bg-emerald-500"
                      }`}
                      style={{ width: `${Math.min(100, Math.max(5, metrics.fatigue_score * 100))}%` }}
                    />
                  </div>
                  <p className="text-[10px] text-muted-foreground leading-relaxed">
                    {metrics.disclaimer}
                  </p>
                </div>

                {/* 7-Day Stats */}
                <div className="grid grid-cols-2 gap-2">
                  <div className="p-2.5 rounded-xl border border-border/60 bg-card text-center">
                    <span className="text-[10px] text-muted-foreground block font-medium">Presented (7d)</span>
                    <span className="text-base font-bold text-foreground font-mono">{metrics.total_presented_7d}</span>
                  </div>
                  <div className="p-2.5 rounded-xl border border-border/60 bg-card text-center">
                    <span className="text-[10px] text-muted-foreground block font-medium">Acceptance Rate</span>
                    <span className="text-base font-bold text-foreground font-mono">
                      {(metrics.acceptance_rate_7d * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="p-2.5 rounded-xl border border-border/60 bg-card text-center">
                    <span className="text-[10px] text-muted-foreground block font-medium">Dismissed (7d)</span>
                    <span className="text-base font-bold text-foreground font-mono">{metrics.total_dismissed_7d}</span>
                  </div>
                  <div className="p-2.5 rounded-xl border border-border/60 bg-card text-center">
                    <span className="text-[10px] text-muted-foreground block font-medium">Consecutive Dismissals</span>
                    <span className="text-base font-bold text-foreground font-mono">{metrics.consecutive_dismissals}</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

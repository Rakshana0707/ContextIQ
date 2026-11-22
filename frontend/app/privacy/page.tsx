"use client";

import { useEffect, useState } from "react";
import {
  ShieldCheck,
  ShieldAlert,
  ShieldOff,
  PauseCircle,
  PlayCircle,
  Clock,
  Trash2,
  PlusCircle,
  CheckCircle2,
  AlertTriangle,
  History,
  Lock,
  EyeOff,
  Database,
  RefreshCw,
  Server,
  Smartphone,
  Info,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  privacyApi,
  TelemetryConsent,
  PrivacySettings,
  AppExclusion,
  TelemetryCategory,
  TelemetryMetadataSummary,
} from "@/lib/api/services/privacy";

const ALL_CATEGORIES: { id: TelemetryCategory; label: string; description: string }[] = [
  {
    id: "APP_TRANSITIONS",
    label: "Active Application Transitions",
    description: "Detects switches between primary desktop windows and focus dwell times.",
  },
  {
    id: "INACTIVITY_DETECTION",
    label: "Inactivity & Idle Detection",
    description: "Monitors periods of no user input without capturing keystroke or mouse details.",
  },
  {
    id: "SESSION_RECONSTRUCTION",
    label: "Session Reconstruction",
    description: "Synthesizes raw focus transitions into contiguous task and work sessions.",
  },
  {
    id: "BEHAVIORAL_ANALYTICS",
    label: "Behavioral & Forgetting Analytics",
    description: "Computes cognitive recovery lag, context switch counts, and forget risk features.",
  },
  {
    id: "LOCAL_STORAGE",
    label: "Offline Local Event Storage",
    description: "Buffers encrypted telemetry in local SQLite database for offline resilience.",
  },
  {
    id: "SERVER_SYNC",
    label: "Server Batch Synchronization",
    description: "Batched, encrypted HTTPS synchronization to the ContextIQ backend.",
  },
];

export default function PrivacySettingsPage() {
  const [loading, setLoading] = useState(true);
  const [activeConsent, setActiveConsent] = useState<TelemetryConsent | null>(null);
  const [settings, setSettings] = useState<PrivacySettings | null>(null);
  const [exclusions, setExclusions] = useState<AppExclusion[]>([]);
  const [history, setHistory] = useState<TelemetryConsent[]>([]);
  const [metadata, setMetadata] = useState<TelemetryMetadataSummary | null>(null);

  // Forms & Inputs
  const [selectedCategories, setSelectedCategories] = useState<TelemetryCategory[]>([]);
  const [newAppInput, setNewAppInput] = useState("");
  const [newAppDesc, setNewAppDesc] = useState("");
  const [retentionDays, setRetentionDays] = useState(30);
  const [purgeConfirmation, setPurgeConfirmation] = useState("");
  const [purgeModalOpen, setPurgeModalOpen] = useState(false);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);

  useEffect(() => {
    loadPrivacyState();
  }, []);

  const loadPrivacyState = async () => {
    setLoading(true);
    try {
      const [consentRes, settingsRes, exclusionsRes, historyRes, metaRes] = await Promise.all([
        privacyApi.getConsent(),
        privacyApi.getSettings(),
        privacyApi.getExclusions(),
        privacyApi.getConsentHistory(),
        privacyApi.getMetadata(),
      ]);
      setActiveConsent(consentRes);
      setSettings(settingsRes);
      setExclusions(exclusionsRes || []);
      setHistory(historyRes || []);
      setMetadata(metaRes);

      if (consentRes?.enabled_categories) {
        setSelectedCategories(consentRes.enabled_categories as TelemetryCategory[]);
      } else {
        setSelectedCategories([
          "APP_TRANSITIONS",
          "INACTIVITY_DETECTION",
          "SESSION_RECONSTRUCTION",
          "BEHAVIORAL_ANALYTICS",
          "LOCAL_STORAGE",
          "SERVER_SYNC",
        ]);
      }
      if (settingsRes?.raw_event_retention_days) {
        setRetentionDays(settingsRes.raw_event_retention_days);
      }
    } catch {
      // Fallback in case backend is offline or mock mode
      setActiveConsent(null);
      setSettings({
        user_id: "demo-user",
        is_paused: false,
        raw_event_retention_days: 30,
        aggregated_metric_retention_days: 365,
        allow_anonymized_research: false,
        updated_at: new Date().toISOString(),
      });
    } finally {
      setLoading(false);
    }
  };

  const showNotification = (msg: string) => {
    setFeedbackMessage(msg);
    setTimeout(() => setFeedbackMessage(null), 4000);
  };

  const toggleCategory = (cat: TelemetryCategory) => {
    setSelectedCategories((prev) =>
      prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat]
    );
  };

  const handleGrantConsent = async () => {
    if (selectedCategories.length === 0) {
      showNotification("Please select at least one collection category.");
      return;
    }
    try {
      const updated = await privacyApi.grantConsent({
        consent_version: "1.0.0",
        enabled_categories: selectedCategories,
        device_id: "desktop_primary",
      });
      setActiveConsent(updated);
      showNotification("Telemetry consent successfully updated and logged.");
      loadPrivacyState();
    } catch {
      showNotification("Failed to update consent. Please verify connection.");
    }
  };

  const handleRevokeConsent = async () => {
    try {
      const revoked = await privacyApi.revokeConsent({
        reason: "User revoked consent via privacy settings",
      });
      setActiveConsent(revoked);
      showNotification("Telemetry consent revoked. Collection has ceased.");
      loadPrivacyState();
    } catch {
      showNotification("Failed to revoke consent.");
    }
  };

  const handlePause = async (minutes: number) => {
    try {
      const updated = await privacyApi.updateSettings({
        is_paused: true,
        pause_duration_minutes: minutes,
      });
      setSettings(updated);
      showNotification(`Monitoring paused for ${minutes} minutes.`);
      loadPrivacyState();
    } catch {
      showNotification("Failed to pause monitoring.");
    }
  };

  const handleResume = async () => {
    try {
      const updated = await privacyApi.updateSettings({ is_paused: false });
      setSettings(updated);
      showNotification("Monitoring manually resumed.");
      loadPrivacyState();
    } catch {
      showNotification("Failed to resume monitoring.");
    }
  };

  const handleAddExclusion = async () => {
    const app = newAppInput.trim().toLowerCase();
    if (!app) return;
    try {
      await privacyApi.addExclusion({
        application_identifier: app,
        description: newAppDesc.trim() || undefined,
      });
      setNewAppInput("");
      setNewAppDesc("");
      showNotification(`Added '${app}' to privacy exclusion list.`);
      loadPrivacyState();
    } catch {
      showNotification(`Could not add '${app}' (may already be excluded).`);
    }
  };

  const handleRemoveExclusion = async (id: string) => {
    try {
      await privacyApi.removeExclusion(id);
      showNotification("Exclusion removed.");
      loadPrivacyState();
    } catch {
      showNotification("Failed to remove exclusion.");
    }
  };

  const handleSaveRetention = async () => {
    try {
      const updated = await privacyApi.updateSettings({
        raw_event_retention_days: Number(retentionDays),
      });
      setSettings(updated);
      showNotification(`Raw telemetry retention set to ${retentionDays} days.`);
    } catch {
      showNotification("Failed to update retention policy.");
    }
  };

  const handlePurgeData = async () => {
    if (purgeConfirmation !== "DELETE MY DATA") {
      showNotification("Confirmation phrase must be 'DELETE MY DATA'");
      return;
    }
    try {
      const res = await privacyApi.purgeData({
        purge_raw_telemetry: true,
        purge_context_sessions: true,
        confirmation_phrase: purgeConfirmation,
      });
      setPurgeModalOpen(false);
      setPurgeConfirmation("");
      showNotification(res.message);
      loadPrivacyState();
    } catch {
      showNotification("Failed to execute data purge.");
    }
  };

  const isConsentActive = activeConsent?.consent_status === "GRANTED";
  const isPaused = settings?.is_paused;

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-12 animate-fade-in">
      {/* Top Banner Message */}
      {feedbackMessage && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-xl border border-primary/40 bg-background/95 px-4 py-2.5 text-xs font-semibold shadow-lg backdrop-blur animate-slide-up text-foreground">
          <CheckCircle2 className="h-4 w-4 text-emerald-500" />
          {feedbackMessage}
        </div>
      )}

      {/* Hero: Privacy & Monitoring Cockpit */}
      <Card className="glass-card overflow-hidden border-border/80 shadow-md">
        <div className="h-[3px] bg-gradient-to-r from-emerald-500 via-teal-400 to-indigo-500" />
        <CardHeader className="p-6 pb-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2.5">
                <ShieldCheck className="h-6 w-6 text-emerald-600 dark:text-emerald-400" />
                <CardTitle className="text-xl font-bold tracking-tight text-foreground">
                  Privacy & Telemetry Controls
                </CardTitle>
                <Badge
                  variant={isConsentActive && !isPaused ? "default" : isPaused ? "outline" : "destructive"}
                  className="font-mono text-[11px] uppercase tracking-wider"
                >
                  {isConsentActive && !isPaused
                    ? "Active & Monitored"
                    : isPaused
                    ? "Collection Paused"
                    : "Monitoring Disabled"}
                </Badge>
              </div>
              <CardDescription className="text-xs text-muted-foreground max-w-2xl">
                ContextIQ operates on strict privacy-by-design principles. Telemetry is 100% opt-in,
                granularly configurable, excludes private tools, and never captures keystrokes or screen contents.
              </CardDescription>
            </div>

            {/* Quick Pause / Resume Controls */}
            <div className="flex items-center gap-2">
              {isConsentActive && !isPaused && (
                <div className="flex items-center gap-1.5 bg-muted/40 p-1 rounded-xl border border-border/80">
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-8 text-xs px-2.5 hover:bg-amber-500/10 hover:text-amber-600"
                    onClick={() => handlePause(60)}
                  >
                    <PauseCircle className="mr-1 h-3.5 w-3.5 text-amber-500" />
                    Pause 1h
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-8 text-xs px-2.5 hover:bg-amber-500/10 hover:text-amber-600"
                    onClick={() => handlePause(240)}
                  >
                    <PauseCircle className="mr-1 h-3.5 w-3.5 text-amber-500" />
                    Pause 4h
                  </Button>
                </div>
              )}

              {isPaused && (
                <Button
                  size="sm"
                  className="h-8 text-xs bg-emerald-600 hover:bg-emerald-700 text-white gap-1.5 shadow-sm"
                  onClick={handleResume}
                >
                  <PlayCircle className="h-4 w-4" />
                  Resume Monitoring
                </Button>
              )}
            </div>
          </div>
        </CardHeader>

        <CardContent className="p-6 pt-2">
          {/* Status Metrics Bar */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
            <div className="rounded-xl border border-border/70 bg-background/60 p-3 space-y-1">
              <span className="text-[10px] uppercase font-mono font-bold tracking-wider text-muted-foreground flex items-center gap-1.5">
                <Database className="h-3 w-3 text-indigo-500" /> Raw Events Stored
              </span>
              <p className="text-lg font-bold font-mono text-foreground">
                {metadata?.total_raw_events ?? 0}
              </p>
            </div>

            <div className="rounded-xl border border-border/70 bg-background/60 p-3 space-y-1">
              <span className="text-[10px] uppercase font-mono font-bold tracking-wider text-muted-foreground flex items-center gap-1.5">
                <EyeOff className="h-3 w-3 text-rose-500" /> Excluded Apps
              </span>
              <p className="text-lg font-bold font-mono text-foreground">
                {exclusions.length} apps
              </p>
            </div>

            <div className="rounded-xl border border-border/70 bg-background/60 p-3 space-y-1">
              <span className="text-[10px] uppercase font-mono font-bold tracking-wider text-muted-foreground flex items-center gap-1.5">
                <Clock className="h-3 w-3 text-amber-500" /> Raw Retention
              </span>
              <p className="text-lg font-bold font-mono text-foreground">
                {settings?.raw_event_retention_days ?? 30} days
              </p>
            </div>

            <div className="rounded-xl border border-border/70 bg-background/60 p-3 space-y-1">
              <span className="text-[10px] uppercase font-mono font-bold tracking-wider text-muted-foreground flex items-center gap-1.5">
                <History className="h-3 w-3 text-teal-500" /> Consent Version
              </span>
              <p className="text-lg font-bold font-mono text-foreground">
                v{activeConsent?.consent_version ?? "None"}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Main Grid: Consent Matrix & Application Exclusions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Granular Consent Categories */}
        <Card className="lg:col-span-2 glass-card border-border/80 shadow-xs">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-bold text-foreground flex items-center gap-2">
              <Lock className="h-4 w-4 text-indigo-500" />
              Granular Telemetry Collection Consent
            </CardTitle>
            <CardDescription className="text-xs text-muted-foreground">
              Select which categories of behavioral telemetry you consent to collect. You can update or revoke this anytime.
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-4">
            <div className="space-y-2.5">
              {ALL_CATEGORIES.map((cat) => {
                const checked = selectedCategories.includes(cat.id);
                return (
                  <div
                    key={cat.id}
                    onClick={() => toggleCategory(cat.id)}
                    className={`flex items-start gap-3 p-3 rounded-xl border transition-all cursor-pointer ${
                      checked
                        ? "border-primary/50 bg-primary/5 dark:bg-primary/10"
                        : "border-border/70 bg-background/40 hover:border-border hover:bg-muted/30"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => {}}
                      className="mt-1 h-4 w-4 rounded border-border text-primary focus:ring-primary/40 cursor-pointer"
                    />
                    <div className="flex-1 space-y-0.5">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-foreground">{cat.label}</span>
                        <span className="text-[10px] font-mono text-muted-foreground">{cat.id}</span>
                      </div>
                      <p className="text-[11px] text-muted-foreground leading-relaxed">
                        {cat.description}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="flex items-center justify-between pt-3 border-t border-border/70">
              <Button
                variant="destructive"
                size="sm"
                className="h-8 text-xs font-semibold"
                disabled={!isConsentActive}
                onClick={handleRevokeConsent}
              >
                <ShieldOff className="mr-1.5 h-3.5 w-3.5" />
                Revoke All Consent
              </Button>

              <Button
                variant="default"
                size="sm"
                className="h-8 text-xs font-semibold bg-primary hover:bg-primary/90 text-primary-foreground shadow-xs"
                onClick={handleGrantConsent}
              >
                <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" />
                Save & Grant Consent
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Right Column: Application Exclusion Blacklist */}
        <Card className="glass-card border-border/80 shadow-xs flex flex-col">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-bold text-foreground flex items-center gap-2">
              <EyeOff className="h-4 w-4 text-rose-500" />
              Application Exclusions
            </CardTitle>
            <CardDescription className="text-xs text-muted-foreground">
              Add desktop processes to immediately blackout from collection (zero identity, duration, or transition tracking).
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-4 flex-1 flex flex-col">
            {/* Add Application Form */}
            <div className="space-y-2 p-3 rounded-xl border border-border/80 bg-background/50">
              <span className="text-[11px] font-semibold text-foreground">Exclude Process:</span>
              <Input
                placeholder="e.g. 1password.exe, whatsapp.exe"
                value={newAppInput}
                onChange={(e) => setNewAppInput(e.target.value)}
                className="h-8 text-xs"
              />
              <Input
                placeholder="Optional description (e.g. Password Vault)"
                value={newAppDesc}
                onChange={(e) => setNewAppDesc(e.target.value)}
                className="h-8 text-xs"
              />
              <Button
                size="sm"
                className="w-full h-8 text-xs font-semibold bg-foreground/10 hover:bg-foreground/15 text-foreground"
                onClick={handleAddExclusion}
              >
                <PlusCircle className="mr-1.5 h-3.5 w-3.5" />
                Add to Exclusion List
              </Button>
            </div>

            {/* List of Excluded Applications */}
            <div className="space-y-1.5 flex-1 overflow-y-auto max-h-[260px] pr-1">
              {exclusions.length === 0 ? (
                <div className="text-center py-6 text-xs text-muted-foreground space-y-1">
                  <ShieldCheck className="h-6 w-6 mx-auto text-muted-foreground/60" />
                  <p>No custom exclusions configured.</p>
                  <p className="text-[10px]">Global password managers are blocked by default.</p>
                </div>
              ) : (
                exclusions.map((app) => (
                  <div
                    key={app.id}
                    className="flex items-center justify-between p-2 rounded-lg border border-border/60 bg-background/70 text-xs"
                  >
                    <div>
                      <span className="font-mono font-semibold text-foreground">
                        {app.application_identifier}
                      </span>
                      {app.description && (
                        <p className="text-[10px] text-muted-foreground">{app.description}</p>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRemoveExclusion(app.id)}
                      className="text-muted-foreground hover:text-rose-500 p-1 transition-colors"
                      title="Remove exclusion"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Retention Management & GDPR Article 17 Erasure */}
      <Card className="glass-card border-border/80 shadow-xs">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-bold text-foreground flex items-center gap-2">
            <Database className="h-4 w-4 text-teal-500" />
            Data Retention & Right to Erasure (GDPR)
          </CardTitle>
          <CardDescription className="text-xs text-muted-foreground">
            Configure how long granular raw desktop transitions are stored before automated expiration, or request an immediate purge.
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 items-center">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-foreground flex items-center justify-between">
                <span>Raw Event Retention Limit:</span>
                <span className="font-mono text-primary font-bold">{retentionDays} Days</span>
              </label>
              <input
                type="range"
                min="1"
                max="90"
                step="1"
                value={retentionDays}
                onChange={(e) => setRetentionDays(Number(e.target.value))}
                className="w-full accent-primary h-1.5 bg-muted rounded-lg appearance-none cursor-pointer"
              />
              <span className="text-[10px] text-muted-foreground block">
                Events older than {retentionDays} days are permanently deleted during nightly sweeps.
              </span>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2 sm:pt-0">
              <Button size="sm" variant="outline" className="h-8 text-xs" onClick={handleSaveRetention}>
                Update Retention Policy
              </Button>

              <Button
                size="sm"
                variant="destructive"
                className="h-8 text-xs font-semibold"
                onClick={() => setPurgeModalOpen(true)}
              >
                <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                Purge All Telemetry
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Confirmation Modal for Data Purge */}
      {purgeModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-fade-in">
          <div className="bg-card border border-destructive/40 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-xl">
            <div className="flex items-center gap-3 text-destructive">
              <AlertTriangle className="h-6 w-6" />
              <h3 className="text-lg font-bold text-foreground">Permanently Delete Telemetry?</h3>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              This action executes your <strong>GDPR Article 17 Right to Erasure</strong>. All raw desktop focus
              transitions and derived context sessions will be permanently purged from the database.
            </p>
            <div className="space-y-1.5">
              <span className="text-[11px] font-semibold text-foreground">
                Type <strong className="text-destructive font-mono">DELETE MY DATA</strong> to confirm:
              </span>
              <Input
                placeholder="DELETE MY DATA"
                value={purgeConfirmation}
                onChange={(e) => setPurgeConfirmation(e.target.value)}
                className="h-9 text-xs font-mono"
              />
            </div>
            <div className="flex items-center justify-end gap-2 pt-2">
              <Button
                variant="ghost"
                size="sm"
                className="h-8 text-xs"
                onClick={() => setPurgeModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                size="sm"
                className="h-8 text-xs font-semibold"
                disabled={purgeConfirmation !== "DELETE MY DATA"}
                onClick={handlePurgeData}
              >
                Confirm Permanent Deletion
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Auditable Consent History Trail */}
      <Card className="glass-card border-border/80 shadow-xs">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-bold text-foreground flex items-center gap-2">
            <History className="h-4 w-4 text-indigo-500" />
            Auditable Consent History Trail
          </CardTitle>
          <CardDescription className="text-xs text-muted-foreground">
            Complete regulatory audit log showing all granted, modified, and revoked consent records. Historical records are immutable.
          </CardDescription>
        </CardHeader>

        <CardContent>
          <div className="space-y-2">
            {history.length === 0 ? (
              <p className="text-xs text-muted-foreground py-4 text-center">
                No consent history records on file.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead>
                    <tr className="border-b border-border text-[11px] font-mono text-muted-foreground">
                      <th className="pb-2">Version</th>
                      <th className="pb-2">Status</th>
                      <th className="pb-2">Active Categories</th>
                      <th className="pb-2">Granted Timestamp</th>
                      <th className="pb-2">Revoked Timestamp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {history.map((record) => (
                      <tr key={record.id} className="text-foreground">
                        <td className="py-2.5 font-mono font-semibold">v{record.consent_version}</td>
                        <td className="py-2.5">
                          <Badge
                            variant={record.consent_status === "GRANTED" ? "default" : "destructive"}
                            className="font-mono text-[9px]"
                          >
                            {record.consent_status}
                          </Badge>
                        </td>
                        <td className="py-2.5 text-muted-foreground">
                          {record.enabled_categories?.join(", ") || "None"}
                        </td>
                        <td className="py-2.5 font-mono text-muted-foreground">
                          {new Date(record.granted_timestamp).toLocaleString()}
                        </td>
                        <td className="py-2.5 font-mono text-muted-foreground">
                          {record.revoked_timestamp
                            ? new Date(record.revoked_timestamp).toLocaleString()
                            : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

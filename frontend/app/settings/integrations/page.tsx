"use client";

import { useEffect, useState } from "react";
import {
  Calendar,
  CheckCircle2,
  RefreshCw,
  AlertCircle,
  ExternalLink,
  ShieldCheck,
  Unlink,
  Clock,
  KeyRound,
  ArrowRight,
  Info,
  Check,
  AlertTriangle,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  integrationsApi,
  IntegrationResponse,
  ConnectionStatus,
  SyncStatus,
} from "@/lib/api/services/integrations";
import { SyncHealthPanel } from "@/components/integrations/sync-health-panel";

interface ProviderConfig {
  id: string;
  name: string;
  description: string;
  iconBg: string;
  accentColor: string;
  defaultScopes: string[];
}

const PROVIDERS: ProviderConfig[] = [
  {
    id: "google_calendar",
    name: "Google Calendar",
    description: "Sync events, discover meeting blackouts, and protect your high-quality focus windows.",
    iconBg: "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20",
    accentColor: "border-red-500/30",
    defaultScopes: ["Read-only Calendar Events", "User Account Identity"],
  },
  {
    id: "microsoft_outlook",
    name: "Microsoft Outlook",
    description: "Connect Microsoft 365 or Outlook.com calendars to prevent interruptions during meetings.",
    iconBg: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20",
    accentColor: "border-blue-500/30",
    defaultScopes: ["Read-only Calendar Events", "Profile & Offline Access"],
  },
];

export default function IntegrationsSettingsPage() {
  const [integrations, setIntegrations] = useState<IntegrationResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const fetchIntegrations = async () => {
    try {
      setLoading(true);
      const data = await integrationsApi.listIntegrations();
      setIntegrations(data);
    } catch {
      setMessage({ type: "error", text: "Failed to load integration connections." });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIntegrations();
  }, []);

  const handleConnect = async (providerId: string) => {
    try {
      setActionLoading(`connect-${providerId}`);
      setMessage(null);
      const resp = await integrationsApi.connectProvider(providerId);
      // In production this redirects to resp.authorization_url; in dev/demo show URL or simulated connect
      if (resp.authorization_url.startsWith("http")) {
        window.location.href = resp.authorization_url;
      }
    } catch {
      setMessage({ type: "error", text: `Failed to initiate connection for ${providerId}.` });
      setActionLoading(null);
    }
  };

  const handleDisconnect = async (integrationId: string, providerName: string) => {
    if (!confirm(`Are you sure you want to disconnect ${providerName}? This will wipe stored credentials and stop meeting blackouts.`)) {
      return;
    }
    try {
      setActionLoading(`disconnect-${integrationId}`);
      setMessage(null);
      await integrationsApi.disconnectIntegration(integrationId);
      setMessage({ type: "success", text: `Successfully disconnected ${providerName}.` });
      await fetchIntegrations();
    } catch {
      setMessage({ type: "error", text: `Failed to disconnect ${providerName}.` });
    } finally {
      setActionLoading(null);
    }
  };

  const handleSyncNow = async (integrationId: string) => {
    try {
      setActionLoading(`sync-${integrationId}`);
      setMessage(null);
      const result = await integrationsApi.triggerSync(integrationId);
      if (result.success) {
        setMessage({
          type: "success",
          text: `Sync complete! Synced ${result.synced_events.length} events in ${result.sync_duration_ms}ms.`,
        });
      } else {
        setMessage({ type: "error", text: result.error_message || "Synchronization encountered an issue." });
      }
      await fetchIntegrations();
    } catch {
      setMessage({ type: "error", text: "Manual sync request failed." });
    } finally {
      setActionLoading(null);
    }
  };

  const formatLastSync = (timestamp?: string | null) => {
    if (!timestamp) return "Never synced";
    const date = new Date(timestamp);
    const diffMins = Math.round((Date.now() - date.getTime()) / 60000);
    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins} min ago`;
    const diffHours = Math.round(diffMins / 60);
    if (diffHours < 24) return `${diffHours} hr ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="space-y-8 p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20">
            <Calendar className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">Calendar Integrations</h1>
            <p className="text-xs text-muted-foreground">
              Connect external productivity ecosystems to discover meeting blackouts, prevent distractions, and align focus blocks.
            </p>
          </div>
        </div>
      </div>

      {/* Global Security / Privacy Banner */}
      <Card className="border-indigo-500/20 bg-indigo-50/40 dark:bg-indigo-950/20">
        <CardContent className="p-4 flex items-start gap-3">
          <ShieldCheck className="h-5 w-5 text-indigo-600 dark:text-indigo-400 shrink-0 mt-0.5" />
          <div className="text-xs space-y-1">
            <p className="font-semibold text-foreground">Zero-Trust & Privacy Invariant</p>
            <p className="text-muted-foreground leading-relaxed">
              ContextIQ requests minimal <strong>read-only</strong> permissions by default. All OAuth access and refresh tokens are encrypted at rest with AES-256-GCM. ContextIQ <strong>never</strong> modifies external meetings or exposes provider credentials to the browser.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Alert Messages */}
      {message && (
        <div
          className={`p-3.5 rounded-xl text-xs flex items-center justify-between border ${
            message.type === "success"
              ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-700 dark:text-emerald-400"
              : "bg-red-500/10 border-red-500/20 text-red-700 dark:text-red-400"
          }`}
        >
          <div className="flex items-center gap-2">
            {message.type === "success" ? <CheckCircle2 className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
            <span>{message.text}</span>
          </div>
          <button onClick={() => setMessage(null)} className="font-bold opacity-60 hover:opacity-100">
            ✕
          </button>
        </div>
      )}

      {/* Providers Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {PROVIDERS.map((provider) => {
          const connected = integrations.find(
            (i) => i.provider === provider.id && i.connection_status === "CONNECTED"
          );
          const isPending = actionLoading?.includes(provider.id);

          return (
            <Card
              key={provider.id}
              className={`transition-all duration-200 border ${
                connected ? "border-border shadow-xs bg-card" : "border-dashed border-border/80 bg-muted/20"
              }`}
            >
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className={`h-10 w-10 rounded-xl flex items-center justify-center border ${provider.iconBg}`}>
                      <Calendar className="h-5 w-5" />
                    </div>
                    <div>
                      <CardTitle className="text-base font-bold text-foreground">{provider.name}</CardTitle>
                      <CardDescription className="text-xs">{provider.description}</CardDescription>
                    </div>
                  </div>
                  <Badge
                    variant={connected ? "default" : "secondary"}
                    className={`text-[10px] font-mono uppercase tracking-wider ${
                      connected
                        ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
                        : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {connected ? "Connected" : "Not Linked"}
                  </Badge>
                </div>
              </CardHeader>

              <CardContent className="space-y-4 pt-1">
                {connected ? (
                  <>
                    <div className="rounded-lg bg-muted/40 p-3 space-y-2 border border-border/50 text-xs">
                      <div className="flex items-center justify-between text-muted-foreground">
                        <span className="flex items-center gap-1.5">
                          <KeyRound className="h-3.5 w-3.5" /> Account:
                        </span>
                        <span className="font-semibold text-foreground">
                          {connected.provider_email || "Authorized User"}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-muted-foreground">
                        <span className="flex items-center gap-1.5">
                          <Clock className="h-3.5 w-3.5" /> Last Sync:
                        </span>
                        <span className="font-mono text-foreground">{formatLastSync(connected.last_synced_at)}</span>
                      </div>
                      <div className="flex items-center justify-between text-muted-foreground">
                        <span className="flex items-center gap-1.5">
                          <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" /> Mode:
                        </span>
                        <span className="font-medium text-emerald-600 dark:text-emerald-400">
                          Two-Way Synchronization
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 pt-1">
                      <Button
                        size="sm"
                        variant="outline"
                        className="flex-1 text-xs font-semibold gap-1.5"
                        onClick={() => handleSyncNow(connected.id)}
                        disabled={!!actionLoading}
                      >
                        <RefreshCw
                          className={`h-3.5 w-3.5 ${actionLoading === `sync-${connected.id}` ? "animate-spin" : ""}`}
                        />
                        {actionLoading === `sync-${connected.id}` ? "Syncing..." : "Sync Now"}
                      </Button>
                      <Button
                        size="sm"
                        variant="destructive"
                        className="text-xs font-semibold gap-1.5"
                        onClick={() => handleDisconnect(connected.id, provider.name)}
                        disabled={!!actionLoading}
                      >
                        <Unlink className="h-3.5 w-3.5" />
                        Disconnect
                      </Button>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="rounded-lg bg-muted/20 p-3 space-y-1.5 border border-border/40 text-xs text-muted-foreground">
                      <p className="font-medium text-foreground">Permissions Requested:</p>
                      <ul className="space-y-1 pl-1">
                        {provider.defaultScopes.map((scope, idx) => (
                          <li key={idx} className="flex items-center gap-1.5 text-[11px]">
                            <Check className="h-3 w-3 text-indigo-500 shrink-0" />
                            <span>{scope}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    <Button
                      size="sm"
                      className="w-full text-xs font-semibold gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white"
                      onClick={() => handleConnect(provider.id)}
                      disabled={isPending}
                    >
                      <ArrowRight className="h-3.5 w-3.5" />
                      {isPending ? "Connecting..." : `Connect ${provider.name}`}
                    </Button>
                  </>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Synchronization Health Status Panel (Phase 5.9 Task 8) */}
      <SyncHealthPanel />

      {/* Two-Way Synchronization Details & Invariants */}
      <Card className="border-border/60">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Info className="h-4 w-4 text-indigo-500" />
            Two-Way Synchronization & Data Governance
          </CardTitle>
        </CardHeader>
        <CardContent className="text-xs text-muted-foreground space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="p-3 rounded-lg bg-muted/30 border border-border/40 space-y-1">
              <span className="font-semibold text-foreground block">Authoritative External Meetings</span>
              <p className="text-[11px] leading-relaxed">External meetings are strictly read-only and authoritative. ContextIQ never overwrites external team events.</p>
            </div>
            <div className="p-3 rounded-lg bg-muted/30 border border-border/40 space-y-1">
              <span className="font-semibold text-foreground block">ContextIQ Focus Blocks</span>
              <p className="text-[11px] leading-relaxed">Focus blocks created by ContextIQ are pushed to Google Calendar. If you adjust them in Google Calendar, ContextIQ adapts gracefully.</p>
            </div>
            <div className="p-3 rounded-lg bg-muted/30 border border-border/40 space-y-1">
              <span className="font-semibold text-foreground block">Differential Sync & Privacy</span>
              <p className="text-[11px] leading-relaxed">Uses Google syncToken caching for efficient delta syncs. Descriptions of private/confidential meetings are automatically redacted.</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

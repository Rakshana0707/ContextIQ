"use client";

import React, { useEffect, useState } from "react";
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Laptop,
  RefreshCw,
  Smartphone,
  ShieldCheck,
  Server,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { integrationsApi, IntegrationResponse } from "@/lib/api/services/integrations";
import { devicesApi, DeviceRead } from "@/lib/api";

export function SyncHealthPanel() {
  const [integrations, setIntegrations] = useState<IntegrationResponse[]>([]);
  const [devices, setDevices] = useState<DeviceRead[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [lastCheck, setLastCheck] = useState<Date>(new Date());

  const loadHealthData = async () => {
    try {
      const [intData, devData] = await Promise.all([
        integrationsApi.listIntegrations().catch(() => []),
        devicesApi.list().catch(() => []),
      ]);
      setIntegrations(intData);
      setDevices(devData);
      setLastCheck(new Date());
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadHealthData();
  }, []);

  const handleManualRefresh = () => {
    setRefreshing(true);
    loadHealthData();
  };

  // Derive sync health stats
  const activeIntegrations = integrations.filter((i) => i.connection_status === "CONNECTED");
  const failedSyncs = integrations.filter((i) => i.sync_status === "ERROR");
  const activeDevices = devices.filter((d) => d.is_active && d.connection_status !== "REVOKED");

  return (
    <Card className="border-border shadow-xs">
      <CardHeader className="pb-3 flex flex-row items-center justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-indigo-500" />
            <CardTitle className="text-sm font-semibold text-foreground">
              Ecosystem Synchronization Health
            </CardTitle>
          </div>
          <CardDescription className="text-xs">
            Real-time synchronization status across calendar providers, telemetry ingestion queues, and authorized devices.
          </CardDescription>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleManualRefresh}
          disabled={refreshing}
          className="text-xs gap-1.5 h-8 font-medium"
        >
          <RefreshCw className={`h-3 w-3 ${refreshing ? "animate-spin" : ""}`} />
          {refreshing ? "Checking..." : "Refresh"}
        </Button>
      </CardHeader>

      <CardContent className="space-y-4 pt-1">
        {/* Metric Summary Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
          <div className="p-3 rounded-lg bg-muted/40 border border-border/50 space-y-1">
            <span className="text-muted-foreground text-[11px] block">Connected Providers</span>
            <span className="text-base font-bold text-foreground font-mono">
              {activeIntegrations.length} / 2
            </span>
          </div>

          <div className="p-3 rounded-lg bg-muted/40 border border-border/50 space-y-1">
            <span className="text-muted-foreground text-[11px] block">Active Hardware Devices</span>
            <span className="text-base font-bold text-foreground font-mono">
              {activeDevices.length}
            </span>
          </div>

          <div className="p-3 rounded-lg bg-muted/40 border border-border/50 space-y-1">
            <span className="text-muted-foreground text-[11px] block">Sync Health Rate</span>
            <span className="text-base font-bold text-emerald-600 dark:text-emerald-400 font-mono">
              {failedSyncs.length === 0 ? "100%" : `${Math.round(((activeIntegrations.length - failedSyncs.length) / (activeIntegrations.length || 1)) * 100)}%`}
            </span>
          </div>

          <div className="p-3 rounded-lg bg-muted/40 border border-border/50 space-y-1">
            <span className="text-muted-foreground text-[11px] block">Pending Operations</span>
            <span className="text-base font-bold text-foreground font-mono">0</span>
          </div>
        </div>

        {/* Calendar Provider Sync Status */}
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-foreground flex items-center gap-1.5">
            <Server className="h-3.5 w-3.5 text-muted-foreground" />
            Calendar Ecosystem Providers
          </h4>

          {loading ? (
            <div className="p-4 text-xs text-muted-foreground text-center animate-pulse">
              Querying sync providers...
            </div>
          ) : (
            <div className="space-y-2">
              {/* Google Calendar */}
              {(() => {
                const gCal = integrations.find((i) => i.provider === "google_calendar");
                const isConn = gCal?.connection_status === "CONNECTED";
                return (
                  <div className="flex items-center justify-between p-2.5 rounded-lg border border-border/60 bg-card text-xs">
                    <div className="flex items-center gap-2.5">
                      <div className="h-7 w-7 rounded-md bg-red-500/10 text-red-600 dark:text-red-400 flex items-center justify-center font-bold text-xs">
                        G
                      </div>
                      <div>
                        <span className="font-semibold text-foreground">Google Calendar</span>
                        <span className="text-[11px] text-muted-foreground block">
                          {isConn ? gCal?.provider_email || "Authorized Account" : "Zero active sync tokens"}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      {isConn ? (
                        <>
                          <span className="text-[11px] font-mono text-muted-foreground hidden sm:inline">
                            Synced {gCal?.last_synced_at ? new Date(gCal.last_synced_at).toLocaleTimeString() : "Pending"}
                          </span>
                          <Badge variant="outline" className="text-[10px] bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30">
                            <CheckCircle2 className="h-2.5 w-2.5 mr-1" />
                            Healthy
                          </Badge>
                        </>
                      ) : (
                        <Badge variant="secondary" className="text-[10px] text-muted-foreground">
                          Not Connected
                        </Badge>
                      )}
                    </div>
                  </div>
                );
              })()}

              {/* Microsoft Outlook */}
              {(() => {
                const msOut = integrations.find((i) => i.provider === "microsoft_outlook");
                const isConn = msOut?.connection_status === "CONNECTED";
                return (
                  <div className="flex items-center justify-between p-2.5 rounded-lg border border-border/60 bg-card text-xs">
                    <div className="flex items-center gap-2.5">
                      <div className="h-7 w-7 rounded-md bg-blue-500/10 text-blue-600 dark:text-blue-400 flex items-center justify-center font-bold text-xs">
                        M
                      </div>
                      <div>
                        <span className="font-semibold text-foreground">Microsoft Outlook</span>
                        <span className="text-[11px] text-muted-foreground block">
                          {isConn ? msOut?.provider_email || "Authorized Account" : "Zero active sync tokens"}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      {isConn ? (
                        <>
                          <span className="text-[11px] font-mono text-muted-foreground hidden sm:inline">
                            Synced {msOut?.last_synced_at ? new Date(msOut.last_synced_at).toLocaleTimeString() : "Pending"}
                          </span>
                          <Badge variant="outline" className="text-[10px] bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30">
                            <CheckCircle2 className="h-2.5 w-2.5 mr-1" />
                            Healthy
                          </Badge>
                        </>
                      ) : (
                        <Badge variant="secondary" className="text-[10px] text-muted-foreground">
                          Not Connected
                        </Badge>
                      )}
                    </div>
                  </div>
                );
              })()}
            </div>
          )}
        </div>

        {/* Registered Devices Telemetry Synchronization */}
        <div className="space-y-2 pt-1">
          <h4 className="text-xs font-semibold text-foreground flex items-center gap-1.5">
            <Laptop className="h-3.5 w-3.5 text-muted-foreground" />
            Device Telemetry Synchronization
          </h4>

          {devices.length === 0 ? (
            <div className="p-3 rounded-lg bg-muted/20 border border-dashed border-border/60 text-xs text-muted-foreground text-center">
              No registered devices reporting. Start the Windows desktop agent or open the mobile companion app to sync.
            </div>
          ) : (
            <div className="space-y-1.5">
              {devices.map((dev) => (
                <div
                  key={dev.id}
                  className="flex items-center justify-between p-2.5 rounded-lg border border-border/50 bg-card text-xs"
                >
                  <div className="flex items-center gap-2.5">
                    {dev.device_type === "MOBILE" ? (
                      <Smartphone className="h-4 w-4 text-indigo-500" />
                    ) : (
                      <Laptop className="h-4 w-4 text-muted-foreground" />
                    )}
                    <div>
                      <div className="flex items-center gap-1.5">
                        <span className="font-semibold text-foreground">{dev.device_name}</span>
                        <span className="text-[10px] font-mono text-muted-foreground">({dev.platform})</span>
                      </div>
                      <span className="text-[10px] text-muted-foreground block font-mono">
                        v{dev.application_version} • Last seen {new Date(dev.last_seen_timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                  </div>
                  <Badge
                    variant="outline"
                    className={`text-[10px] ${
                      dev.connection_status === "ONLINE"
                        ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30"
                        : dev.connection_status === "REVOKED"
                        ? "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/30"
                        : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {dev.connection_status}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

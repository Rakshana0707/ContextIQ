"use client";

import { useEffect, useState } from "react";
import {
  Radio,
  RefreshCw,
  Sliders,
  ShieldCheck,
  AlertCircle,
  Activity,
  CheckCircle2,
  Layers,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { DesktopAgentStatus } from "@/components/telemetry/desktop-agent-status";
import { TelemetryOverviewCard } from "@/components/telemetry/telemetry-overview-card";
import { ActivityTimelineChart } from "@/components/telemetry/activity-timeline-chart";
import { InterruptionExplorer } from "@/components/telemetry/interruption-explorer";
import { RecoveryAnalyticsPanel } from "@/components/telemetry/recovery-analytics-panel";
import { TelemetryPrivacyControls } from "@/components/telemetry/telemetry-privacy-controls";
import { telemetryApi } from "@/lib/api/services/telemetry";
import type {
  TelemetryAgentStatus,
  DailyTelemetryOverview,
  DetectedInterruptionItem,
  RecoveryAnalyticsData,
  BehavioralFrictionData,
  InterruptionTrendPoint,
  PersonalBaselineData,
  InterruptionFeedbackPayload,
} from "@/types/telemetry";

export default function TelemetryDashboardPage() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notification, setNotification] = useState<string | null>(null);

  // Core Data States
  const [agentStatus, setAgentStatus] = useState<TelemetryAgentStatus | null>(null);
  const [overview, setOverview] = useState<DailyTelemetryOverview | null>(null);
  const [interruptions, setInterruptions] = useState<DetectedInterruptionItem[]>([]);
  const [recovery, setRecovery] = useState<RecoveryAnalyticsData | null>(null);
  const [friction, setFriction] = useState<BehavioralFrictionData | null>(null);
  const [trends, setTrends] = useState<InterruptionTrendPoint[]>([]);
  const [baseline, setBaseline] = useState<PersonalBaselineData | null>(null);

  // Pause action state
  const [isTogglingPause, setIsTogglingPause] = useState(false);

  useEffect(() => {
    loadTelemetryData();
  }, []);

  const loadTelemetryData = async (isManualRefresh = false) => {
    if (isManualRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const [
        statusRes,
        overviewRes,
        interruptionsRes,
        recoveryRes,
        frictionRes,
        trendsRes,
        baselineRes,
      ] = await Promise.all([
        telemetryApi.getAgentStatus(),
        telemetryApi.getOverview(),
        telemetryApi.getDetectedInterruptions(),
        telemetryApi.getRecoveryAnalytics(),
        telemetryApi.getFrictionIndex(),
        telemetryApi.getInterruptionTrends(),
        telemetryApi.getPersonalBaseline(),
      ]);

      if (statusRes.data) setAgentStatus(statusRes.data);
      if (overviewRes.data) setOverview(overviewRes.data);
      if (interruptionsRes.data) setInterruptions(interruptionsRes.data);
      if (recoveryRes.data) setRecovery(recoveryRes.data);
      if (frictionRes.data) setFriction(frictionRes.data);
      if (trendsRes.data) setTrends(trendsRes.data);
      if (baselineRes.data) setBaseline(baselineRes.data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to load telemetry data";
      setError(message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const notify = (msg: string) => {
    setNotification(msg);
    setTimeout(() => setNotification(null), 3500);
  };

  const handleTogglePause = async () => {
    if (!agentStatus) return;
    setIsTogglingPause(true);
    try {
      if (agentStatus.is_paused) {
        await telemetryApi.resumeAgent();
        setAgentStatus((prev) =>
          prev ? { ...prev, is_paused: false, status: "online" } : null,
        );
        notify("Desktop monitoring resumed.");
      } else {
        await telemetryApi.pauseAgent(60);
        setAgentStatus((prev) =>
          prev ? { ...prev, is_paused: true, status: "paused" } : null,
        );
        notify("Desktop monitoring paused for 60 minutes.");
      }
    } catch {
      notify("Failed to change agent state.");
    } finally {
      setIsTogglingPause(false);
    }
  };

  const handleQuickPause = async (minutes: number = 60) => {
    setIsTogglingPause(true);
    try {
      await telemetryApi.pauseAgent(minutes);
      setAgentStatus((prev) =>
        prev ? { ...prev, is_paused: true, status: "paused" } : null,
      );
      notify(`Desktop monitoring paused for ${minutes} minutes.`);
    } catch {
      notify("Failed to pause monitoring.");
    } finally {
      setIsTogglingPause(false);
    }
  };

  const handleResumeMonitoring = async () => {
    setIsTogglingPause(true);
    try {
      await telemetryApi.resumeAgent();
      setAgentStatus((prev) =>
        prev ? { ...prev, is_paused: false, status: "online" } : null,
      );
      notify("Desktop monitoring resumed.");
    } catch {
      notify("Failed to resume monitoring.");
    } finally {
      setIsTogglingPause(false);
    }
  };

  const handleFeedbackSubmit = async (
    id: string,
    payload: InterruptionFeedbackPayload,
  ) => {
    try {
      await telemetryApi.submitFeedback(id, payload);
      setInterruptions((prev) =>
        prev.map((item) =>
          item.id === id
            ? {
                ...item,
                feedback_classification: payload.classification,
                feedback_notes: payload.notes ?? item.feedback_notes,
              }
            : item,
        ),
      );
      notify("Interruption feedback recorded. Models updated.");
    } catch {
      notify("Failed to record feedback.");
    }
  };

  return (
    <div className="space-y-6 pb-12 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b pb-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-primary/10 text-primary">
              <Radio className="h-5 w-5" />
            </div>
            <h1 className="text-2xl font-bold tracking-tight">Behavioral Telemetry & Desktop Agent</h1>
          </div>
          <p className="text-xs text-muted-foreground">
            Observable desktop focus transitions, micro-delays, and background agent health
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <Button
            variant="outline"
            size="sm"
            onClick={() => loadTelemetryData(true)}
            disabled={refreshing || loading}
            className="text-xs h-8"
          >
            <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Floating Notification Toast */}
      {notification && (
        <Alert className="bg-primary/10 border-primary/30 text-foreground text-xs py-2.5 transition-all">
          <CheckCircle2 className="h-4 w-4 text-primary" />
          <AlertTitle className="text-xs font-semibold">Updated</AlertTitle>
          <AlertDescription className="text-xs">{notification}</AlertDescription>
        </Alert>
      )}

      {/* Error alert with retry */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Connection Notice</AlertTitle>
          <AlertDescription className="flex items-center justify-between text-xs">
            <span>{error}</span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => loadTelemetryData()}
              className="text-xs h-6 px-2"
            >
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {/* Agent Status Card */}
      <DesktopAgentStatus
        status={agentStatus}
        loading={loading || refreshing}
        onRefresh={() => loadTelemetryData(true)}
        onTogglePause={handleTogglePause}
        isTogglingPause={isTogglingPause}
      />

      {/* Overview KPI Cards */}
      <TelemetryOverviewCard overview={overview} loading={loading} />

      {/* Main Tabbed Sections */}
      <Tabs defaultValue="timeline" className="space-y-4">
        <TabsList className="grid grid-cols-3 max-w-md h-9 text-xs">
          <TabsTrigger value="timeline" className="text-xs">
            Timeline & Explorer
          </TabsTrigger>
          <TabsTrigger value="recovery" className="text-xs">
            Cognitive Recovery
          </TabsTrigger>
          <TabsTrigger value="privacy" className="text-xs">
            Agency & Controls
          </TabsTrigger>
        </TabsList>

        {/* Tab 1: Timeline & Interruption Explorer */}
        <TabsContent value="timeline" className="space-y-4">
          <ActivityTimelineChart interruptions={interruptions} loading={loading} />
          <InterruptionExplorer
            interruptions={interruptions}
            onSubmitFeedback={handleFeedbackSubmit}
            loading={loading}
          />
        </TabsContent>

        {/* Tab 2: Cognitive Recovery & Behavioral Friction */}
        <TabsContent value="recovery" className="space-y-4">
          <RecoveryAnalyticsPanel
            recovery={recovery}
            friction={friction}
            trends={trends}
            baseline={baseline}
            loading={loading}
          />
        </TabsContent>

        {/* Tab 3: Agency & Controls */}
        <TabsContent value="privacy" className="space-y-4">
          <TelemetryPrivacyControls
            isPaused={agentStatus?.is_paused ?? false}
            onPause={handleQuickPause}
            onResume={handleResumeMonitoring}
            loading={isTogglingPause}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}

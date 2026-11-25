/**
 * ContextIQ — Behavioral Telemetry & Desktop Agent Types
 * -----------------------------------------------------
 * TypeScript interfaces matching backend telemetry models and analytics schemas.
 */

export type AgentStatusType = "online" | "offline" | "paused" | "unknown";

export interface TelemetryAgentStatus {
  status: AgentStatusType;
  last_seen: string | null;
  pending_events: number;
  agent_version: string | null;
  is_paused: boolean;
  device_id: string | null;
}

export type TelemetryEventType =
  | "application_activated"
  | "application_deactivated"
  | "user_idle_started"
  | "user_active_returned"
  | "agent_started"
  | "agent_stopped"
  | "telemetry_paused"
  | "telemetry_resumed";

export interface TelemetryEventItem {
  id: string;
  event_type: TelemetryEventType;
  event_timestamp: string;
  application_name: string | null;
  window_title: string | null;
  device_id: string | null;
  schema_version?: string;
  payload?: Record<string, unknown>;
}

export type InterruptionSeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type InterruptionType =
  | "APPLICATION_SWITCH"
  | "EXTENDED_INACTIVITY"
  | "RAPID_SWITCHING"
  | "SYSTEM_EVENT";

export type InterruptionFeedbackClassification =
  | "GENUINE_INTERRUPTION"
  | "INTENTIONAL_SWITCH"
  | "INCORRECT_DETECTION"
  | "IGNORE";

export interface DetectedInterruptionItem {
  id: string;
  interruption_type: InterruptionType;
  severity: InterruptionSeverity;
  confidence_score: number;
  start_timestamp: string;
  end_timestamp: string | null;
  duration_seconds: number;
  resumption_lag_seconds: number | null;
  return_to_device_delay_seconds?: number | null;
  return_to_app_delay_seconds?: number | null;
  confirmed_task_resumption_delay_seconds?: number | null;
  evidence_signals?: string[] | Record<string, unknown>;
  session_id?: string | null;
  task_id?: string | null;
  feedback_classification?: InterruptionFeedbackClassification | null;
  feedback_notes?: string | null;
}

export interface InterruptionFeedbackPayload {
  classification: InterruptionFeedbackClassification;
  resumption_delay_actual_seconds?: number;
  notes?: string;
}

export interface TimelineSegment {
  id: string;
  type: "focus" | "idle" | "interruption" | "session";
  startTime: string;
  endTime: string;
  durationMinutes: number;
  title: string;
  subtitle?: string;
  isEstimated: boolean;
  severity?: InterruptionSeverity;
  application?: string;
}

export interface ResumptionLagBreakdown {
  tier: "return_to_device" | "return_to_app" | "confirmed_task_resumption";
  label: string;
  description: string;
  seconds: number | null;
  isEstimated: boolean;
}

export interface RecoveryAnalyticsData {
  mean_resumption_lag_seconds: number;
  median_resumption_lag_seconds: number;
  mean_return_to_device_delay_seconds: number;
  mean_return_to_app_delay_seconds: number;
  mean_confirmed_resumption_delay_seconds: number;
  total_interruptions_measured: number;
  lag_distribution: Array<{ range: string; count: number }>;
  trend_daily?: Array<{ date: string; avg_lag_seconds: number; count: number }>;
}

export type FrictionTier = "LOW" | "MODERATE" | "HIGH" | "SEVERE";

export interface BehavioralFrictionData {
  friction_index: number;
  friction_tier: FrictionTier;
  component_scores: Record<string, number>;
  dominant_friction_driver: string;
  interpretation: string;
  as_of?: string;
}

export interface InterruptionTrendPoint {
  hour_of_day: number;
  interruption_count: number;
  avg_resumption_lag_seconds: number;
}

export interface PersonalBaselineData {
  rolling_14d_mean_lag: number;
  rolling_14d_interruption_freq: number;
  today_relative_lag_ratio: number;
  today_relative_freq_ratio: number;
  baseline_tier: "BETTER" | "SIMILAR" | "ELEVATED";
}

export interface DailyTelemetryOverview {
  total_events_today: number;
  total_focus_minutes: number;
  total_idle_minutes: number;
  detected_interruptions_count: number;
  top_applications: Array<{ name: string; focusMinutes: number; percentage: number }>;
  sync_status: "HEALTHY" | "DEGRADED" | "DISCONNECTED";
  last_sync_timestamp: string | null;
}

export interface RecoveryContributingFactorItem {
  feature_name: string;
  impact_minutes: number;
  direction: "INCREASES_RECOVERY" | "DECREASES_RECOVERY";
  explanation: string;
}

export interface RecoveryPredictionIntervalData {
  lower_seconds: number;
  upper_seconds: number;
  lower_minutes: number;
  upper_minutes: number;
  confidence_level: number;
}

export interface RecoveryPredictionData {
  user_id: string;
  prediction_timestamp: string;
  estimated_recovery_duration_seconds: number;
  estimated_recovery_duration_minutes: number;
  median_recovery_duration_minutes: number;
  recovery_probabilities: Record<string, number>;
  confidence_interval: RecoveryPredictionIntervalData;
  confidence_tier: "COLD_START" | "EMERGING" | "ESTABLISHED" | "CONFIDENT";
  is_personalized: boolean;
  model_version: string;
  main_contributing_factors: RecoveryContributingFactorItem[];
  disclaimer: string;
}


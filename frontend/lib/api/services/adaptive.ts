import { apiClient, mockResult } from "@/lib/api/client";
import type { ApiResult } from "@/types";

// ============================================================================
// 1. Task Ranking Types (Phase 4.4)
// ============================================================================

export interface ScoreBreakdown {
  urgency_score: number;
  forgetting_risk_score: number;
  personal_suitability_score: number;
  context_compatibility_score: number;
  scheduling_feasibility_score: number;
}

export interface RecommendedFocusWindow {
  start_time: string;
  end_time: string;
  quality_score: number;
  task_category?: string;
  reason: string;
}

export interface RankedTaskItem {
  task_id: string;
  title: string;
  context_tag?: string;
  priority: string;
  status: string;
  due_at?: string;
  estimated_minutes: number;
  recovery_buffer_minutes: number;
  rank: number;
  composite_score: number;
  primary_driver: string;
  score_breakdown: ScoreBreakdown;
  grounded_explanation: string;
  recommended_focus_window?: RecommendedFocusWindow;
  constraints_applied: string[];
  is_blocked: boolean;
  blocked_by_task_id?: string;
  data_sufficiency: string;
  user_pinned?: boolean;
}

export interface TaskRankingResponse {
  user_id: string;
  generated_at: string;
  reference_time: string;
  preset_applied: string;
  current_context: Record<string, any>;
  items: RankedTaskItem[];
  summary_insights: string[];
}

export interface TaskRankingPreviewRequest {
  as_of?: string;
  current_context_tag?: string;
  preset?: "BALANCED" | "DEEP_WORK" | "DEADLINE_CRUNCH" | "RECOVERY_MODE";
  include_blocked?: boolean;
  active_hour?: number;
}

export interface TaskRankingFeedbackCreate {
  task_id: string;
  action: "ACCEPTED" | "SNOOZED" | "PINNED" | "DISMISSED" | "REORDERED";
  rank_position: number;
  composite_score: number;
  feedback_note?: string;
}

export interface TaskRankingFeedbackRead {
  id: string;
  task_id: string;
  action: string;
  rank_position: number;
  composite_score: number;
  feedback_note?: string;
  created_at: string;
}

// ============================================================================
// 2. Behavioral Profile & Digital Twin Types (Phase 4.2)
// ============================================================================

export interface DimensionConfidence {
  sample_size: number;
  coverage_ratio: number;
  confidence_score: number;
  confidence_level: "LOW" | "MEDIUM" | "HIGH";
}

export interface FocusDimension {
  typical_focus_session_minutes: number;
  focus_session_std_dev: number;
  historical_uninterrupted_mean_minutes: number;
  confidence: DimensionConfidence;
}

export interface InterruptionDimension {
  mean_hourly_interruptions: number;
  interruption_sensitivity_index: number;
  mean_recovery_lag_seconds: number;
  confidence: DimensionConfidence;
}

export interface TaskCompletionDimension {
  overall_completion_rate: number;
  postponement_frequency_ratio: number;
  deadline_adherence_rate: number;
  confidence: DimensionConfidence;
}

export interface ContextDimension {
  mean_switches_per_session: number;
  switch_recovery_overhead_seconds: number;
  primary_work_context: string;
  confidence: DimensionConfidence;
}

export interface TemporalDimension {
  circadian_morning_suitability: number;
  circadian_afternoon_suitability: number;
  circadian_evening_suitability: number;
  confidence: DimensionConfidence;
}

export interface DigitalTwinProfileRead {
  id: string;
  user_id: string;
  profile_version: string;
  is_cold_start: boolean;
  personalization_enabled: boolean;
  telemetry_days_observed: number;
  total_sessions_observed: number;
  total_tasks_observed: number;
  total_interruptions_observed: number;
  overall_profile_confidence: number;
  confidence_tier: "COLD_START" | "EMERGING" | "ESTABLISHED" | "CONFIDENT";
  focus_dimension: FocusDimension;
  interruption_dimension: InterruptionDimension;
  task_completion_dimension: TaskCompletionDimension;
  context_dimension: ContextDimension;
  temporal_dimension: TemporalDimension;
  updated_at: string;
  created_at: string;
}

export interface ProfileSnapshotRead {
  id: string;
  snapshot_version: string;
  trigger_reason: string;
  created_at: string;
  summary_metrics: Record<string, any>;
}

// ============================================================================
// 3. Focus Window Types (Phase 4.3)
// ============================================================================

export interface FocusWindowItemRead {
  id: string;
  user_id: string;
  day_of_week: number;
  day_name: string;
  start_time: string;
  end_time: string;
  task_category?: string;
  completion_rate: number;
  interruption_density: number;
  mean_resumption_lag_seconds: number;
  switch_frequency: number;
  historical_consistency_score: number;
  quality_score: number;
  confidence: number;
  is_recommended: boolean;
}

export interface CategoryFocusWindowRead {
  category: string;
  recommended_windows: FocusWindowItemRead[];
}

export interface FocusWindowMetricsResponse {
  total_windows_discovered: number;
  peak_focus_window: string;
  mean_window_quality: number;
  highest_quality_category: string;
  windows_by_day: Record<string, number>;
}

// ============================================================================
// 4. Personalized Interventions Types (Phase 4.5)
// ============================================================================

export interface UserInterventionItem {
  id: string;
  user_id: string;
  associated_task_id?: string;
  intervention_type: string;
  intervention_category: "FOCUS" | "RECOVERY" | "TASK" | "CONTEXTUAL" | "WORKLOAD";
  title: string;
  message: string;
  trigger_condition: string;
  supporting_evidence: Record<string, any>;
  expected_outcome: string;
  estimated_effort: "LOW" | "MEDIUM" | "HIGH";
  relevance_score: number;
  confidence: number;
  lifecycle_status: "GENERATED" | "PRESENTED" | "ACCEPTED" | "DISMISSED" | "DEFERRED" | "EXPIRED" | "COMPLETED";
  creation_timestamp: string;
  expiration_timestamp: string;
  deferred_until?: string;
  completed_at?: string;
  user_feedback_note?: string;
}

export interface InterventionGenerateResponse {
  user_id: string;
  generated_count: number;
  suppressed_count: number;
  interventions: UserInterventionItem[];
  context_summary: Record<string, any>;
}

// ============================================================================
// 5. Contextual Bandit Types (Phase 4.6)
// ============================================================================

export interface BanditPolicyResponse {
  user_id: string;
  algorithm: string;
  policy_version: string;
  feature_dimension: number;
  all_registered_arms: string[];
  quarantined_arms: string[];
  quiet_hours: number[];
  rate_limit_minutes: number;
}

export interface BanditArmMetric {
  arm_id: string;
  algorithm: string;
  pull_count: number;
  cumulative_reward: number;
  average_reward: number;
  consecutive_negatives: number;
  is_quarantined: boolean;
  quarantined_until?: string;
}

export interface BanditMetricsResponse {
  user_id: string;
  total_decisions: number;
  total_feedback_events: number;
  mean_cumulative_reward: number;
  active_arms_count: number;
  quarantined_arms_count: number;
  arm_metrics: BanditArmMetric[];
}

// ============================================================================
// 6. Causal Evaluation & Effectiveness Types (Phase 4.7)
// ============================================================================

export interface InterventionEffectivenessOverview {
  total_interventions: number;
  treated_count: number;
  control_count: number;
  accepted_count: number;
  acceptance_rate: number;
  executed_count: number;
  execution_rate: number;
  execution_to_acceptance_gap: number;
  mean_bfi_reduction: number;
  mean_resumption_lag_reduction_seconds: number;
  task_completion_lift: number;
  overall_causal_ate?: number;
  top_effective_interventions: string[];
  fatigued_interventions: string[];
  methodological_disclaimer: string;
}

export interface InterventionTypeComparison {
  intervention_type: string;
  intervention_category: string;
  sample_size_treated: number;
  sample_size_control: number;
  acceptance_rate: number;
  execution_rate: number;
  execution_to_acceptance_gap: number;
  unadjusted_observational_difference: number;
  estimated_ate?: number;
  confidence_interval_95?: [number, number];
  p_value?: number;
  estimation_method: string;
  is_statistically_valid: boolean;
  validation_note?: string;
  is_fatigued: boolean;
  fatigue_slope?: number;
}

export interface InterventionExperimentRead {
  id: string;
  user_id: string;
  experiment_name: string;
  target_intervention_type: string;
  control_policy: string;
  allocation_ratio: number;
  is_active: boolean;
  sample_size_treated: number;
  sample_size_control: number;
  estimated_ate?: number;
  p_value?: number;
  start_date: string;
  end_date?: string;
  created_at: string;
}

export interface InterventionOutcomeRead {
  id: string;
  user_id: string;
  intervention_id?: string;
  decision_id?: string;
  intervention_type: string;
  intervention_category: string;
  treatment_status: string;
  experiment_id?: string;
  presented_at: string;
  user_action: string;
  was_executed: boolean;
  window_start: string;
  window_end: string;
  observation_window_minutes: number;
  baseline_bfi: number;
  baseline_resumption_lag_seconds: number;
  observed_bfi?: number;
  observed_resumption_lag_seconds?: number;
  target_task_completed: boolean;
  bfi_delta?: number;
  resumption_lag_delta_seconds?: number;
  composite_effectiveness_score: number;
  is_statistically_valid: boolean;
  created_at: string;
}

// ============================================================================
// 7. Notification Types (Phase 4.8)
// ============================================================================

export interface UserNotificationItem {
  id: string;
  user_id: string;
  intervention_id?: string;
  category: string;
  priority: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "BACKGROUND";
  title: string;
  message: string;
  delivery_channel: string;
  delivery_strategy: string;
  is_delivered: boolean;
  delivered_at?: string;
  is_read: boolean;
  read_at?: string;
  is_dismissed: boolean;
  dismissed_at?: string;
  is_deferred: boolean;
  deferred_until?: string;
  expires_at?: string;
  metadata_payload: Record<string, any>;
  created_at: string;
}

export interface UserNotificationPreference {
  id: string;
  user_id: string;
  enabled_categories: Record<string, boolean>;
  quiet_hours_start: number;
  quiet_hours_end: number;
  quiet_hours_enabled: boolean;
  max_notifications_per_hour: number;
  max_notifications_per_day: number;
  summary_frequency: "DAILY" | "TWICE_DAILY" | "OFF";
  is_paused: boolean;
  paused_until?: string;
  desktop_agent_enabled: boolean;
  sound_enabled: boolean;
  updated_at: string;
}

export interface NotificationMetrics {
  user_id: string;
  fatigue_score: number;
  fatigue_level: string;
  total_presented_7d: number;
  total_accepted_7d: number;
  total_dismissed_7d: number;
  total_deferred_7d: number;
  acceptance_rate_7d: number;
  consecutive_dismissals: number;
  active_quiet_hours: boolean;
  is_paused: boolean;
  paused_until?: string;
  notifications_delivered_today: number;
  notifications_delivered_current_hour: number;
  channel_distribution: Record<string, number>;
  category_distribution: Record<string, number>;
  disclaimer: string;
}

// ============================================================================
// Adaptive API Interface & Implementation
// ============================================================================

export interface AdaptiveApi {
  // Task Ranking
  getTaskRanking(params?: {
    as_of?: string;
    context_tag?: string;
    preset?: string;
    include_blocked?: boolean;
    limit?: number;
  }): Promise<ApiResult<TaskRankingResponse>>;

  previewTaskRanking(
    request: TaskRankingPreviewRequest,
  ): Promise<ApiResult<TaskRankingResponse>>;

  recordFeedback(
    feedback: TaskRankingFeedbackCreate,
  ): Promise<ApiResult<TaskRankingFeedbackRead>>;

  // Digital Twin Profile
  getProfile(): Promise<ApiResult<DigitalTwinProfileRead>>;
  getProfileHistory(limit?: number): Promise<ApiResult<ProfileSnapshotRead[]>>;
  rebuildProfile(): Promise<ApiResult<DigitalTwinProfileRead>>;
  resetProfile(): Promise<ApiResult<{ message: string; is_reset: boolean }>>;
  togglePersonalization(enabled: boolean): Promise<ApiResult<{ personalization_enabled: boolean }>>;

  // Focus Windows
  getFocusWindows(params?: { day_of_week?: number; min_quality?: number }): Promise<ApiResult<FocusWindowItemRead[]>>;
  getCategoryFocusWindows(): Promise<ApiResult<CategoryFocusWindowRead[]>>;
  getFocusWindowMetrics(): Promise<ApiResult<FocusWindowMetricsResponse>>;
  discoverFocusWindows(): Promise<ApiResult<{ message: string; discovered_count: number }>>;

  // Personalized Interventions
  generateInterventions(as_of?: string): Promise<ApiResult<InterventionGenerateResponse>>;
  getActiveInterventions(): Promise<ApiResult<UserInterventionItem[]>>;
  getInterventionHistory(limit?: number): Promise<ApiResult<UserInterventionItem[]>>;
  actionIntervention(
    id: string,
    action: "ACCEPT" | "DISMISS" | "DEFER" | "COMPLETE",
    feedbackNote?: string
  ): Promise<ApiResult<UserInterventionItem>>;

  // Contextual Bandit
  getBanditPolicy(): Promise<ApiResult<BanditPolicyResponse>>;
  getBanditMetrics(): Promise<ApiResult<BanditMetricsResponse>>;

  // Causal Evaluation & Effectiveness
  getEffectivenessOverview(): Promise<ApiResult<InterventionEffectivenessOverview>>;
  getInterventionsEffectiveness(): Promise<ApiResult<InterventionTypeComparison[]>>;
  getEffectivenessExperiments(): Promise<ApiResult<InterventionExperimentRead[]>>;
  getInterventionOutcome(id: string): Promise<ApiResult<InterventionOutcomeRead>>;

  // Notifications
  getNotifications(params?: {
    unread_only?: boolean;
    category?: string;
    limit?: number;
  }): Promise<ApiResult<UserNotificationItem[]>>;

  getNotificationPreferences(): Promise<ApiResult<UserNotificationPreference>>;

  updateNotificationPreferences(
    update: Partial<UserNotificationPreference> & { pause_duration_minutes?: number }
  ): Promise<ApiResult<UserNotificationPreference>>;

  acknowledgeNotification(id: string): Promise<ApiResult<{ id: string; is_read: boolean; acknowledged_at: string }>>;

  dismissNotification(
    id: string,
    reason?: string,
    annoyanceLevel?: number
  ): Promise<ApiResult<{ id: string; is_dismissed: boolean; updated_fatigue_score: number }>>;

  getNotificationMetrics(): Promise<ApiResult<NotificationMetrics>>;
}

export const adaptiveApi: AdaptiveApi = {
  // Task Ranking
  async getTaskRanking(params) {
    return apiClient.request<TaskRankingResponse>("/adaptive/task-ranking", {
      method: "GET",
      query: params,
    });
  },

  async previewTaskRanking(request) {
    return apiClient.request<TaskRankingResponse>("/adaptive/task-ranking/preview", {
      method: "POST",
      body: request,
    });
  },

  async recordFeedback(feedback) {
    return apiClient.request<TaskRankingFeedbackRead>("/adaptive/task-ranking/feedback", {
      method: "POST",
      body: feedback,
    });
  },

  // Digital Twin Profile
  async getProfile() {
    return apiClient.request<DigitalTwinProfileRead>("/adaptive/profile", {
      method: "GET",
    });
  },

  async getProfileHistory(limit = 20) {
    return apiClient.request<ProfileSnapshotRead[]>("/adaptive/profile/history", {
      method: "GET",
      query: { limit },
    });
  },

  async rebuildProfile() {
    return apiClient.request<DigitalTwinProfileRead>("/adaptive/profile/rebuild", {
      method: "POST",
    });
  },

  async resetProfile() {
    return apiClient.request<{ message: string; is_reset: boolean }>("/adaptive/profile/reset", {
      method: "POST",
    });
  },

  async togglePersonalization(enabled: boolean) {
    return apiClient.request<{ personalization_enabled: boolean }>("/adaptive/profile/toggle-personalization", {
      method: "POST",
      body: { personalization_enabled: enabled },
    });
  },

  // Focus Windows
  async getFocusWindows(params) {
    return apiClient.request<FocusWindowItemRead[]>("/adaptive/focus-windows", {
      method: "GET",
      query: params,
    });
  },

  async getCategoryFocusWindows() {
    return apiClient.request<CategoryFocusWindowRead[]>("/adaptive/focus-windows/categories", {
      method: "GET",
    });
  },

  async getFocusWindowMetrics() {
    return apiClient.request<FocusWindowMetricsResponse>("/adaptive/focus-windows/metrics", {
      method: "GET",
    });
  },

  async discoverFocusWindows() {
    return apiClient.request<{ message: string; discovered_count: number }>("/adaptive/focus-windows/discover", {
      method: "POST",
    });
  },

  // Personalized Interventions
  async generateInterventions(as_of) {
    return apiClient.request<InterventionGenerateResponse>("/adaptive/interventions/generate", {
      method: "POST",
      body: as_of ? { as_of } : {},
    });
  },

  async getActiveInterventions() {
    return apiClient.request<UserInterventionItem[]>("/adaptive/interventions/active", {
      method: "GET",
    });
  },

  async getInterventionHistory(limit = 50) {
    return apiClient.request<UserInterventionItem[]>("/adaptive/interventions/history", {
      method: "GET",
      query: { limit },
    });
  },

  async actionIntervention(id, action, feedbackNote) {
    return apiClient.request<UserInterventionItem>(`/adaptive/interventions/${id}/action`, {
      method: "POST",
      body: { action, feedback_note: feedbackNote },
    });
  },

  // Contextual Bandit
  async getBanditPolicy() {
    return apiClient.request<BanditPolicyResponse>("/adaptive/bandit/policy", {
      method: "GET",
    });
  },

  async getBanditMetrics() {
    return apiClient.request<BanditMetricsResponse>("/adaptive/bandit/metrics", {
      method: "GET",
    });
  },

  // Causal Evaluation & Effectiveness
  async getEffectivenessOverview() {
    return apiClient.request<InterventionEffectivenessOverview>("/adaptive/effectiveness/overview", {
      method: "GET",
    });
  },

  async getInterventionsEffectiveness() {
    return apiClient.request<InterventionTypeComparison[]>("/adaptive/effectiveness/interventions", {
      method: "GET",
    });
  },

  async getEffectivenessExperiments() {
    return apiClient.request<InterventionExperimentRead[]>("/adaptive/effectiveness/experiments", {
      method: "GET",
    });
  },

  async getInterventionOutcome(id: string) {
    return apiClient.request<InterventionOutcomeRead>(`/adaptive/effectiveness/${id}`, {
      method: "GET",
    });
  },

  // Notifications
  async getNotifications(params) {
    return apiClient.request<UserNotificationItem[]>("/adaptive/notifications", {
      method: "GET",
      query: params,
    });
  },

  async getNotificationPreferences() {
    return apiClient.request<UserNotificationPreference>("/adaptive/notifications/preferences", {
      method: "GET",
    });
  },

  async updateNotificationPreferences(update) {
    return apiClient.request<UserNotificationPreference>("/adaptive/notifications/preferences", {
      method: "POST",
      body: update,
    });
  },

  async acknowledgeNotification(id) {
    return apiClient.request<{ id: string; is_read: boolean; acknowledged_at: string }>(
      `/adaptive/notifications/${id}/acknowledge`,
      { method: "POST" }
    );
  },

  async dismissNotification(id, reason, annoyanceLevel) {
    return apiClient.request<{ id: string; is_dismissed: boolean; updated_fatigue_score: number }>(
      `/adaptive/notifications/${id}/dismiss`,
      {
        method: "POST",
        body: { reason, annoyance_level: annoyanceLevel },
      }
    );
  },

  async getNotificationMetrics() {
    return apiClient.request<NotificationMetrics>("/adaptive/notifications/metrics", {
      method: "GET",
    });
  },
};

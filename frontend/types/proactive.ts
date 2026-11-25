/**
 * Types for Proactive Behavioral Intelligence and Event Feed (Phase 7.3).
 */

export type FeedItemStatus = "ACTIVE" | "SNOOZED" | "DISMISSED" | "ACTIONED";

export interface SuggestedAction {
  action_type: string;
  label?: string;
  parameters?: Record<string, any>;
}

export interface ProactiveFeedItem {
  id: string;
  user_id: string;
  event_id?: string;
  detection_type: string;
  title: string;
  why_it_matters: string;
  related_task_id?: string;
  related_context: Record<string, any>;
  recommended_response: string;
  evidence: Record<string, any>;
  confidence_score: number;
  uncertainty_lower_bound: number;
  uncertainty_upper_bound: number;
  conformal_interval_text: string;
  status: FeedItemStatus;
  requires_approval: boolean;
  suggested_action?: SuggestedAction;
  snoozed_until?: string;
  expires_at?: string;
  created_at: string;
  updated_at: string;
}

export interface EventProcessingResult {
  event_id: string;
  status: string;
  is_duplicate: boolean;
  rules_matched: number;
  executions_created: number;
  proactive_feed_item_created: boolean;
  proactive_feed_item_id?: string;
  suppressed_by_fatigue: boolean;
  rationale?: string;
}

export interface DeadLetterRecord {
  id: string;
  event_id?: string;
  user_id?: string;
  raw_payload: Record<string, any>;
  error_code: string;
  error_reason: string;
  retry_count: number;
  max_retries: number;
  status: string;
  created_at: string;
  updated_at: string;
}

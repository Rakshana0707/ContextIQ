/**
 * TypeScript types for ContextIQ Long-Term Behavioral Memory & Pattern Evolution (Phase 8.3).
 */

export type MemoryCategory =
  | "BEHAVIORAL_PREFERENCES"
  | "PRODUCTIVITY_PATTERNS"
  | "FOCUS_PATTERNS"
  | "RECOVERY_PATTERNS"
  | "TASK_MANAGEMENT_PREFERENCES"
  | "CONTEXT_ASSOCIATIONS"
  | "SUCCESSFUL_INTERVENTIONS"
  | "UNSUCCESSFUL_INTERVENTIONS"
  | "LONG_TERM_GOALS"
  | "EXPLICIT_USER_INSTRUCTIONS";

export type MemorySourceType =
  | "EXPLICIT_USER_INSTRUCTION"
  | "FREQUENTLY_OBSERVED_BEHAVIOR"
  | "MODEL_INFERRED_PATTERN";

export type MemoryValidityStatus =
  | "ACTIVE"
  | "EMERGING"
  | "STRENGTHENING"
  | "WEAKENING"
  | "CONTRADICTED"
  | "OUTDATED"
  | "ARCHIVED"
  | "CORRECTED";

export type PatternEvolutionType =
  | "EMERGING"
  | "STRENGTHENING"
  | "WEAKENING"
  | "CONTRADICTORY"
  | "OUTDATED"
  | "PREFERENCE_CHANGE";

export interface PatternEvolutionEvent {
  timestamp: string;
  evolution_type: PatternEvolutionType;
  previous_status: string | null;
  new_status: string;
  previous_confidence: number | null;
  new_confidence: number;
  reason: string;
  evidence_summary?: Record<string, any>;
}

export interface BehavioralMemory {
  id: string;
  user_id: string;
  category: MemoryCategory;
  title: string;
  description: string;
  source_type: MemorySourceType;
  validity_status: MemoryValidityStatus;
  confidence: number;
  observation_count: number;
  reinforcement_count: number;
  contradiction_count: number;
  first_observed_at: string;
  last_observed_at: string;
  last_reinforced_at?: string | null;
  last_contradicted_at?: string | null;
  supporting_evidence: Record<string, any>;
  evolution_history: PatternEvolutionEvent[];
  expiration_policy: {
    retention_days: number;
    review_after_days: number;
    auto_outdate_dormant_days: number;
  };
  is_user_corrected: boolean;
  user_correction_notes?: string | null;
  is_disabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface BehavioralTemporalSummary {
  id: string;
  user_id: string;
  period_type: "WEEKLY" | "MONTHLY";
  period_start: string;
  period_end: string;
  summary_metrics: {
    total_memories: number;
    emerging_count: number;
    strengthened_count: number;
    weakened_count: number;
    outdated_count: number;
    baseline_focus_duration: number;
    baseline_recovery_seconds: number;
    baseline_bfi: number;
  };
  emerging_pattern_ids: string[];
  strengthened_pattern_ids: string[];
  weakened_pattern_ids: string[];
  outdated_pattern_ids: string[];
  narrative_summary?: string | null;
  created_at: string;
}

export interface MemoryPreference {
  user_id: string;
  disabled_categories: string[];
  retention_policy_days: number;
  auto_outdate_dormant_days: number;
  auto_synthesis_enabled: boolean;
  updated_at: string;
}

export interface BehavioralMemoryOverview {
  total_memories: number;
  active_patterns_count: number;
  emerging_patterns_count: number;
  strengthening_patterns_count: number;
  weakening_patterns_count: number;
  outdated_patterns_count: number;
  contradicted_patterns_count: number;
  explicit_instructions_count: number;
  user_corrected_count: number;
  category_counts: Record<string, number>;
  source_type_counts: Record<string, number>;
  status_counts: Record<string, number>;
  primary_profile_status?: string | null;
  primary_profile_confidence?: number | null;
  recent_memories: BehavioralMemory[];
  recent_evolutions: Array<PatternEvolutionEvent & { memory_id: string; memory_title: string; category: string }>;
}

export interface MemorySynthesisResult {
  created_memories_count: number;
  reinforced_memories_count: number;
  weakened_memories_count: number;
  outdated_memories_count: number;
  total_active_memories: number;
  synthesis_messages: string[];
}

export interface MemoryCorrectionInput {
  corrected_description?: string;
  user_notes: string;
  is_inaccurate?: boolean;
  validity_status?: MemoryValidityStatus;
}

export interface MemoryCreateInput {
  category: MemoryCategory;
  title: string;
  description: string;
  source_type?: MemorySourceType;
  confidence?: number;
  supporting_evidence?: Record<string, any>;
}

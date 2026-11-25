/**
 * Frontend API client service for Long-Term Behavioral Memory & Pattern Evolution (Phase 8.3).
 */
import { apiClient } from "@/lib/api/client";
import type {
  BehavioralMemory,
  BehavioralMemoryOverview,
  BehavioralTemporalSummary,
  MemoryCategory,
  MemoryCorrectionInput,
  MemoryCreateInput,
  MemoryPreference,
  MemorySourceType,
  MemorySynthesisResult,
  MemoryValidityStatus,
} from "@/types/behavioral_memory";

const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK_API === "true";

export const MOCK_MEMORIES: BehavioralMemory[] = [
  {
    id: "mem-1",
    user_id: "user-1",
    category: "FOCUS_PATTERNS",
    title: "Morning Deep Focus Window (09:00 - 11:30)",
    description: "Recurrent peak focus interval discovered on weekdays with 88% completion velocity and minimal interruption sensitivity.",
    source_type: "FREQUENTLY_OBSERVED_BEHAVIOR",
    validity_status: "ACTIVE",
    confidence: 0.94,
    observation_count: 24,
    reinforcement_count: 12,
    contradiction_count: 1,
    first_observed_at: "2026-10-01T09:00:00Z",
    last_observed_at: "2026-11-24T11:00:00Z",
    last_reinforced_at: "2026-11-24T11:00:00Z",
    supporting_evidence: {
      discovery_source: "UserFocusWindow",
      quality_score: 91.5,
      median_duration_minutes: 52,
    },
    evolution_history: [
      {
        timestamp: "2026-10-01T09:00:00Z",
        evolution_type: "EMERGING",
        previous_status: null,
        new_status: "EMERGING",
        previous_confidence: null,
        new_confidence: 0.75,
        reason: "Initial window discovery.",
      },
      {
        timestamp: "2026-10-18T11:00:00Z",
        evolution_type: "STRENGTHENING",
        previous_status: "EMERGING",
        new_status: "STRENGTHENING",
        previous_confidence: 0.75,
        new_confidence: 0.88,
        reason: "Corroborated across 10 consecutive working sessions.",
      },
      {
        timestamp: "2026-11-05T09:30:00Z",
        evolution_type: "STRENGTHENING",
        previous_status: "STRENGTHENING",
        new_status: "ACTIVE",
        previous_confidence: 0.88,
        new_confidence: 0.94,
        reason: "Sustained high completion velocity (>85%).",
      },
    ],
    expiration_policy: {
      retention_days: 365,
      review_after_days: 30,
      auto_outdate_dormant_days: 45,
    },
    is_user_corrected: false,
    is_disabled: false,
    created_at: "2026-10-01T09:00:00Z",
    updated_at: "2026-11-24T11:00:00Z",
  },
  {
    id: "mem-2",
    user_id: "user-1",
    category: "EXPLICIT_USER_INSTRUCTIONS",
    title: "Never Interrupt During Code Review Sessions",
    description: "Explicit instruction: Mute all non-critical nudges and defer task reminders during tagged review blocks.",
    source_type: "EXPLICIT_USER_INSTRUCTION",
    validity_status: "ACTIVE",
    confidence: 1.0,
    observation_count: 1,
    reinforcement_count: 0,
    contradiction_count: 0,
    first_observed_at: "2026-10-15T14:20:00Z",
    last_observed_at: "2026-11-25T10:00:00Z",
    supporting_evidence: {
      source: "user_settings_override",
      directive: "no_interrupt_code_review",
    },
    evolution_history: [
      {
        timestamp: "2026-10-15T14:20:00Z",
        evolution_type: "PREFERENCE_CHANGE",
        previous_status: null,
        new_status: "ACTIVE",
        previous_confidence: null,
        new_confidence: 1.0,
        reason: "Explicit user command submitted via memory preferences.",
      },
    ],
    expiration_policy: {
      retention_days: 730,
      review_after_days: 90,
      auto_outdate_dormant_days: 365,
    },
    is_user_corrected: false,
    is_disabled: false,
    created_at: "2026-10-15T14:20:00Z",
    updated_at: "2026-10-15T14:20:00Z",
  },
  {
    id: "mem-3",
    user_id: "user-1",
    category: "RECOVERY_PATTERNS",
    title: "High Interruption Vulnerability on Unplanned Context Switches",
    description: "Empirical recovery lag extends to 184 seconds following unscheduled browser switches during architecture tasks.",
    source_type: "MODEL_INFERRED_PATTERN",
    validity_status: "STRENGTHENING",
    confidence: 0.86,
    observation_count: 14,
    reinforcement_count: 5,
    contradiction_count: 2,
    first_observed_at: "2026-10-20T16:00:00Z",
    last_observed_at: "2026-11-23T15:30:00Z",
    last_reinforced_at: "2026-11-23T15:30:00Z",
    supporting_evidence: {
      isi_score: 0.74,
      p90_recovery_seconds: 240,
    },
    evolution_history: [
      {
        timestamp: "2026-10-20T16:00:00Z",
        evolution_type: "EMERGING",
        previous_status: null,
        new_status: "EMERGING",
        previous_confidence: null,
        new_confidence: 0.72,
        reason: "Initial detection by Interruption Sensitivity Index.",
      },
      {
        timestamp: "2026-11-12T17:00:00Z",
        evolution_type: "STRENGTHENING",
        previous_status: "EMERGING",
        new_status: "STRENGTHENING",
        previous_confidence: 0.72,
        new_confidence: 0.86,
        reason: "Corroborated across 5 additional context disruption events.",
      },
    ],
    expiration_policy: {
      retention_days: 180,
      review_after_days: 30,
      auto_outdate_dormant_days: 45,
    },
    is_user_corrected: false,
    is_disabled: false,
    created_at: "2026-10-20T16:00:00Z",
    updated_at: "2026-11-23T15:30:00Z",
  },
  {
    id: "mem-4",
    user_id: "user-1",
    category: "SUCCESSFUL_INTERVENTIONS",
    title: "Receptive to Post-Break Work Session Hydration Nudges",
    description: "User accepted 8 out of 9 micro-break hydration interventions within 45 seconds of session closure.",
    source_type: "FREQUENTLY_OBSERVED_BEHAVIOR",
    validity_status: "ACTIVE",
    confidence: 0.91,
    observation_count: 9,
    reinforcement_count: 8,
    contradiction_count: 1,
    first_observed_at: "2026-10-25T11:00:00Z",
    last_observed_at: "2026-11-22T14:00:00Z",
    supporting_evidence: {
      intervention_type: "HYDRATION_BREAK",
      accepted_count: 8,
    },
    evolution_history: [],
    expiration_policy: {
      retention_days: 365,
      review_after_days: 30,
      auto_outdate_dormant_days: 60,
    },
    is_user_corrected: false,
    is_disabled: false,
    created_at: "2026-10-25T11:00:00Z",
    updated_at: "2026-11-22T14:00:00Z",
  },
  {
    id: "mem-5",
    user_id: "user-1",
    category: "UNSUCCESSFUL_INTERVENTIONS",
    title: "Frequent Dismissal of Mid-Afternoon Task Re-ordering Prompts",
    description: "User dismissed 6 consecutive re-ranking recommendations prompted between 14:00 and 16:00.",
    source_type: "FREQUENTLY_OBSERVED_BEHAVIOR",
    validity_status: "ACTIVE",
    confidence: 0.89,
    observation_count: 6,
    reinforcement_count: 5,
    contradiction_count: 0,
    first_observed_at: "2026-11-01T15:00:00Z",
    last_observed_at: "2026-11-20T15:30:00Z",
    supporting_evidence: {
      intervention_type: "TASK_REORDER",
      dismissed_count: 6,
    },
    evolution_history: [],
    expiration_policy: {
      retention_days: 180,
      review_after_days: 30,
      auto_outdate_dormant_days: 45,
    },
    is_user_corrected: false,
    is_disabled: false,
    created_at: "2026-11-01T15:00:00Z",
    updated_at: "2026-11-20T15:30:00Z",
  },
  {
    id: "mem-6",
    user_id: "user-1",
    category: "PRODUCTIVITY_PATTERNS",
    title: "Late Night Code Production (Dormant Trend)",
    description: "Previously observed habit of coding past midnight; no active telemetry recorded for 50 days.",
    source_type: "MODEL_INFERRED_PATTERN",
    validity_status: "OUTDATED",
    confidence: 0.42,
    observation_count: 18,
    reinforcement_count: 0,
    contradiction_count: 8,
    first_observed_at: "2026-08-10T01:00:00Z",
    last_observed_at: "2026-10-05T01:30:00Z",
    supporting_evidence: {
      inactive_days: 51,
      prior_confidence: 0.85,
    },
    evolution_history: [
      {
        timestamp: "2026-11-19T00:00:00Z",
        evolution_type: "OUTDATED",
        previous_status: "ACTIVE",
        new_status: "OUTDATED",
        previous_confidence: 0.85,
        new_confidence: 0.42,
        reason: "No observations in 50+ days.",
      },
    ],
    expiration_policy: {
      retention_days: 180,
      review_after_days: 30,
      auto_outdate_dormant_days: 45,
    },
    is_user_corrected: false,
    is_disabled: false,
    created_at: "2026-08-10T01:00:00Z",
    updated_at: "2026-11-19T00:00:00Z",
  },
];

export const behavioralMemoryApi = {
  async getOverview(): Promise<BehavioralMemoryOverview> {
    if (USE_MOCK) {
      return {
        total_memories: MOCK_MEMORIES.length,
        active_patterns_count: 3,
        emerging_patterns_count: 0,
        strengthening_patterns_count: 1,
        weakening_patterns_count: 0,
        outdated_patterns_count: 1,
        contradicted_patterns_count: 0,
        explicit_instructions_count: 1,
        user_corrected_count: 0,
        category_counts: {
          FOCUS_PATTERNS: 1,
          EXPLICIT_USER_INSTRUCTIONS: 1,
          RECOVERY_PATTERNS: 1,
          SUCCESSFUL_INTERVENTIONS: 1,
          UNSUCCESSFUL_INTERVENTIONS: 1,
          PRODUCTIVITY_PATTERNS: 1,
        },
        source_type_counts: {
          FREQUENTLY_OBSERVED_BEHAVIOR: 3,
          MODEL_INFERRED_PATTERN: 2,
          EXPLICIT_USER_INSTRUCTION: 1,
        },
        status_counts: {
          ACTIVE: 4,
          STRENGTHENING: 1,
          OUTDATED: 1,
        },
        primary_profile_status: "ESTABLISHED",
        primary_profile_confidence: 0.89,
        recent_memories: MOCK_MEMORIES,
        recent_evolutions: [
          {
            timestamp: "2026-11-19T00:00:00Z",
            evolution_type: "OUTDATED",
            previous_status: "ACTIVE",
            new_status: "OUTDATED",
            previous_confidence: 0.85,
            new_confidence: 0.42,
            reason: "No observations in 50+ days.",
            memory_id: "mem-6",
            memory_title: "Late Night Code Production (Dormant Trend)",
            category: "PRODUCTIVITY_PATTERNS",
          },
          {
            timestamp: "2026-11-12T17:00:00Z",
            evolution_type: "STRENGTHENING",
            previous_status: "EMERGING",
            new_status: "STRENGTHENING",
            previous_confidence: 0.72,
            new_confidence: 0.86,
            reason: "Corroborated across 5 additional context disruption events.",
            memory_id: "mem-3",
            memory_title: "High Interruption Vulnerability on Unplanned Context Switches",
            category: "RECOVERY_PATTERNS",
          },
        ],
      };
    }
    const res = await apiClient.request<BehavioralMemoryOverview>("/memory/overview", {
      method: "GET",
    });
    if (res.error || !res.data) {
      throw new Error(res.error?.message ?? "Failed to fetch behavioral memory overview");
    }
    return res.data;
  },

  async listMemories(params?: {
    category?: MemoryCategory;
    validity_status?: MemoryValidityStatus;
    source_type?: MemorySourceType;
    q?: string;
    include_disabled?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<BehavioralMemory[]> {
    if (USE_MOCK) {
      let filtered = [...MOCK_MEMORIES];
      if (params?.category) filtered = filtered.filter((m) => m.category === params.category);
      if (params?.validity_status) filtered = filtered.filter((m) => m.validity_status === params.validity_status);
      if (params?.source_type) filtered = filtered.filter((m) => m.source_type === params.source_type);
      if (params?.q) {
        const qLower = params.q.toLowerCase();
        filtered = filtered.filter((m) => m.title.toLowerCase().includes(qLower) || m.description.toLowerCase().includes(qLower));
      }
      return filtered;
    }
    const query: Record<string, any> = {};
    if (params?.category) query.category = params.category;
    if (params?.validity_status) query.validity_status = params.validity_status;
    if (params?.source_type) query.source_type = params.source_type;
    if (params?.q) query.q = params.q;
    if (params?.include_disabled !== undefined) query.include_disabled = params.include_disabled;
    if (params?.limit) query.limit = params.limit;
    if (params?.offset) query.offset = params.offset;

    const res = await apiClient.request<BehavioralMemory[]>("/memory", {
      method: "GET",
      query,
    });
    return res.data ?? [];
  },

  async createMemory(payload: MemoryCreateInput): Promise<BehavioralMemory> {
    if (USE_MOCK) {
      const newMem: BehavioralMemory = {
        id: `mem-${Date.now()}`,
        user_id: "user-1",
        category: payload.category,
        title: payload.title,
        description: payload.description,
        source_type: payload.source_type || "EXPLICIT_USER_INSTRUCTION",
        validity_status: "ACTIVE",
        confidence: payload.confidence ?? 1.0,
        observation_count: 1,
        reinforcement_count: 0,
        contradiction_count: 0,
        first_observed_at: new Date().toISOString(),
        last_observed_at: new Date().toISOString(),
        supporting_evidence: payload.supporting_evidence || {},
        evolution_history: [
          {
            timestamp: new Date().toISOString(),
            evolution_type: "EMERGING",
            previous_status: null,
            new_status: "ACTIVE",
            previous_confidence: null,
            new_confidence: payload.confidence ?? 1.0,
            reason: "User created explicit instruction.",
          },
        ],
        expiration_policy: {
          retention_days: 365,
          review_after_days: 30,
          auto_outdate_dormant_days: 45,
        },
        is_user_corrected: false,
        is_disabled: false,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      MOCK_MEMORIES.unshift(newMem);
      return newMem;
    }
    const res = await apiClient.request<BehavioralMemory>("/memory", {
      method: "POST",
      body: payload,
    });
    if (res.error || !res.data) throw new Error(res.error?.message ?? "Failed to create behavioral memory");
    return res.data;
  },

  async correctMemory(memoryId: string, payload: MemoryCorrectionInput): Promise<BehavioralMemory> {
    if (USE_MOCK) {
      const mem = MOCK_MEMORIES.find((m) => m.id === memoryId);
      if (!mem) throw new Error("Memory not found");
      mem.is_user_corrected = true;
      mem.user_correction_notes = payload.user_notes;
      if (payload.corrected_description) mem.description = payload.corrected_description;
      if (payload.is_inaccurate) {
        mem.validity_status = "CORRECTED";
        mem.confidence = Math.max(0.1, mem.confidence * 0.5);
      }
      return mem;
    }
    const res = await apiClient.request<BehavioralMemory>(`/memory/${memoryId}/correct`, {
      method: "POST",
      body: payload,
    });
    if (res.error || !res.data) throw new Error(res.error?.message ?? "Failed to correct memory");
    return res.data;
  },

  async deleteMemory(memoryId: string): Promise<void> {
    if (USE_MOCK) {
      const idx = MOCK_MEMORIES.findIndex((m) => m.id === memoryId);
      if (idx !== -1) MOCK_MEMORIES.splice(idx, 1);
      return;
    }
    const res = await apiClient.request<void>(`/memory/${memoryId}`, {
      method: "DELETE",
    });
    if (res.error) throw new Error(res.error.message);
  },

  async synthesize(): Promise<MemorySynthesisResult> {
    if (USE_MOCK) {
      return {
        created_memories_count: 2,
        reinforced_memories_count: 3,
        weakened_memories_count: 0,
        outdated_memories_count: 1,
        total_active_memories: 5,
        synthesis_messages: [
          "Extracted focus windows into long-term Focus Patterns.",
          "Updated recovery lag parameters from Interruption Sensitivity Index.",
          "Marked 1 dormant trend as outdated.",
        ],
      };
    }
    const res = await apiClient.request<MemorySynthesisResult>("/memory/synthesize", {
      method: "POST",
    });
    if (res.error || !res.data) throw new Error(res.error?.message ?? "Failed to synthesize behavioral memories");
    return res.data;
  },

  async getPreferences(): Promise<MemoryPreference> {
    if (USE_MOCK) {
      return {
        user_id: "user-1",
        disabled_categories: [],
        retention_policy_days: 365,
        auto_outdate_dormant_days: 45,
        auto_synthesis_enabled: true,
        updated_at: new Date().toISOString(),
      };
    }
    const res = await apiClient.request<MemoryPreference>("/memory/preferences", {
      method: "GET",
    });
    if (res.error || !res.data) throw new Error(res.error?.message ?? "Failed to get memory preferences");
    return res.data;
  },

  async updatePreferences(payload: Partial<MemoryPreference>): Promise<MemoryPreference> {
    if (USE_MOCK) {
      return {
        user_id: "user-1",
        disabled_categories: payload.disabled_categories ?? [],
        retention_policy_days: payload.retention_policy_days ?? 365,
        auto_outdate_dormant_days: payload.auto_outdate_dormant_days ?? 45,
        auto_synthesis_enabled: payload.auto_synthesis_enabled ?? true,
        updated_at: new Date().toISOString(),
      };
    }
    const res = await apiClient.request<MemoryPreference>("/memory/preferences", {
      method: "PATCH",
      body: payload,
    });
    if (res.error || !res.data) throw new Error(res.error?.message ?? "Failed to update memory preferences");
    return res.data;
  },

  async getSummaries(limit: number = 10): Promise<BehavioralTemporalSummary[]> {
    if (USE_MOCK) {
      return [
        {
          id: "sum-1",
          user_id: "user-1",
          period_type: "WEEKLY",
          period_start: "2026-11-18T00:00:00Z",
          period_end: "2026-11-25T00:00:00Z",
          summary_metrics: {
            total_memories: 6,
            emerging_count: 0,
            strengthened_count: 2,
            weakened_count: 0,
            outdated_count: 1,
            baseline_focus_duration: 52,
            baseline_recovery_seconds: 140,
            baseline_bfi: 24.5,
          },
          emerging_pattern_ids: [],
          strengthened_pattern_ids: ["mem-1", "mem-3"],
          weakened_pattern_ids: [],
          outdated_pattern_ids: ["mem-6"],
          narrative_summary: "Weekly Summary: Sustained morning focus windows confirmed. Late-night coding pattern retired due to lack of recent activity.",
          created_at: new Date().toISOString(),
        },
      ];
    }
    const res = await apiClient.request<BehavioralTemporalSummary[]>("/memory/summaries", {
      method: "GET",
      query: { limit },
    });
    return res.data ?? [];
  },

  async resetMemories(category?: MemoryCategory): Promise<{ status: string; deleted_count: number; message: string }> {
    if (USE_MOCK) {
      return {
        status: "success",
        deleted_count: category ? 2 : MOCK_MEMORIES.length,
        message: "Reset completed successfully.",
      };
    }
    const query: Record<string, any> = {};
    if (category) query.category = category;
    const res = await apiClient.request<{ status: string; deleted_count: number; message: string }>("/memory/reset", {
      method: "POST",
      query,
    });
    if (res.error || !res.data) throw new Error(res.error?.message ?? "Failed to reset memories");
    return res.data;
  },
};

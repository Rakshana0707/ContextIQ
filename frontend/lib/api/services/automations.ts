/**
 * Frontend Service for User-Defined Automation Rules and Trigger Engine (Phase 7.2).
 */
import { apiClient } from "@/lib/api/client";
import { USE_MOCK } from "@/lib/api";
import type {
  AutomationRule,
  AutomationExecution,
  AutomationRuleVersion,
} from "@/types/automations";

export const mockAutomationRules: AutomationRule[] = [
  {
    id: "rule-101",
    user_id: "usr-001",
    name: "Forgetting Risk Impending Warning",
    description: "Prepares a contextual reminder when a high-priority task forgetting risk exceeds 70%.",
    is_enabled: true,
    version: 2,
    priority: 1,
    cooldown_minutes: 60,
    max_executions_per_day: 3,
    requires_approval: true,
    risk_tier: "Tier 1",
    active_schedule: {
      days_of_week: [1, 2, 3, 4, 5],
      start_time: "09:00",
      end_time: "18:00",
      timezone: "UTC",
    },
    quiet_hours: {
      enabled: true,
      start_time: "22:00",
      end_time: "07:00",
      bypass_on_critical: false,
    },
    execution_count_today: 1,
    last_triggered_at: new Date(Date.now() - 3600000).toISOString(),
    created_at: new Date(Date.now() - 86400000).toISOString(),
    updated_at: new Date().toISOString(),
    triggers: [
      {
        id: "trig-101",
        rule_id: "rule-101",
        trigger_type: "FORGETTING_THRESHOLD_EXCEEDED",
        parameters: { threshold: 0.7 },
        is_authorized: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ],
    conditions: [
      {
        id: "cond-101",
        rule_id: "rule-101",
        condition_group: 0,
        logical_operator: "AND",
        field_path: "task.priority",
        operator: "IN_LIST",
        expected_value: ["HIGH", "CRITICAL"],
        min_evidence_observations: 1,
        confidence_threshold: 0.8,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ],
    actions: [
      {
        id: "act-101",
        rule_id: "rule-101",
        action_order: 1,
        action_identifier: "reminder:stage_context_warming",
        parameters_template: { lead_time_minutes: 15, channel: "IN_APP_TOAST" },
        is_critical: true,
        is_reversible: true,
        action_preview_template: {
          title: "Pre-Stage 15-Minute Task Warming Nudge",
          description: "Delivers a gentle focus preview before risk of lapse manifests.",
        },
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ],
  },
  {
    id: "rule-102",
    user_id: "usr-001",
    name: "Post-Focus Session Cognitive Cooldown",
    description: "Schedules a 10-minute non-negotiable recovery buffer following a sustained 50m focus block.",
    is_enabled: true,
    version: 1,
    priority: 2,
    cooldown_minutes: 45,
    max_executions_per_day: 4,
    requires_approval: false,
    risk_tier: "Tier 1",
    active_schedule: {
      days_of_week: [1, 2, 3, 4, 5],
      start_time: "08:30",
      end_time: "19:00",
      timezone: "UTC",
    },
    quiet_hours: {
      enabled: false,
      start_time: "22:00",
      end_time: "07:00",
      bypass_on_critical: false,
    },
    execution_count_today: 2,
    last_triggered_at: new Date(Date.now() - 7200000).toISOString(),
    created_at: new Date(Date.now() - 172800000).toISOString(),
    updated_at: new Date().toISOString(),
    triggers: [
      {
        id: "trig-102",
        rule_id: "rule-102",
        trigger_type: "RECOVERY_SESSION_ENDED",
        parameters: { min_duration_minutes: 45 },
        is_authorized: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ],
    conditions: [
      {
        id: "cond-102",
        rule_id: "rule-102",
        condition_group: 0,
        logical_operator: "AND",
        field_path: "session.duration_minutes",
        operator: "GREATER_THAN_OR_EQUAL",
        expected_value: 45,
        min_evidence_observations: 1,
        confidence_threshold: 0.0,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ],
    actions: [
      {
        id: "act-102",
        rule_id: "rule-102",
        action_order: 1,
        action_identifier: "recovery:insert_post_interruption_buffer",
        parameters_template: { buffer_duration_minutes: 10 },
        is_critical: false,
        is_reversible: true,
        action_preview_template: {
          title: "Insert 10-Minute Cognitive Recovery Buffer",
          description: "Guarantees working memory recharge after intense deep work.",
        },
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ],
  },
  {
    id: "rule-103",
    user_id: "usr-001",
    name: "Anti-Thrash Perimeter Shielding",
    description: "Detects context thrashing (>7 switches/min) and triggers fullscreen calming pause.",
    is_enabled: true,
    version: 3,
    priority: 1,
    cooldown_minutes: 30,
    max_executions_per_day: 5,
    requires_approval: true,
    risk_tier: "Tier 1",
    active_schedule: {
      days_of_week: [1, 2, 3, 4, 5],
      start_time: "09:00",
      end_time: "18:00",
      timezone: "UTC",
    },
    quiet_hours: {
      enabled: true,
      start_time: "22:00",
      end_time: "07:00",
      bypass_on_critical: true,
    },
    execution_count_today: 0,
    created_at: new Date(Date.now() - 259200000).toISOString(),
    updated_at: new Date().toISOString(),
    triggers: [
      {
        id: "trig-103",
        rule_id: "rule-103",
        trigger_type: "THRASHING_DETECTED",
        parameters: { threshold_switches_per_min: 7.0 },
        is_authorized: true,
        authorization_source: "telemetry_consent",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ],
    conditions: [
      {
        id: "cond-103",
        rule_id: "rule-103",
        condition_group: 0,
        logical_operator: "AND",
        field_path: "telemetry.switches_per_minute",
        operator: "GREATER_THAN",
        expected_value: 6.5,
        min_evidence_observations: 1,
        confidence_threshold: 0.85,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ],
    actions: [
      {
        id: "act-103",
        rule_id: "rule-103",
        action_order: 1,
        action_identifier: "intervention:anti_thrash_fullscreen_prompt",
        parameters_template: { switches_per_minute: 7.2 },
        is_critical: true,
        is_reversible: false,
        action_preview_template: {
          title: "Trigger Calming Focus Re-centering Overlay",
          description: "Halts attention dissipation and presents resumption anchor.",
        },
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ],
  },
];

export const mockExecutions: AutomationExecution[] = [
  {
    id: "exec-901",
    rule_id: "rule-101",
    user_id: "usr-001",
    trigger_event_id: "evt-81234",
    trigger_type: "FORGETTING_THRESHOLD_EXCEEDED",
    status: "PENDING_APPROVAL",
    matched_conditions: {
      field_path: "task.priority",
      operator: "IN_LIST",
      actual_value: "HIGH",
      passed: true,
    },
    idempotency_key: "idemp-019284124",
    execution_duration_ms: 12.4,
    executed_at: new Date(Date.now() - 3600000).toISOString(),
  },
  {
    id: "exec-902",
    rule_id: "rule-102",
    user_id: "usr-001",
    trigger_event_id: "evt-77123",
    trigger_type: "RECOVERY_SESSION_ENDED",
    status: "EXECUTED",
    matched_conditions: {
      field_path: "session.duration_minutes",
      operator: "GREATER_THAN_OR_EQUAL",
      actual_value: 50,
      passed: true,
    },
    idempotency_key: "idemp-889123841",
    execution_duration_ms: 8.7,
    executed_at: new Date(Date.now() - 7200000).toISOString(),
  },
];

export const automationsApi = {
  async listRules(isEnabled?: boolean): Promise<AutomationRule[]> {
    if (USE_MOCK) {
      if (isEnabled !== undefined) {
        return mockAutomationRules.filter((r) => r.is_enabled === isEnabled);
      }
      return [...mockAutomationRules];
    }
    const res = await apiClient.request<AutomationRule[]>("/automations/rules", {
      method: "GET",
      query: isEnabled !== undefined ? { is_enabled: isEnabled } : undefined,
    });
    if (res.error) throw new Error(res.error.message);
    return res.data ?? [];
  },

  async getRule(id: string): Promise<AutomationRule> {
    if (USE_MOCK) {
      const found = mockAutomationRules.find((r) => r.id === id);
      if (!found) throw new Error("Automation rule not found");
      return found;
    }
    const res = await apiClient.request<AutomationRule>(`/automations/rules/${id}`, {
      method: "GET",
    });
    if (res.error) throw new Error(res.error.message);
    return res.data!;
  },

  async createRule(payload: any): Promise<AutomationRule> {
    if (USE_MOCK) {
      const newRule: AutomationRule = {
        id: `rule-${Date.now()}`,
        user_id: "usr-001",
        version: 1,
        execution_count_today: 0,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        ...payload,
      };
      mockAutomationRules.unshift(newRule);
      return newRule;
    }
    const res = await apiClient.request<AutomationRule>("/automations/rules", {
      method: "POST",
      body: payload,
    });
    if (res.error) throw new Error(res.error.message);
    return res.data!;
  },

  async updateRule(id: string, payload: any): Promise<AutomationRule> {
    if (USE_MOCK) {
      const idx = mockAutomationRules.findIndex((r) => r.id === id);
      if (idx === -1) throw new Error("Automation rule not found");
      mockAutomationRules[idx] = {
        ...mockAutomationRules[idx],
        ...payload,
        version: mockAutomationRules[idx].version + 1,
        updated_at: new Date().toISOString(),
      };
      return mockAutomationRules[idx];
    }
    const res = await apiClient.request<AutomationRule>(`/automations/rules/${id}`, {
      method: "PUT",
      body: payload,
    });
    if (res.error) throw new Error(res.error.message);
    return res.data!;
  },

  async toggleRule(id: string): Promise<AutomationRule> {
    if (USE_MOCK) {
      const rule = mockAutomationRules.find((r) => r.id === id);
      if (!rule) throw new Error("Rule not found");
      rule.is_enabled = !rule.is_enabled;
      rule.updated_at = new Date().toISOString();
      return { ...rule };
    }
    const res = await apiClient.request<AutomationRule>(`/automations/rules/${id}/toggle`, {
      method: "PATCH",
    });
    if (res.error) throw new Error(res.error.message);
    return res.data!;
  },

  async deleteRule(id: string): Promise<void> {
    if (USE_MOCK) {
      const idx = mockAutomationRules.findIndex((r) => r.id === id);
      if (idx !== -1) mockAutomationRules.splice(idx, 1);
      return;
    }
    const res = await apiClient.request<void>(`/automations/rules/${id}`, {
      method: "DELETE",
    });
    if (res.error) throw new Error(res.error.message);
  },

  async listExecutions(ruleId?: string): Promise<AutomationExecution[]> {
    if (USE_MOCK) {
      if (ruleId) {
        return mockExecutions.filter((e) => e.rule_id === ruleId);
      }
      return [...mockExecutions];
    }
    const res = await apiClient.request<AutomationExecution[]>("/automations/executions", {
      method: "GET",
      query: ruleId ? { rule_id: ruleId } : undefined,
    });
    if (res.error) throw new Error(res.error.message);
    return res.data ?? [];
  },

  async evaluateTrigger(triggerType: string, contextPayload: Record<string, any>): Promise<any> {
    if (USE_MOCK) {
      return {
        trigger_type: triggerType,
        trigger_event_id: `evt-${Date.now()}`,
        evaluated_rules_count: mockAutomationRules.length,
        matched_rules_count: 1,
        results: [
          {
            rule_id: mockAutomationRules[0].id,
            rule_name: mockAutomationRules[0].name,
            is_matched: true,
            status: "PENDING_APPROVAL",
            matched_conditions: { passed: true },
            proposed_actions: mockAutomationRules[0].actions || [],
          },
        ],
      };
    }
    const res = await apiClient.request<any>("/automations/evaluate", {
      method: "POST",
      body: {
        trigger_type: triggerType,
        context_payload: contextPayload,
      },
    });
    if (res.error) throw new Error(res.error.message);
    return res.data;
  },
};

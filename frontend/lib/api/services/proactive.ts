import { apiClient, USE_MOCK } from "@/lib/api/client";
import type {
  ProactiveFeedItem,
  EventProcessingResult,
  DeadLetterRecord,
} from "@/types/proactive";

const mockFeedItems: ProactiveFeedItem[] = [
  {
    id: "feed-001",
    user_id: "usr-001",
    event_id: "evt-thrash-01",
    detection_type: "THRASHING_DETECTED",
    title: "Context Thrashing Detected",
    why_it_matters:
      "You switched applications 8 times in the last minute. Rapid task switching degrades working memory and compounds cognitive fatigue.",
    related_context: {
      switch_count: 8,
      active_apps: ["IDE", "Slack", "Browser", "Terminal", "Email"],
    },
    recommended_response:
      "Shield your workspace with a 25-minute focus session or close unused communication tabs.",
    evidence: {
      switches_per_min: 8.0,
      confidence_score: 0.92,
      sampling_window_sec: 60,
    },
    confidence_score: 0.92,
    uncertainty_lower_bound: 0.82,
    uncertainty_upper_bound: 0.97,
    conformal_interval_text: "Conformal [82%-97%] (90% coverage)",
    status: "ACTIVE",
    requires_approval: true,
    suggested_action: {
      action_type: "CREATE_FOCUS_SESSION",
      label: "Start 25m Focus Block",
      parameters: { duration_minutes: 25 },
    },
    created_at: new Date(Date.now() - 15 * 60000).toISOString(),
    updated_at: new Date(Date.now() - 15 * 60000).toISOString(),
  },
  {
    id: "feed-002",
    user_id: "usr-001",
    event_id: "evt-forget-02",
    detection_type: "FORGETTING_RISK_SPIKE",
    title: "Forgetting Risk Spike: 'Review Architecture RFC'",
    why_it_matters:
      "Statistical lapse probability reached 78%. Without a prompt, delayed micro-tasks have an exponentially lower resumption rate.",
    related_context: {
      task_id: "tsk-991",
      task_title: "Review Architecture RFC",
      lapse_probability: 0.78,
    },
    recommended_response:
      "Prepare a context reminder or re-anchor your current objective.",
    evidence: {
      predicted_decay: 0.78,
      hours_inactive: 3.2,
    },
    confidence_score: 0.88,
    uncertainty_lower_bound: 0.75,
    uncertainty_upper_bound: 0.94,
    conformal_interval_text: "Conformal [75%-94%] (90% coverage)",
    status: "ACTIVE",
    requires_approval: true,
    suggested_action: {
      action_type: "SEND_REMINDER",
      label: "Send Task Reminder",
      parameters: { task_id: "tsk-991" },
    },
    created_at: new Date(Date.now() - 45 * 60000).toISOString(),
    updated_at: new Date(Date.now() - 45 * 60000).toISOString(),
  },
];

export const proactiveApi = {
  getFeed: async (statusFilter?: string, limit: number = 20): Promise<ProactiveFeedItem[]> => {
    if (USE_MOCK) {
      if (statusFilter && statusFilter !== "ALL") {
        return mockFeedItems.filter((f) => f.status === statusFilter);
      }
      return [...mockFeedItems];
    }
    const query: Record<string, any> = { limit };
    if (statusFilter) query.status_filter = statusFilter;
    const res = await apiClient.request<ProactiveFeedItem[]>("/proactive/feed", {
      method: "GET",
      query,
    });
    if (res.error) throw new Error(res.error.message);
    return res.data ?? [];
  },

  respondToFeedItem: async (
    itemId: string,
    action: "APPROVE" | "SNOOZE" | "DISMISS",
    snoozeMinutes: number = 60
  ): Promise<ProactiveFeedItem> => {
    if (USE_MOCK) {
      const item = mockFeedItems.find((f) => f.id === itemId);
      if (!item) throw new Error("Item not found");
      if (action === "APPROVE") item.status = "ACTIONED";
      else if (action === "SNOOZE") {
        item.status = "SNOOZED";
        item.snoozed_until = new Date(Date.now() + snoozeMinutes * 60000).toISOString();
      } else if (action === "DISMISS") item.status = "DISMISSED";
      item.updated_at = new Date().toISOString();
      return { ...item };
    }
    const res = await apiClient.request<ProactiveFeedItem>(`/proactive/feed/${itemId}/action`, {
      method: "POST",
      body: {
        action,
        snooze_minutes: snoozeMinutes,
      },
    });
    if (res.error) throw new Error(res.error.message);
    return res.data!;
  },

  ingestEvent: async (payload: {
    event_type: string;
    payload?: Record<string, any>;
    device_id?: string;
    source?: string;
    idempotency_key?: string;
  }): Promise<EventProcessingResult> => {
    if (USE_MOCK) {
      return {
        event_id: `evt-${Date.now()}`,
        status: "PROCESSED",
        is_duplicate: false,
        rules_matched: 1,
        executions_created: 1,
        proactive_feed_item_created: true,
        proactive_feed_item_id: "feed-mock-new",
        suppressed_by_fatigue: false,
        rationale: "Proactive intelligence insight generated and posted to user feed.",
      };
    }
    const res = await apiClient.request<EventProcessingResult>("/proactive/events/ingest", {
      method: "POST",
      body: payload,
    });
    if (res.error) throw new Error(res.error.message);
    return res.data!;
  },

  simulateDetection: async (detectionType: string): Promise<EventProcessingResult> => {
    if (USE_MOCK) {
      const newItem: ProactiveFeedItem = {
        id: `feed-sim-${Date.now()}`,
        user_id: "usr-001",
        detection_type: `${detectionType.toUpperCase()}_DETECTED`,
        title: `Simulated ${detectionType} Detection`,
        why_it_matters: "Simulated behavioral event generated for live testing and inspection.",
        related_context: { simulated: true, timestamp: new Date().toISOString() },
        recommended_response: "Review simulated recommendation.",
        evidence: { simulation_mode: true },
        confidence_score: 0.89,
        uncertainty_lower_bound: 0.78,
        uncertainty_upper_bound: 0.95,
        conformal_interval_text: "Conformal [78%-95%] (90% coverage)",
        status: "ACTIVE",
        requires_approval: true,
        suggested_action: {
          action_type: "EXECUTE_WORKFLOW",
          label: "Execute Workflow",
        },
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      mockFeedItems.unshift(newItem);
      return {
        event_id: `evt-sim-${Date.now()}`,
        status: "PROCESSED",
        is_duplicate: false,
        rules_matched: 1,
        executions_created: 1,
        proactive_feed_item_created: true,
        proactive_feed_item_id: newItem.id,
        suppressed_by_fatigue: false,
        rationale: "Simulated proactive intelligence insight generated.",
      };
    }
    const res = await apiClient.request<EventProcessingResult>("/proactive/simulate-detection", {
      method: "POST",
      query: { detection_type: detectionType },
    });
    if (res.error) throw new Error(res.error.message);
    return res.data!;
  },

  getDeadLetterRecords: async (limit: number = 50): Promise<DeadLetterRecord[]> => {
    if (USE_MOCK) return [];
    const res = await apiClient.request<DeadLetterRecord[]>("/proactive/dead-letter", {
      method: "GET",
      query: { limit },
    });
    if (res.error) throw new Error(res.error.message);
    return res.data ?? [];
  },
};

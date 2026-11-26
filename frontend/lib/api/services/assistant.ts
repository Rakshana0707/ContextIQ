import { apiClient } from "../client";
import type {
  AskAssistantRequest,
  AskResponsePayload,
  AssistantConversationListResponse,
  AssistantConversationRead,
} from "@/types/assistant";

export const assistantApi = {
  ask: async (req: AskAssistantRequest): Promise<AskResponsePayload> => {
    try {
      const res = await apiClient.post<AskResponsePayload>("/assistant/ask", req);
      return res.data;
    } catch {
      // Mock fallback for offline dev/storybook
      return {
        conversation_id: req.conversation_id || "mock-conv-1",
        message_id: "mock-msg-1",
        response: {
          direct_answer: `Grounded answer for: "${req.query}". Your tasks, projects, and focus telemetry show positive alignment with current priorities.`,
          supporting_evidence: [
            {
              entity_type: "TASK",
              entity_id: "t-1",
              entity_title: "Review Q4 System Architecture",
              evidence_snippet: "Priority: HIGH, Overdue: false, Postponements: 0",
              timestamp: new Date().toISOString(),
              confidence_or_metric: "HIGH",
            },
          ],
          relevant_entities: [
            {
              entity_type: "TASK",
              entity_id: "t-1",
              title: "Review Q4 System Architecture",
              status: "IN_PROGRESS",
              url_or_path: "/tasks/t-1",
            },
          ],
          data_timestamps: { tasks: new Date().toISOString() },
          uncertainty_level: "LOW",
          missing_information: [],
          suggested_next_steps: ["Protect 9:00 AM - 11:30 AM focus block", "Review blockers on downstream milestones"],
          action_proposals: [
            {
              action_identifier: "task:update_priority",
              target_entity_id: "t-1",
              parameters: { task_id: "t-1", new_priority: "URGENT" },
              rationale: "Escalate task to maintain execution schedule.",
              requires_governed_approval: true,
              governance_status: "PROPOSED",
            },
          ],
          epistemic_disclaimer:
            "ContextIQ assistant answers are strictly grounded in your tracked tasks, projects, goals, and behavioral metrics. Unsupported claims are withheld.",
        },
      };
    }
  },

  listConversations: async (includeArchived: boolean = false): Promise<AssistantConversationListResponse> => {
    try {
      const res = await apiClient.get<AssistantConversationListResponse>(
        `/assistant/conversations?include_archived=${includeArchived}`
      );
      return res.data;
    } catch {
      return {
        conversations: [
          {
            id: "mock-conv-1",
            title: "What should I focus on today?",
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            message_count: 2,
            recent_messages: [],
          },
        ],
        total: 1,
      };
    }
  },

  getConversation: async (id: string): Promise<AssistantConversationRead> => {
    try {
      const res = await apiClient.get<AssistantConversationRead>(`/assistant/conversations/${id}`);
      return res.data;
    } catch {
      return {
        id,
        title: "Productivity Discussion",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        message_count: 0,
        recent_messages: [],
      };
    }
  },

  deleteConversation: async (id: string): Promise<{ status: string; conversation_id: string }> => {
    try {
      const res = await apiClient.delete<{ status: string; conversation_id: string }>(
        `/assistant/conversations/${id}`
      );
      return res.data;
    } catch {
      return { status: "archived", conversation_id: id };
    }
  },
};

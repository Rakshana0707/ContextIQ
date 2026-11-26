export interface EvidenceItem {
  entity_type: string;
  entity_id: string;
  entity_title: string;
  evidence_snippet: string;
  timestamp?: string | null;
  confidence_or_metric?: string | null;
}

export interface EntityReference {
  entity_type: string;
  entity_id: string;
  title: string;
  status?: string | null;
  url_or_path?: string | null;
}

export interface ActionProposal {
  action_identifier: string;
  target_entity_id?: string | null;
  parameters: Record<string, any>;
  rationale: string;
  requires_governed_approval: boolean;
  governance_status: string;
}

export interface StructuredAssistantResponse {
  direct_answer: string;
  supporting_evidence: EvidenceItem[];
  relevant_entities: EntityReference[];
  data_timestamps: Record<string, string | null>;
  uncertainty_level: "LOW" | "MEDIUM" | "HIGH" | "UNCERTAIN";
  uncertainty_notes?: string | null;
  missing_information: string[];
  suggested_next_steps: string[];
  action_proposals: ActionProposal[];
  epistemic_disclaimer?: string | null;
}

export interface AskAssistantRequest {
  query: string;
  conversation_id?: string | null;
  include_evidence?: boolean;
  include_proposals?: boolean;
}

export interface AskResponsePayload {
  conversation_id: string;
  message_id: string;
  response: StructuredAssistantResponse;
}

export interface AssistantMessageRead {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  structured_response?: StructuredAssistantResponse | null;
  created_at: string;
}

export interface AssistantConversationRead {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  recent_messages: AssistantMessageRead[];
}

export interface AssistantConversationListResponse {
  conversations: AssistantConversationRead[];
  total: number;
}

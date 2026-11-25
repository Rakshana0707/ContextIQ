import { apiClient, USE_MOCK } from "@/lib/api/client";
import type {
  AutoPopulateResult,
  DirectRelationships,
  GraphNodeType,
  GraphOverview,
  GraphRelationshipType,
  KnowledgeEvidence,
  KnowledgeGraphVersion,
  KnowledgeNode,
  KnowledgeRelationship,
  MultiHopTraversal,
} from "@/types/knowledge_graph";

// Mock Data for offline / mock testing
const MOCK_NODES: KnowledgeNode[] = [
  {
    id: "node-user-1",
    user_id: "user-1",
    node_type: "USER",
    name: "Alex Rivera",
    entity_id: "user-1",
    entity_table: "users",
    properties: { role_persona: "developer", focus_rhythm: "morning" },
    is_archived: false,
    created_at: new Date(Date.now() - 30 * 86400000).toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "node-goal-1",
    user_id: "user-1",
    node_type: "GOAL",
    name: "Ship ContextIQ Knowledge Engine",
    entity_id: "goal-1",
    entity_table: "goals",
    properties: { category: "PRODUCTIVITY", progress_pct: 75.0, status: "ACTIVE" },
    is_archived: false,
    created_at: new Date(Date.now() - 20 * 86400000).toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "node-proj-1",
    user_id: "user-1",
    node_type: "PROJECT",
    name: "Phase 8 Knowledge Graph Integration",
    entity_id: "proj-1",
    entity_table: "projects",
    properties: { status: "ACTIVE", priority: "HIGH" },
    is_archived: false,
    created_at: new Date(Date.now() - 10 * 86400000).toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "node-task-1",
    user_id: "user-1",
    node_type: "TASK",
    name: "Implement Graph Traversal API",
    entity_id: "task-1",
    entity_table: "tasks",
    properties: { status: "IN_PROGRESS", priority: "HIGH", context_tag: "backend" },
    is_archived: false,
    created_at: new Date(Date.now() - 5 * 86400000).toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "node-task-2",
    user_id: "user-1",
    node_type: "TASK",
    name: "PostgreSQL Recursive CTE Schemas",
    entity_id: "task-2",
    entity_table: "tasks",
    properties: { status: "COMPLETED", priority: "HIGH", context_tag: "database" },
    is_archived: false,
    created_at: new Date(Date.now() - 7 * 86400000).toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "node-pat-1",
    user_id: "user-1",
    node_type: "BEHAVIORAL_PATTERN",
    name: "Deep Work Morning Momentum",
    entity_id: "pat-1",
    entity_table: "behavioral_patterns",
    properties: { category: "FOCUS_OPTIMAL", friction_impact: 0.12, confidence: 0.94 },
    is_archived: false,
    created_at: new Date(Date.now() - 15 * 86400000).toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "node-pat-2",
    user_id: "user-1",
    node_type: "BEHAVIORAL_PATTERN",
    name: "Afternoon Meeting Context Thrash",
    entity_id: "pat-2",
    entity_table: "behavioral_patterns",
    properties: { category: "FRICTION", friction_impact: 0.78, confidence: 0.86 },
    is_archived: false,
    created_at: new Date(Date.now() - 12 * 86400000).toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "node-cal-1",
    user_id: "user-1",
    node_type: "CALENDAR_EVENT",
    name: "Sprint Retrospective & Roadmap",
    entity_id: "cal-1",
    entity_table: "external_calendar_events",
    properties: { transparency: "OPAQUE", start_time: "2026-11-26T14:00:00Z" },
    is_archived: false,
    created_at: new Date(Date.now() - 3 * 86400000).toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "node-rec-1",
    user_id: "user-1",
    node_type: "RECOMMENDATION",
    name: "Reserve 90m Focus Buffer Before Retro",
    entity_id: "rec-1",
    entity_table: "recommendations",
    properties: { recommendation_type: "BREAK_SUGGESTION", priority: 2 },
    is_archived: false,
    created_at: new Date(Date.now() - 2 * 86400000).toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "node-dec-1",
    user_id: "user-1",
    node_type: "DECISION",
    name: "Approve Afternoon Focus Shield",
    entity_id: "dec-1",
    entity_table: "decisions",
    properties: { chosen_option: "APPROVE_FOCUS_BLOCK", rationale: "Mitigate 24m resumption lag" },
    is_archived: false,
    created_at: new Date(Date.now() - 1 * 86400000).toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "node-out-1",
    user_id: "user-1",
    node_type: "OUTCOME",
    name: "45 Minutes Cognitive Delay Avoided",
    entity_id: "out-1",
    entity_table: "outcomes",
    properties: { outcome_type: "RECOVERY_RESTORED", delay_reduction_minutes: 45 },
    is_archived: false,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

const MOCK_RELATIONSHIPS: KnowledgeRelationship[] = [
  {
    id: "edge-1",
    user_id: "user-1",
    source_node_id: "node-proj-1",
    target_node_id: "node-goal-1",
    relationship_type: "CONTRIBUTES_TO",
    evidence_source: "EXPLICIT_USER",
    confidence: 1.0,
    is_inferred: false,
    weight: 1.0,
    valid_from: new Date().toISOString(),
    provenance_payload: { declared_by: "user_ui" },
    evidences: [
      {
        id: "ev-1",
        user_id: "user-1",
        relationship_id: "edge-1",
        evidence_type: "EXPLICIT_USER",
        confidence_score: 1.0,
        payload: { channel: "project_dashboard" },
        recorded_at: new Date().toISOString(),
        is_valid: true,
      },
    ],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "edge-2",
    user_id: "user-1",
    source_node_id: "node-task-1",
    target_node_id: "node-proj-1",
    relationship_type: "BELONGS_TO",
    evidence_source: "EXPLICIT_USER",
    confidence: 1.0,
    is_inferred: false,
    weight: 1.0,
    valid_from: new Date().toISOString(),
    provenance_payload: {},
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "edge-3",
    user_id: "user-1",
    source_node_id: "node-task-1",
    target_node_id: "node-task-2",
    relationship_type: "DEPENDS_ON",
    evidence_source: "EXPLICIT_USER",
    confidence: 1.0,
    is_inferred: false,
    weight: 1.0,
    valid_from: new Date().toISOString(),
    provenance_payload: {},
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "edge-4",
    user_id: "user-1",
    source_node_id: "node-pat-2",
    target_node_id: "node-rec-1",
    relationship_type: "GENERATED_BY",
    evidence_source: "ML_PREDICTION",
    confidence: 0.88,
    is_inferred: true,
    weight: 0.88,
    valid_from: new Date().toISOString(),
    provenance_payload: { model: "ContextThrashDetector_v2", shap_value: 0.42 },
    evidences: [
      {
        id: "ev-2",
        user_id: "user-1",
        relationship_id: "edge-4",
        evidence_type: "ML_PREDICTION",
        confidence_score: 0.88,
        payload: { model_version: "2.3.1", risk_category: "FRICTION" },
        recorded_at: new Date().toISOString(),
        is_valid: true,
      },
    ],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "edge-5",
    user_id: "user-1",
    source_node_id: "node-rec-1",
    target_node_id: "node-dec-1",
    relationship_type: "RESULTED_IN",
    evidence_source: "EXPLICIT_USER",
    confidence: 1.0,
    is_inferred: false,
    weight: 1.0,
    valid_from: new Date().toISOString(),
    provenance_payload: {},
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "edge-6",
    user_id: "user-1",
    source_node_id: "node-dec-1",
    target_node_id: "node-out-1",
    relationship_type: "RESULTED_IN",
    evidence_source: "EXPLICIT_USER",
    confidence: 1.0,
    is_inferred: false,
    weight: 1.0,
    valid_from: new Date().toISOString(),
    provenance_payload: {},
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "edge-7",
    user_id: "user-1",
    source_node_id: "node-cal-1",
    target_node_id: "node-pat-2",
    relationship_type: "INFLUENCES",
    evidence_source: "STATISTICAL_ANALYSIS",
    confidence: 0.82,
    is_inferred: true,
    weight: 0.82,
    valid_from: new Date().toISOString(),
    provenance_payload: { p_value: 0.004, correlation: 0.67 },
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

export const knowledgeGraphApi = {
  async getOverview(): Promise<GraphOverview> {
    if (USE_MOCK) {
      return {
        total_nodes: MOCK_NODES.length,
        total_relationships: MOCK_RELATIONSHIPS.length,
        node_type_counts: {
          USER: 1,
          GOAL: 1,
          PROJECT: 1,
          TASK: 2,
          BEHAVIORAL_PATTERN: 2,
          CALENDAR_EVENT: 1,
          RECOMMENDATION: 1,
          DECISION: 1,
          OUTCOME: 1,
        },
        relationship_type_counts: {
          CONTRIBUTES_TO: 1,
          BELONGS_TO: 1,
          DEPENDS_ON: 1,
          GENERATED_BY: 1,
          RESULTED_IN: 2,
          INFLUENCES: 1,
        },
        current_version: 4,
        inferred_relationship_count: 2,
        explicit_relationship_count: 5,
        recent_changes: [
          {
            id: "ver-4",
            user_id: "user-1",
            version_number: 4,
            change_type: "AUTO_POPULATED",
            affected_node_ids: ["node-task-1", "node-task-2"],
            affected_relationship_ids: ["edge-1", "edge-2", "edge-3"],
            change_summary: "Auto-populated knowledge graph from operational entities.",
            version_metadata: { nodes_count: 11, edges_count: 7 },
            created_at: new Date().toISOString(),
          },
        ],
      };
    }
    const res = await apiClient.request<GraphOverview>("/graph/overview", {
      method: "GET",
    });
    if (res.error || !res.data) {
      throw new Error(res.error?.message ?? "Failed to fetch graph overview");
    }
    return res.data;
  },

  async getNodes(params?: {
    q?: string;
    node_type?: GraphNodeType[];
    include_archived?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<KnowledgeNode[]> {
    if (USE_MOCK) {
      let filtered = [...MOCK_NODES];
      if (params?.q) {
        const qLower = params.q.toLowerCase();
        filtered = filtered.filter((n) => n.name.toLowerCase().includes(qLower));
      }
      if (params?.node_type && params.node_type.length > 0) {
        filtered = filtered.filter((n) => params.node_type?.includes(n.node_type));
      }
      if (!params?.include_archived) {
        filtered = filtered.filter((n) => !n.is_archived);
      }
      return filtered;
    }
    const query: Record<string, any> = {};
    if (params?.q) query.q = params.q;
    if (params?.node_type) query.node_type = params.node_type;
    if (params?.include_archived !== undefined) query.include_archived = params.include_archived;
    if (params?.limit) query.limit = params.limit;
    if (params?.offset) query.offset = params.offset;

    const res = await apiClient.request<KnowledgeNode[]>("/graph/nodes", {
      method: "GET",
      query,
    });
    return res.data ?? [];
  },

  async getNode(nodeId: string): Promise<KnowledgeNode> {
    if (USE_MOCK) {
      const node = MOCK_NODES.find((n) => n.id === nodeId);
      if (!node) throw new Error("Node not found");
      return node;
    }
    const res = await apiClient.request<KnowledgeNode>(`/graph/nodes/${nodeId}`, {
      method: "GET",
    });
    if (res.error || !res.data) throw new Error(res.error?.message ?? "Failed to fetch node");
    return res.data;
  },

  async getRelated(nodeId: string): Promise<DirectRelationships> {
    if (USE_MOCK) {
      const node = MOCK_NODES.find((n) => n.id === nodeId);
      if (!node) throw new Error("Node not found");
      const outgoing = MOCK_RELATIONSHIPS.filter((e) => e.source_node_id === nodeId);
      const incoming = MOCK_RELATIONSHIPS.filter((e) => e.target_node_id === nodeId);
      return {
        node,
        outgoing,
        incoming,
        total_connections: outgoing.length + incoming.length,
      };
    }
    const res = await apiClient.request<DirectRelationships>(`/graph/nodes/${nodeId}/related`, {
      method: "GET",
    });
    if (res.error || !res.data) throw new Error(res.error?.message ?? "Failed to fetch related entities");
    return res.data;
  },

  async getRelationships(params?: {
    source_node_id?: string;
    target_node_id?: string;
    relationship_type?: GraphRelationshipType[];
    is_inferred?: boolean;
    active_only?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<KnowledgeRelationship[]> {
    if (USE_MOCK) {
      let filtered = [...MOCK_RELATIONSHIPS];
      if (params?.source_node_id) {
        filtered = filtered.filter((r) => r.source_node_id === params.source_node_id);
      }
      if (params?.target_node_id) {
        filtered = filtered.filter((r) => r.target_node_id === params.target_node_id);
      }
      if (params?.relationship_type && params.relationship_type.length > 0) {
        filtered = filtered.filter((r) => params.relationship_type?.includes(r.relationship_type));
      }
      if (params?.is_inferred !== undefined) {
        filtered = filtered.filter((r) => r.is_inferred === params.is_inferred);
      }
      return filtered;
    }
    const query: Record<string, any> = {};
    if (params?.source_node_id) query.source_node_id = params.source_node_id;
    if (params?.target_node_id) query.target_node_id = params.target_node_id;
    if (params?.relationship_type) query.relationship_type = params.relationship_type;
    if (params?.is_inferred !== undefined) query.is_inferred = params.is_inferred;
    if (params?.active_only !== undefined) query.active_only = params.active_only;
    if (params?.limit) query.limit = params.limit;
    if (params?.offset) query.offset = params.offset;

    const res = await apiClient.request<KnowledgeRelationship[]>("/graph/relationships", {
      method: "GET",
      query,
    });
    return res.data ?? [];
  },

  async createRelationship(payload: {
    source_node_id: string;
    target_node_id: string;
    relationship_type: GraphRelationshipType;
    evidence_source?: string;
    confidence?: number;
    is_inferred?: boolean;
    weight?: number;
    provenance_payload?: Record<string, any>;
  }): Promise<KnowledgeRelationship> {
    if (USE_MOCK) {
      const newEdge: KnowledgeRelationship = {
        id: `edge-${Date.now()}`,
        user_id: "user-1",
        source_node_id: payload.source_node_id,
        target_node_id: payload.target_node_id,
        relationship_type: payload.relationship_type,
        evidence_source: payload.evidence_source || "EXPLICIT_USER",
        confidence: payload.confidence ?? 1.0,
        is_inferred: payload.is_inferred ?? false,
        weight: payload.weight ?? 1.0,
        valid_from: new Date().toISOString(),
        provenance_payload: payload.provenance_payload || {},
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      MOCK_RELATIONSHIPS.push(newEdge);
      return newEdge;
    }
    const res = await apiClient.request<KnowledgeRelationship>("/graph/relationships", {
      method: "POST",
      body: payload,
    });
    if (res.error || !res.data) throw new Error(res.error?.message ?? "Failed to create relationship");
    return res.data;
  },

  async removeInferredRelationship(relId: string): Promise<void> {
    if (USE_MOCK) {
      const idx = MOCK_RELATIONSHIPS.findIndex((r) => r.id === relId);
      if (idx !== -1) MOCK_RELATIONSHIPS.splice(idx, 1);
      return;
    }
    const res = await apiClient.request<void>(`/graph/relationships/${relId}/inferred`, {
      method: "DELETE",
    });
    if (res.error) throw new Error(res.error.message);
  },

  async getEvidence(relId: string): Promise<KnowledgeEvidence[]> {
    if (USE_MOCK) {
      const edge = MOCK_RELATIONSHIPS.find((r) => r.id === relId);
      return edge?.evidences || [];
    }
    const res = await apiClient.request<KnowledgeEvidence[]>(`/graph/relationships/${relId}/evidence`, {
      method: "GET",
    });
    return res.data ?? [];
  },

  async autoPopulate(): Promise<AutoPopulateResult> {
    if (USE_MOCK) {
      return {
        created_nodes_count: 11,
        created_edges_count: 7,
        attached_evidence_count: 3,
        new_version: 5,
        summary_messages: [
          "Auto-populated knowledge graph with 11 nodes and 7 edges.",
          "Connected tasks to projects, goals, and external calendar events.",
        ],
      };
    }
    const res = await apiClient.request<AutoPopulateResult>("/graph/populate", {
      method: "POST",
    });
    if (res.error || !res.data) throw new Error(res.error?.message ?? "Failed to auto-populate graph");
    return res.data;
  },

  async getVersions(limit: number = 20): Promise<KnowledgeGraphVersion[]> {
    if (USE_MOCK) {
      return [
        {
          id: "ver-1",
          user_id: "user-1",
          version_number: 1,
          change_type: "AUTO_POPULATED",
          affected_node_ids: ["node-task-1", "node-task-2"],
          affected_relationship_ids: ["edge-1"],
          change_summary: "Initial knowledge graph snapshot.",
          version_metadata: {},
          created_at: new Date().toISOString(),
        },
      ];
    }
    const res = await apiClient.request<KnowledgeGraphVersion[]>("/graph/versions", {
      method: "GET",
      query: { limit },
    });
    return res.data ?? [];
  },

  async traverseMultiHop(rootNodeId: string, maxDepth: number = 3, maxPaths: number = 25): Promise<MultiHopTraversal> {
    if (USE_MOCK) {
      return {
        root_node_id: rootNodeId,
        max_depth_reached: 2,
        paths: [],
        visited_nodes_count: 4,
      };
    }
    const res = await apiClient.request<MultiHopTraversal>("/graph/traversal/multihop", {
      method: "GET",
      query: { root_node_id: rootNodeId, max_depth: maxDepth, max_paths: maxPaths },
    });
    if (res.error || !res.data) throw new Error(res.error?.message ?? "Failed to traverse multi-hop");
    return res.data;
  },
};

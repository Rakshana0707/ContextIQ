export type GraphNodeType =
  | "USER"
  | "TASK"
  | "PROJECT"
  | "GOAL"
  | "MILESTONE"
  | "HABIT"
  | "BEHAVIORAL_PATTERN"
  | "CONTEXT"
  | "INTERRUPTION"
  | "RECOMMENDATION"
  | "DECISION"
  | "CALENDAR_EVENT"
  | "WORKFLOW"
  | "OUTCOME"
  | "RESOURCE";

export type GraphRelationshipType =
  | "BELONGS_TO"
  | "DEPENDS_ON"
  | "CONTRIBUTES_TO"
  | "BLOCKS"
  | "RELATED_TO"
  | "GENERATED_BY"
  | "INFLUENCES"
  | "PRECEDED_BY"
  | "RESULTED_IN"
  | "SUPPORTS"
  | "CONFLICTS_WITH"
  | "COMPLETED_AS"
  | "DERIVED_FROM";

export interface KnowledgeNode {
  id: string;
  user_id: string;
  node_type: GraphNodeType;
  name: string;
  entity_id: string;
  entity_table: string;
  properties: Record<string, any>;
  is_archived: boolean;
  archived_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeEvidence {
  id: string;
  user_id: string;
  relationship_id: string;
  evidence_type: string;
  source_entity_id?: string | null;
  source_entity_table?: string | null;
  confidence_score: number;
  payload: Record<string, any>;
  recorded_at: string;
  is_valid: boolean;
}

export interface KnowledgeRelationship {
  id: string;
  user_id: string;
  source_node_id: string;
  target_node_id: string;
  source_entity_id?: string | null;
  target_entity_id?: string | null;
  relationship_type: GraphRelationshipType;
  evidence_source: string;
  confidence: number;
  is_inferred: boolean;
  weight: number;
  valid_from: string;
  valid_until?: string | null;
  provenance_payload: Record<string, any>;
  evidences?: KnowledgeEvidence[];
  created_at: string;
  updated_at: string;
}

export interface KnowledgeGraphVersion {
  id: string;
  user_id: string;
  version_number: number;
  change_type: string;
  affected_node_ids: string[];
  affected_relationship_ids: string[];
  change_summary: string;
  version_metadata: Record<string, any>;
  created_at: string;
}

export interface GraphOverview {
  total_nodes: number;
  total_relationships: number;
  node_type_counts: Record<string, number>;
  relationship_type_counts: Record<string, number>;
  current_version: number;
  inferred_relationship_count: number;
  explicit_relationship_count: number;
  recent_changes: KnowledgeGraphVersion[];
}

export interface DirectRelationships {
  node: KnowledgeNode;
  outgoing: KnowledgeRelationship[];
  incoming: KnowledgeRelationship[];
  total_connections: number;
}

export interface MultiHopPath {
  path: KnowledgeNode[];
  edges: KnowledgeRelationship[];
  path_confidence: number;
  has_inferred_steps: boolean;
  depth: number;
}

export interface MultiHopTraversal {
  root_node_id: string;
  max_depth_reached: number;
  paths: MultiHopPath[];
  visited_nodes_count: number;
}

export interface AutoPopulateResult {
  created_nodes_count: number;
  created_edges_count: number;
  attached_evidence_count: number;
  new_version: number;
  summary_messages: string[];
}

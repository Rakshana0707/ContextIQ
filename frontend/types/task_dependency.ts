/**
 * TypeScript definitions for Cross-Task Dependency Discovery and Intelligent Relationship Analysis (Phase 8.5).
 */

export type TaskDependencyType =
  | 'EXPLICIT_DEPENDENCY'
  | 'INFERRED_DEPENDENCY'
  | 'SHARED_PROJECT'
  | 'SHARED_GOAL'
  | 'TEMPORAL_ASSOCIATION'
  | 'RESOURCE_CONFLICT'
  | 'REPEATED_WORKFLOW'
  | 'POTENTIAL_BLOCKER';

export type DependencyValidationStatus =
  | 'PROPOSED'
  | 'CONFIRMED'
  | 'REJECTED'
  | 'CONVERTED_EXPLICIT'
  | 'ARCHIVED';

export type DependencyDetectionMethod =
  | 'RULE_BASED'
  | 'ASSOCIATION_MINING'
  | 'TEMPORAL_SEQUENCE'
  | 'GRAPH_STRUCTURAL'
  | 'EXPLICIT_INPUT';

export interface TaskDependency {
  id: string;
  user_id: string;
  source_task_id: string;
  target_task_id: string;
  source_task_title?: string | null;
  target_task_title?: string | null;
  source_task_status?: string | null;
  target_task_status?: string | null;
  source_task_priority?: string | null;
  target_task_priority?: string | null;
  dependency_type: TaskDependencyType;
  is_inferred: boolean;
  confidence: number;
  detection_method: DependencyDetectionMethod;
  validation_status: DependencyValidationStatus;
  supporting_observations: Record<string, any>;
  first_observed_at: string;
  last_observed_at: string;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface TaskDependencyCreate {
  source_task_id: string;
  target_task_id: string;
  dependency_type?: TaskDependencyType;
  confidence?: number;
  notes?: string;
}

export interface TaskDependencyConfirmation {
  action: 'CONFIRM' | 'REJECT' | 'CONVERT_EXPLICIT';
  corrected_type?: TaskDependencyType;
  notes?: string;
}

export interface DependencyDiscoveryRequest {
  lookback_days?: number;
  min_confidence?: number;
  include_temporal?: boolean;
  include_project_goals?: boolean;
  include_resource_conflicts?: boolean;
}

export interface DependencyDiscoveryResult {
  discovered_count: number;
  updated_count: number;
  dependencies: TaskDependency[];
  summary: {
    total_tasks_evaluated: number;
    discovered_new_count: number;
    updated_count: number;
    proposed_total: number;
    breakdown_by_type: Record<string, number>;
  };
}

export interface ImpactAnalysisRequest {
  task_id: string;
  hypothetical_delay_days?: number;
  is_blocked?: boolean;
}

export interface ImpactedTaskItem {
  task_id: string;
  title: string;
  status: string;
  priority: string;
  due_at?: string | null;
  dependency_type: string;
  confidence: number;
  hop_distance: number;
  critical_path: boolean;
  projected_delay_days: number;
}

export interface ImpactedMilestoneItem {
  milestone_id: string;
  title: string;
  due_date?: string | null;
  is_completed: boolean;
  at_risk: boolean;
  days_until_due?: number | null;
  project_id?: string | null;
  goal_id?: string | null;
}

export interface ImpactedProjectItem {
  project_id: string;
  title: string;
  health_status: string;
  projected_health_status: string;
  is_stalled: boolean;
}

export interface ImpactedGoalItem {
  goal_id: string;
  title: string;
  hierarchy_level: string;
  priority: string;
  risk_level: string;
}

export interface ImpactAnalysisResult {
  focal_task_id: string;
  focal_task_title: string;
  hypothetical_delay_days: number;
  is_blocked: boolean;
  total_downstream_tasks: number;
  critical_path_tasks_count: number;
  affected_milestones: ImpactedMilestoneItem[];
  affected_projects: ImpactedProjectItem[];
  affected_goals: ImpactedGoalItem[];
  downstream_tasks: ImpactedTaskItem[];
  critical_path_risk: boolean;
  impact_severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  analysis_summary: string;
}

export interface DependencyGraphNode {
  id: string;
  label: string;
  entity_type: 'TASK' | 'PROJECT' | 'GOAL' | 'MILESTONE';
  status?: string | null;
  priority?: string | null;
  is_critical: boolean;
  entity_id?: string | null;
}

export interface DependencyGraphEdge {
  id: string;
  source: string;
  target: string;
  dependency_type: string;
  confidence: number;
  is_inferred: boolean;
  validation_status: string;
}

export interface DependencyGraphResponse {
  nodes: DependencyGraphNode[];
  edges: DependencyGraphEdge[];
  total_explicit: number;
  total_inferred: number;
  potential_blockers_count: number;
}

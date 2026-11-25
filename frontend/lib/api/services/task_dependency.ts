/**
 * Frontend API client service for Cross-Task Dependency Discovery and Intelligent Relationship Analysis (Phase 8.5).
 */
import { apiClient } from "@/lib/api/client";
import type {
  DependencyDiscoveryRequest,
  DependencyDiscoveryResult,
  DependencyGraphResponse,
  ImpactAnalysisRequest,
  ImpactAnalysisResult,
  TaskDependency,
  TaskDependencyConfirmation,
  TaskDependencyCreate,
} from "@/types/task_dependency";

const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK_API === "true";

export const MOCK_DEPENDENCIES: TaskDependency[] = [
  {
    id: "dep-1",
    user_id: "user-1",
    source_task_id: "task-1",
    target_task_id: "task-2",
    source_task_title: "Finalize API Schemas & Data Contracts",
    target_task_title: "Implement Dependency Graph REST Endpoints",
    source_task_status: "COMPLETED",
    target_task_status: "IN_PROGRESS",
    source_task_priority: "HIGH",
    target_task_priority: "HIGH",
    dependency_type: "EXPLICIT_DEPENDENCY",
    is_inferred: false,
    confidence: 1.0,
    detection_method: "EXPLICIT_INPUT",
    validation_status: "CONVERTED_EXPLICIT",
    supporting_observations: {
      source: "user_declared",
      reason: "API schemas are an explicit prerequisite for endpoint implementation.",
    },
    first_observed_at: "2026-11-20T10:00:00Z",
    last_observed_at: "2026-11-25T14:00:00Z",
    notes: "Mandatory architectural dependency.",
    created_at: "2026-11-20T10:00:00Z",
    updated_at: "2026-11-25T14:00:00Z",
  },
  {
    id: "dep-2",
    user_id: "user-1",
    source_task_id: "task-3",
    target_task_id: "task-4",
    source_task_title: "Audit Micro-delay Telemetry Agent",
    target_task_title: "Deploy Behavioral Intelligence Model",
    source_task_status: "PENDING",
    target_task_status: "PENDING",
    source_task_priority: "HIGH",
    target_task_priority: "HIGH",
    dependency_type: "POTENTIAL_BLOCKER",
    is_inferred: true,
    confidence: 0.88,
    detection_method: "RULE_BASED",
    validation_status: "PROPOSED",
    supporting_observations: {
      is_upstream_overdue: true,
      is_critical_path: true,
      time_gap_hours: 18.0,
      reason: "Overdue telemetry audit directly threatens downstream behavioral deployment milestone.",
    },
    first_observed_at: "2026-11-24T09:00:00Z",
    last_observed_at: "2026-11-25T16:00:00Z",
    notes: "Detected via deadline sequence & overdue telemetry analysis.",
    created_at: "2026-11-24T09:00:00Z",
    updated_at: "2026-11-25T16:00:00Z",
  },
  {
    id: "dep-3",
    user_id: "user-1",
    source_task_id: "task-5",
    target_task_id: "task-6",
    source_task_title: "Conduct Weekly Code Review",
    target_task_title: "Run Integration Regression Test Suite",
    source_task_status: "COMPLETED",
    target_task_status: "COMPLETED",
    source_task_priority: "MEDIUM",
    target_task_priority: "MEDIUM",
    dependency_type: "REPEATED_WORKFLOW",
    is_inferred: true,
    confidence: 0.92,
    detection_method: "TEMPORAL_SEQUENCE",
    validation_status: "CONFIRMED",
    supporting_observations: {
      transition_probability: 0.85,
      co_occurrence_count: 5,
      distinct_days_count: 4,
      support: 0.35,
      confidence: 0.85,
      lift: 2.1,
      reason: "Integration test execution follows code review in 85% of sessions across multiple calendar days.",
    },
    first_observed_at: "2026-11-10T11:00:00Z",
    last_observed_at: "2026-11-25T17:00:00Z",
    created_at: "2026-11-10T11:00:00Z",
    updated_at: "2026-11-25T17:00:00Z",
  },
  {
    id: "dep-4",
    user_id: "user-1",
    source_task_id: "task-7",
    target_task_id: "task-8",
    source_task_title: "Client Security Review Presentation",
    target_task_title: "Refactor Database Indexing",
    source_task_status: "PENDING",
    target_task_status: "PENDING",
    source_task_priority: "HIGH",
    target_task_priority: "HIGH",
    dependency_type: "RESOURCE_CONFLICT",
    is_inferred: true,
    confidence: 0.75,
    detection_method: "RULE_BASED",
    validation_status: "PROPOSED",
    supporting_observations: {
      time_delta_hours: 0.5,
      reason: "Both high-focus tasks are scheduled within 30 minutes of each other on the same afternoon.",
    },
    first_observed_at: "2026-11-25T08:00:00Z",
    last_observed_at: "2026-11-25T15:00:00Z",
    created_at: "2026-11-25T08:00:00Z",
    updated_at: "2026-11-25T15:00:00Z",
  },
];

export const MOCK_GRAPH: DependencyGraphResponse = {
  nodes: [
    { id: "task_1", label: "Finalize API Schemas", entity_type: "TASK", status: "COMPLETED", priority: "HIGH", is_critical: true },
    { id: "task_2", label: "Implement REST Endpoints", entity_type: "TASK", status: "IN_PROGRESS", priority: "HIGH", is_critical: true },
    { id: "task_3", label: "Audit Micro-delay Telemetry", entity_type: "TASK", status: "PENDING", priority: "HIGH", is_critical: true },
    { id: "task_4", label: "Deploy Behavioral Model", entity_type: "TASK", status: "PENDING", priority: "HIGH", is_critical: true },
    { id: "task_5", label: "Weekly Code Review", entity_type: "TASK", status: "COMPLETED", priority: "MEDIUM", is_critical: false },
    { id: "task_6", label: "Run Integration Tests", entity_type: "TASK", status: "COMPLETED", priority: "MEDIUM", is_critical: false },
    { id: "proj_1", label: "ContextIQ Production Engine", entity_type: "PROJECT", status: "ON_TRACK", is_critical: false },
    { id: "goal_1", label: "v1.0 General Availability", entity_type: "GOAL", status: "ACTIVE", priority: "HIGH", is_critical: true },
  ],
  edges: [
    { id: "e-1", source: "task_1", target: "task_2", dependency_type: "EXPLICIT_DEPENDENCY", confidence: 1.0, is_inferred: false, validation_status: "CONVERTED_EXPLICIT" },
    { id: "e-2", source: "task_3", target: "task_4", dependency_type: "POTENTIAL_BLOCKER", confidence: 0.88, is_inferred: true, validation_status: "PROPOSED" },
    { id: "e-3", source: "task_5", target: "task_6", dependency_type: "REPEATED_WORKFLOW", confidence: 0.92, is_inferred: true, validation_status: "CONFIRMED" },
  ],
  total_explicit: 1,
  total_inferred: 3,
  potential_blockers_count: 1,
};

export const taskDependencyApi = {
  async listDependencies(filters?: {
    source_task_id?: string;
    target_task_id?: string;
    dependency_type?: string;
    validation_status?: string;
    is_inferred?: boolean;
  }): Promise<TaskDependency[]> {
    if (USE_MOCK) return MOCK_DEPENDENCIES;
    try {
      const params = new URLSearchParams();
      if (filters?.source_task_id) params.set("source_task_id", filters.source_task_id);
      if (filters?.target_task_id) params.set("target_task_id", filters.target_task_id);
      if (filters?.dependency_type) params.set("dependency_type", filters.dependency_type);
      if (filters?.validation_status) params.set("validation_status", filters.validation_status);
      if (filters?.is_inferred !== undefined) params.set("is_inferred", String(filters.is_inferred));
      const res = await apiClient.get<TaskDependency[]>(`/dependencies?${params.toString()}`);
      return res.data;
    } catch {
      return MOCK_DEPENDENCIES;
    }
  },

  async createExplicitDependency(payload: TaskDependencyCreate): Promise<TaskDependency> {
    if (USE_MOCK) {
      const newDep: TaskDependency = {
        id: `dep-${Date.now()}`,
        user_id: "user-1",
        source_task_id: payload.source_task_id,
        target_task_id: payload.target_task_id,
        dependency_type: payload.dependency_type || "EXPLICIT_DEPENDENCY",
        is_inferred: false,
        confidence: payload.confidence || 1.0,
        detection_method: "EXPLICIT_INPUT",
        validation_status: "CONVERTED_EXPLICIT",
        supporting_observations: { source: "user_declared" },
        first_observed_at: new Date().toISOString(),
        last_observed_at: new Date().toISOString(),
        notes: payload.notes,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      MOCK_DEPENDENCIES.unshift(newDep);
      return newDep;
    }
    const res = await apiClient.post<TaskDependency>("/dependencies", payload);
    return res.data;
  },

  async discoverDependencies(payload: DependencyDiscoveryRequest = {}): Promise<DependencyDiscoveryResult> {
    if (USE_MOCK) {
      return {
        discovered_count: 2,
        updated_count: 1,
        dependencies: MOCK_DEPENDENCIES,
        summary: {
          total_tasks_evaluated: 12,
          discovered_new_count: 2,
          updated_count: 1,
          proposed_total: 2,
          breakdown_by_type: {
            POTENTIAL_BLOCKER: 1,
            REPEATED_WORKFLOW: 1,
            RESOURCE_CONFLICT: 1,
            EXPLICIT_DEPENDENCY: 1,
          },
        },
      };
    }
    try {
      const res = await apiClient.post<DependencyDiscoveryResult>("/dependencies/discover", payload);
      return res.data;
    } catch {
      return {
        discovered_count: 0,
        updated_count: 0,
        dependencies: MOCK_DEPENDENCIES,
        summary: {
          total_tasks_evaluated: 8,
          discovered_new_count: 0,
          updated_count: 0,
          proposed_total: 2,
          breakdown_by_type: {},
        },
      };
    }
  },

  async confirmOrReviewDependency(
    dependencyId: string,
    payload: TaskDependencyConfirmation
  ): Promise<TaskDependency> {
    if (USE_MOCK) {
      const dep = MOCK_DEPENDENCIES.find((d) => d.id === dependencyId);
      if (dep) {
        if (payload.action === "CONFIRM") dep.validation_status = "CONFIRMED";
        else if (payload.action === "REJECT") dep.validation_status = "REJECTED";
        else if (payload.action === "CONVERT_EXPLICIT") {
          dep.validation_status = "CONVERTED_EXPLICIT";
          dep.is_inferred = false;
        }
        if (payload.corrected_type) dep.dependency_type = payload.corrected_type;
        return dep;
      }
    }
    const res = await apiClient.post<TaskDependency>(`/dependencies/${dependencyId}/confirm`, payload);
    return res.data;
  },

  async runImpactAnalysis(payload: ImpactAnalysisRequest): Promise<ImpactAnalysisResult> {
    if (USE_MOCK) {
      return {
        focal_task_id: payload.task_id,
        focal_task_title: "Audit Micro-delay Telemetry Agent",
        hypothetical_delay_days: payload.hypothetical_delay_days || 3.0,
        is_blocked: payload.is_blocked ?? true,
        total_downstream_tasks: 2,
        critical_path_tasks_count: 1,
        affected_milestones: [
          {
            milestone_id: "m-1",
            title: "Behavioral Model GA Deployment",
            due_date: "2026-11-28T00:00:00Z",
            is_completed: false,
            at_risk: true,
            days_until_due: 2.5,
          },
        ],
        affected_projects: [
          {
            project_id: "p-1",
            title: "ContextIQ Production Release",
            health_status: "ON_TRACK",
            projected_health_status: "AT_RISK",
            is_stalled: false,
          },
        ],
        affected_goals: [
          {
            goal_id: "g-1",
            title: "v1.0 GA Engine Launch",
            hierarchy_level: "LONG_TERM",
            priority: "HIGH",
            risk_level: "HIGH",
          },
        ],
        downstream_tasks: [
          {
            task_id: "task-4",
            title: "Deploy Behavioral Intelligence Model",
            status: "PENDING",
            priority: "HIGH",
            due_at: "2026-11-28T00:00:00Z",
            dependency_type: "POTENTIAL_BLOCKER",
            confidence: 0.88,
            hop_distance: 1,
            critical_path: true,
            projected_delay_days: 2.6,
          },
        ],
        critical_path_risk: true,
        impact_severity: "HIGH",
        analysis_summary:
          "Hypothetical delay of 3.0 days cascades to 2 downstream deliverables and puts Milestone 'Behavioral Model GA Deployment' at risk.",
      };
    }
    const res = await apiClient.post<ImpactAnalysisResult>("/dependencies/impact-analysis", payload);
    return res.data;
  },

  async getDependencyGraph(): Promise<DependencyGraphResponse> {
    if (USE_MOCK) return MOCK_GRAPH;
    try {
      const res = await apiClient.get<DependencyGraphResponse>("/dependencies/graph");
      return res.data;
    } catch {
      return MOCK_GRAPH;
    }
  },

  async deleteDependency(dependencyId: string): Promise<void> {
    if (USE_MOCK) {
      const idx = MOCK_DEPENDENCIES.findIndex((d) => d.id === dependencyId);
      if (idx !== -1) MOCK_DEPENDENCIES.splice(idx, 1);
      return;
    }
    await apiClient.delete(`/dependencies/${dependencyId}`);
  },
};

/**
 * Frontend API client service for Goal and Project Intelligence (Phase 8.4).
 */
import { apiClient } from "@/lib/api/client";
import type {
  Goal,
  GoalIntelligenceDashboard,
  GoalRecommendation,
  GoalTaskAssociation,
  Milestone,
  Project,
} from "@/types/goal_project";

const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK_API === "true";

export const MOCK_GOALS: Goal[] = [
  {
    id: "goal-1",
    user_id: "user-1",
    title: "ContextIQ Production Release (v1.0)",
    description: "Launch ContextIQ enterprise intelligence engine with micro-delay analytics and personal digital twin.",
    category: "ENGINEERING",
    hierarchy_level: "LONG_TERM",
    priority: "HIGH",
    status: "ACTIVE",
    target_date: "2026-12-15T00:00:00Z",
    progress_pct: 68.5,
    evidence_based_progress: 68.5,
    health_status: "ON_TRACK",
    completion_criteria: "Complete Phases 1-8, achieve >90% test coverage, and deploy telemetry agent.",
    risk_factors: [],
    milestones: [
      {
        id: "m-1",
        user_id: "user-1",
        goal_id: "goal-1",
        title: "Complete Behavioral Memory (Phase 8.3)",
        status: "COMPLETED",
        is_completed: true,
        completed_at: "2026-11-25T12:00:00Z",
        order_index: 1,
        created_at: "2026-10-01T00:00:00Z",
        updated_at: "2026-11-25T12:00:00Z",
      },
      {
        id: "m-2",
        user_id: "user-1",
        goal_id: "goal-1",
        title: "Goal & Project Intelligence (Phase 8.4)",
        due_date: "2026-11-28T00:00:00Z",
        status: "IN_PROGRESS",
        is_completed: false,
        order_index: 2,
        created_at: "2026-10-01T00:00:00Z",
        updated_at: "2026-11-25T00:00:00Z",
      },
    ],
    associated_projects_count: 2,
    associated_tasks_count: 14,
    completed_tasks_count: 10,
    overdue_tasks_count: 0,
    created_at: "2026-10-01T00:00:00Z",
    updated_at: "2026-11-25T00:00:00Z",
  },
  {
    id: "goal-2",
    user_id: "user-1",
    title: "Reduce Average Interruption Recovery Lag < 60s",
    description: "Behavioral goal to optimize cognitive re-entry and minimize disruption propagation.",
    category: "BEHAVIORAL",
    hierarchy_level: "INTERMEDIATE",
    priority: "MEDIUM",
    status: "ACTIVE",
    target_date: "2026-12-31T00:00:00Z",
    progress_pct: 42.0,
    evidence_based_progress: 42.0,
    health_status: "AT_RISK",
    completion_criteria: "Empirical recovery lag distribution median below 60 seconds across 30 days.",
    risk_factors: ["REPEATED_POSTPONEMENTS"],
    milestones: [],
    associated_projects_count: 1,
    associated_tasks_count: 6,
    completed_tasks_count: 2,
    overdue_tasks_count: 2,
    created_at: "2026-10-15T00:00:00Z",
    updated_at: "2026-11-25T00:00:00Z",
  },
];

export const MOCK_PROJECTS: Project[] = [
  {
    id: "proj-1",
    user_id: "user-1",
    title: "ContextIQ Backend & Intelligence Engine",
    description: "FastAPI, PostgreSQL graph tables, behavioral profiling, and causal survival analysis.",
    status: "ACTIVE",
    priority: "HIGH",
    health_status: "ON_TRACK",
    target_completion_date: "2026-12-10T00:00:00Z",
    completion_criteria: "All REST APIs verified with 100% passing tests.",
    evidence_based_progress: 78.0,
    milestones: [],
    contributing_to_goals: ["ContextIQ Production Release (v1.0)"],
    total_tasks_count: 18,
    completed_tasks_count: 14,
    overdue_tasks_count: 0,
    blocked_tasks_count: 0,
    total_productive_minutes: 1480,
    risk_factors: [],
    created_at: "2026-10-01T00:00:00Z",
    updated_at: "2026-11-25T00:00:00Z",
  },
  {
    id: "proj-2",
    user_id: "user-1",
    title: "Next.js Executive Analytics Dashboard",
    description: "Responsive Next.js UI, SVG Knowledge Graph explorer, and Behavioral Memory interfaces.",
    status: "ACTIVE",
    priority: "MEDIUM",
    health_status: "ON_TRACK",
    target_completion_date: "2026-12-12T00:00:00Z",
    completion_criteria: "Tailwind UI with zero TypeScript errors.",
    evidence_based_progress: 65.0,
    milestones: [],
    contributing_to_goals: ["ContextIQ Production Release (v1.0)"],
    total_tasks_count: 12,
    completed_tasks_count: 8,
    overdue_tasks_count: 1,
    blocked_tasks_count: 0,
    total_productive_minutes: 920,
    risk_factors: [],
    created_at: "2026-10-10T00:00:00Z",
    updated_at: "2026-11-25T00:00:00Z",
  },
];

export const goalProjectApi = {
  async getDashboard(): Promise<GoalIntelligenceDashboard> {
    if (USE_MOCK) {
      return {
        total_goals: MOCK_GOALS.length,
        active_projects: MOCK_PROJECTS.length,
        completed_goals: 0,
        overall_health: "HEALTHY",
        goals_at_risk_count: 1,
        projects_stalled_count: 0,
        total_completed_milestones: 1,
        behavioral_alignment: {
          top_time_invested_projects: [
            {
              project_id: "proj-1",
              project_title: "ContextIQ Backend & Intelligence Engine",
              total_productive_minutes: 1480,
              percentage_of_focus_time: 61.7,
            },
            {
              project_id: "proj-2",
              project_title: "Next.js Executive Analytics Dashboard",
              total_productive_minutes: 920,
              percentage_of_focus_time: 38.3,
            },
          ],
          postponement_friction_goals: [
            {
              goal_id: "goal-2",
              goal_title: "Reduce Average Interruption Recovery Lag < 60s",
              overdue_tasks_count: 2,
              friction_indicator: "MODERATE",
            },
          ],
          high_interruption_projects: [
            {
              project_id: "proj-2",
              project_title: "Next.js Executive Analytics Dashboard",
              interruptions_count: 14,
            },
          ],
          recommended_focus_windows_for_goals: [
            {
              window_id: "win-1",
              day_and_time: "Monday 09:00 - 11:30",
              quality_score: 91.5,
              recommended_for: "Critical Path Strategic Projects",
            },
          ],
          descriptive_correlations: [
            "Project 'ContextIQ Backend' accounts for 62% of logged deep focus sessions this month.",
            "Descriptive observation: Tasks executed during morning focus windows show 2.1x lower postponement probability.",
          ],
        },
        goals: MOCK_GOALS,
        projects: MOCK_PROJECTS,
        pending_recommendations: [
          {
            id: "rec-1",
            user_id: "user-1",
            goal_id: "goal-1",
            project_id: "proj-1",
            recommendation_type: "NEXT_BEST_TASK",
            title: "Prioritize Critical Path Task: Database Migration",
            rationale: "Task 'Database Migration' is on the critical path for Phase 8 release delivery and is completely unblocked.",
            suggested_action: { action: "START_TASK", suggested_priority: "HIGH" },
            priority_score: 0.95,
            requires_approval: true,
            created_at: new Date().toISOString(),
          },
        ],
      };
    }
    const res = await apiClient.request<GoalIntelligenceDashboard>("/goals/dashboard", {
      method: "GET",
    });
    if (res.error || !res.data) throw new Error(res.error?.message ?? "Failed to fetch goal dashboard");
    return res.data;
  },

  async listGoals(): Promise<Goal[]> {
    if (USE_MOCK) return MOCK_GOALS;
    const res = await apiClient.request<Goal[]>("/goals", { method: "GET" });
    return res.data ?? [];
  },

  async createGoal(payload: Partial<Goal>): Promise<Goal> {
    if (USE_MOCK) {
      const newG: Goal = {
        id: `goal-${Date.now()}`,
        user_id: "user-1",
        title: payload.title || "New Strategic Goal",
        description: payload.description,
        category: payload.category || "PRODUCTIVITY",
        hierarchy_level: payload.hierarchy_level || "LONG_TERM",
        priority: payload.priority || "MEDIUM",
        status: "ACTIVE",
        progress_pct: 0.0,
        evidence_based_progress: 0.0,
        health_status: "ON_TRACK",
        risk_factors: [],
        milestones: [],
        associated_projects_count: 0,
        associated_tasks_count: 0,
        completed_tasks_count: 0,
        overdue_tasks_count: 0,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      MOCK_GOALS.unshift(newG);
      return newG;
    }
    const res = await apiClient.request<Goal>("/goals", {
      method: "POST",
      body: payload,
    });
    if (res.error || !res.data) throw new Error(res.error?.message ?? "Failed to create goal");
    return res.data;
  },

  async updateGoal(goalId: string, payload: Partial<Goal>): Promise<Goal> {
    if (USE_MOCK) {
      const g = MOCK_GOALS.find((x) => x.id === goalId);
      if (!g) throw new Error("Goal not found");
      Object.assign(g, payload);
      return g;
    }
    const res = await apiClient.request<Goal>(`/goals/${goalId}`, {
      method: "PATCH",
      body: payload,
    });
    if (res.error || !res.data) throw new Error(res.error?.message ?? "Failed to update goal");
    return res.data;
  },

  async deleteGoal(goalId: string): Promise<void> {
    if (USE_MOCK) {
      const idx = MOCK_GOALS.findIndex((x) => x.id === goalId);
      if (idx !== -1) MOCK_GOALS.splice(idx, 1);
      return;
    }
    const res = await apiClient.request<void>(`/goals/${goalId}`, { method: "DELETE" });
    if (res.error) throw new Error(res.error.message);
  },

  async listProjects(): Promise<Project[]> {
    if (USE_MOCK) return MOCK_PROJECTS;
    const res = await apiClient.request<Project[]>("/goals/projects/all", { method: "GET" });
    return res.data ?? [];
  },

  async createProject(payload: Partial<Project>): Promise<Project> {
    if (USE_MOCK) {
      const newP: Project = {
        id: `proj-${Date.now()}`,
        user_id: "user-1",
        title: payload.title || "New Project",
        description: payload.description,
        status: "ACTIVE",
        priority: payload.priority || "MEDIUM",
        health_status: "ON_TRACK",
        evidence_based_progress: 0.0,
        milestones: [],
        contributing_to_goals: [],
        total_tasks_count: 0,
        completed_tasks_count: 0,
        overdue_tasks_count: 0,
        blocked_tasks_count: 0,
        total_productive_minutes: 0,
        risk_factors: [],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      MOCK_PROJECTS.unshift(newP);
      return newP;
    }
    const res = await apiClient.request<Project>("/goals/projects", {
      method: "POST",
      body: payload,
    });
    if (res.error || !res.data) throw new Error(res.error?.message ?? "Failed to create project");
    return res.data;
  },

  async createMilestone(payload: {
    title: string;
    description?: string;
    due_date?: string;
    goal_id?: string;
    project_id?: string;
  }): Promise<Milestone> {
    if (USE_MOCK) {
      const newM: Milestone = {
        id: `m-${Date.now()}`,
        user_id: "user-1",
        title: payload.title,
        description: payload.description,
        due_date: payload.due_date,
        status: "PENDING",
        is_completed: false,
        order_index: 0,
        goal_id: payload.goal_id,
        project_id: payload.project_id,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      return newM;
    }
    const res = await apiClient.request<Milestone>("/goals/milestones", {
      method: "POST",
      body: payload,
    });
    if (res.error || !res.data) throw new Error(res.error?.message ?? "Failed to create milestone");
    return res.data;
  },

  async updateMilestone(milestoneId: string, payload: Partial<Milestone>): Promise<Milestone> {
    const res = await apiClient.request<Milestone>(`/goals/milestones/${milestoneId}`, {
      method: "PATCH",
      body: payload,
    });
    if (res.error || !res.data) throw new Error(res.error?.message ?? "Failed to update milestone");
    return res.data;
  },

  async associateTask(payload: {
    task_id: string;
    goal_id?: string;
    project_id?: string;
    importance_weight?: number;
    effort_weight?: number;
    is_critical_path?: boolean;
  }): Promise<GoalTaskAssociation> {
    const res = await apiClient.request<GoalTaskAssociation>("/goals/associations/task", {
      method: "POST",
      body: payload,
    });
    if (res.error || !res.data) throw new Error(res.error?.message ?? "Failed to link task");
    return res.data;
  },

  async listTaskAssociations(params?: { goal_id?: string; project_id?: string }): Promise<GoalTaskAssociation[]> {
    const res = await apiClient.request<GoalTaskAssociation[]>("/goals/associations/task", {
      method: "GET",
      query: params,
    });
    return res.data ?? [];
  },

  async removeTaskAssociation(associationId: string): Promise<void> {
    const res = await apiClient.request<void>(`/goals/associations/task/${associationId}`, {
      method: "DELETE",
    });
    if (res.error) throw new Error(res.error.message);
  },

  async approveRecommendation(
    recommendationId: string,
    payload: { approve: boolean; apply_immediately?: boolean; user_notes?: string }
  ): Promise<GoalRecommendation> {
    const res = await apiClient.request<GoalRecommendation>(`/goals/recommendations/${recommendationId}/approve`, {
      method: "POST",
      body: payload,
    });
    if (res.error || !res.data) throw new Error(res.error?.message ?? "Failed to approve recommendation");
    return res.data;
  },
};

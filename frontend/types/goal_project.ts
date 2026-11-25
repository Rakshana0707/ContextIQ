/**
 * TypeScript types for ContextIQ Goal and Project Intelligence (Phase 8.4).
 */

export type GoalHierarchyLevel = "LONG_TERM" | "INTERMEDIATE" | "SHORT_TERM";

export type ProjectHealthStatus =
  | "ON_TRACK"
  | "AT_RISK"
  | "OFF_TRACK"
  | "STALLED"
  | "BLOCKED"
  | "COMPLETED";

export type GoalRiskFactor =
  | "DEADLINE_PROXIMITY"
  | "STALLED_PROGRESS"
  | "UNRESOLVED_BLOCKERS"
  | "REPEATED_POSTPONEMENTS"
  | "INSUFFICIENT_TIME"
  | "DEPENDENCY_CONFLICT";

export interface Milestone {
  id: string;
  user_id: string;
  project_id?: string | null;
  goal_id?: string | null;
  title: string;
  description?: string | null;
  due_date?: string | null;
  status: string;
  is_completed: boolean;
  completed_at?: string | null;
  order_index: number;
  created_at: string;
  updated_at: string;
}

export interface GoalTaskAssociation {
  id: string;
  user_id: string;
  goal_id?: string | null;
  project_id?: string | null;
  milestone_id?: string | null;
  task_id: string;
  association_type: string;
  importance_weight: number;
  effort_weight: number;
  is_critical_path: boolean;
  task_title?: string | null;
  task_status?: string | null;
  task_priority?: string | null;
  task_due_at?: string | null;
  created_at: string;
}

export interface Goal {
  id: string;
  user_id: string;
  parent_goal_id?: string | null;
  title: string;
  description?: string | null;
  category: string;
  hierarchy_level: GoalHierarchyLevel;
  priority: string;
  status: string;
  target_date?: string | null;
  progress_pct: number;
  evidence_based_progress: number;
  health_status: string;
  completion_criteria?: string | null;
  risk_factors: string[];
  milestones: Milestone[];
  associated_projects_count: number;
  associated_tasks_count: number;
  completed_tasks_count: number;
  overdue_tasks_count: number;
  created_at: string;
  updated_at: string;
}

export interface Project {
  id: string;
  user_id: string;
  title: string;
  description?: string | null;
  status: string;
  priority: string;
  health_status: ProjectHealthStatus;
  target_completion_date?: string | null;
  completion_criteria?: string | null;
  evidence_based_progress: number;
  milestones: Milestone[];
  contributing_to_goals: string[];
  total_tasks_count: number;
  completed_tasks_count: number;
  overdue_tasks_count: number;
  blocked_tasks_count: number;
  total_productive_minutes: number;
  risk_factors: string[];
  created_at: string;
  updated_at: string;
}

export interface GoalRecommendation {
  id: string;
  user_id: string;
  goal_id?: string | null;
  project_id?: string | null;
  recommendation_type: string;
  title: string;
  rationale: string;
  suggested_action: Record<string, any>;
  priority_score: number;
  requires_approval: boolean;
  is_approved?: boolean | null;
  applied_at?: string | null;
  created_at: string;
}

export interface BehavioralGoalAlignment {
  top_time_invested_projects: Array<{
    project_id: string;
    project_title: string;
    total_productive_minutes: number;
    percentage_of_focus_time: number;
  }>;
  postponement_friction_goals: Array<{
    goal_id: string;
    goal_title: string;
    overdue_tasks_count: number;
    friction_indicator: string;
  }>;
  high_interruption_projects: Array<{
    project_id: string;
    project_title: string;
    interruptions_count: number;
  }>;
  recommended_focus_windows_for_goals: Array<{
    window_id: string;
    day_and_time: string;
    quality_score: number;
    recommended_for: string;
  }>;
  descriptive_correlations: string[];
}

export interface GoalIntelligenceDashboard {
  total_goals: number;
  active_projects: number;
  completed_goals: number;
  overall_health: string;
  goals_at_risk_count: number;
  projects_stalled_count: number;
  total_completed_milestones: number;
  behavioral_alignment: BehavioralGoalAlignment;
  goals: Goal[];
  projects: Project[];
  pending_recommendations: GoalRecommendation[];
}

/**
 * Multi-Objective Intervention Optimization API Client & Mock Service (ContextIQ Phase 6.7).
 */
import type {
  CandidateIntervention,
  MultiObjectiveOptimizationResponseData,
  UserOptimizationPreferencesData,
} from "@/types/optimization";

export const mockOptimizationResponse: MultiObjectiveOptimizationResponseData = {
  optimization_id: "opt_mock_9921",
  user_id: "usr_mock_001",
  evaluated_at: new Date().toISOString(),
  selected_intervention: "short_recovery_buffer",
  is_no_action: false,
  selection_rationale:
    "Selected 'Micro Recovery Buffer (10m)' (Non-dominated Pareto-optimal) with weighted utility 0.792 (+0.185 lift over No-Action). Optimizes Cognitive Recovery Enhancement (+48.0%) and Cognitive Friction Reduction (+34.0%) while safely respecting quiet hours and notification quotas.",
  effective_weights: {
    task_completion: 0.16,
    task_resumption: 0.14,
    recovery_duration: 0.22,
    behavioral_friction: 0.22,
    notification_economy: 0.12,
    interruption_comfort: 0.08,
    user_preferences: 0.03,
    schedule_feasibility: 0.03,
  },
  context_adaptations: [
    "Elevated Cognitive Fatigue (BFI 68 > 65): Prioritized Recovery (+10%) & Friction Reduction (+10%), reduced Task Completion pressure.",
  ],
  pareto_frontier: [
    {
      candidate: "no_intervention",
      title: "No Intervention (Passive Holdout)",
      is_feasible: true,
      constraint_violations: [],
      objectives: {
        task_completion: 0.52,
        task_resumption: 0.45,
        recovery_duration: 0.40,
        behavioral_friction: 0.48,
        notification_economy: 1.00,
        interruption_comfort: 1.00,
        user_preferences: 0.70,
        schedule_feasibility: 1.00,
      },
      weighted_utility: 0.607,
      net_utility_lift: 0.0,
      is_pareto_optimal: true,
      pareto_rank: 1,
      dominates: [],
      dominated_by: [],
      improved_objectives: [],
      worsened_objectives: [],
      confidence_score: 0.92,
      uncertainty_width: 0.16,
    },
    {
      candidate: "short_recovery_buffer",
      title: "Micro Recovery Buffer (10m)",
      is_feasible: true,
      constraint_violations: [],
      objectives: {
        task_completion: 0.64,
        task_resumption: 0.76,
        recovery_duration: 0.88,
        behavioral_friction: 0.82,
        notification_economy: 0.80,
        interruption_comfort: 0.85,
        user_preferences: 0.80,
        schedule_feasibility: 0.85,
      },
      weighted_utility: 0.792,
      net_utility_lift: 0.185,
      is_pareto_optimal: true,
      pareto_rank: 1,
      dominates: ["delayed_reminder"],
      dominated_by: [],
      improved_objectives: [
        "Cognitive Recovery Enhancement (+48.0%)",
        "Cognitive Friction Reduction (+34.0%)",
        "Task Resumption Speed (+31.0%)",
      ],
      worsened_objectives: [
        "Notification Economy (-20.0%)",
        "Interruption Comfort (-15.0%)",
      ],
      confidence_score: 0.90,
      uncertainty_width: 0.20,
    },
    {
      candidate: "focus_session_recommendation",
      title: "Protected Focus Block (45m)",
      is_feasible: true,
      constraint_violations: [],
      objectives: {
        task_completion: 0.86,
        task_resumption: 0.70,
        recovery_duration: 0.75,
        behavioral_friction: 0.78,
        notification_economy: 0.75,
        interruption_comfort: 0.75,
        user_preferences: 0.75,
        schedule_feasibility: 0.65,
      },
      weighted_utility: 0.768,
      net_utility_lift: 0.161,
      is_pareto_optimal: true,
      pareto_rank: 1,
      dominates: [],
      dominated_by: [],
      improved_objectives: [
        "Task Completion Likelihood (+34.0%)",
        "Cognitive Recovery Enhancement (+35.0%)",
      ],
      worsened_objectives: [
        "Notification Economy (-25.0%)",
        "Schedule Feasibility (-35.0%)",
      ],
      confidence_score: 0.85,
      uncertainty_width: 0.30,
    },
  ],
  all_evaluated_candidates: [
    {
      candidate: "short_recovery_buffer",
      title: "Micro Recovery Buffer (10m)",
      is_feasible: true,
      constraint_violations: [],
      objectives: {
        task_completion: 0.64,
        task_resumption: 0.76,
        recovery_duration: 0.88,
        behavioral_friction: 0.82,
        notification_economy: 0.80,
        interruption_comfort: 0.85,
        user_preferences: 0.80,
        schedule_feasibility: 0.85,
      },
      weighted_utility: 0.792,
      net_utility_lift: 0.185,
      is_pareto_optimal: true,
      pareto_rank: 1,
      dominates: ["delayed_reminder"],
      dominated_by: [],
      improved_objectives: [
        "Cognitive Recovery Enhancement (+48.0%)",
        "Cognitive Friction Reduction (+34.0%)",
      ],
      worsened_objectives: ["Notification Economy (-20.0%)"],
      confidence_score: 0.90,
      uncertainty_width: 0.20,
    },
    {
      candidate: "no_intervention",
      title: "No Intervention (Passive Holdout)",
      is_feasible: true,
      constraint_violations: [],
      objectives: {
        task_completion: 0.52,
        task_resumption: 0.45,
        recovery_duration: 0.40,
        behavioral_friction: 0.48,
        notification_economy: 1.00,
        interruption_comfort: 1.00,
        user_preferences: 0.70,
        schedule_feasibility: 1.00,
      },
      weighted_utility: 0.607,
      net_utility_lift: 0.0,
      is_pareto_optimal: true,
      pareto_rank: 1,
      dominates: [],
      dominated_by: [],
      improved_objectives: [],
      worsened_objectives: [],
      confidence_score: 0.92,
      uncertainty_width: 0.16,
    },
    {
      candidate: "immediate_reminder",
      title: "Immediate Contextual Reminder",
      is_feasible: false,
      constraint_violations: [
        "Violates quiet hours: Audible or visual notifications prohibited.",
      ],
      objectives: {
        task_completion: 0.72,
        task_resumption: 0.82,
        recovery_duration: 0.50,
        behavioral_friction: 0.52,
        notification_economy: 0.35,
        interruption_comfort: 0.45,
        user_preferences: 0.65,
        schedule_feasibility: 0.95,
      },
      weighted_utility: 0.612,
      net_utility_lift: 0.005,
      is_pareto_optimal: false,
      pareto_rank: 2,
      dominates: [],
      dominated_by: [],
      improved_objectives: ["Task Resumption Speed (+37.0%)"],
      worsened_objectives: ["Notification Economy (-65.0%)", "Interruption Comfort (-55.0%)"],
      confidence_score: 0.88,
      uncertainty_width: 0.24,
    },
  ],
  applied_constraints: [
    {
      constraint_type: "quiet_hours",
      passed: true,
      reason: "Current time (14:30) is outside quiet hours window.",
    },
    {
      constraint_type: "max_notification_freq",
      passed: true,
      reason: "Notification frequency within quota (1/2 hourly, 3/8 daily).",
    },
    {
      constraint_type: "calendar_availability",
      passed: true,
      reason: "Calendar availability confirmed (3.0h booked, free slots available).",
    },
    {
      constraint_type: "working_hours",
      passed: true,
      reason: "Current time is within working hours (09:00-18:00).",
    },
    {
      constraint_type: "task_constraints",
      passed: true,
      reason: "No hard task deadline or immutability constraints violated.",
    },
    {
      constraint_type: "consent_permissions",
      passed: true,
      reason: "Notification and telemetry consent verified.",
    },
    {
      constraint_type: "user_opt_out",
      passed: true,
      reason: "No intervention opt-outs configured.",
    },
  ],
  improved_objectives: [
    "Cognitive Recovery Enhancement (+48.0%)",
    "Cognitive Friction Reduction (+34.0%)",
    "Task Resumption Speed (+31.0%)",
  ],
  worsened_objectives: [
    "Notification Economy (-20.0%)",
    "Interruption Comfort (-15.0%)",
  ],
  requires_authorization: true,
  disclaimer:
    "Optimization balances productivity against cognitive burden and quiet hours. No-Action is preferred when benefit is negligible or uncertainty exceeds tolerance.",
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export const optimizationApi = {
  async optimize(
    taskId?: string,
    contextFeatures?: Record<string, any>
  ): Promise<MultiObjectiveOptimizationResponseData> {
    try {
      const res = await fetch(`${API_BASE}/optimization/optimize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task_id: taskId,
          context_features: contextFeatures || {},
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch {
      return mockOptimizationResponse;
    }
  },

  async getPreferences(): Promise<UserOptimizationPreferencesData> {
    try {
      const res = await fetch(`${API_BASE}/optimization/preferences`, {
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch {
      return {
        user_id: "usr_mock_001",
        preferred_weights: mockOptimizationResponse.effective_weights,
        opted_out_interventions: [],
        max_daily_interventions: 8,
        max_hourly_interventions: 2,
        cooldown_minutes_between_interventions: 30,
        updated_at: new Date().toISOString(),
      };
    }
  },
};

/**
 * Counterfactual Comparison API Client & Mock Service (ContextIQ Phase 6.4).
 */
import type {
  CounterfactualComparisonResponseData,
  CounterfactualLearnerType,
} from "@/types/counterfactual";

export const mockCounterfactualResponse: CounterfactualComparisonResponseData = {
  context_id: "cf_ctx_mock789",
  user_id: "usr_mock_001",
  evaluation_timestamp: new Date().toISOString(),
  target_task_id: null,
  baseline_candidate: "no_intervention",
  recommendation_source: "counterfactual_optimized",
  recommended_champion: "short_recovery_buffer",
  fallback_reason: null,
  candidates: [
    {
      candidate: "no_intervention",
      title: "No Intervention (Control Baseline)",
      description: "Standard unassisted operation; no proactive nudges or schedule alterations.",
      category: "BASELINE",
      is_supported: true,
      coverage_tier: "strong",
      exclusion_reason: null,
      potential_outcomes: {
        task_resumption_probability: 0.52,
        task_completion_probability: 0.58,
        expected_recovery_duration_seconds: 245.0,
        expected_behavioral_friction: 54.0,
        expected_notification_burden: 0.0,
      },
      incremental_benefit: {
        resumption_lift_pct: 0.0,
        completion_lift_pct: 0.0,
        recovery_time_saved_seconds: 0.0,
        friction_reduction_points: 0.0,
        burden_penalty: 0.0,
      },
      composite_uplift_score: 0.0,
      uncertainty_intervals: {
        task_resumption_probability: [0.44, 0.60],
        task_completion_probability: [0.49, 0.67],
      },
      empirical_sample_size: 110,
      empirical_execution_rate: 0.0,
      overlap_score: 1.0,
      learner_used: "doubly_robust_learner",
      assumptions: ["Passive holdout consistency"],
    },
    {
      candidate: "short_recovery_buffer",
      title: "Cognitive Recovery Buffer (3-5 min)",
      description: "Insert brief post-interruption buffer with context re-anchoring card.",
      category: "RECOVERY",
      is_supported: true,
      coverage_tier: "strong",
      exclusion_reason: null,
      potential_outcomes: {
        task_resumption_probability: 0.74,
        task_completion_probability: 0.65,
        expected_recovery_duration_seconds: 165.0,
        expected_behavioral_friction: 42.0,
        expected_notification_burden: 0.12,
      },
      incremental_benefit: {
        resumption_lift_pct: 22.0,
        completion_lift_pct: 7.0,
        recovery_time_saved_seconds: 80.0,
        friction_reduction_points: 12.0,
        burden_penalty: 0.12,
      },
      composite_uplift_score: 14.85,
      uncertainty_intervals: {
        task_resumption_probability: [0.63, 0.85],
        task_completion_probability: [0.55, 0.75],
      },
      empirical_sample_size: 68,
      empirical_execution_rate: 0.82,
      overlap_score: 0.85,
      learner_used: "doubly_robust_learner",
      assumptions: ["Conditional exchangeability", "Positivity"],
    },
    {
      candidate: "focus_session_recommendation",
      title: "Protected Deep Focus Session (45 min)",
      description: "Suppress desktop notifications and activate shielded focus window.",
      category: "FOCUS",
      is_supported: true,
      coverage_tier: "moderate",
      exclusion_reason: null,
      potential_outcomes: {
        task_resumption_probability: 0.68,
        task_completion_probability: 0.78,
        expected_recovery_duration_seconds: 185.0,
        expected_behavioral_friction: 39.0,
        expected_notification_burden: 0.10,
      },
      incremental_benefit: {
        resumption_lift_pct: 16.0,
        completion_lift_pct: 20.0,
        recovery_time_saved_seconds: 60.0,
        friction_reduction_points: 15.0,
        burden_penalty: 0.10,
      },
      composite_uplift_score: 13.55,
      uncertainty_intervals: {
        task_resumption_probability: [0.51, 0.85],
        task_completion_probability: [0.58, 0.98],
      },
      empirical_sample_size: 34,
      empirical_execution_rate: 0.76,
      overlap_score: 0.65,
      learner_used: "doubly_robust_learner",
      assumptions: ["Focus window availability"],
    },
    {
      candidate: "calendar_rescheduling",
      title: "Calendar-Aware Focus Rescheduling",
      description: "Automatically propose dedicated focus block aligned with circadian peak.",
      category: "FOCUS",
      is_supported: true,
      coverage_tier: "moderate",
      exclusion_reason: null,
      potential_outcomes: {
        task_resumption_probability: 0.60,
        task_completion_probability: 0.82,
        expected_recovery_duration_seconds: 205.0,
        expected_behavioral_friction: 46.0,
        expected_notification_burden: 0.08,
      },
      incremental_benefit: {
        resumption_lift_pct: 8.0,
        completion_lift_pct: 24.0,
        recovery_time_saved_seconds: 40.0,
        friction_reduction_points: 8.0,
        burden_penalty: 0.08,
      },
      composite_uplift_score: 11.20,
      uncertainty_intervals: {
        task_resumption_probability: [0.45, 0.75],
        task_completion_probability: [0.62, 0.99],
      },
      empirical_sample_size: 28,
      empirical_execution_rate: 0.71,
      overlap_score: 0.58,
      learner_used: "doubly_robust_learner",
      assumptions: ["Calendar provider sync consistency"],
    },
    {
      candidate: "delayed_reminder",
      title: "Cognitive Slack Boundary Reminder",
      description: "Postpone reminder until detected typing pause or application transition.",
      category: "TASK",
      is_supported: true,
      coverage_tier: "moderate",
      exclusion_reason: null,
      potential_outcomes: {
        task_resumption_probability: 0.55,
        task_completion_probability: 0.72,
        expected_recovery_duration_seconds: 235.0,
        expected_behavioral_friction: 52.0,
        expected_notification_burden: 0.15,
      },
      incremental_benefit: {
        resumption_lift_pct: 3.0,
        completion_lift_pct: 14.0,
        recovery_time_saved_seconds: 10.0,
        friction_reduction_points: 2.0,
        burden_penalty: 0.15,
      },
      composite_uplift_score: 4.85,
      uncertainty_intervals: {
        task_resumption_probability: [0.41, 0.69],
        task_completion_probability: [0.54, 0.90],
      },
      empirical_sample_size: 24,
      empirical_execution_rate: 0.79,
      overlap_score: 0.52,
      learner_used: "doubly_robust_learner",
      assumptions: ["Keystroke pause detection threshold"],
    },
    {
      candidate: "break_large_task",
      title: "Task Decomposition Nudge",
      description: "Prompt user to break large task into modular 15-minute sub-steps.",
      category: "TASK",
      is_supported: false,
      coverage_tier: "unsupported",
      exclusion_reason: "Insufficient historical evidence: N=8 < 10 (overlap score: 0.18). Excluded to prevent ungrounded decisioning.",
      potential_outcomes: null,
      incremental_benefit: null,
      composite_uplift_score: null,
      uncertainty_intervals: null,
      empirical_sample_size: 8,
      empirical_execution_rate: 0.62,
      overlap_score: 0.18,
      learner_used: "doubly_robust_learner",
      assumptions: ["Unverifiable overlap"],
    },
  ],
  disclaimer: "COUNTERFACTUAL POTENTIAL OUTCOMES ARE MODELED ESTIMATES, NOT OBSERVED HISTORICAL FACTS. Estimates represent conditional expectations E[Y(a)|X] valid strictly under exchangeability and positivity assumptions. Unsupported options are explicitly excluded from decisioning.",
};

export const counterfactualApi = {
  async compareInterventions(
    learner: CounterfactualLearnerType = "doubly_robust_learner"
  ): Promise<CounterfactualComparisonResponseData> {
    try {
      const res = await fetch(`/api/v1/counterfactual/compare?learner=${learner}`);
      if (!res.ok) throw new Error("API error");
      return await res.json();
    } catch {
      return mockCounterfactualResponse;
    }
  },
};

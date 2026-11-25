/**
 * Causal Analysis API Client & Mock Service (ContextIQ Phase 6.3).
 */
import type {
  CausalAnalysisResultData,
  CausalQuestionId,
  CausalMethod,
  CausalQuestionSummary,
} from "@/types/causal";

export const mockCausalResult: CausalAnalysisResultData = {
  question_id: "recovery_buffer_on_resumption",
  title: "Target Trial 1: Scheduled Recovery Buffer vs Immediate Resumption on Task Return",
  status: "convincing",
  method_used: "doubly_robust_aipw",
  target_trial: {
    question_id: "recovery_buffer_on_resumption",
    title: "Target Trial 1: Scheduled Recovery Buffer vs Immediate Resumption on Task Return",
    eligibility_criteria: [
      "User experienced a detected cognitive interruption exceeding 60 seconds",
      "Disrupted task had an active in-progress status prior to interruption",
      "User has active telemetry consent and working session enabled",
      "Disrupted task deadline is not within the immediate 2 hours (safety exemption)",
    ],
    treatment_strategy: "Deliver a scheduled cognitive recovery buffer (3-5 minutes) with context re-anchoring card at interruption termination.",
    control_strategy: "Deliver no recovery buffer; allow immediate unassisted task resumption (standard practice).",
    time_zero_definition: "Timestamp of cognitive interruption termination (t_T0). Treatment strategy is assigned strictly at t_T0.",
    follow_up_window: "15 minutes following interruption termination [t_T0, t_T0 + 15 min].",
    outcome_definition: "Confirmed task resumption (Y in {0, 1}) grounded in deliberate keyboard/IDE input within 15 minutes of T0.",
    causal_estimand: "treatment_effect_on_treated",
    analysis_plan: "Doubly Robust AIPW and IPW estimation adjusting for pre-T0 confounders; sensitivity E-value evaluation.",
    immortal_time_bias_prevention: "Eligibility is determined strictly prior to t_T0. Both treatment and control arms begin follow-up simultaneously at t_T0.",
  },
  sample_size_treated: 112,
  sample_size_control: 138,
  total_sample_size: 250,
  raw_observational_difference: 0.124,
  estimated_causal_effect: 0.176,
  confidence_interval: [0.082, 0.270],
  standard_error: 0.048,
  p_value: 0.0003,
  covariate_balance: [
    {
      covariate_name: "baseline_bfi",
      mean_treated: 48.2,
      mean_control: 47.9,
      smd_unadjusted: 0.42,
      smd_adjusted: 0.03,
      is_balanced: true,
    },
    {
      covariate_name: "interruption_duration",
      mean_treated: 242.0,
      mean_control: 238.5,
      smd_unadjusted: 0.35,
      smd_adjusted: 0.04,
      is_balanced: true,
    },
    {
      covariate_name: "task_priority",
      mean_treated: 2.3,
      mean_control: 2.2,
      smd_unadjusted: 0.28,
      smd_adjusted: 0.05,
      is_balanced: true,
    },
    {
      covariate_name: "calendar_meeting_density",
      mean_treated: 3.1,
      mean_control: 3.0,
      smd_unadjusted: 0.19,
      smd_adjusted: 0.02,
      is_balanced: true,
    },
  ],
  overlap_diagnostics: {
    common_support_min: 0.124,
    common_support_max: 0.882,
    treated_propensity_mean: 0.548,
    control_propensity_mean: 0.384,
    positivity_violations_count: 6,
    positivity_violations_pct: 2.4,
    has_sufficient_overlap: true,
  },
  sensitivity: {
    e_value_estimate: 2.68,
    e_value_lower_bound: 1.84,
    interpretation: "Robust to moderate unmeasured confounding (E-value = 2.68). An unmeasured confounder must multiply the risk of both intervention and outcome by at least 2.68-fold to fully explain away this estimated effect.",
    robustness_assessment: "ROBUST",
  },
  effect_heterogeneity: [
    {
      subgroup_name: "Coding",
      dimension: "Task Category",
      sample_size_treated: 42,
      sample_size_control: 38,
      estimated_cate: 0.214,
      ci_lower: 0.082,
      ci_upper: 0.346,
      is_statistically_sound: true,
    },
    {
      subgroup_name: "DeepWork",
      dimension: "Task Category",
      sample_size_treated: 35,
      sample_size_control: 40,
      estimated_cate: 0.185,
      ci_lower: 0.042,
      ci_upper: 0.328,
      is_statistically_sound: true,
    },
    {
      subgroup_name: "Administrative",
      dimension: "Task Category",
      sample_size_treated: 12,
      sample_size_control: 15,
      estimated_cate: null,
      ci_lower: null,
      ci_upper: null,
      is_statistically_sound: false,
      abstention_reason: "Underpowered subgroup: N=27 < 30 (Treated: 12, Control: 15). Suppressed to prevent premature conclusions.",
    },
  ],
  identification_assumptions: [
    "Conditional Exchangeability (No unmeasured confounders conditional on adjustment set)",
    "Positivity / Common Support (0 < P(A=1|X) < 1 across all covariate strata)",
    "Consistency (Observed outcome under intervention matches counterfactual potential outcome)",
    "SUTVA (Stable Unit Treatment Value Assumption: No interference between distinct disruption episodes)",
  ],
  limitations: [
    "Observational design cannot completely rule out unmeasured psychological frustration or offline disruption.",
    "Immortal-time bias was controlled by strict T0 alignment, but self-selection into software usage may persist.",
    "Subgroup CATE estimates with N < 30 are suppressed to prevent premature generalizations.",
  ],
  disclaimer: "CORRELATION IS NOT CAUSATION. Causal claims are valid strictly under the stated unverifiable identification assumptions (conditional exchangeability, positivity, consistency, and SUTVA). Predictive associations and feature weights must never be interpreted as causal intervention effects.",
};

export const causalApi = {
  async getQuestions(): Promise<CausalQuestionSummary[]> {
    try {
      const res = await fetch("/api/v1/causal/questions");
      if (!res.ok) throw new Error("API error");
      return await res.json();
    } catch {
      return [
        {
          question_id: "recovery_buffer_on_resumption",
          title: "DAG: Recovery Buffer on Confirmed Task Resumption",
          treatment_node: "recovery_buffer",
          outcome_node: "task_resumption",
          adjustment_set: ["baseline_bfi", "task_priority", "interruption_duration", "hour_of_day", "calendar_meeting_density"],
          forbidden_controls: ["context_card_read_latency"],
          unmeasured_risks_count: 2,
        },
        {
          question_id: "adaptive_scheduling_on_completion",
          title: "DAG: Adaptive Scheduling on Task Completion",
          treatment_node: "adaptive_scheduling",
          outcome_node: "task_completion",
          adjustment_set: ["task_complexity", "historical_completion_rate", "calendar_load", "task_urgency"],
          forbidden_controls: ["focus_window_duration"],
          unmeasured_risks_count: 2,
        },
      ];
    }
  },

  async evaluateQuestion(
    questionId: CausalQuestionId,
    method: CausalMethod = "doubly_robust_aipw"
  ): Promise<CausalAnalysisResultData> {
    try {
      const res = await fetch(`/api/v1/causal/evaluate/${questionId}?method=${method}`);
      if (!res.ok) throw new Error("API error");
      return await res.json();
    } catch {
      return mockCausalResult;
    }
  },
};

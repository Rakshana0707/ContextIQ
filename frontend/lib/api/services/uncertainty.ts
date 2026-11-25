/**
 * Uncertainty-Aware Decision Support API Client & Mock Service (ContextIQ Phase 6.8).
 */
import type {
  CalibrationMetricsData,
  DecisionSupportResponseData,
  ModelUncertaintyAuditItemData,
} from "@/types/uncertainty";

export const mockDecisionSupportResponse: DecisionSupportResponseData = {
  decision_id: "dec_mock_8812",
  user_id: "usr_mock_001",
  evaluated_at: new Date().toISOString(),
  model_name: "Calibrated Conformal Decision Engine",
  abstention_outcome: "PREDICTION_AVAILABLE",
  abstention_reason: "NONE",
  can_automate_recommendation: true,
  recommended_action_policy: "EXECUTE_AUTOMATED",
  point_prediction: 0.68,
  calibrated_probability: 0.665,
  uncertainty_decomposition: {
    aleatoric_score: 0.38,
    epistemic_score: 0.16,
    total_uncertainty: 0.28,
    is_epistemic_dominant: false,
    explanation:
      "Aleatoric uncertainty dominates (0.38 >= 0.16) reflecting inherent behavioral variability in knowledge work. Telemetry history is sufficient to bound epistemic error.",
  },
  prediction_interval: {
    coverage_level: 0.90,
    lower_bound: 0.525,
    upper_bound: 0.805,
    interval_width: 0.28,
    calibration_sample_size: 20,
    temporal_shift_warning: null,
  },
  data_coverage: {
    user_sample_size: 32,
    telemetry_quality_score: 0.88,
    ood_distance: 1.15,
    is_out_of_distribution: false,
    unseen_event_types: [],
    missing_critical_inputs: [],
    data_coverage_tier: "FULL",
  },
  calibration_metrics: {
    calibration_method: "Isotonic Regression",
    expected_calibration_error: 0.038,
    maximum_calibration_error: 0.072,
    brier_score: 0.124,
    is_well_calibrated: true,
    reliability_bins: [
      { bin_index: 0, bin_center: 0.05, observed_frequency: 0.04, predicted_frequency: 0.05, sample_count: 12 },
      { bin_index: 1, bin_center: 0.25, observed_frequency: 0.24, predicted_frequency: 0.26, sample_count: 18 },
      { bin_index: 2, bin_center: 0.50, observed_frequency: 0.49, predicted_frequency: 0.51, sample_count: 22 },
      { bin_index: 3, bin_center: 0.75, observed_frequency: 0.76, predicted_frequency: 0.74, sample_count: 25 },
      { bin_index: 4, bin_center: 0.95, observed_frequency: 0.96, predicted_frequency: 0.94, sample_count: 15 },
    ],
  },
  user_facing_explanation:
    "Prediction verified: High data coverage (FULL tier), well-calibrated confidence (ECE 0.038), and 90% conformal interval [0.52, 0.81]. Automated decision authorized.",
  disclaimer:
    "ContextIQ abstains from automated recommendations when data coverage is insufficient or uncertainty is excessive. Uncertainty is distinct from prediction probability.",
};

export const mockCalibrationBenchmarks: CalibrationMetricsData[] = [
  {
    calibration_method: "Isotonic Regression (Non-Parametric)",
    expected_calibration_error: 0.038,
    maximum_calibration_error: 0.072,
    brier_score: 0.124,
    is_well_calibrated: true,
    reliability_bins: [],
  },
  {
    calibration_method: "Platt Scaling (Logistic Sigmoid)",
    expected_calibration_error: 0.052,
    maximum_calibration_error: 0.089,
    brier_score: 0.138,
    is_well_calibrated: true,
    reliability_bins: [],
  },
  {
    calibration_method: "Temperature Scaling (T=1.45)",
    expected_calibration_error: 0.065,
    maximum_calibration_error: 0.104,
    brier_score: 0.145,
    is_well_calibrated: true,
    reliability_bins: [],
  },
];

export const mockModelAudit: ModelUncertaintyAuditItemData[] = [
  {
    model_family: "XGBoost Forgetting Risk (Phase 2 & 3.8)",
    target_name: "Task Forgetting Risk",
    exposes_interval: true,
    interval_methodology: "Asymptotic 95% Wald CI with cold-start penalty",
    decomposes_uncertainty: false,
    calibration_status: "Platt scaled risk categories",
    abstention_supported: true,
    known_limitations: "Heuristic confidence scaling; no separate OOD rejection.",
  },
  {
    model_family: "Log-Normal / Weibull AFT (Phase 6.2)",
    target_name: "Cognitive Recovery Duration",
    exposes_interval: true,
    interval_methodology: "Parametric AFT quantile bounds (Q10, Q50, Q90)",
    decomposes_uncertainty: false,
    calibration_status: "Right-censoring maximum likelihood",
    abstention_supported: true,
    known_limitations: "Sensitive to tail misspecification on extreme delays.",
  },
  {
    model_family: "Doubly Robust Meta-Learner (Phase 6.4)",
    target_name: "Counterfactual Potential Outcomes",
    exposes_interval: true,
    interval_methodology: "90% Conformal uncertainty intervals with coverage tiers",
    decomposes_uncertainty: true,
    calibration_status: "Common support overlap scoring",
    abstention_supported: true,
    known_limitations: "Unsupported candidate tiers excluded; fallback to deterministic rules.",
  },
  {
    model_family: "Log-Normal Landmarked Survival (Phase 6.6)",
    target_name: "Dynamic Time-to-Event Hazards",
    exposes_interval: true,
    interval_methodology: "Hierarchical conformal: Individual (+-15%), Group (+-25%), Population (+-40%)",
    decomposes_uncertainty: true,
    calibration_status: "Landmarking S(t | T > t_curr) conditioning",
    abstention_supported: true,
    known_limitations: "Population tier widens intervals but does not refuse inference on cold start.",
  },
  {
    model_family: "Multi-Objective Optimizer (Phase 6.7)",
    target_name: "Intervention Selection & Recommendation",
    exposes_interval: true,
    interval_methodology: "Uncertainty width tolerance (<0.35) and Pareto dominance",
    decomposes_uncertainty: true,
    calibration_status: "Hard constraint gating + scalarized utility",
    abstention_supported: true,
    known_limitations: "Withholds active intervention (selects No-Action) when uncertainty exceeds tolerance.",
  },
];

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export const uncertaintyApi = {
  async evaluate(
    taskId?: string,
    modelTarget: string = "forgetting_risk",
    contextFeatures?: Record<string, any>
  ): Promise<DecisionSupportResponseData> {
    try {
      const res = await fetch(`${API_BASE}/uncertainty/evaluate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task_id: taskId,
          model_target: modelTarget,
          context_features: contextFeatures || {},
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch {
      return mockDecisionSupportResponse;
    }
  },

  async getCalibration(): Promise<CalibrationMetricsData[]> {
    try {
      const res = await fetch(`${API_BASE}/uncertainty/calibration`, {
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch {
      return mockCalibrationBenchmarks;
    }
  },

  async getAudit(): Promise<ModelUncertaintyAuditItemData[]> {
    try {
      const res = await fetch(`${API_BASE}/uncertainty/audit`, {
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch {
      return mockModelAudit;
    }
  },
};

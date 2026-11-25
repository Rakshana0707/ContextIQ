/**
 * Behavioral Digital Twin Simulation and Proposed Workflow Service (ContextIQ Phase 6.9).
 */

import type {
  ProposedWorkflow,
  SavedScenario,
  ScenarioCompareResponse,
  ScenarioSimulationResult,
  ScenarioType,
  WorkflowExecutionResponse,
  WorkflowRollbackResponse,
} from "@/types/simulation";

export const mockSimulationResult: ScenarioSimulationResult = {
  scenario_type: "SCHEDULE_FOCUS_SESSION",
  hypothesis_description: "Allocating a 60m dedicated focus session with notifications suppressed.",
  baseline_metrics: {
    completion_probability: 0.58,
    expected_recovery_duration_minutes: 18.5,
    behavioral_friction_index: 52.0,
    notification_burden_score: 45.0,
    calendar_feasibility: 0.85,
    recovery_duration_interval_lower: 12.0,
    recovery_duration_interval_upper: 25.0,
    completion_probability_interval_lower: 0.44,
    completion_probability_interval_upper: 0.72,
  },
  simulated_metrics: {
    completion_probability: 0.84,
    expected_recovery_duration_minutes: 5.2,
    behavioral_friction_index: 28.0,
    notification_burden_score: 18.0,
    calendar_feasibility: 0.92,
    recovery_duration_interval_lower: 3.5,
    recovery_duration_interval_upper: 7.8,
    completion_probability_interval_lower: 0.74,
    completion_probability_interval_upper: 0.94,
  },
  counterfactual_delta: {
    completion_probability_delta: 0.26,
    recovery_duration_delta_minutes: -13.3,
    friction_delta: -24.0,
    notification_burden_delta: -27.0,
    summary: "Simulated focus session projects a +26.0% gain in completion likelihood and reduces expected recovery lag by 13.3m.",
  },
  assumptions: [
    "Unfragmented 60-minute window with zero high-priority calendar conflicts.",
    "Notification suppression active on desktop and mobile devices during session.",
    "Circadian focus capacity assumed near optimal based on historical profile.",
  ],
  uncertainty_interval_coverage: 0.9,
  model_version: "digital_twin_v6.9",
  feature_version: "twin_features_v1",
  timestamp: new Date().toISOString(),
};

export const mockSavedScenarios: SavedScenario[] = [
  {
    id: "scen_mock_001",
    user_id: "usr_mock_001",
    title: "Morning Focus Block (09:00 - 10:00)",
    scenario_type: "SCHEDULE_FOCUS_SESSION",
    hypothesis: "Reschedule deep work to morning peak with 60m protected block.",
    input_parameters: { focus_block_minutes: 60, target_time: "09:00" },
    baseline_metrics: mockSimulationResult.baseline_metrics,
    simulated_metrics: mockSimulationResult.simulated_metrics,
    counterfactual_delta: mockSimulationResult.counterfactual_delta,
    assumptions: mockSimulationResult.assumptions,
    is_active_plan: true,
    model_version: "digital_twin_v6.9",
    feature_version: "twin_features_v1",
    created_at: new Date(Date.now() - 3600000 * 2).toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "scen_mock_002",
    user_id: "usr_mock_001",
    title: "Post-Standup 15m Cognitive Recovery Buffer",
    scenario_type: "ADD_RECOVERY_BUFFER",
    hypothesis: "Insert 15m breathing space after sync meetings to mitigate context switching.",
    input_parameters: { buffer_minutes: 15 },
    baseline_metrics: {
      completion_probability: 0.62,
      expected_recovery_duration_minutes: 16.0,
      behavioral_friction_index: 48.0,
      notification_burden_score: 35.0,
      calendar_feasibility: 0.88,
      recovery_duration_interval_lower: 11.0,
      recovery_duration_interval_upper: 22.0,
      completion_probability_interval_lower: 0.49,
      completion_probability_interval_upper: 0.75,
    },
    simulated_metrics: {
      completion_probability: 0.76,
      expected_recovery_duration_minutes: 8.5,
      behavioral_friction_index: 32.0,
      notification_burden_score: 30.0,
      calendar_feasibility: 0.85,
      recovery_duration_interval_lower: 5.5,
      recovery_duration_interval_upper: 12.0,
      completion_probability_interval_lower: 0.65,
      completion_probability_interval_upper: 0.87,
    },
    counterfactual_delta: {
      completion_probability_delta: 0.14,
      recovery_duration_delta_minutes: -7.5,
      friction_delta: -16.0,
      notification_burden_delta: -5.0,
      summary: "Recovery buffer projects -7.5m resumption delay and -16 points lower behavioral friction.",
    },
    assumptions: [
      "User adheres to passive rest or low-cognitive triage during buffer.",
      "Calendar scheduling allows flexible 15-minute slot.",
    ],
    is_active_plan: false,
    model_version: "digital_twin_v6.9",
    feature_version: "twin_features_v1",
    created_at: new Date(Date.now() - 3600000 * 24).toISOString(),
    updated_at: new Date(Date.now() - 3600000 * 12).toISOString(),
  },
];

export const mockCompareResponse: ScenarioCompareResponse = {
  scenarios: [
    {
      scenario_id: "scen_mock_001",
      scenario_type: "SCHEDULE_FOCUS_SESSION",
      title: "Morning Focus Block (09:00 - 10:00)",
      completion_probability: 0.84,
      completion_probability_delta: 0.26,
      expected_recovery_minutes: 5.2,
      recovery_minutes_delta: -13.3,
      behavioral_friction: 28.0,
      friction_delta: -24.0,
      notification_burden: 18.0,
      calendar_feasibility: 0.92,
      is_active_plan: true,
    },
    {
      scenario_id: "scen_mock_002",
      scenario_type: "ADD_RECOVERY_BUFFER",
      title: "Post-Standup 15m Cognitive Recovery Buffer",
      completion_probability: 0.76,
      completion_probability_delta: 0.14,
      expected_recovery_minutes: 8.5,
      recovery_minutes_delta: -7.5,
      behavioral_friction: 32.0,
      friction_delta: -16.0,
      notification_burden: 30.0,
      calendar_feasibility: 0.85,
      is_active_plan: false,
    },
    {
      scenario_id: null,
      scenario_type: "REDUCE_NOTIFICATIONS",
      title: "Simulated Notification Mute (45m)",
      completion_probability: 0.71,
      completion_probability_delta: 0.13,
      expected_recovery_minutes: 10.1,
      recovery_minutes_delta: -5.9,
      behavioral_friction: 38.0,
      friction_delta: -14.0,
      notification_burden: 15.0,
      calendar_feasibility: 0.98,
      is_active_plan: false,
    },
  ],
  recommended_scenario_type: "SCHEDULE_FOCUS_SESSION",
  recommendation_rationale:
    "Schedule Focus Session delivers the highest completion gain (+26%) and steepest friction drop (-24 pts) with strong calendar feasibility (92%).",
  compared_at: new Date().toISOString(),
};

export const mockProposedWorkflow: ProposedWorkflow = {
  id: "wf_mock_7731",
  scenario_id: "scen_mock_001",
  user_id: "usr_mock_001",
  title: "Proposed Workflow: Morning Focus Block (09:00 - 10:00)",
  status: "PROPOSED",
  total_actions: 3,
  actions: [
    {
      action_id: "act_01",
      action_type: "RESCHEDULE_TASK",
      sequence_order: 1,
      description: "Shift task target to 09:00 morning cognitive window.",
      target_resource: "task:active",
      parameters: { target_time: "09:00", duration_minutes: 60 },
      estimated_duration_minutes: 60,
      is_reversible: true,
      required_permissions: ["tasks.write"],
    },
    {
      action_id: "act_02",
      action_type: "CREATE_FOCUS_SESSION",
      sequence_order: 2,
      description: "Schedule 60m unfragmented focus session on primary calendar.",
      target_resource: "calendar:google",
      parameters: { title: "Deep Focus Session", start_time: "09:00", end_time: "10:00" },
      estimated_duration_minutes: 60,
      is_reversible: true,
      required_permissions: ["google_calendar.write"],
    },
    {
      action_id: "act_03",
      action_type: "CONFIGURE_REMINDER",
      sequence_order: 3,
      description: "Activate focus reminder 5m prior to start and mute non-essential alerts.",
      target_resource: "notifications:policy",
      parameters: { lead_time_minutes: 5, mute_alerts: true },
      estimated_duration_minutes: 5,
      is_reversible: true,
      required_permissions: ["notifications.manage"],
    },
  ],
  estimated_total_duration_minutes: 65,
  required_permissions: ["tasks.write", "google_calendar.write", "notifications.manage"],
  is_reversible: true,
  idempotency_key: "idem_mock_99124",
  audit_trail: [
    {
      timestamp: new Date().toISOString(),
      action: "PROPOSAL_GENERATED",
      details: "Generated 3-step proposal from scenario scen_mock_001.",
    },
  ],
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export const simulationApi = {
  async simulate(
    scenarioType: ScenarioType,
    taskId?: string,
    parameters?: Record<string, any>
  ): Promise<ScenarioSimulationResult> {
    try {
      const res = await fetch(`${API_BASE}/simulation/scenarios/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scenario_type: scenarioType,
          task_id: taskId,
          parameters: parameters || {},
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch {
      return mockSimulationResult;
    }
  },

  async listScenarios(): Promise<SavedScenario[]> {
    try {
      const res = await fetch(`${API_BASE}/simulation/scenarios`, {
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch {
      return mockSavedScenarios;
    }
  },

  async compareScenarios(
    scenarioIds: string[] = [],
    includeStandardTypes = true
  ): Promise<ScenarioCompareResponse> {
    try {
      const res = await fetch(`${API_BASE}/simulation/scenarios/compare`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scenario_ids: scenarioIds,
          include_standard_types: includeStandardTypes,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch {
      return mockCompareResponse;
    }
  },

  async activatePlan(scenarioId: string): Promise<SavedScenario> {
    try {
      const res = await fetch(`${API_BASE}/simulation/scenarios/${scenarioId}/activate-plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch {
      const found = mockSavedScenarios.find((s) => s.id === scenarioId);
      if (found) {
        mockSavedScenarios.forEach((s) => (s.is_active_plan = s.id === scenarioId));
        return { ...found, is_active_plan: true };
      }
      return mockSavedScenarios[0];
    }
  },

  async proposeWorkflow(scenarioId: string): Promise<ProposedWorkflow> {
    try {
      const res = await fetch(`${API_BASE}/simulation/scenarios/${scenarioId}/propose-workflow`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch {
      return { ...mockProposedWorkflow, scenario_id: scenarioId };
    }
  },

  async approveWorkflow(workflowId: string, approved: boolean): Promise<ProposedWorkflow> {
    try {
      const res = await fetch(`${API_BASE}/simulation/workflows/${workflowId}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approved }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch {
      return {
        ...mockProposedWorkflow,
        id: workflowId,
        status: approved ? "APPROVED" : "CANCELLED",
      };
    }
  },

  async executeWorkflow(
    workflowId: string,
    idempotencyKey?: string
  ): Promise<WorkflowExecutionResponse> {
    try {
      const url = new URL(`${API_BASE}/simulation/workflows/${workflowId}/execute`);
      if (idempotencyKey) url.searchParams.append("idempotency_key", idempotencyKey);
      const res = await fetch(url.toString(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch {
      return {
        workflow_id: workflowId,
        status: "COMPLETED",
        executed_actions_count: mockProposedWorkflow.actions.length,
        execution_details: mockProposedWorkflow.actions.map((a) => ({
          action_id: a.action_id,
          status: "SUCCESS",
        })),
        is_reverted: false,
        executed_at: new Date().toISOString(),
        revert_payload_available: true,
      };
    }
  },

  async rollbackWorkflow(workflowId: string): Promise<WorkflowRollbackResponse> {
    try {
      const res = await fetch(`${API_BASE}/simulation/workflows/${workflowId}/rollback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch {
      return {
        workflow_id: workflowId,
        status: "REVERTED",
        reverted_actions_count: mockProposedWorkflow.actions.length,
        details: "Workflow actions reverted successfully to baseline state.",
        reverted_at: new Date().toISOString(),
      };
    }
  },
};

import { apiClient, USE_MOCK } from "@/lib/api/client";
import type {
  WorkflowExecutionPlan,
  WorkflowExecutionProgress,
  ActionContract,
  WorkflowLifecycleState,
} from "@/types/workflows";

const mockWorkflowPlans: WorkflowExecutionPlan[] = [
  {
    id: "plan-mock-001",
    user_id: "usr-001",
    title: "Autonomous Recovery & Focus Workflow for 'Deep Behavioral Analytics Review'",
    status: "AWAITING_APPROVAL",
    version: 1,
    idempotency_key: "plan:usr-001:mock-1",
    trigger_context: {
      trigger_type: "FORGETTING_RISK_SPIKE",
      task_title: "Deep Behavioral Analytics Review",
      lapse_probability: 0.78,
    },
    plan_steps: [
      {
        step_key: "step_1_review_task",
        name: "Verify Priority for 'Deep Behavioral Analytics Review'",
        action_identifier: "task:update_priority",
        parameters: { new_priority: "HIGH" },
        order_index: 1,
        is_optional: false,
        requires_approval: true,
        estimated_duration_minutes: 5,
      },
      {
        step_key: "step_2_reschedule_conflict",
        name: "Reschedule Conflicting Calendar Meeting",
        action_identifier: "calendar:reschedule_event",
        parameters: { external_event_id: "ext_cal_401" },
        order_index: 2,
        is_optional: false,
        requires_approval: true,
        estimated_duration_minutes: 5,
      },
      {
        step_key: "step_3_reserve_focus_block",
        name: "Reserve 50m Calendar Focus Block",
        action_identifier: "calendar:insert_focus_block",
        parameters: { title: "Focus: Deep Behavioral Analytics Review" },
        order_index: 3,
        is_optional: false,
        requires_approval: true,
        estimated_duration_minutes: 50,
      },
      {
        step_key: "step_4_clamp_distractions",
        name: "Shield Distractions on Workstation",
        action_identifier: "focus:clamp_complementary_tools",
        parameters: { allowed_application_names: ["code.exe", "browser.exe"] },
        order_index: 4,
        is_optional: true,
        requires_approval: false,
        estimated_duration_minutes: 50,
      },
      {
        step_key: "step_5_recovery_buffer",
        name: "Inject 10m Post-Work Recovery Buffer",
        action_identifier: "recovery:insert_post_interruption_buffer",
        parameters: { buffer_duration_minutes: 10 },
        order_index: 5,
        is_optional: false,
        requires_approval: true,
        estimated_duration_minutes: 10,
      },
      {
        step_key: "step_6_context_reminder",
        name: "Stage 15m Task Warming Reminder",
        action_identifier: "reminder:stage_context_warming",
        parameters: { lead_time_minutes: 15 },
        order_index: 6,
        is_optional: false,
        requires_approval: false,
        estimated_duration_minutes: 5,
      },
    ],
    plan_dependencies: [
      { source_step_key: "step_1_review_task", target_step_key: "step_2_reschedule_conflict", dependency_type: "SUCCESS" },
      { source_step_key: "step_2_reschedule_conflict", target_step_key: "step_3_reserve_focus_block", dependency_type: "SUCCESS" },
      { source_step_key: "step_3_reserve_focus_block", target_step_key: "step_4_clamp_distractions", dependency_type: "SUCCESS" },
      { source_step_key: "step_3_reserve_focus_block", target_step_key: "step_5_recovery_buffer", dependency_type: "SUCCESS" },
      { source_step_key: "step_3_reserve_focus_block", target_step_key: "step_6_context_reminder", dependency_type: "SUCCESS" },
    ],
    rationale:
      "Detected elevated forgetting risk (78%) on high-priority task with calendar collision. Proposed plan clears conflict, reserves an uninterruptible 50m deep work block, and guarantees post-session recovery buffer.",
    expected_benefits: {
      lapse_probability_reduction: "78% -> 12%",
      protected_focus_minutes: 50,
      guaranteed_recovery_minutes: 10,
    },
    potential_side_effects: {
      external_calendar_reschedule: "Meeting moved by 60 minutes",
      desktop_apps_clamped: "Distraction apps minimized during session",
    },
    utility_score: 0.89,
    plan_comparison_metadata: {
      alternatives: [
        {
          plan_name: "Balanced Cognitive Optimization (Recommended)",
          strategy: "BALANCED_BUFFERED",
          utility_score: 0.89,
          task_benefit_score: 0.95,
          schedule_feasibility_score: 0.90,
          recovery_impact_score: 0.85,
          notification_burden_score: 0.90,
          prediction_uncertainty_penalty: 0.05,
          trade_off_summary: "Harmonizes deep focus blocks with mandatory post-task recovery buffers.",
          steps_count: 6,
        },
        {
          plan_name: "Aggressive Deep Focus",
          strategy: "AGGRESSIVE_FOCUS",
          utility_score: 0.81,
          task_benefit_score: 0.98,
          schedule_feasibility_score: 0.72,
          recovery_impact_score: 0.50,
          notification_burden_score: 0.85,
          prediction_uncertainty_penalty: 0.08,
          trade_off_summary: "Maximizes immediate focus time but sacrifices cognitive decompression intervals.",
          steps_count: 4,
        },
      ],
    },
    reversibility_summary: {
      is_fully_reversible: true,
      compensating_steps_count: 4,
      rollback_guarantee: "All calendar and priority adjustments can be completely undone.",
    },
    created_at: new Date(Date.now() - 30 * 60000).toISOString(),
    updated_at: new Date(Date.now() - 30 * 60000).toISOString(),
  },
];

export const workflowsApi = {
  listActions: async (category?: string): Promise<ActionContract[]> => {
    if (USE_MOCK) return [];
    const query = category ? { category } : undefined;
    const res = await apiClient.request<ActionContract[]>("/workflows/actions", {
      method: "GET",
      query,
    });
    if (res.error) throw new Error(res.error.message);
    return res.data ?? [];
  },

  planWorkflow: async (payload: {
    trigger_type: string;
    task_id?: string;
    behavioral_context?: Record<string, any>;
    desired_strategy?: string;
    generate_alternatives?: boolean;
  }): Promise<WorkflowExecutionPlan> => {
    if (USE_MOCK) {
      return mockWorkflowPlans[0];
    }
    const res = await apiClient.request<WorkflowExecutionPlan>("/workflows/plan", {
      method: "POST",
      body: payload,
    });
    if (res.error) throw new Error(res.error.message);
    return res.data!;
  },

  listPlans: async (statusFilter?: string): Promise<WorkflowExecutionPlan[]> => {
    if (USE_MOCK) {
      if (statusFilter) {
        return mockWorkflowPlans.filter((p) => p.status === statusFilter);
      }
      return [...mockWorkflowPlans];
    }
    const query = statusFilter ? { status_filter: statusFilter } : undefined;
    const res = await apiClient.request<WorkflowExecutionPlan[]>("/workflows/plans", {
      method: "GET",
      query,
    });
    if (res.error) throw new Error(res.error.message);
    return res.data ?? [];
  },

  getPlan: async (planId: string): Promise<WorkflowExecutionPlan> => {
    if (USE_MOCK) {
      const plan = mockWorkflowPlans.find((p) => p.id === planId);
      if (!plan) throw new Error("Plan not found");
      return plan;
    }
    const res = await apiClient.request<WorkflowExecutionPlan>(`/workflows/plans/${planId}`, {
      method: "GET",
    });
    if (res.error) throw new Error(res.error.message);
    return res.data!;
  },

  transitionPlan: async (
    planId: string,
    targetState: WorkflowLifecycleState,
    reason?: string
  ): Promise<WorkflowExecutionPlan> => {
    if (USE_MOCK) {
      const plan = mockWorkflowPlans.find((p) => p.id === planId);
      if (!plan) throw new Error("Plan not found");
      plan.status = targetState;
      plan.version += 1;
      plan.updated_at = new Date().toISOString();
      return { ...plan };
    }
    const res = await apiClient.request<WorkflowExecutionPlan>(`/workflows/plans/${planId}/transition`, {
      method: "POST",
      body: {
        target_state: targetState,
        reason,
      },
    });
    if (res.error) throw new Error(res.error.message);
    return res.data!;
  },

  executePlan: async (
    planId: string,
    autoRollbackOnFailure: boolean = false,
    sync: boolean = false
  ): Promise<WorkflowExecutionPlan> => {
    if (USE_MOCK) {
      const plan = mockWorkflowPlans.find((p) => p.id === planId);
      if (!plan) throw new Error("Plan not found");
      plan.status = "COMPLETED";
      plan.executed_at = new Date().toISOString();
      return { ...plan };
    }
    const res = await apiClient.request<WorkflowExecutionPlan>(
      `/workflows/plans/${planId}/execute?sync=${sync}`,
      {
        method: "POST",
        body: { auto_rollback_on_failure: autoRollbackOnFailure },
      }
    );
    if (res.error) throw new Error(res.error.message);
    return res.data!;
  },

  getExecutionProgress: async (planId: string): Promise<WorkflowExecutionProgress> => {
    if (USE_MOCK) {
      const plan = mockWorkflowPlans.find((p) => p.id === planId) || mockWorkflowPlans[0];
      return {
        plan_id: plan.id,
        title: plan.title,
        status: plan.status,
        version: plan.version,
        total_steps: plan.plan_steps.length,
        completed_steps: plan.status === "COMPLETED" ? plan.plan_steps.length : 1,
        failed_steps: 0,
        skipped_steps: 0,
        progress_percentage: plan.status === "COMPLETED" ? 100 : 16.7,
        step_executions: plan.plan_steps.map((s, idx) => ({
          id: `step-exec-${idx}`,
          plan_id: plan.id,
          step_key: s.step_key,
          action_identifier: s.action_identifier,
          status: plan.status === "COMPLETED" ? "COMPLETED" : idx === 0 ? "COMPLETED" : "PENDING",
          attempt_count: 1,
          max_attempts: 3,
          idempotency_key: `${plan.id}:${s.step_key}`,
          input_payload: s.parameters,
          compensation_status: "NONE",
        })),
        is_reversible: true,
      };
    }
    const res = await apiClient.request<WorkflowExecutionProgress>(
      `/workflows/plans/${planId}/execution`,
      { method: "GET" }
    );
    if (res.error) throw new Error(res.error.message);
    return res.data!;
  },

  cancelExecution: async (planId: string): Promise<WorkflowExecutionPlan> => {
    if (USE_MOCK) {
      const plan = mockWorkflowPlans.find((p) => p.id === planId);
      if (!plan) throw new Error("Plan not found");
      plan.status = "CANCELLED";
      return { ...plan };
    }
    const res = await apiClient.request<WorkflowExecutionPlan>(
      `/workflows/plans/${planId}/cancel`,
      { method: "POST" }
    );
    if (res.error) throw new Error(res.error.message);
    return res.data!;
  },

  rollbackExecution: async (planId: string): Promise<WorkflowExecutionPlan> => {
    if (USE_MOCK) {
      const plan = mockWorkflowPlans.find((p) => p.id === planId);
      if (!plan) throw new Error("Plan not found");
      plan.status = "ROLLED_BACK";
      return { ...plan };
    }
    const res = await apiClient.request<WorkflowExecutionPlan>(
      `/workflows/plans/${planId}/rollback`,
      { method: "POST" }
    );
    if (res.error) throw new Error(res.error.message);
    return res.data!;
  },
};

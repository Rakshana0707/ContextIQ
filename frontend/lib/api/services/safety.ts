import { apiClient, USE_MOCK } from "@/lib/api/client";
import type {
  EmergencyStopEvent,
  EmergencyStatusSummary,
  WorkflowAuditEvent,
  WorkflowRollbackRecord,
  SafetyOverview,
  ReversibilityCheckResult,
} from "@/types/safety";

const mockActiveStops: EmergencyStopEvent[] = [];

const mockAuditEvents: WorkflowAuditEvent[] = [
  {
    id: "evt-001",
    user_id: "usr-001",
    plan_id: "plan-mock-001",
    workflow_version: 1,
    event_type: "STEP_COMPLETED",
    action_identifier: "task:update_priority",
    step_key: "step_1_review_task",
    execution_timestamp: new Date().toISOString(),
    policy_decision: "ALLOWED",
    result_status: "COMPLETED",
    sanitized_payload: { task_id: "task-01", new_priority: "HIGH" },
  },
  {
    id: "evt-002",
    user_id: "usr-001",
    plan_id: "plan-mock-001",
    workflow_version: 1,
    event_type: "STEP_DISPATCHED",
    action_identifier: "calendar:insert_focus_block",
    step_key: "step_3_reserve_focus_block",
    execution_timestamp: new Date(Date.now() - 60000).toISOString(),
    policy_decision: "ALLOWED",
    sanitized_payload: { title: "Deep Focus Session", duration_minutes: 50 },
  },
  {
    id: "evt-003",
    user_id: "usr-001",
    plan_id: "plan-mock-001",
    workflow_version: 1,
    event_type: "WORKFLOW_PLAN_APPROVED",
    execution_timestamp: new Date(Date.now() - 120000).toISOString(),
    approval_reference: "appr-001",
    result_status: "APPROVED",
  },
];

const mockRollbackRecords: WorkflowRollbackRecord[] = [];

export const safetyApi = {
  getOverview: async (): Promise<SafetyOverview> => {
    if (USE_MOCK) {
      return {
        active_plans_count: 2,
        awaiting_approval_count: 1,
        failed_plans_count: 0,
        reversible_plans_count: 3,
        emergency_stop_active: mockActiveStops.some((s) => s.is_active),
        recent_audit_events: [...mockAuditEvents],
        active_emergency_stops: [...mockActiveStops],
      };
    }
    const res = await apiClient.request<SafetyOverview>("/safety/overview", {
      method: "GET",
    });
    if (res.error) throw new Error(res.error.message || "Failed to fetch safety overview");
    return res.data!;
  },

  getStatus: async (): Promise<EmergencyStatusSummary> => {
    if (USE_MOCK) {
      const isStopped = mockActiveStops.some((s) => s.is_active);
      return {
        is_stopped: isStopped,
        active_stops: mockActiveStops.filter((s) => s.is_active),
        global_kill_switch_active: mockActiveStops.some(
          (s) => s.is_active && s.scope === "ADMIN_GLOBAL"
        ),
        user_stop_active: mockActiveStops.some(
          (s) => s.is_active && s.scope === "USER_LEVEL"
        ),
      };
    }
    const res = await apiClient.request<EmergencyStatusSummary>("/safety/emergency-stop/status", {
      method: "GET",
    });
    if (res.error) throw new Error(res.error.message || "Failed to fetch emergency status");
    return res.data!;
  },

  triggerEmergencyStop: async (payload: {
    reason: string;
    scope?: "USER_LEVEL" | "ADMIN_GLOBAL";
    auto_cancel_pending?: boolean;
  }): Promise<EmergencyStopEvent> => {
    if (USE_MOCK) {
      const stop: EmergencyStopEvent = {
        id: `stop-${Date.now()}`,
        scope: payload.scope || "USER_LEVEL",
        user_id: "usr-001",
        triggered_by: "USER",
        reason: payload.reason,
        is_active: true,
        affected_plans_count: 2,
        affected_rules_count: 3,
        started_at: new Date().toISOString(),
      };
      mockActiveStops.push(stop);
      mockAuditEvents.unshift({
        id: `evt-${Date.now()}`,
        user_id: "usr-001",
        workflow_version: 1,
        event_type: "EMERGENCY_STOP_TRIGGERED",
        execution_timestamp: new Date().toISOString(),
        policy_decision: "EMERGENCY_HALT",
        result_status: "STOP_ACTIVATED",
        sanitized_payload: { reason: payload.reason, scope: payload.scope },
      });
      return stop;
    }
    const res = await apiClient.request<EmergencyStopEvent>("/safety/emergency-stop", {
      method: "POST",
      body: payload,
    });
    if (res.error) throw new Error(res.error.message || "Failed to trigger emergency stop");
    return res.data!;
  },

  liftEmergencyStop: async (payload: {
    emergency_stop_id: string;
    notes?: string;
  }): Promise<EmergencyStopEvent> => {
    if (USE_MOCK) {
      const stop = mockActiveStops.find((s) => s.id === payload.emergency_stop_id);
      if (stop) {
        stop.is_active = false;
        stop.lifted_at = new Date().toISOString();
        mockAuditEvents.unshift({
          id: `evt-${Date.now()}`,
          user_id: "usr-001",
          workflow_version: 1,
          event_type: "EMERGENCY_STOP_LIFTED",
          execution_timestamp: new Date().toISOString(),
          result_status: "STOP_LIFTED",
        });
        return { ...stop };
      }
      throw new Error("Emergency stop not found");
    }
    const res = await apiClient.request<EmergencyStopEvent>("/safety/emergency-stop/lift", {
      method: "POST",
      body: payload,
    });
    if (res.error) throw new Error(res.error.message || "Failed to lift emergency stop");
    return res.data!;
  },

  getAuditEvents: async (limit = 50, planId?: string): Promise<WorkflowAuditEvent[]> => {
    if (USE_MOCK) {
      return planId
        ? mockAuditEvents.filter((e) => e.plan_id === planId)
        : [...mockAuditEvents];
    }
    const query: Record<string, any> = { limit };
    if (planId) query.plan_id = planId;
    const res = await apiClient.request<WorkflowAuditEvent[]>("/safety/audit/events", {
      method: "GET",
      query,
    });
    if (res.error) throw new Error(res.error.message || "Failed to fetch audit events");
    return res.data ?? [];
  },

  checkReversibility: async (planId: string): Promise<ReversibilityCheckResult> => {
    if (USE_MOCK) {
      return {
        plan_id: planId,
        is_reversible: true,
        summary: "All operations are eligible for automated rollback.",
        step_details: [
          {
            step_key: "step_1_review_task",
            action_identifier: "task:update_priority",
            is_reversible: true,
            has_receipt: true,
            compensation_status: "PENDING",
          },
        ],
      };
    }
    const res = await apiClient.request<ReversibilityCheckResult>(`/safety/rollback/check/${planId}`, {
      method: "GET",
    });
    if (res.error) throw new Error(res.error.message || "Failed to check reversibility");
    return res.data!;
  },

  executeRollback: async (
    planId: string,
    payload?: { reason?: string; force?: boolean }
  ): Promise<WorkflowRollbackRecord> => {
    if (USE_MOCK) {
      const rec: WorkflowRollbackRecord = {
        id: `rb-${Date.now()}`,
        plan_id: planId,
        user_id: "usr-001",
        triggered_by: "USER_MANUAL",
        status: "COMPLETED",
        total_steps_to_compensate: 1,
        compensated_steps_count: 1,
        started_at: new Date().toISOString(),
        completed_at: new Date().toISOString(),
      };
      mockRollbackRecords.unshift(rec);
      mockAuditEvents.unshift({
        id: `evt-${Date.now()}`,
        user_id: "usr-001",
        plan_id: planId,
        workflow_version: 1,
        event_type: "ROLLBACK_COMPLETED",
        execution_timestamp: new Date().toISOString(),
        result_status: "COMPLETED",
      });
      return rec;
    }
    const res = await apiClient.request<WorkflowRollbackRecord>(`/safety/rollback/${planId}`, {
      method: "POST",
      body: payload || {},
    });
    if (res.error) throw new Error(res.error.message || "Failed to execute rollback");
    return res.data!;
  },

  getRollbackRecords: async (limit = 50, planId?: string): Promise<WorkflowRollbackRecord[]> => {
    if (USE_MOCK) {
      return planId
        ? mockRollbackRecords.filter((r) => r.plan_id === planId)
        : [...mockRollbackRecords];
    }
    const query: Record<string, any> = { limit };
    if (planId) query.plan_id = planId;
    const res = await apiClient.request<WorkflowRollbackRecord[]>("/safety/rollback/records", {
      method: "GET",
      query,
    });
    if (res.error) throw new Error(res.error.message || "Failed to fetch rollback records");
    return res.data ?? [];
  },
};

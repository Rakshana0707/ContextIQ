import { apiClient } from "../client";

export interface BusyBlockRead {
  title: string;
  start_time: string;
  end_time: string;
  source: string;
  is_recovery_buffer: boolean;
}

export interface AvailabilityWindowRead {
  start_time: string;
  end_time: string;
  duration_minutes: number;
  focus_quality_score: number;
  is_peak_focus: boolean;
}

export interface UserAvailabilityResponse {
  user_id: string;
  horizon_start: string;
  horizon_end: string;
  total_available_minutes: number;
  busy_blocks: BusyBlockRead[];
  available_windows: AvailabilityWindowRead[];
}

export interface ScheduleExplanationDTO {
  primary_rationale: string;
  behavioral_factors: Record<string, any>;
  calendar_constraints_considered: string[];
  rejected_alternatives: string[];
  confidence_score: number;
}

export interface ScheduledSlotDTO {
  task_id: string;
  task_title: string;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  calendar_id?: string;
  focus_quality_score: number;
  is_peak_focus: boolean;
  explanation: ScheduleExplanationDTO;
}

export interface UnscheduledTaskDTO {
  task_id: string;
  task_title: string;
  reason: string;
  required_duration_minutes: number;
}

export interface ScheduleProposalResponse {
  proposal_id?: string | null;
  user_id: string;
  status: "DRAFT" | "PENDING_APPROVAL" | "APPROVED" | "REJECTED" | "COMMITTED" | "SUPERSEDED";
  scheduled_slots: ScheduledSlotDTO[];
  unscheduled_tasks: UnscheduledTaskDTO[];
  total_scheduled_minutes: number;
  created_at: string;
}

export interface ScheduleGenerateRequest {
  start_date?: string;
  horizon_days?: number;
  task_ids?: string[];
  working_hour_start?: number;
  working_hour_end?: number;
  include_weekends?: boolean;
  enforce_lunch_break?: boolean;
  lunch_start_hour?: number;
  lunch_duration_minutes?: number;
  recovery_buffer_minutes?: number;
  min_slot_minutes?: number;
}

export interface ScheduleModifySlotRequest {
  task_id: string;
  new_start_time: string;
  new_end_time: string;
}

export interface ScheduleApprovalRequest {
  target_provider?: "google_calendar" | "microsoft_outlook";
  target_calendar_id?: string;
}

export interface ScheduleApprovalResponse {
  proposal_id: string;
  status: string;
  total_slots: number;
  committed_events: number;
  created_calendar_event_ids: string[];
  provider: string;
  committed_at: string;
}

export const schedulingApi = {
  getAvailability: async (params?: {
    start_date?: string;
    horizon_days?: number;
    working_hour_start?: number;
    working_hour_end?: number;
    include_weekends?: boolean;
    enforce_lunch_break?: boolean;
    lunch_start_hour?: number;
    lunch_duration_minutes?: number;
    recovery_buffer_minutes?: number;
  }): Promise<UserAvailabilityResponse> => {
    const resp = await apiClient.get<UserAvailabilityResponse>("/scheduling/availability", { params });
    return resp.data;
  },

  generate: async (payload: ScheduleGenerateRequest): Promise<ScheduleProposalResponse> => {
    const resp = await apiClient.post<ScheduleProposalResponse>("/scheduling/generate", payload);
    return resp.data;
  },

  preview: async (proposalId: string): Promise<ScheduleProposalResponse> => {
    const resp = await apiClient.post<ScheduleProposalResponse>("/scheduling/preview", null, {
      params: { proposal_id: proposalId },
    });
    return resp.data;
  },

  modifySlot: async (proposalId: string, payload: ScheduleModifySlotRequest): Promise<ScheduleProposalResponse> => {
    const resp = await apiClient.patch<ScheduleProposalResponse>(`/scheduling/modify?proposal_id=${proposalId}`, payload);
    return resp.data;
  },

  approve: async (proposalId: string, payload: ScheduleApprovalRequest = {}): Promise<ScheduleApprovalResponse> => {
    const resp = await apiClient.post<ScheduleApprovalResponse>(`/scheduling/approve?proposal_id=${proposalId}`, payload);
    return resp.data;
  },

  reject: async (proposalId: string, reason?: string): Promise<{ proposal_id: string; status: string; reason?: string }> => {
    const resp = await apiClient.post<{ proposal_id: string; status: string; reason?: string }>(
      `/scheduling/reject?proposal_id=${proposalId}`,
      null,
      { params: reason ? { reason } : undefined }
    );
    return resp.data;
  },
};

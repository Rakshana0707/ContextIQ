import { apiClient } from "../client";

export interface DeviceRead {
  id: string;
  user_id: string;
  device_id: string;
  device_type: "DESKTOP" | "MOBILE" | "TABLET" | "WEB" | string;
  platform: "WINDOWS" | "ANDROID" | "IOS" | "MACOS" | "LINUX" | "WEB" | string;
  device_name: string;
  application_version: string;
  registration_timestamp: string;
  last_seen_timestamp: string;
  connection_status: "ONLINE" | "OFFLINE" | "REVOKED";
  synchronization_status: "SYNCED" | "PENDING" | "SYNCING" | "ERROR";
  device_metadata: Record<string, any>;
  is_active: boolean;
  revoked_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface DeviceRegisterRequest {
  device_id: string;
  device_type?: string;
  platform?: string;
  device_name?: string;
  application_version?: string;
  device_metadata?: Record<string, any>;
}

export interface UnifiedTimelineEventDTO {
  event_id: string;
  source: string;
  device_id?: string | null;
  device_name?: string | null;
  device_type: "DESKTOP" | "MOBILE" | "TABLET" | "WEB" | "CALENDAR" | string;
  platform: string;
  event_type: string;
  occurred_at: string;
  ingested_at: string;
  timezone_offset_minutes: number;
  clock_skew_seconds: number;
  original_event_id?: string | null;
  application_identifier?: string | null;
  task_id?: string | null;
  duration_seconds?: number | null;
  payload: Record<string, any>;
}

export interface CrossDeviceSessionRead {
  session_id: string;
  started_at: string;
  ended_at?: string | null;
  duration_seconds: number;
  primary_device_type: string;
  device_transitions_count: number;
  device_time_breakdown: Record<string, number>;
  cross_device_interruption_seconds: number;
  continuity_score: number;
  timeline_segments: any[];
}

export const devicesApi = {
  list: async (): Promise<DeviceRead[]> => {
    const resp = await apiClient.get<DeviceRead[]>("/devices");
    return resp.data;
  },

  register: async (payload: DeviceRegisterRequest): Promise<DeviceRead> => {
    const resp = await apiClient.post<DeviceRead>("/devices/register", payload);
    return resp.data;
  },

  revoke: async (deviceId: string): Promise<{ device_id: string; status: string; message: string }> => {
    const resp = await apiClient.delete<{ device_id: string; status: string; message: string }>(`/devices/${deviceId}`);
    return resp.data;
  },
};

export const activityApi = {
  getTimeline: async (params?: {
    device_id?: string;
    device_type?: string;
    start_time?: string;
    end_time?: string;
    task_id?: string;
    application?: string;
    event_type?: string;
    limit?: number;
    offset?: number;
  }): Promise<UnifiedTimelineEventDTO[]> => {
    const resp = await apiClient.get<UnifiedTimelineEventDTO[]>("/activity/timeline", { params });
    return resp.data;
  },

  sync: async (payload: {
    device_id: string;
    client_timestamp: string;
    events: any[];
  }): Promise<any> => {
    const resp = await apiClient.post<any>("/activity/sync", payload);
    return resp.data;
  },

  getCrossDeviceSessions: async (lookbackHours: number = 24): Promise<CrossDeviceSessionRead[]> => {
    const resp = await apiClient.get<CrossDeviceSessionRead[]>("/activity/cross-device-sessions", {
      params: { lookback_hours: lookbackHours },
    });
    return resp.data;
  },
};

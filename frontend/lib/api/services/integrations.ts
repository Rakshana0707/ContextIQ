import { apiClient } from "../client";

export type ConnectionStatus = "CONNECTED" | "EXPIRED" | "REVOKED" | "ERROR";
export type SyncStatus = "INITIALIZING" | "SYNCED" | "IN_PROGRESS" | "FAILED";

export interface IntegrationResponse {
  id: string;
  user_id: string;
  provider: "google_calendar" | "microsoft_outlook" | string;
  provider_account_id?: string | null;
  provider_email?: string | null;
  connection_status: ConnectionStatus;
  granted_scopes: string[];
  last_synced_at?: string | null;
  sync_status: SyncStatus;
  created_at: string;
  updated_at: string;
}

export interface ConnectResponse {
  provider: string;
  authorization_url: string;
  state: string;
  code_verifier?: string | null;
}

export interface IntegrationStatusResponse {
  id: string;
  provider: string;
  connection_status: ConnectionStatus;
  is_active: boolean;
  has_valid_token: boolean;
  expires_in_seconds?: number | null;
  last_synced_at?: string | null;
  sync_status: SyncStatus;
  error_message?: string | null;
}

export interface CalendarDTO {
  calendar_id: string;
  name: string;
  is_primary: boolean;
  access_role: string;
  description?: string | null;
  time_zone?: string | null;
}

export interface CalendarListResponse {
  integration_id: string;
  provider: string;
  calendars: CalendarDTO[];
}

export interface SyncResult {
  success: boolean;
  new_sync_token?: string | null;
  synced_events: any[];
  deleted_event_ids: string[];
  full_resync_required: boolean;
  sync_duration_ms: number;
  error_message?: string | null;
}

export interface GoogleSyncResponse {
  success: boolean;
  integration_id: string;
  sync_status: string;
  events_created: number;
  events_updated: number;
  events_deleted: number;
  new_sync_token?: string | null;
  full_resync_occurred: boolean;
  duration_ms: number;
  error_message?: string | null;
}

export interface GoogleEventRead {
  id: string;
  integration_id: string;
  calendar_id: string;
  external_event_id: string;
  title: string;
  description?: string | null;
  location_name?: string | null;
  start_time: string;
  end_time: string;
  timezone: string;
  is_all_day: boolean;
  status: string;
  transparency: string;
  visibility: string;
  is_private: boolean;
  is_recurring: boolean;
  recurring_event_id?: string | null;
  is_organizer: boolean;
  organizer_email?: string | null;
  attendees_count: number;
  etag?: string | null;
  html_link?: string | null;
  is_contextiq_managed: boolean;
  linked_task_id?: string | null;
  last_synced_at: string;
  created_at: string;
  updated_at: string;
}

export const integrationsApi = {
  listIntegrations: async (): Promise<IntegrationResponse[]> => {
    try {
      const resp = await apiClient.get<IntegrationResponse[]>("/integrations");
      return resp.data;
    } catch {
      // Return safe mock default for preview
      return [
        {
          id: "int-mock-google-1",
          user_id: "00000000-0000-0000-0000-000000000001",
          provider: "google_calendar",
          provider_account_id: "109823471029384",
          provider_email: "alex.chen.dev@gmail.com",
          connection_status: "CONNECTED",
          granted_scopes: [
            "https://www.googleapis.com/auth/calendar.events",
            "https://www.googleapis.com/auth/userinfo.email"
          ],
          last_synced_at: new Date(Date.now() - 1000 * 60 * 12).toISOString(),
          sync_status: "SYNCED",
          created_at: new Date(Date.now() - 1000 * 60 * 60 * 24 * 7).toISOString(),
          updated_at: new Date(Date.now() - 1000 * 60 * 12).toISOString(),
        }
      ];
    }
  },

  listCalendars: async (): Promise<CalendarListResponse[]> => {
    try {
      const resp = await apiClient.get<CalendarListResponse[]>("/integrations/calendars");
      return resp.data;
    } catch {
      return [];
    }
  },

  connectProvider: async (
    provider: string,
    payload?: { redirect_uri?: string; request_write_access?: boolean }
  ): Promise<ConnectResponse> => {
    const resp = await apiClient.post<ConnectResponse>(`/integrations/${provider}/connect`, payload || {});
    return resp.data;
  },

  getIntegrationStatus: async (integrationId: string): Promise<IntegrationStatusResponse> => {
    const resp = await apiClient.get<IntegrationStatusResponse>(`/integrations/${integrationId}/status`);
    return resp.data;
  },

  disconnectIntegration: async (integrationId: string): Promise<void> => {
    await apiClient.post(`/integrations/${integrationId}/disconnect`, {});
  },

  triggerSync: async (integrationId: string): Promise<SyncResult> => {
    const resp = await apiClient.post<SyncResult>(`/integrations/${integrationId}/sync`, {});
    return resp.data;
  },
};

export const googleCalendarApi = {
  sync: async (calendarId: string = "primary", forceFull: boolean = false): Promise<GoogleSyncResponse> => {
    const resp = await apiClient.post<GoogleSyncResponse>("/integrations/google/sync", {
      calendar_id: calendarId,
      force_full: forceFull,
    });
    return resp.data;
  },

  listCalendars: async (): Promise<CalendarDTO[]> => {
    const resp = await apiClient.get<CalendarDTO[]>("/integrations/google/calendars");
    return resp.data;
  },

  listEvents: async (params?: {
    calendar_id?: string;
    start_time?: string;
    end_time?: string;
    transparency?: string;
    limit?: number;
  }): Promise<GoogleEventRead[]> => {
    const resp = await apiClient.get<GoogleEventRead[]>("/integrations/google/events", { params });
    return resp.data;
  },

  createEvent: async (payload: {
    calendar_id?: string;
    title: string;
    start_time: string;
    end_time: string;
    description?: string;
    location_name?: string;
    transparency?: string;
    linked_task_id?: string;
  }): Promise<GoogleEventRead> => {
    const resp = await apiClient.post<GoogleEventRead>("/integrations/google/events", payload);
    return resp.data;
  },

  updateEvent: async (
    eventId: string,
    payload: {
      title?: string;
      start_time?: string;
      end_time?: string;
      description?: string;
      location_name?: string;
      transparency?: string;
      allow_external_modification?: boolean;
    }
  ): Promise<GoogleEventRead> => {
    const resp = await apiClient.patch<GoogleEventRead>(`/integrations/google/events/${eventId}`, payload);
    return resp.data;
  },

  deleteEvent: async (eventId: string): Promise<{ success: boolean; event_id: string }> => {
    const resp = await apiClient.delete<{ success: boolean; event_id: string }>(`/integrations/google/events/${eventId}`);
    return resp.data;
  },
};

export const microsoftCalendarApi = {
  sync: async (calendarId: string = "primary", forceFull: boolean = false): Promise<GoogleSyncResponse> => {
    const resp = await apiClient.post<GoogleSyncResponse>("/integrations/microsoft/sync", {
      calendar_id: calendarId,
      force_full: forceFull,
    });
    return resp.data;
  },

  listCalendars: async (): Promise<CalendarDTO[]> => {
    const resp = await apiClient.get<CalendarDTO[]>("/integrations/microsoft/calendars");
    return resp.data;
  },

  listEvents: async (params?: {
    calendar_id?: string;
    start_time?: string;
    end_time?: string;
    transparency?: string;
    limit?: number;
  }): Promise<GoogleEventRead[]> => {
    const resp = await apiClient.get<GoogleEventRead[]>("/integrations/microsoft/events", { params });
    return resp.data;
  },

  createEvent: async (payload: {
    calendar_id?: string;
    title: string;
    start_time: string;
    end_time: string;
    description?: string;
    location_name?: string;
    transparency?: string;
    linked_task_id?: string;
  }): Promise<GoogleEventRead> => {
    const resp = await apiClient.post<GoogleEventRead>("/integrations/microsoft/events", payload);
    return resp.data;
  },

  updateEvent: async (
    eventId: string,
    payload: {
      title?: string;
      start_time?: string;
      end_time?: string;
      description?: string;
      location_name?: string;
      transparency?: string;
      allow_external_modification?: boolean;
    }
  ): Promise<GoogleEventRead> => {
    const resp = await apiClient.patch<GoogleEventRead>(`/integrations/microsoft/events/${eventId}`, payload);
    return resp.data;
  },

  deleteEvent: async (eventId: string): Promise<{ success: boolean; event_id: string }> => {
    const resp = await apiClient.delete<{ success: boolean; event_id: string }>(`/integrations/microsoft/events/${eventId}`);
    return resp.data;
  },
};



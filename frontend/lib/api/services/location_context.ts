import { apiClient } from "../client";

export interface LocationContextRead {
  id: string;
  user_id: string;
  name: string;
  location_type: string;
  latitude?: number | null;
  longitude?: number | null;
  radius_meters?: number | null;
  is_active: boolean;
  reminders_enabled: boolean;
  arrival_reminder_enabled: boolean;
  departure_reminder_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface LocationContextCreate {
  name: string;
  location_type: string;
  latitude?: number | null;
  longitude?: number | null;
  radius_meters?: number | null;
  is_active?: boolean;
  reminders_enabled?: boolean;
  arrival_reminder_enabled?: boolean;
  departure_reminder_enabled?: boolean;
}

export interface LocationCheckInCreate {
  location_id?: string | null;
  location_name?: string | null;
  check_in_type?: "MANUAL" | "GEOFENCE_ENTER" | "GEOFENCE_EXIT";
  device_id?: string | null;
  occurred_at?: string | null;
  notes?: string | null;
  payload?: Record<string, any>;
}

export interface LocationCheckInRead {
  id: string;
  user_id: string;
  location_id?: string | null;
  location_name: string;
  location_type: string;
  check_in_type: string;
  device_id?: string | null;
  occurred_at: string;
  notes?: string | null;
  created_at: string;
}

export interface LocationReminderDTO {
  task_id?: string | null;
  title: string;
  due_at?: string | null;
  priority: string;
  trigger_type: string;
  association_source: string;
  confidence_score: number;
  message: string;
  recommendation_arm: string;
}

export interface LocationRecommendationsResponse {
  location_id?: string | null;
  location_name: string;
  trigger_type: string;
  reminders: LocationReminderDTO[];
  total_reminders: number;
  quiet_hours_active: boolean;
  focus_session_active: boolean;
  suppressed_count: number;
}

export interface LocationConsentDTO {
  location_tracking_enabled: boolean;
  allow_geofencing: boolean;
  allow_manual_checkins: boolean;
  permitted_categories: string[];
}

export const locationContextApi = {
  getLocations: async (activeOnly = true): Promise<LocationContextRead[]> => {
    const resp = await apiClient.get<LocationContextRead[]>("/context/locations", {
      params: { active_only: activeOnly },
    });
    return resp.data;
  },

  createLocation: async (payload: LocationContextCreate): Promise<LocationContextRead> => {
    const resp = await apiClient.post<LocationContextRead>("/context/locations", payload);
    return resp.data;
  },

  deleteLocation: async (locationId: string): Promise<void> => {
    await apiClient.delete(`/context/locations/${locationId}`);
  },

  recordCheckIn: async (payload: LocationCheckInCreate): Promise<LocationCheckInRead> => {
    const resp = await apiClient.post<LocationCheckInRead>("/context/check-ins", payload);
    return resp.data;
  },

  getLocationRecommendations: async (params?: {
    location_id?: string;
    location_name?: string;
    trigger_type?: "ARRIVAL" | "DEPARTURE" | "MANUAL";
  }): Promise<LocationRecommendationsResponse> => {
    const resp = await apiClient.get<LocationRecommendationsResponse>("/context/location-recommendations", {
      params,
    });
    return resp.data;
  },
};

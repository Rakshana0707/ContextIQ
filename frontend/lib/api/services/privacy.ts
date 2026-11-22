import { apiClient } from "../client";

export type ConsentStatus = "GRANTED" | "REVOKED" | "PAUSED" | "EXPIRED";

export type TelemetryCategory =
  | "APP_TRANSITIONS"
  | "INACTIVITY_DETECTION"
  | "SESSION_RECONSTRUCTION"
  | "BEHAVIORAL_ANALYTICS"
  | "LOCAL_STORAGE"
  | "SERVER_SYNC";

export interface TelemetryConsent {
  id: string;
  user_id: string;
  consent_version: string;
  enabled_categories: string[];
  granted_timestamp: string;
  updated_timestamp: string;
  revoked_timestamp?: string | null;
  device_id?: string | null;
  consent_status: ConsentStatus;
  created_at: string;
}

export interface PrivacySettings {
  user_id: string;
  is_paused: boolean;
  paused_until?: string | null;
  raw_event_retention_days: number;
  aggregated_metric_retention_days: number;
  allow_anonymized_research: boolean;
  updated_at: string;
}

export interface AppExclusion {
  id: string;
  user_id: string;
  application_identifier: string;
  description?: string | null;
  created_at: string;
}

export interface TelemetryMetadataSummary {
  total_raw_events: number;
  total_context_sessions: number;
  oldest_event_at?: string | null;
  newest_event_at?: string | null;
  active_monitoring_status: "ACTIVE" | "PAUSED" | "DISABLED";
  active_categories_count: number;
  excluded_apps_count: number;
  retention_days_raw: number;
}

export interface ConsentGrantPayload {
  consent_version?: string;
  enabled_categories: TelemetryCategory[];
  device_id?: string;
}

export interface ConsentRevokePayload {
  device_id?: string;
  reason?: string;
}

export interface PrivacySettingsUpdatePayload {
  is_paused?: boolean;
  pause_duration_minutes?: number;
  raw_event_retention_days?: number;
  aggregated_metric_retention_days?: number;
  allow_anonymized_research?: boolean;
}

export interface AppExclusionPayload {
  application_identifier: string;
  description?: string;
}

export interface DataPurgePayload {
  purge_raw_telemetry: boolean;
  purge_context_sessions: boolean;
  confirmation_phrase: string;
}

export interface DataPurgeResponse {
  status: string;
  message: string;
  purged_raw_telemetry_count: number;
  purged_context_sessions_count: number;
  purged_at: string;
}

export const privacyApi = {
  async getConsent(deviceId?: string): Promise<TelemetryConsent | null> {
    return apiClient.request<TelemetryConsent | null>("/privacy/consent", {
      service: "core",
      query: deviceId ? { device_id: deviceId } : undefined,
    });
  },

  async grantConsent(payload: ConsentGrantPayload): Promise<TelemetryConsent> {
    return apiClient.request<TelemetryConsent>("/privacy/consent", {
      service: "core",
      method: "POST",
      body: payload,
    });
  },

  async revokeConsent(payload: ConsentRevokePayload = {}): Promise<TelemetryConsent> {
    return apiClient.request<TelemetryConsent>("/privacy/consent/revoke", {
      service: "core",
      method: "POST",
      body: payload,
    });
  },

  async getConsentHistory(): Promise<TelemetryConsent[]> {
    return apiClient.request<TelemetryConsent[]>("/privacy/consent/history", {
      service: "core",
    });
  },

  async getSettings(): Promise<PrivacySettings> {
    return apiClient.request<PrivacySettings>("/privacy/settings", {
      service: "core",
    });
  },

  async updateSettings(payload: PrivacySettingsUpdatePayload): Promise<PrivacySettings> {
    return apiClient.request<PrivacySettings>("/privacy/settings", {
      service: "core",
      method: "PATCH",
      body: payload,
    });
  },

  async getExclusions(): Promise<AppExclusion[]> {
    return apiClient.request<AppExclusion[]>("/privacy/exclusions", {
      service: "core",
    });
  },

  async addExclusion(payload: AppExclusionPayload): Promise<AppExclusion> {
    return apiClient.request<AppExclusion>("/privacy/exclusions", {
      service: "core",
      method: "POST",
      body: payload,
    });
  },

  async removeExclusion(exclusionId: string): Promise<void> {
    return apiClient.request<void>(`/privacy/exclusions/${exclusionId}`, {
      service: "core",
      method: "DELETE",
    });
  },

  async purgeData(payload: DataPurgePayload): Promise<DataPurgeResponse> {
    return apiClient.request<DataPurgeResponse>("/privacy/data/purge", {
      service: "core",
      method: "POST",
      body: payload,
    });
  },

  async getMetadata(): Promise<TelemetryMetadataSummary> {
    return apiClient.request<TelemetryMetadataSummary>("/privacy/metadata", {
      service: "core",
    });
  },
};

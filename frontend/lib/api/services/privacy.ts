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
    const res = await apiClient.request<TelemetryConsent | null>("/privacy/consent", {
      baseUrl: "core",
      query: deviceId ? { device_id: deviceId } : undefined,
    });
    return res.data;
  },

  async grantConsent(payload: ConsentGrantPayload): Promise<TelemetryConsent> {
    const res = await apiClient.request<TelemetryConsent>("/privacy/consent", {
      baseUrl: "core",
      method: "POST",
      body: payload,
    });
    if (!res.data) throw new Error(res.error?.message ?? "Failed to grant consent");
    return res.data;
  },

  async revokeConsent(payload: ConsentRevokePayload = {}): Promise<TelemetryConsent> {
    const res = await apiClient.request<TelemetryConsent>("/privacy/consent/revoke", {
      baseUrl: "core",
      method: "POST",
      body: payload,
    });
    if (!res.data) throw new Error(res.error?.message ?? "Failed to revoke consent");
    return res.data;
  },

  async getConsentHistory(): Promise<TelemetryConsent[]> {
    const res = await apiClient.request<TelemetryConsent[]>("/privacy/consent/history", {
      baseUrl: "core",
    });
    return res.data ?? [];
  },

  async getSettings(): Promise<PrivacySettings> {
    const res = await apiClient.request<PrivacySettings>("/privacy/settings", {
      baseUrl: "core",
    });
    if (!res.data) throw new Error(res.error?.message ?? "Failed to fetch settings");
    return res.data;
  },

  async updateSettings(payload: PrivacySettingsUpdatePayload): Promise<PrivacySettings> {
    const res = await apiClient.request<PrivacySettings>("/privacy/settings", {
      baseUrl: "core",
      method: "PATCH",
      body: payload,
    });
    if (!res.data) throw new Error(res.error?.message ?? "Failed to update settings");
    return res.data;
  },

  async getExclusions(): Promise<AppExclusion[]> {
    const res = await apiClient.request<AppExclusion[]>("/privacy/exclusions", {
      baseUrl: "core",
    });
    return res.data ?? [];
  },

  async addExclusion(payload: AppExclusionPayload): Promise<AppExclusion> {
    const res = await apiClient.request<AppExclusion>("/privacy/exclusions", {
      baseUrl: "core",
      method: "POST",
      body: payload,
    });
    if (!res.data) throw new Error(res.error?.message ?? "Failed to add exclusion");
    return res.data;
  },

  async removeExclusion(exclusionId: string): Promise<void> {
    const res = await apiClient.request<void>(`/privacy/exclusions/${exclusionId}`, {
      baseUrl: "core",
      method: "DELETE",
    });
    if (res.error) throw new Error(res.error.message);
  },

  async purgeData(payload: DataPurgePayload): Promise<DataPurgeResponse> {
    const res = await apiClient.request<DataPurgeResponse>("/privacy/data/purge", {
      baseUrl: "core",
      method: "POST",
      body: payload,
    });
    if (!res.data) throw new Error(res.error?.message ?? "Failed to purge data");
    return res.data;
  },

  async getMetadata(): Promise<TelemetryMetadataSummary> {
    const res = await apiClient.request<TelemetryMetadataSummary>("/privacy/metadata", {
      baseUrl: "core",
    });
    if (!res.data) throw new Error(res.error?.message ?? "Failed to fetch metadata");
    return res.data;
  },
};

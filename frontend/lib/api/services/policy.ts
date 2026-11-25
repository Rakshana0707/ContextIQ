import { apiClient, USE_MOCK } from "@/lib/api/client";
import type {
  PolicyConsent,
  PolicyConsentGrantPayload,
  PolicyConsentRevokePayload,
  PolicyEvaluationPayload,
  PolicyEvaluationResult,
  PolicyAuditTrail,
  UserPolicyOverview,
  PermissionScope,
} from "@/types/policy";

const mockPermissions: PolicyConsent[] = [
  {
    id: "pol-001",
    user_id: "usr-001",
    scope: "tasks:read",
    consent_status: "GRANTED",
    consent_version: "1.0.0",
    granted_timestamp: new Date().toISOString(),
    source: "USER_EXPLICIT",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "pol-002",
    user_id: "usr-001",
    scope: "tasks:write",
    consent_status: "GRANTED",
    consent_version: "1.0.0",
    granted_timestamp: new Date().toISOString(),
    source: "USER_EXPLICIT",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "pol-003",
    user_id: "usr-001",
    scope: "calendar:read",
    consent_status: "GRANTED",
    consent_version: "1.0.0",
    granted_timestamp: new Date().toISOString(),
    source: "OAUTH_DELEGATION",
    integration_id: "google_calendar",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "pol-004",
    user_id: "usr-001",
    scope: "calendar:events:create",
    consent_status: "GRANTED",
    consent_version: "1.0.0",
    granted_timestamp: new Date().toISOString(),
    source: "OAUTH_DELEGATION",
    integration_id: "google_calendar",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "pol-005",
    user_id: "usr-001",
    scope: "calendar:events:modify",
    consent_status: "GRANTED",
    consent_version: "1.0.0",
    granted_timestamp: new Date().toISOString(),
    source: "USER_EXPLICIT",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "pol-006",
    user_id: "usr-001",
    scope: "notifications:send",
    consent_status: "GRANTED",
    consent_version: "1.0.0",
    granted_timestamp: new Date().toISOString(),
    source: "USER_EXPLICIT",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "pol-007",
    user_id: "usr-001",
    scope: "telemetry:desktop:collect",
    consent_status: "GRANTED",
    consent_version: "1.0.0",
    granted_timestamp: new Date().toISOString(),
    source: "USER_EXPLICIT",
    device_id: "desktop-win-01",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "pol-008",
    user_id: "usr-001",
    scope: "location:read",
    consent_status: "REVOKED",
    consent_version: "1.0.0",
    granted_timestamp: new Date().toISOString(),
    revoked_timestamp: new Date().toISOString(),
    revocation_reason: "User revoked location tracking",
    source: "USER_EXPLICIT",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "pol-009",
    user_id: "usr-001",
    scope: "automation:schedule:run",
    consent_status: "GRANTED",
    consent_version: "1.0.0",
    granted_timestamp: new Date().toISOString(),
    source: "USER_EXPLICIT",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "pol-010",
    user_id: "usr-001",
    scope: "workflows:execute",
    consent_status: "GRANTED",
    consent_version: "1.0.0",
    granted_timestamp: new Date().toISOString(),
    source: "USER_EXPLICIT",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

const mockAuditLogs: PolicyAuditTrail[] = [
  {
    id: "audit-001",
    user_id: "usr-001",
    action_identifier: "calendar:reschedule_event",
    scope_checked: "calendar:events:modify",
    decision: "ALLOWED",
    risk_tier: "CONSEQUENTIAL_EXTERNAL_ACTION",
    reason: "Explicit user approval and granted scope verified",
    evaluated_at: new Date().toISOString(),
  },
  {
    id: "audit-002",
    user_id: "usr-001",
    action_identifier: "reminder:stage_context_warming",
    scope_checked: "notifications:send",
    decision: "BLOCKED_BY_QUIET_HOURS",
    risk_tier: "EXTERNAL_MODIFICATION",
    reason: "Notification suppressed: quiet hours currently active for user.",
    evaluated_at: new Date(Date.now() - 3600000).toISOString(),
  },
  {
    id: "audit-003",
    user_id: "usr-001",
    action_identifier: "task:update_priority",
    scope_checked: "tasks:write",
    decision: "ALLOWED",
    risk_tier: "REVERSIBLE_INTERNAL_MODIFICATION",
    reason: "Reversible internal modification authorized under active scope.",
    evaluated_at: new Date(Date.now() - 7200000).toISOString(),
  },
];

export const policyApi = {
  listPermissions: async (): Promise<PolicyConsent[]> => {
    if (USE_MOCK) {
      return [...mockPermissions];
    }
    const res = await apiClient.request<PolicyConsent[]>("/policy/permissions", {
      method: "GET",
    });
    if (res.error) throw new Error(res.error.message || "Failed to fetch permissions");
    return res.data ?? [];
  },

  getOverview: async (): Promise<UserPolicyOverview> => {
    if (USE_MOCK) {
      const active = mockPermissions
        .filter((p) => p.consent_status === "GRANTED")
        .map((p) => p.scope);
      return {
        user_id: "usr-001",
        permissions: [...mockPermissions],
        active_scopes: active,
        risk_tier_rules: {
          INFORMATIONAL: { requires_approval: false, actions: ["tasks:read", "calendar:read", "location:read"] },
          RECOMMENDATION_ONLY: { requires_approval: false, actions: ["recommendations:generate"] },
          REVERSIBLE_INTERNAL_MODIFICATION: { requires_approval: false, actions: ["task:update_priority", "task:defer_task", "focus:create_session_block"] },
          EXTERNAL_MODIFICATION: { requires_approval: true, actions: ["calendar:insert_focus_block", "reminder:stage_context_warming"] },
          CONSEQUENTIAL_EXTERNAL_ACTION: { requires_approval: true, actions: ["calendar:reschedule_event", "task:decompose_into_subtasks"] },
        },
        quiet_hours_active: false,
      };
    }
    const res = await apiClient.request<UserPolicyOverview>("/policy/overview", {
      method: "GET",
    });
    if (res.error) throw new Error(res.error.message || "Failed to fetch policy overview");
    return res.data!;
  },

  grantPermission: async (payload: PolicyConsentGrantPayload): Promise<PolicyConsent> => {
    if (USE_MOCK) {
      const existing = mockPermissions.find((p) => p.scope === payload.scope);
      if (existing) {
        existing.consent_status = "GRANTED";
        existing.revoked_timestamp = null;
        existing.revocation_reason = null;
        existing.updated_at = new Date().toISOString();
        return { ...existing };
      }
      const newPerm: PolicyConsent = {
        id: `pol-${Date.now()}`,
        user_id: "usr-001",
        scope: payload.scope,
        consent_status: "GRANTED",
        consent_version: payload.consent_version || "1.0.0",
        granted_timestamp: new Date().toISOString(),
        source: payload.source || "USER_EXPLICIT",
        device_id: payload.device_id,
        integration_id: payload.integration_id,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      mockPermissions.push(newPerm);
      return { ...newPerm };
    }
    const res = await apiClient.request<PolicyConsent>("/policy/permissions/grant", {
      method: "POST",
      body: payload,
    });
    if (res.error) throw new Error(res.error.message || "Failed to grant permission");
    return res.data!;
  },

  revokePermission: async (payload: PolicyConsentRevokePayload): Promise<PolicyConsent> => {
    if (USE_MOCK) {
      const existing = mockPermissions.find((p) => p.scope === payload.scope);
      if (existing) {
        existing.consent_status = "REVOKED";
        existing.revoked_timestamp = new Date().toISOString();
        existing.revocation_reason = payload.reason || "User revoked consent";
        existing.updated_at = new Date().toISOString();
        return { ...existing };
      }
      const revPerm: PolicyConsent = {
        id: `pol-${Date.now()}`,
        user_id: "usr-001",
        scope: payload.scope,
        consent_status: "REVOKED",
        consent_version: "1.0.0",
        granted_timestamp: new Date().toISOString(),
        revoked_timestamp: new Date().toISOString(),
        revocation_reason: payload.reason || "User revoked consent",
        source: "USER_EXPLICIT",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      mockPermissions.push(revPerm);
      return { ...revPerm };
    }
    const res = await apiClient.request<PolicyConsent>("/policy/permissions/revoke", {
      method: "POST",
      body: payload,
    });
    if (res.error) throw new Error(res.error.message || "Failed to revoke permission");
    return res.data!;
  },

  evaluatePolicy: async (payload: PolicyEvaluationPayload): Promise<PolicyEvaluationResult> => {
    if (USE_MOCK) {
      return {
        allowed: true,
        risk_tier: "REVERSIBLE_INTERNAL_MODIFICATION",
        requires_approval: false,
      };
    }
    const res = await apiClient.request<PolicyEvaluationResult>("/policy/evaluate", {
      method: "POST",
      body: payload,
    });
    if (res.error) throw new Error(res.error.message || "Failed to evaluate policy");
    return res.data!;
  },

  getAuditHistory: async (limit = 50): Promise<PolicyAuditTrail[]> => {
    if (USE_MOCK) {
      return [...mockAuditLogs];
    }
    const res = await apiClient.request<PolicyAuditTrail[]>("/policy/history", {
      method: "GET",
      query: { limit },
    });
    if (res.error) throw new Error(res.error.message || "Failed to fetch policy audit history");
    return res.data ?? [];
  },
};

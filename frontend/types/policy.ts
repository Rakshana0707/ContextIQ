export type PermissionScope =
  | "tasks:read"
  | "tasks:write"
  | "calendar:read"
  | "calendar:events:create"
  | "calendar:events:modify"
  | "notifications:send"
  | "telemetry:desktop:collect"
  | "location:read"
  | "automation:schedule:run"
  | "workflows:execute";

export type ActionRiskTier =
  | "INFORMATIONAL"
  | "RECOMMENDATION_ONLY"
  | "REVERSIBLE_INTERNAL_MODIFICATION"
  | "EXTERNAL_MODIFICATION"
  | "CONSEQUENTIAL_EXTERNAL_ACTION";

export type ConsentStatus = "GRANTED" | "REVOKED" | "SUSPENDED" | "EXPIRED";

export type ConsentSource =
  | "USER_EXPLICIT"
  | "SYSTEM_DEFAULT"
  | "OAUTH_DELEGATION"
  | "ADMIN_POLICY";

export interface PolicyConsent {
  id: string;
  user_id: string;
  scope: PermissionScope | string;
  consent_status: ConsentStatus;
  consent_version: string;
  granted_timestamp: string;
  revoked_timestamp?: string | null;
  source: ConsentSource | string;
  device_id?: string | null;
  integration_id?: string | null;
  revocation_reason?: string | null;
  policy_metadata?: Record<string, any> | null;
  created_at: string;
  updated_at: string;
}

export interface PolicyConsentGrantPayload {
  scope: PermissionScope;
  device_id?: string;
  integration_id?: string;
  consent_version?: string;
  source?: ConsentSource;
  policy_metadata?: Record<string, any>;
}

export interface PolicyConsentRevokePayload {
  scope: PermissionScope;
  reason?: string;
}

export interface PolicyEvaluationPayload {
  action_identifier: string;
  parameters?: Record<string, any>;
  workflow_plan_id?: string;
  step_key?: string;
}

export interface PolicyEvaluationResult {
  allowed: boolean;
  risk_tier: ActionRiskTier;
  requires_approval: boolean;
  denial_reason?: string | null;
  scope_required?: PermissionScope | null;
  details?: Record<string, any> | null;
}

export interface PolicyAuditTrail {
  id: string;
  user_id: string;
  action_identifier: string;
  scope_checked?: string | null;
  decision: "ALLOWED" | "DENIED" | "BLOCKED_BY_POLICY" | "BLOCKED_BY_QUIET_HOURS" | "GRANTED" | "REVOKED";
  risk_tier: string;
  reason?: string | null;
  context_snapshot?: Record<string, any> | null;
  evaluated_at: string;
}

export interface UserPolicyOverview {
  user_id: string;
  permissions: PolicyConsent[];
  active_scopes: string[];
  risk_tier_rules: Record<string, { requires_approval: boolean; actions: string[] }>;
  quiet_hours_active: boolean;
}

"""
Deterministic Policy and Consent Enforcement Engine (ContextIQ Phase 7.6).
Governs what ContextIQ is permitted to observe, recommend, prepare, and execute,
completely independent of LLM decisions.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.notification_models import UserNotificationPreference
from app.models.policy_models import PolicyAuditTrail, UserPolicyConsent
from app.models.task import Task
from app.models.telemetry_consent import UserPrivacySettings
from app.models.workflow_models import (
    WorkflowExecutionPlan,
    WorkflowStepExecution,
)
from app.schemas.workflow_schemas import (
    WorkflowLifecycleState,
)
from app.schemas.policy_schemas import (
    ActionRiskTier,
    ConsentSource,
    ConsentStatusEnum,
    PermissionScope,
    PolicyEvaluationResult,
)

logger = logging.getLogger(__name__)


# Action specifications: (Risk Tier, Required Scope, Requires User Approval)
ACTION_POLICY_SPECS: Dict[str, Tuple[ActionRiskTier, PermissionScope, bool]] = {
    "tasks:read": (ActionRiskTier.INFORMATIONAL, PermissionScope.TASKS_READ, False),
    "calendar:read": (ActionRiskTier.INFORMATIONAL, PermissionScope.CALENDAR_READ, False),
    "location:read": (ActionRiskTier.INFORMATIONAL, PermissionScope.LOCATION_READ, False),
    "telemetry:collect": (ActionRiskTier.INFORMATIONAL, PermissionScope.TELEMETRY_DESKTOP_COLLECT, False),
    "recommendations:generate": (ActionRiskTier.RECOMMENDATION_ONLY, PermissionScope.WORKFLOWS_EXECUTE, False),
    "task:update_priority": (ActionRiskTier.REVERSIBLE_INTERNAL_MODIFICATION, PermissionScope.TASKS_WRITE, False),
    "task:defer_task": (ActionRiskTier.REVERSIBLE_INTERNAL_MODIFICATION, PermissionScope.TASKS_WRITE, False),
    "task:create": (ActionRiskTier.REVERSIBLE_INTERNAL_MODIFICATION, PermissionScope.TASKS_WRITE, False),
    "focus:create_session_block": (ActionRiskTier.REVERSIBLE_INTERNAL_MODIFICATION, PermissionScope.AUTOMATION_SCHEDULE_RUN, False),
    "focus:clamp_complementary_tools": (ActionRiskTier.REVERSIBLE_INTERNAL_MODIFICATION, PermissionScope.AUTOMATION_SCHEDULE_RUN, False),
    "reminder:snooze_non_urgent": (ActionRiskTier.REVERSIBLE_INTERNAL_MODIFICATION, PermissionScope.NOTIFICATIONS_SEND, False),
    "intervention:trigger_micro_break": (ActionRiskTier.REVERSIBLE_INTERNAL_MODIFICATION, PermissionScope.NOTIFICATIONS_SEND, False),
    "sync:cross_device_handoff": (ActionRiskTier.REVERSIBLE_INTERNAL_MODIFICATION, PermissionScope.WORKFLOWS_EXECUTE, False),
    "calendar:insert_focus_block": (ActionRiskTier.EXTERNAL_MODIFICATION, PermissionScope.CALENDAR_EVENTS_CREATE, True),
    "recovery:insert_post_interruption_buffer": (ActionRiskTier.EXTERNAL_MODIFICATION, PermissionScope.CALENDAR_EVENTS_CREATE, True),
    "recovery:meeting_decompression_slot": (ActionRiskTier.EXTERNAL_MODIFICATION, PermissionScope.CALENDAR_EVENTS_CREATE, True),
    "reminder:stage_context_warming": (ActionRiskTier.EXTERNAL_MODIFICATION, PermissionScope.NOTIFICATIONS_SEND, True),
    "calendar:reschedule_event": (ActionRiskTier.CONSEQUENTIAL_EXTERNAL_ACTION, PermissionScope.CALENDAR_EVENTS_MODIFY, True),
    "task:decompose_into_subtasks": (ActionRiskTier.CONSEQUENTIAL_EXTERNAL_ACTION, PermissionScope.TASKS_WRITE, True),
}


class PolicyEngine:
    """
    Centralized, deterministic policy evaluation and consent management layer.
    """

    @classmethod
    def get_action_spec(cls, action_identifier: str) -> Optional[Tuple[ActionRiskTier, PermissionScope, bool]]:
        return ACTION_POLICY_SPECS.get(action_identifier)

    @classmethod
    def is_quiet_hours_active(cls, db: Session, user_id: uuid.UUID, current_hour: Optional[int] = None) -> bool:
        """
        Determines if quiet hours are currently in effect for the given user.
        """
        pref = db.execute(
            select(UserNotificationPreference).where(UserNotificationPreference.user_id == user_id)
        ).scalar_one_or_none()

        if not pref or not pref.quiet_hours_enabled:
            return False

        if current_hour is None:
            current_hour = datetime.now(timezone.utc).hour

        start = pref.quiet_hours_start
        end = pref.quiet_hours_end

        if start > end:
            # e.g., 22:00 to 08:00 (crosses midnight)
            return current_hour >= start or current_hour < end
        elif start < end:
            return start <= current_hour < end
        return False

    @classmethod
    def evaluate_action_policy(
        cls,
        db: Session,
        user_id: uuid.UUID,
        action_identifier: str,
        parameters: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> PolicyEvaluationResult:
        """
        Deterministically evaluates policy for a proposed action.
        Independent of LLM output.
        """
        context = context or {}
        parameters = parameters or {}
        now = datetime.now(timezone.utc)

        spec = cls.get_action_spec(action_identifier)
        if not spec:
            reason = f"Action identifier '{action_identifier}' is unregistered or invalid."
            cls._log_audit(
                db=db,
                user_id=user_id,
                action_identifier=action_identifier,
                scope_checked=None,
                decision="DENIED",
                risk_tier=ActionRiskTier.CONSEQUENTIAL_EXTERNAL_ACTION.value,
                reason=reason,
                context_snapshot={"parameters": parameters, "context": context},
            )
            return PolicyEvaluationResult(
                allowed=False,
                risk_tier=ActionRiskTier.CONSEQUENTIAL_EXTERNAL_ACTION,
                requires_approval=True,
                denial_reason=reason,
                scope_required=None,
            )

        risk_tier, required_scope, requires_approval = spec

        # 1. Tenant boundary validation (e.g. task_id belongs to this user)
        task_id = parameters.get("task_id")
        if task_id:
            try:
                task_uuid = uuid.UUID(str(task_id))
                task = db.execute(
                    select(Task).where(Task.id == task_uuid)
                ).scalar_one_or_none()
                if task and task.user_id != user_id:
                    reason = "Tenant boundary violation: requested task does not belong to authorized user."
                    cls._log_audit(
                        db=db,
                        user_id=user_id,
                        action_identifier=action_identifier,
                        scope_checked=required_scope.value,
                        decision="DENIED",
                        risk_tier=risk_tier.value,
                        reason=reason,
                        context_snapshot={"task_id": str(task_id)},
                    )
                    return PolicyEvaluationResult(
                        allowed=False,
                        risk_tier=risk_tier,
                        requires_approval=requires_approval,
                        denial_reason=reason,
                        scope_required=required_scope,
                    )
            except (ValueError, TypeError):
                pass

        # 2. Scope Permission / Consent check
        consent = db.execute(
            select(UserPolicyConsent).where(
                and_(
                    UserPolicyConsent.user_id == user_id,
                    UserPolicyConsent.scope == required_scope.value,
                    UserPolicyConsent.consent_status == ConsentStatusEnum.GRANTED.value,
                )
            )
        ).scalar_one_or_none()

        if not consent:
            reason = f"Permission scope '{required_scope.value}' is not granted or has been revoked."
            cls._log_audit(
                db=db,
                user_id=user_id,
                action_identifier=action_identifier,
                scope_checked=required_scope.value,
                decision="DENIED",
                risk_tier=risk_tier.value,
                reason=reason,
                context_snapshot={"required_scope": required_scope.value},
            )
            return PolicyEvaluationResult(
                allowed=False,
                risk_tier=risk_tier,
                requires_approval=requires_approval,
                denial_reason=reason,
                scope_required=required_scope,
            )

        # 3. Approval verification for actions requiring explicit approval
        is_executing = context.get("is_executing", True)
        is_approved = context.get("is_approved", False)
        if is_executing and requires_approval and not is_approved:
            reason = f"Action '{action_identifier}' (Tier: {risk_tier.value}) requires explicit user approval before execution."
            cls._log_audit(
                db=db,
                user_id=user_id,
                action_identifier=action_identifier,
                scope_checked=required_scope.value,
                decision="DENIED",
                risk_tier=risk_tier.value,
                reason=reason,
                context_snapshot={"approval_status": "UNAPPROVED"},
            )
            return PolicyEvaluationResult(
                allowed=False,
                risk_tier=risk_tier,
                requires_approval=requires_approval,
                denial_reason=reason,
                scope_required=required_scope,
            )

        # 4. Quiet hours and user notification preferences
        if required_scope == PermissionScope.NOTIFICATIONS_SEND:
            if cls.is_quiet_hours_active(db, user_id):
                reason = "Notification suppressed: quiet hours currently active for user."
                cls._log_audit(
                    db=db,
                    user_id=user_id,
                    action_identifier=action_identifier,
                    scope_checked=required_scope.value,
                    decision="BLOCKED_BY_QUIET_HOURS",
                    risk_tier=risk_tier.value,
                    reason=reason,
                    context_snapshot={"quiet_hours": True},
                )
                return PolicyEvaluationResult(
                    allowed=False,
                    risk_tier=risk_tier,
                    requires_approval=requires_approval,
                    denial_reason=reason,
                    scope_required=required_scope,
                )

        # 5. Global Privacy Pause Check
        privacy_settings = db.execute(
            select(UserPrivacySettings).where(UserPrivacySettings.user_id == user_id)
        ).scalar_one_or_none()
        if privacy_settings and privacy_settings.is_paused:
            reason = "Automations suppressed: user privacy paused."
            cls._log_audit(
                db=db,
                user_id=user_id,
                action_identifier=action_identifier,
                scope_checked=required_scope.value,
                decision="DENIED",
                risk_tier=risk_tier.value,
                reason=reason,
                context_snapshot={"is_paused": True},
            )
            return PolicyEvaluationResult(
                allowed=False,
                risk_tier=risk_tier,
                requires_approval=requires_approval,
                denial_reason=reason,
                scope_required=required_scope,
            )

        # Policy checks passed
        cls._log_audit(
            db=db,
            user_id=user_id,
            action_identifier=action_identifier,
            scope_checked=required_scope.value,
            decision="ALLOWED",
            risk_tier=risk_tier.value,
            reason=None,
            context_snapshot={"parameters": parameters},
        )
        return PolicyEvaluationResult(
            allowed=True,
            risk_tier=risk_tier,
            requires_approval=requires_approval,
            denial_reason=None,
            scope_required=required_scope,
        )

    @classmethod
    def grant_scope(
        cls,
        db: Session,
        user_id: uuid.UUID,
        scope: PermissionScope,
        source: ConsentSource = ConsentSource.USER_EXPLICIT,
        device_id: Optional[str] = None,
        integration_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UserPolicyConsent:
        """
        Grants a permission scope to a user, reactivating or creating a consent record.
        """
        now = datetime.now(timezone.utc)
        consent = db.execute(
            select(UserPolicyConsent).where(
                and_(
                    UserPolicyConsent.user_id == user_id,
                    UserPolicyConsent.scope == scope.value,
                )
            )
        ).scalar_one_or_none()

        if consent:
            consent.consent_status = ConsentStatusEnum.GRANTED.value
            consent.granted_timestamp = now
            consent.revoked_timestamp = None
            consent.revocation_reason = None
            consent.source = source.value
            consent.device_id = device_id or consent.device_id
            consent.integration_id = integration_id or consent.integration_id
            if metadata:
                consent.policy_metadata = metadata
            consent.updated_at = now
        else:
            consent = UserPolicyConsent(
                user_id=user_id,
                scope=scope.value,
                consent_status=ConsentStatusEnum.GRANTED.value,
                consent_version="1.0.0",
                granted_timestamp=now,
                source=source.value,
                device_id=device_id,
                integration_id=integration_id,
                policy_metadata=metadata or {},
            )
            db.add(consent)

        cls._log_audit(
            db=db,
            user_id=user_id,
            action_identifier=f"policy:grant:{scope.value}",
            scope_checked=scope.value,
            decision="GRANTED",
            risk_tier=ActionRiskTier.INFORMATIONAL.value,
            reason=f"User granted consent for scope {scope.value} via {source.value}.",
            context_snapshot={"source": source.value, "device_id": device_id, "integration_id": integration_id},
        )
        db.commit()
        db.refresh(consent)
        return consent

    @classmethod
    def revoke_scope(
        cls,
        db: Session,
        user_id: uuid.UUID,
        scope: PermissionScope,
        reason: Optional[str] = None,
    ) -> UserPolicyConsent:
        """
        Revokes a permission scope, stops scheduled workflows requiring this scope,
        marks pending steps as blocked, and records an audit log.
        """
        now = datetime.now(timezone.utc)
        consent = db.execute(
            select(UserPolicyConsent).where(
                and_(
                    UserPolicyConsent.user_id == user_id,
                    UserPolicyConsent.scope == scope.value,
                )
            )
        ).scalar_one_or_none()

        if consent:
            consent.consent_status = ConsentStatusEnum.REVOKED.value
            consent.revoked_timestamp = now
            consent.revocation_reason = reason or "User revoked consent"
            consent.updated_at = now
        else:
            consent = UserPolicyConsent(
                user_id=user_id,
                scope=scope.value,
                consent_status=ConsentStatusEnum.REVOKED.value,
                consent_version="1.0.0",
                granted_timestamp=now,
                revoked_timestamp=now,
                source=ConsentSource.USER_EXPLICIT.value,
                revocation_reason=reason or "User revoked consent",
            )
            db.add(consent)

        # Revocation Cascade: Find all active or scheduled plans for this user
        plans = db.execute(
            select(WorkflowExecutionPlan).where(
                and_(
                    WorkflowExecutionPlan.user_id == user_id,
                    WorkflowExecutionPlan.status.in_([
                        WorkflowLifecycleState.CREATED.value,
                        WorkflowLifecycleState.DRAFT.value,
                        WorkflowLifecycleState.VALIDATING.value,
                        WorkflowLifecycleState.AWAITING_APPROVAL.value,
                        WorkflowLifecycleState.APPROVED.value,
                        WorkflowLifecycleState.SCHEDULED.value,
                    ])
                )
            )
        ).scalars().all()

        for plan in plans:
            raw_steps = plan.plan_steps or []
            needs_cancel = False
            for s in raw_steps:
                action_id = s.get("action_identifier")
                spec = cls.get_action_spec(action_id)
                if spec and spec[1] == scope:
                    needs_cancel = True
                    break

            if needs_cancel:
                plan.status = WorkflowLifecycleState.CANCELLED.value
                tc = dict(plan.trigger_context or {})
                tc["cancellation_reason"] = f"Plan cancelled due to revoked permission scope: {scope.value}"
                plan.trigger_context = tc
                plan.updated_at = now

                # Mark any existing step execution records as BLOCKED_BY_POLICY
                step_execs = db.execute(
                    select(WorkflowStepExecution).where(
                        and_(
                            WorkflowStepExecution.plan_id == plan.id,
                            WorkflowStepExecution.status.in_(["PENDING", "EXECUTING"]),
                        )
                    )
                ).scalars().all()
                for se in step_execs:
                    se.status = "BLOCKED_BY_POLICY"
                    se.error_message = f"Revocation of required permission scope: {scope.value}"
                    se.completed_at = now

        cls._log_audit(
            db=db,
            user_id=user_id,
            action_identifier=f"policy:revoke:{scope.value}",
            scope_checked=scope.value,
            decision="REVOKED",
            risk_tier=ActionRiskTier.INFORMATIONAL.value,
            reason=reason or "User revoked consent",
            context_snapshot={"revoked_scope": scope.value},
        )
        db.commit()
        db.refresh(consent)
        return consent

    @classmethod
    def list_user_consents(cls, db: Session, user_id: uuid.UUID) -> List[UserPolicyConsent]:
        """Lists all consent records for user."""
        return db.execute(
            select(UserPolicyConsent)
            .where(UserPolicyConsent.user_id == user_id)
            .order_by(UserPolicyConsent.created_at.desc())
        ).scalars().all()

    @classmethod
    def get_user_policy_overview(cls, db: Session, user_id: uuid.UUID) -> Dict[str, Any]:
        """Returns structured policy overview including active scopes, risk tiers, and quiet hours."""
        consents = cls.list_user_consents(db, user_id)
        active_scopes = [
            c.scope for c in consents if c.consent_status == ConsentStatusEnum.GRANTED.value
        ]
        quiet_hours = cls.is_quiet_hours_active(db, user_id)

        # Risk tier rules summary
        risk_tier_rules = {
            tier.value: {
                "requires_approval": tier in (
                    ActionRiskTier.EXTERNAL_MODIFICATION,
                    ActionRiskTier.CONSEQUENTIAL_EXTERNAL_ACTION,
                ),
                "actions": [
                    act for act, spec in ACTION_POLICY_SPECS.items() if spec[0] == tier
                ],
            }
            for tier in ActionRiskTier
        }

        return {
            "user_id": user_id,
            "permissions": consents,
            "active_scopes": active_scopes,
            "risk_tier_rules": risk_tier_rules,
            "quiet_hours_active": quiet_hours,
        }

    @classmethod
    def _log_audit(
        cls,
        db: Session,
        user_id: uuid.UUID,
        action_identifier: str,
        scope_checked: Optional[str],
        decision: str,
        risk_tier: str,
        reason: Optional[str],
        context_snapshot: Optional[Dict[str, Any]] = None,
    ) -> PolicyAuditTrail:
        """Writes an immutable policy audit record."""
        audit = PolicyAuditTrail(
            user_id=user_id,
            action_identifier=action_identifier,
            scope_checked=scope_checked,
            decision=decision,
            risk_tier=risk_tier,
            reason=reason,
            context_snapshot=context_snapshot,
            evaluated_at=datetime.now(timezone.utc),
        )
        db.add(audit)
        try:
            db.commit()
        except Exception as e:
            logger.error(f"Failed to commit policy audit log: {e}")
            db.rollback()
        return audit

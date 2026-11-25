"""
FastAPI router for Permission, Consent, and Deterministic Policy Enforcement (ContextIQ Phase 7.6).
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_id
from app.db.session import get_db
from app.models.policy_models import PolicyAuditTrail
from app.schemas.policy_schemas import (
    PermissionScope,
    PolicyAuditTrailResponse,
    PolicyConsentGrantRequest,
    PolicyConsentResponse,
    PolicyConsentRevokeRequest,
    PolicyEvaluationRequest,
    PolicyEvaluationResult,
    UserPolicyOverviewResponse,
)
from app.services.policy_engine import PolicyEngine

router = APIRouter(prefix="/policy", tags=["policy"])


@router.get("/permissions", response_model=List[PolicyConsentResponse])
def get_user_permissions(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> List[PolicyConsentResponse]:
    """Lists all permission consent records for the authenticated user."""
    consents = PolicyEngine.list_user_consents(db, user_id)
    return [PolicyConsentResponse.model_validate(c) for c in consents]


@router.get("/overview", response_model=UserPolicyOverviewResponse)
def get_policy_overview(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> UserPolicyOverviewResponse:
    """Returns structured policy overview including active scopes, risk tiers, and quiet hours."""
    overview = PolicyEngine.get_user_policy_overview(db, user_id)
    return UserPolicyOverviewResponse(
        user_id=overview["user_id"],
        permissions=[PolicyConsentResponse.model_validate(c) for c in overview["permissions"]],
        active_scopes=overview["active_scopes"],
        risk_tier_rules=overview["risk_tier_rules"],
        quiet_hours_active=overview["quiet_hours_active"],
    )


@router.post("/permissions/grant", response_model=PolicyConsentResponse)
def grant_permission(
    payload: PolicyConsentGrantRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> PolicyConsentResponse:
    """Grants consent for a specific permission scope."""
    consent = PolicyEngine.grant_scope(
        db=db,
        user_id=user_id,
        scope=payload.scope,
        source=payload.source,
        device_id=payload.device_id,
        integration_id=payload.integration_id,
        metadata=payload.policy_metadata,
    )
    return PolicyConsentResponse.model_validate(consent)


@router.post("/permissions/revoke", response_model=PolicyConsentResponse)
def revoke_permission(
    payload: PolicyConsentRevokeRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> PolicyConsentResponse:
    """Revokes consent for a permission scope and cancels affected scheduled workflows."""
    consent = PolicyEngine.revoke_scope(
        db=db,
        user_id=user_id,
        scope=payload.scope,
        reason=payload.reason,
    )
    return PolicyConsentResponse.model_validate(consent)


@router.post("/evaluate", response_model=PolicyEvaluationResult)
def evaluate_action_policy(
    payload: PolicyEvaluationRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> PolicyEvaluationResult:
    """Evaluates whether an action would be permitted under current user consent and system policies."""
    context: Dict[str, Any] = {
        "is_executing": False,
        "plan_id": str(payload.workflow_plan_id) if payload.workflow_plan_id else None,
        "step_key": payload.step_key,
    }
    return PolicyEngine.evaluate_action_policy(
        db=db,
        user_id=user_id,
        action_identifier=payload.action_identifier,
        parameters=payload.parameters or {},
        context=context,
    )


@router.get("/history", response_model=List[PolicyAuditTrailResponse])
def get_policy_audit_history(
    limit: int = Query(50, ge=1, le=200),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> List[PolicyAuditTrailResponse]:
    """Retrieves immutable audit trail of policy evaluations for the current user."""
    records = db.execute(
        select(PolicyAuditTrail)
        .where(PolicyAuditTrail.user_id == user_id)
        .order_by(desc(PolicyAuditTrail.evaluated_at))
        .limit(limit)
    ).scalars().all()
    return [PolicyAuditTrailResponse.model_validate(r) for r in records]

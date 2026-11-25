"""
FastAPI router for User-Defined Automation Rules, Triggers, and Executions (Phase 7.2).
"""
from __future__ import annotations

import json
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_id
from app.db.session import get_db
from app.models.automation_rule import (
    AutomationActionDefinition,
    AutomationCondition,
    AutomationExecution,
    AutomationRule,
    AutomationRuleVersion,
    AutomationTrigger,
)
from app.schemas.automation_schemas import (
    AutomationExecutionResponse,
    AutomationRuleCreate,
    AutomationRuleDetailResponse,
    AutomationRuleResponse,
    AutomationRuleUpdate,
    AutomationRuleVersionResponse,
    TriggerEvaluationRequest,
    TriggerEvaluationResponse,
)
from app.services.automation_engine import AutomationTriggerEngine

router = APIRouter(prefix="/automations", tags=["automations"])


def _serialize_rule_snapshot(rule: AutomationRule) -> dict:
    """Creates a complete frozen dictionary snapshot of a rule and its components."""
    return {
        "name": rule.name,
        "description": rule.description,
        "is_enabled": rule.is_enabled,
        "version": rule.version,
        "priority": rule.priority,
        "cooldown_minutes": rule.cooldown_minutes,
        "max_executions_per_day": rule.max_executions_per_day,
        "requires_approval": rule.requires_approval,
        "risk_tier": rule.risk_tier,
        "active_schedule": rule.active_schedule,
        "quiet_hours": rule.quiet_hours,
        "expires_at": rule.expires_at.isoformat() if rule.expires_at else None,
        "triggers": [
            {
                "trigger_type": t.trigger_type,
                "parameters": t.parameters,
                "is_authorized": t.is_authorized,
                "authorization_source": t.authorization_source,
            }
            for t in rule.triggers
        ],
        "conditions": [
            {
                "condition_group": c.condition_group,
                "logical_operator": c.logical_operator,
                "field_path": c.field_path,
                "operator": c.operator,
                "expected_value": c.expected_value,
                "min_evidence_observations": c.min_evidence_observations,
                "confidence_threshold": c.confidence_threshold,
            }
            for c in rule.conditions
        ],
        "actions": [
            {
                "action_order": a.action_order,
                "action_identifier": a.action_identifier,
                "parameters_template": a.parameters_template,
                "is_critical": a.is_critical,
                "is_reversible": a.is_reversible,
                "action_preview_template": a.action_preview_template,
            }
            for a in rule.actions
        ],
    }


@router.get("/rules", response_model=List[AutomationRuleResponse], summary="List User Automation Rules")
def list_rules(
    is_enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Returns all automation rules configured by the authenticated user."""
    query = select(AutomationRule).where(AutomationRule.user_id == user_id)
    if is_enabled is not None:
        query = query.where(AutomationRule.is_enabled == is_enabled)
    query = query.order_by(AutomationRule.priority.asc(), AutomationRule.created_at.desc())
    rules = db.execute(query).scalars().all()
    return rules


@router.post("/rules", response_model=AutomationRuleDetailResponse, status_code=status.HTTP_201_CREATED, summary="Create Automation Rule")
def create_rule(
    payload: AutomationRuleCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Creates a new user-defined automation rule with triggers, conditions, and action definitions."""
    rule = AutomationRule(
        user_id=user_id,
        name=payload.name,
        description=payload.description,
        is_enabled=payload.is_enabled,
        version=1,
        priority=payload.priority,
        cooldown_minutes=payload.cooldown_minutes,
        max_executions_per_day=payload.max_executions_per_day,
        requires_approval=payload.requires_approval,
        risk_tier=payload.risk_tier,
        active_schedule=payload.active_schedule,
        quiet_hours=payload.quiet_hours,
        expires_at=payload.expires_at,
    )
    db.add(rule)
    db.flush()

    # Add triggers
    for t in payload.triggers:
        trigger = AutomationTrigger(
            rule_id=rule.id,
            trigger_type=t.trigger_type.value,
            parameters=t.parameters,
            is_authorized=t.is_authorized,
            authorization_source=t.authorization_source,
        )
        db.add(trigger)

    # Add conditions
    for c in payload.conditions:
        condition = AutomationCondition(
            rule_id=rule.id,
            condition_group=c.condition_group,
            logical_operator=c.logical_operator.value,
            field_path=c.field_path,
            operator=c.operator.value,
            expected_value=c.expected_value,
            min_evidence_observations=c.min_evidence_observations,
            confidence_threshold=c.confidence_threshold,
        )
        db.add(condition)

    # Add actions
    for a in payload.actions:
        action = AutomationActionDefinition(
            rule_id=rule.id,
            action_order=a.action_order,
            action_identifier=a.action_identifier,
            parameters_template=a.parameters_template,
            is_critical=a.is_critical,
            is_reversible=a.is_reversible,
            action_preview_template=a.action_preview_template,
        )
        db.add(action)

    db.flush()
    db.refresh(rule)

    # Snapshot initial version (v1)
    snapshot = _serialize_rule_snapshot(rule)
    rule_version = AutomationRuleVersion(
        rule_id=rule.id,
        version_number=1,
        rule_snapshot=snapshot,
        change_summary="Initial rule creation",
        changed_by=user_id,
    )
    db.add(rule_version)
    db.commit()
    db.refresh(rule)

    return rule


@router.get("/rules/{rule_id}", response_model=AutomationRuleDetailResponse, summary="Get Rule Details")
def get_rule(
    rule_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Retrieves full details of a specific automation rule including triggers, conditions, and actions."""
    rule = db.execute(
        select(AutomationRule).where(AutomationRule.id == rule_id, AutomationRule.user_id == user_id)
    ).scalar_one_or_none()

    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation rule not found")

    return rule


@router.put("/rules/{rule_id}", response_model=AutomationRuleDetailResponse, summary="Update Automation Rule")
def update_rule(
    rule_id: uuid.UUID,
    payload: AutomationRuleUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Updates an existing automation rule. Increments version and records an immutable version snapshot."""
    rule = db.execute(
        select(AutomationRule).where(AutomationRule.id == rule_id, AutomationRule.user_id == user_id)
    ).scalar_one_or_none()

    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation rule not found")

    if payload.name is not None:
        rule.name = payload.name
    if payload.description is not None:
        rule.description = payload.description
    if payload.is_enabled is not None:
        rule.is_enabled = payload.is_enabled
    if payload.priority is not None:
        rule.priority = payload.priority
    if payload.cooldown_minutes is not None:
        rule.cooldown_minutes = payload.cooldown_minutes
    if payload.max_executions_per_day is not None:
        rule.max_executions_per_day = payload.max_executions_per_day
    if payload.requires_approval is not None:
        rule.requires_approval = payload.requires_approval
    if payload.risk_tier is not None:
        rule.risk_tier = payload.risk_tier
    if payload.active_schedule is not None:
        rule.active_schedule = payload.active_schedule
    if payload.quiet_hours is not None:
        rule.quiet_hours = payload.quiet_hours
    if payload.expires_at is not None:
        rule.expires_at = payload.expires_at

    # If triggers provided, replace
    if payload.triggers is not None:
        for t in list(rule.triggers):
            db.delete(t)
        for t in payload.triggers:
            db.add(AutomationTrigger(
                rule_id=rule.id,
                trigger_type=t.trigger_type.value,
                parameters=t.parameters,
                is_authorized=t.is_authorized,
                authorization_source=t.authorization_source,
            ))

    # If conditions provided, replace
    if payload.conditions is not None:
        for c in list(rule.conditions):
            db.delete(c)
        for c in payload.conditions:
            db.add(AutomationCondition(
                rule_id=rule.id,
                condition_group=c.condition_group,
                logical_operator=c.logical_operator.value,
                field_path=c.field_path,
                operator=c.operator.value,
                expected_value=c.expected_value,
                min_evidence_observations=c.min_evidence_observations,
                confidence_threshold=c.confidence_threshold,
            ))

    # If actions provided, replace
    if payload.actions is not None:
        for a in list(rule.actions):
            db.delete(a)
        for a in payload.actions:
            db.add(AutomationActionDefinition(
                rule_id=rule.id,
                action_order=a.action_order,
                action_identifier=a.action_identifier,
                parameters_template=a.parameters_template,
                is_critical=a.is_critical,
                is_reversible=a.is_reversible,
                action_preview_template=a.action_preview_template,
            ))

    rule.version += 1
    db.flush()
    db.refresh(rule)

    # Version snapshot
    snapshot = _serialize_rule_snapshot(rule)
    db.add(AutomationRuleVersion(
        rule_id=rule.id,
        version_number=rule.version,
        rule_snapshot=snapshot,
        change_summary=payload.change_summary or f"Updated to version {rule.version}",
        changed_by=user_id,
    ))

    db.commit()
    db.refresh(rule)
    return rule


@router.patch("/rules/{rule_id}/toggle", response_model=AutomationRuleResponse, summary="Toggle Rule Enabled Status")
def toggle_rule(
    rule_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Enables or disables an automation rule immediately."""
    rule = db.execute(
        select(AutomationRule).where(AutomationRule.id == rule_id, AutomationRule.user_id == user_id)
    ).scalar_one_or_none()

    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation rule not found")

    rule.is_enabled = not rule.is_enabled
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete Automation Rule")
def delete_rule(
    rule_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Deletes an automation rule and all associated triggers, conditions, and actions."""
    rule = db.execute(
        select(AutomationRule).where(AutomationRule.id == rule_id, AutomationRule.user_id == user_id)
    ).scalar_one_or_none()

    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation rule not found")

    db.delete(rule)
    db.commit()
    return None


@router.post("/evaluate", response_model=TriggerEvaluationResponse, summary="Evaluate Trigger Against Rules")
def evaluate_trigger(
    payload: TriggerEvaluationRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Evaluates incoming event or telemetry trigger against all registered user automation rules.
    If conditions match and eligibility passes, generates action plans and records execution audit.
    """
    return AutomationTriggerEngine.evaluate_trigger(
        db=db,
        user_id=user_id,
        trigger_type=payload.trigger_type.value,
        trigger_event_id=payload.trigger_event_id,
        context_payload=payload.context_payload,
        dry_run=False,
    )


@router.post("/dry-run", response_model=TriggerEvaluationResponse, summary="Dry Run Trigger Evaluation")
def dry_run_trigger(
    payload: TriggerEvaluationRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Simulates trigger and condition evaluation without creating workflows or execution records."""
    return AutomationTriggerEngine.evaluate_trigger(
        db=db,
        user_id=user_id,
        trigger_type=payload.trigger_type.value,
        trigger_event_id=payload.trigger_event_id,
        context_payload=payload.context_payload,
        dry_run=True,
    )


@router.get("/executions", response_model=List[AutomationExecutionResponse], summary="List Rule Executions History")
def list_executions(
    rule_id: Optional[uuid.UUID] = Query(None, description="Filter by rule ID"),
    status_filter: Optional[str] = Query(None, description="Filter by execution status"),
    limit: int = Query(50, ge=1, le=200),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Returns execution and evaluation audit trail for the authenticated user's rules."""
    query = select(AutomationExecution).where(AutomationExecution.user_id == user_id)
    if rule_id:
        query = query.where(AutomationExecution.rule_id == rule_id)
    if status_filter:
        query = query.where(AutomationExecution.status == status_filter)
    query = query.order_by(AutomationExecution.executed_at.desc()).limit(limit)

    return db.execute(query).scalars().all()


@router.get("/rules/{rule_id}/versions", response_model=List[AutomationRuleVersionResponse], summary="List Rule Versions")
def list_rule_versions(
    rule_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Returns the immutable version history of a rule."""
    rule = db.execute(
        select(AutomationRule).where(AutomationRule.id == rule_id, AutomationRule.user_id == user_id)
    ).scalar_one_or_none()

    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation rule not found")

    versions = db.execute(
        select(AutomationRuleVersion)
        .where(AutomationRuleVersion.rule_id == rule_id)
        .order_by(AutomationRuleVersion.version_number.desc())
    ).scalars().all()

    return versions

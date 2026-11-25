"""
Deterministic Automation Rule and Trigger Evaluation Engine (ContextIQ Phase 7.2).

Provides:
- Safe, non-executable, pure-functional condition evaluation (no eval/exec).
- Dotted dictionary field traversal with strict type coercion.
- Nested AND / OR condition grouping.
- Schedule, quiet hours, cooldown, and daily execution throttling.
- User authorization guards (telemetry consent, calendar scopes).
- Idempotency fencing and event deduplication.
"""
from __future__ import annotations

import hashlib
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.automation_rule import (
    AutomationActionDefinition,
    AutomationCondition,
    AutomationExecution,
    AutomationRule,
    AutomationRuleVersion,
    AutomationTrigger,
)
from app.models.simulation_models import ProposedWorkflow
from app.models.telemetry_consent import TelemetryConsent
from app.schemas.automation_schemas import (
    ConditionOperator,
    ExecutionStatus,
    LogicalOperator,
    TriggerEvaluationResponse,
    TriggerEvaluationResultItem,
    TriggerType,
)

logger = logging.getLogger(__name__)


class AutomationConditionEvaluator:
    """
    Evaluates condition predicates against a runtime context payload.
    Strictly deterministic and safe: never calls eval(), exec(), or shell interpreters.
    """

    @classmethod
    def extract_field_value(cls, payload: Dict[str, Any], field_path: str) -> Tuple[bool, Any]:
        """
        Safely retrieves a value from a nested dictionary using dot-notation.
        Returns (found: bool, value: Any).
        """
        parts = field_path.strip().split(".")
        current: Any = payload

        for part in parts:
            if not isinstance(current, dict):
                return False, None
            if part not in current:
                return False, None
            current = current[part]

        return True, current

    @classmethod
    def evaluate_single_condition(
        cls,
        condition: AutomationCondition,
        context_payload: Dict[str, Any],
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Evaluates a single condition against the context payload.
        Returns (is_satisfied: bool, audit_info: dict).
        """
        found, actual_value = cls.extract_field_value(context_payload, condition.field_path)
        op = condition.operator
        expected = condition.expected_value

        audit_info = {
            "field_path": condition.field_path,
            "operator": op,
            "expected_value": expected,
            "actual_value": actual_value,
            "field_found": found,
            "passed": False,
        }

        if not found:
            # Field does not exist in context
            return False, audit_info

        try:
            passed = False
            if op == ConditionOperator.EQUALS.value:
                passed = actual_value == expected
            elif op == ConditionOperator.NOT_EQUALS.value:
                passed = actual_value != expected
            elif op == ConditionOperator.GREATER_THAN.value:
                passed = float(actual_value) > float(expected)
            elif op == ConditionOperator.GREATER_THAN_OR_EQUAL.value:
                passed = float(actual_value) >= float(expected)
            elif op == ConditionOperator.LESS_THAN.value:
                passed = float(actual_value) < float(expected)
            elif op == ConditionOperator.LESS_THAN_OR_EQUAL.value:
                passed = float(actual_value) <= float(expected)
            elif op == ConditionOperator.BETWEEN.value:
                if isinstance(expected, (list, tuple)) and len(expected) == 2:
                    passed = float(expected[0]) <= float(actual_value) <= float(expected[1])
            elif op == ConditionOperator.IS_TRUE.value:
                passed = bool(actual_value) is True
            elif op == ConditionOperator.IS_FALSE.value:
                passed = bool(actual_value) is False
            elif op == ConditionOperator.CONTAINS.value:
                if isinstance(actual_value, (list, tuple, str)):
                    passed = expected in actual_value
            elif op == ConditionOperator.IN_LIST.value:
                if isinstance(expected, (list, tuple)):
                    passed = actual_value in expected

            # Check minimum evidence requirements if specified
            if passed and condition.min_evidence_observations > 1:
                obs_found, obs_count = cls.extract_field_value(
                    context_payload, f"{condition.field_path}_observations"
                )
                if obs_found and int(obs_count) < condition.min_evidence_observations:
                    passed = False
                    audit_info["evidence_failed"] = f"Observations {obs_count} < required {condition.min_evidence_observations}"

            # Check confidence threshold if specified
            if passed and condition.confidence_threshold > 0.0:
                conf_found, conf_val = cls.extract_field_value(
                    context_payload, f"{condition.field_path}_confidence"
                )
                if conf_found and float(conf_val) < condition.confidence_threshold:
                    passed = False
                    audit_info["confidence_failed"] = f"Confidence {conf_val} < required {condition.confidence_threshold}"

            audit_info["passed"] = passed
            return passed, audit_info

        except (ValueError, TypeError) as e:
            logger.warning(
                f"Error evaluating condition on {condition.field_path}: {e}"
            )
            audit_info["error"] = str(e)
            return False, audit_info

    @classmethod
    def evaluate_condition_group(
        cls,
        conditions: List[AutomationCondition],
        context_payload: Dict[str, Any],
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Evaluates a list of conditions supporting condition_group partitioning
        and logical operators (AND / OR).
        """
        if not conditions:
            # An empty condition set evaluates to True by default
            return True, {"evaluation": "empty_conditions_always_pass", "details": []}

        # Group conditions by condition_group integer
        groups: Dict[int, List[AutomationCondition]] = {}
        for cond in conditions:
            groups.setdefault(cond.condition_group, []).append(cond)

        group_results: List[bool] = []
        audit_details: List[Dict[str, Any]] = []

        for group_id, cond_list in groups.items():
            # In each group, check logical operator between conditions (default AND)
            group_passed = True
            for i, cond in enumerate(cond_list):
                passed, detail = cls.evaluate_single_condition(cond, context_payload)
                audit_details.append(detail)

                if i == 0:
                    group_passed = passed
                else:
                    if cond.logical_operator == LogicalOperator.OR.value:
                        group_passed = group_passed or passed
                    else:
                        group_passed = group_passed and passed

            group_results.append(group_passed)

        # Cross-group combination: all top-level groups must pass (AND)
        overall_passed = all(group_results)
        return overall_passed, {"overall_passed": overall_passed, "details": audit_details}


class AutomationRuleEvaluator:
    """
    Evaluates rule eligibility, schedule boundaries, quiet hours,
    cooldowns, and daily frequency limits.
    """

    @classmethod
    def check_user_authorization(
        cls, db: Session, user_id: uuid.UUID, trigger: AutomationTrigger
    ) -> Tuple[bool, Optional[str]]:
        """
        Verifies that the user has authorized events for this trigger source.
        """
        if not trigger.is_authorized:
            return False, "Trigger explicitly marked unauthorized by user"

        ttype = trigger.trigger_type
        # If trigger relies on passive telemetry (interruption, thrashing, BFI), check TelemetryConsent
        if ttype in (
            TriggerType.INTERRUPTION_BURST_DETECTED.value,
            TriggerType.THRASHING_DETECTED.value,
            TriggerType.BFI_THRESHOLD_EXCEEDED.value,
            TriggerType.COGNITIVE_FATIGUE_HIGH.value,
            TriggerType.RECOVERY_SESSION_ENDED.value,
        ):
            consent = db.execute(
                select(TelemetryConsent).where(
                    TelemetryConsent.user_id == user_id,
                    TelemetryConsent.consent_status == "GRANTED",
                )
            ).scalar_one_or_none()
            if not consent:
                return False, "Telemetry consent is required for behavioral trigger sources"

        return True, None

    @classmethod
    def check_eligibility(
        cls,
        rule: AutomationRule,
        now: datetime,
    ) -> Tuple[bool, ExecutionStatus, Optional[str]]:
        """
        Determines whether a rule is currently eligible to execute based on its
        enabled flag, expiration, schedule, quiet hours, cooldown, and daily limits.
        """
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        if not rule.is_enabled:
            return False, ExecutionStatus.SUPPRESSED_DISABLED, "Rule is disabled"

        if rule.expires_at:
            exp = rule.expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if now > exp:
                return False, ExecutionStatus.SUPPRESSED_EXPIRED, f"Rule expired at {exp.isoformat()}"

        # 1. Cooldown check
        if rule.last_triggered_at and rule.cooldown_minutes > 0:
            last_trig = rule.last_triggered_at
            if last_trig.tzinfo is None:
                last_trig = last_trig.replace(tzinfo=timezone.utc)
            elapsed_seconds = (now - last_trig).total_seconds()
            cooldown_seconds = rule.cooldown_minutes * 60
            if elapsed_seconds < cooldown_seconds:
                remaining_min = round((cooldown_seconds - elapsed_seconds) / 60, 1)
                return (
                    False,
                    ExecutionStatus.SUPPRESSED_COOLDOWN,
                    f"Rule in cooldown. {remaining_min} minutes remaining.",
                )

        # 2. Daily frequency limit check
        if rule.last_execution_date:
            if rule.last_execution_date.date() == now.date():
                if rule.execution_count_today >= rule.max_executions_per_day:
                    return (
                        False,
                        ExecutionStatus.SUPPRESSED_MAX_DAILY,
                        f"Daily limit of {rule.max_executions_per_day} executions reached for today.",
                    )

        # 3. Active Schedule check
        sched = rule.active_schedule or {}
        days = sched.get("days_of_week", [1, 2, 3, 4, 5])
        # Python weekday: Monday is 0, Sunday is 6. Schedule convention: 1 = Mon .. 7 = Sun
        current_iso_weekday = now.isoweekday()
        if current_iso_weekday not in days:
            return (
                False,
                ExecutionStatus.SUPPRESSED_SCHEDULE,
                f"Current day ({current_iso_weekday}) is outside active schedule days {days}",
            )

        start_time_str = sched.get("start_time", "00:00")
        end_time_str = sched.get("end_time", "23:59")
        current_time_str = now.strftime("%H:%M")
        if not (start_time_str <= current_time_str <= end_time_str):
            return (
                False,
                ExecutionStatus.SUPPRESSED_SCHEDULE,
                f"Current time ({current_time_str}) is outside active hours ({start_time_str} - {end_time_str})",
            )

        # 4. Quiet Hours check
        qh = rule.quiet_hours or {}
        if qh.get("enabled", False):
            qh_start = qh.get("start_time", "22:00")
            qh_end = qh.get("end_time", "07:00")
            is_quiet = False
            if qh_start > qh_end:  # Crosses midnight (e.g. 22:00 to 07:00)
                is_quiet = current_time_str >= qh_start or current_time_str <= qh_end
            else:
                is_quiet = qh_start <= current_time_str <= qh_end

            if is_quiet and not qh.get("bypass_on_critical", False):
                return (
                    False,
                    ExecutionStatus.SUPPRESSED_QUIET_HOURS,
                    f"Quiet hours active ({qh_start} - {qh_end})",
                )

        return True, ExecutionStatus.EVALUATED_TRUE, None


class AutomationTriggerEngine:
    """
    Main orchestration engine for evaluating incoming triggers and matching automation rules.
    """

    @classmethod
    def evaluate_trigger(
        cls,
        db: Session,
        user_id: uuid.UUID,
        trigger_type: str,
        trigger_event_id: Optional[str] = None,
        context_payload: Optional[Dict[str, Any]] = None,
        dry_run: bool = False,
    ) -> TriggerEvaluationResponse:
        """
        Evaluates all active automation rules registered for the user and trigger_type.
        """
        start_time = time.monotonic()
        now = datetime.now(timezone.utc)
        payload = context_payload or {}
        event_id = trigger_event_id or f"evt_{uuid.uuid4().hex[:12]}"

        # Query all active rules for this user matching trigger_type
        rules = (
            db.execute(
                select(AutomationRule)
                .join(AutomationTrigger)
                .where(
                    AutomationRule.user_id == user_id,
                    AutomationRule.is_enabled.is_(True),
                    AutomationTrigger.trigger_type == trigger_type,
                )
                .order_by(AutomationRule.priority.asc())
            )
            .scalars()
            .unique()
            .all()
        )

        results: List[TriggerEvaluationResultItem] = []
        matched_count = 0

        for rule in rules:
            rule_start = time.monotonic()
            matching_trigger = next(
                (t for t in rule.triggers if t.trigger_type == trigger_type), None
            )
            if not matching_trigger:
                continue

            # 1. Authorization check
            is_authorized, auth_err = AutomationRuleEvaluator.check_user_authorization(
                db, user_id, matching_trigger
            )
            if not is_authorized:
                results.append(
                    TriggerEvaluationResultItem(
                        rule_id=rule.id,
                        rule_name=rule.name,
                        is_matched=False,
                        status=ExecutionStatus.SUPPRESSED_UNAUTHORIZED,
                        suppression_reason=auth_err,
                    )
                )
                continue

            # 2. Eligibility & safety checks
            is_eligible, status, reason = AutomationRuleEvaluator.check_eligibility(
                rule, now
            )
            if not is_eligible:
                results.append(
                    TriggerEvaluationResultItem(
                        rule_id=rule.id,
                        rule_name=rule.name,
                        is_matched=False,
                        status=status,
                        suppression_reason=reason,
                    )
                )
                continue

            # 3. Deterministic condition evaluation
            conditions_passed, condition_audit = (
                AutomationConditionEvaluator.evaluate_condition_group(
                    rule.conditions, payload
                )
            )

            if not conditions_passed:
                results.append(
                    TriggerEvaluationResultItem(
                        rule_id=rule.id,
                        rule_name=rule.name,
                        is_matched=False,
                        status=ExecutionStatus.EVALUATED_FALSE,
                        matched_conditions=condition_audit,
                    )
                )
                continue

            # Rule is matched!
            matched_count += 1
            proposed_actions = []
            for act in rule.actions:
                proposed_actions.append({
                    "action_identifier": act.action_identifier,
                    "action_order": act.action_order,
                    "parameters": act.parameters_template,
                    "is_critical": act.is_critical,
                    "is_reversible": act.is_reversible,
                    "preview": act.action_preview_template,
                })

            # Idempotency key for this trigger evaluation
            idemp_raw = f"{user_id}:{rule.id}:{event_id}:{rule.version}"
            idempotency_key = hashlib.sha256(idemp_raw.encode("utf-8")).hexdigest()

            workflow_id: Optional[uuid.UUID] = None
            final_status = (
                ExecutionStatus.PENDING_APPROVAL
                if rule.requires_approval
                else ExecutionStatus.EXECUTED
            )

            if not dry_run:
                # Check for duplicate execution record
                existing_exec = db.execute(
                    select(AutomationExecution).where(
                        AutomationExecution.idempotency_key == idempotency_key
                    )
                ).scalar_one_or_none()

                if existing_exec:
                    logger.info(f"Duplicate trigger suppressed by idempotency key {idempotency_key}")
                    results.append(
                        TriggerEvaluationResultItem(
                            rule_id=rule.id,
                            rule_name=rule.name,
                            is_matched=True,
                            status=ExecutionStatus.SUPPRESSED_COOLDOWN,
                            suppression_reason="Duplicate trigger event deduplicated by idempotency key",
                            workflow_id=existing_exec.workflow_instance_id,
                        )
                    )
                    continue

                # Create ProposedWorkflow instance if rule has actions
                if proposed_actions:
                    workflow = ProposedWorkflow(
                        user_id=user_id,
                        title=f"Automation Plan: {rule.name}",
                        status="PENDING_APPROVAL" if rule.requires_approval else "APPROVED",
                        idempotency_key=f"wf_{idempotency_key[:16]}",
                        actions=proposed_actions,
                        permission_audit={
                            "rule_id": str(rule.id),
                            "risk_tier": rule.risk_tier,
                            "requires_approval": rule.requires_approval,
                            "evaluated_at": now.isoformat(),
                        },
                        is_reversible=all(a.get("is_reversible", True) for a in proposed_actions),
                    )
                    db.add(workflow)
                    db.flush()
                    workflow_id = workflow.id

                # Record Execution History
                exec_dur = (time.monotonic() - rule_start) * 1000.0
                execution_record = AutomationExecution(
                    rule_id=rule.id,
                    user_id=user_id,
                    trigger_event_id=event_id,
                    trigger_type=trigger_type,
                    status=final_status.value,
                    matched_conditions=condition_audit,
                    suppression_reason=None,
                    workflow_instance_id=workflow_id,
                    idempotency_key=idempotency_key,
                    execution_duration_ms=round(exec_dur, 2),
                    executed_at=now,
                )
                db.add(execution_record)

                # Update Rule execution counters
                rule.last_triggered_at = now
                if rule.last_execution_date and rule.last_execution_date.date() == now.date():
                    rule.execution_count_today += 1
                else:
                    rule.execution_count_today = 1
                rule.last_execution_date = now

                db.commit()

            results.append(
                TriggerEvaluationResultItem(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    is_matched=True,
                    status=final_status,
                    matched_conditions=condition_audit,
                    proposed_actions=proposed_actions,
                    workflow_id=workflow_id,
                )
            )

        return TriggerEvaluationResponse(
            trigger_type=trigger_type,
            trigger_event_id=event_id,
            evaluated_rules_count=len(rules),
            matched_rules_count=matched_count,
            results=results,
        )

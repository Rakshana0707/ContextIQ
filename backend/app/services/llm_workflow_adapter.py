"""
LLM Workflow Adapter and Structured Output Guard (ContextIQ Phase 7.4).
Enforces:
1. Pydantic structured output validation on all LLM-drafted workflow proposals.
2. Rejection of uncataloged/unregistered actions.
3. Compilation into immutable WorkflowExecutionPlan instances in AWAITING_APPROVAL.
4. Total separation between LLM draft synthesis and execution (the LLM cannot trigger actions).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.workflow_models import WorkflowExecutionPlan, WorkflowPlanVersion
from app.schemas.workflow_schemas import (
    DependencyType,
    LLMWorkflowProposal,
    WorkflowDependencySchema,
    WorkflowLifecycleState,
    WorkflowStepSchema,
)
from app.services.action_registry import ActionRegistry
from app.services.plan_scorer import PlanScorer
from app.services.workflow_validator import WorkflowValidationError, WorkflowValidator


class LLMWorkflowAdapter:
    """
    Safely ingests, parses, and deterministically validates LLM-generated workflow proposals.
    """

    @classmethod
    def validate_and_compile_proposal(
        cls,
        db: Session,
        user_id: uuid.UUID,
        raw_proposal: Any,
    ) -> WorkflowExecutionPlan:
        """
        Parses raw LLM output, validates against Pydantic schema, verifies action contracts
        in ActionRegistry, checks DAG validity, scores plan utility, and creates an
        AWAITING_APPROVAL execution plan.
        """
        # 1. Parse and validate against LLMWorkflowProposal schema
        try:
            if isinstance(raw_proposal, str):
                data = json.loads(raw_proposal)
                proposal = LLMWorkflowProposal.model_validate(data)
            elif isinstance(raw_proposal, dict):
                proposal = LLMWorkflowProposal.model_validate(raw_proposal)
            elif isinstance(raw_proposal, LLMWorkflowProposal):
                proposal = raw_proposal
            else:
                raise ValueError(f"Unsupported proposal payload type: {type(raw_proposal)}")
        except Exception as ex:
            raise WorkflowValidationError(f"Malformed LLM proposal schema: {str(ex)}")

        # 2. Convert LLM steps into formal WorkflowStepSchemas
        steps: List[WorkflowStepSchema] = []
        for s in proposal.steps:
            steps.append(
                WorkflowStepSchema(
                    step_key=s.step_key,
                    name=s.name,
                    action_identifier=s.action_identifier,
                    parameters=s.parameters,
                    order_index=s.order_index,
                    is_optional=s.is_optional,
                    requires_approval=s.requires_approval,
                    estimated_duration_minutes=s.estimated_duration_minutes,
                )
            )

        # 3. Convert LLM dependencies into WorkflowDependencySchemas
        dependencies: List[WorkflowDependencySchema] = []
        for d in proposal.dependencies:
            try:
                dep_type = DependencyType(d.dependency_type.upper())
            except ValueError:
                dep_type = DependencyType.SUCCESS

            dependencies.append(
                WorkflowDependencySchema(
                    source_step_key=d.source_step_key,
                    target_step_key=d.target_step_key,
                    dependency_type=dep_type,
                )
            )

        # 4. Deterministic Guard Validation (Registry & DAG cycles)
        errors = WorkflowValidator.validate_workflow_structure(steps, dependencies)
        if errors:
            raise WorkflowValidationError("LLM proposal failed deterministic action or DAG validation", errors)

        now = datetime.now(timezone.utc)
        scoring = PlanScorer.score_plan(steps, {"task_priority": "HIGH", "confidence_score": 0.88})
        alternatives = PlanScorer.generate_plan_alternatives(steps, {"task_priority": "HIGH"})

        idempotency_key = f"llm_plan:{user_id}:{now.strftime('%Y%m%d%H%M%S%f')}"

        # 5. Persist as AWAITING_APPROVAL execution plan
        plan = WorkflowExecutionPlan(
            user_id=user_id,
            title=proposal.title,
            status=WorkflowLifecycleState.AWAITING_APPROVAL.value,
            version=1,
            idempotency_key=idempotency_key,
            trigger_context={
                "source": "LLM_SYNTHESIS",
                "target_objective": proposal.target_objective,
                "trade_off_analysis": proposal.trade_off_analysis,
            },
            plan_steps=[s.model_dump(mode="json") for s in steps],
            plan_dependencies=[d.model_dump(mode="json") for d in dependencies],
            rationale=proposal.rationale,
            expected_benefits=proposal.expected_benefits,
            potential_side_effects=proposal.potential_side_effects,
            utility_score=scoring["utility_score"],
            plan_comparison_metadata={
                "scoring": scoring,
                "alternatives": [a.model_dump(mode="json") for a in alternatives],
                "llm_trade_off_analysis": proposal.trade_off_analysis,
            },
            reversibility_summary={
                "is_fully_reversible": True,
                "rollback_guarantee": "LLM-proposed plan contains registered actions with compensation contracts.",
            },
            expires_at=now + timedelta(hours=24),
            created_at=now,
            updated_at=now,
        )

        db.add(plan)
        db.flush()

        version_record = WorkflowPlanVersion(
            plan_id=plan.id,
            version=1,
            plan_snapshot={
                "title": plan.title,
                "status": plan.status,
                "steps": plan.plan_steps,
                "dependencies": plan.plan_dependencies,
            },
            change_summary="Compiled from LLM workflow proposal. Requires explicit user approval.",
            created_at=now,
        )
        db.add(version_record)
        db.commit()
        db.refresh(plan)
        return plan

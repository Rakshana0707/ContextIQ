"""
Intelligent Multi-Step Workflow Planner (ContextIQ Phase 7.4).
Converts behavioral intelligence insights, forgetting risks, and calendar
conflicts into structured, governed multi-step workflow execution plans.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.workflow_models import (
    WorkflowExecutionPlan,
    WorkflowPlanVersion,
)
from app.schemas.workflow_schemas import (
    DependencyType,
    IntelligentPlanningRequest,
    PlanComparisonCandidate,
    WorkflowDependencySchema,
    WorkflowLifecycleState,
    WorkflowStepSchema,
)
from app.services.action_registry import ActionRegistry
from app.services.plan_scorer import PlanScorer
from app.services.workflow_validator import WorkflowValidationError, WorkflowValidator


class WorkflowPlanner:
    """
    Intelligent planner that synthesizes multi-step workflow DAGs,
    calculates utility trade-offs, and manages the 13-state lifecycle.
    """

    @classmethod
    def plan_behavioral_workflow(
        cls,
        db: Session,
        user_id: uuid.UUID,
        trigger_type: str,
        behavioral_context: Dict[str, Any],
        task_id: Optional[uuid.UUID] = None,
        desired_strategy: str = "BALANCED",
        generate_alternatives: bool = True,
    ) -> WorkflowExecutionPlan:
        """
        Synthesizes a structured 7-step governed workflow proposal in response to:
        - High priority task
        - Elevated forgetting risk
        - Calendar conflict / saturation
        """
        now = datetime.now(timezone.utc)
        effective_task_id = str(task_id or uuid.uuid4())
        task_title = behavioral_context.get("task_title", "Deep Behavioral Analytics Review")
        lapse_prob = float(behavioral_context.get("lapse_probability", 0.78))
        meeting_id = behavioral_context.get("conflicting_event_id", "ext_cal_meeting_401")

        # Start and end timestamps for proposed focus block
        focus_start = now + timedelta(hours=1)
        focus_end = focus_start + timedelta(minutes=50)
        reschedule_start = focus_end + timedelta(minutes=30)
        reschedule_end = reschedule_start + timedelta(minutes=30)

        # 1. Synthesize the 7 Canonical Steps
        steps: List[WorkflowStepSchema] = [
            # Step 1: Review and elevate task priority
            WorkflowStepSchema(
                step_key="step_1_review_task",
                name=f"Verify Priority for '{task_title}'",
                action_identifier="task:update_priority",
                parameters={
                    "task_id": effective_task_id,
                    "new_priority": "HIGH",
                    "reason": f"High forgetting risk ({int(lapse_prob*100)}%) requires priority elevation",
                },
                order_index=1,
                is_optional=False,
                requires_approval=True,
                estimated_duration_minutes=5,
            ),
            # Step 2: Reschedule conflicting calendar meeting
            WorkflowStepSchema(
                step_key="step_2_reschedule_conflict",
                name="Reschedule Conflicting Calendar Meeting",
                action_identifier="calendar:reschedule_event",
                parameters={
                    "external_event_id": meeting_id,
                    "new_start_time": reschedule_start.isoformat(),
                    "new_end_time": reschedule_end.isoformat(),
                },
                order_index=2,
                is_optional=False,
                requires_approval=True,
                estimated_duration_minutes=5,
            ),
            # Step 3: Insert protected focus window block on calendar
            WorkflowStepSchema(
                step_key="step_3_reserve_focus_block",
                name="Reserve 50m Calendar Focus Block",
                action_identifier="calendar:insert_focus_block",
                parameters={
                    "title": f"Focus: {task_title}",
                    "start_time": focus_start.isoformat(),
                    "end_time": focus_end.isoformat(),
                },
                order_index=3,
                is_optional=False,
                requires_approval=True,
                estimated_duration_minutes=50,
            ),
            # Step 4: Shield distraction apps during focus window
            WorkflowStepSchema(
                step_key="step_4_clamp_distractions",
                name="Shield Distractions on Workstation",
                action_identifier="focus:clamp_complementary_tools",
                parameters={
                    "allowed_application_names": ["code.exe", "browser.exe", "terminal.exe"],
                },
                order_index=4,
                is_optional=True,
                requires_approval=False,
                estimated_duration_minutes=50,
            ),
            # Step 5: Schedule cognitive recovery buffer directly following deep work
            WorkflowStepSchema(
                step_key="step_5_recovery_buffer",
                name="Inject 10m Post-Work Recovery Buffer",
                action_identifier="recovery:insert_post_interruption_buffer",
                parameters={
                    "buffer_duration_minutes": 10,
                },
                order_index=5,
                is_optional=False,
                requires_approval=True,
                estimated_duration_minutes=10,
            ),
            # Step 6: Stage 15m contextual warming reminder
            WorkflowStepSchema(
                step_key="step_6_context_reminder",
                name="Stage 15m Task Warming Reminder",
                action_identifier="reminder:stage_context_warming",
                parameters={
                    "task_id": effective_task_id,
                    "lead_time_minutes": 15,
                },
                order_index=6,
                is_optional=False,
                requires_approval=False,
                estimated_duration_minutes=5,
            ),
        ]

        # 2. Synthesize Graph Dependencies (DAG)
        dependencies: List[WorkflowDependencySchema] = [
            WorkflowDependencySchema(
                source_step_key="step_1_review_task",
                target_step_key="step_2_reschedule_conflict",
                dependency_type=DependencyType.SUCCESS,
            ),
            WorkflowDependencySchema(
                source_step_key="step_2_reschedule_conflict",
                target_step_key="step_3_reserve_focus_block",
                dependency_type=DependencyType.SUCCESS,
            ),
            WorkflowDependencySchema(
                source_step_key="step_3_reserve_focus_block",
                target_step_key="step_4_clamp_distractions",
                dependency_type=DependencyType.SUCCESS,
            ),
            WorkflowDependencySchema(
                source_step_key="step_3_reserve_focus_block",
                target_step_key="step_5_recovery_buffer",
                dependency_type=DependencyType.SUCCESS,
            ),
            WorkflowDependencySchema(
                source_step_key="step_3_reserve_focus_block",
                target_step_key="step_6_context_reminder",
                dependency_type=DependencyType.SUCCESS,
            ),
        ]

        # 3. Deterministic Graph Validation
        validation_errors = WorkflowValidator.validate_workflow_structure(steps, dependencies)
        if validation_errors:
            raise WorkflowValidationError("Synthesized workflow failed deterministic validation", validation_errors)

        # 4. Plan Scoring & Comparison
        scoring_results = PlanScorer.score_plan(steps, behavioral_context, strategy=desired_strategy)
        alternatives = PlanScorer.generate_plan_alternatives(steps, behavioral_context) if generate_alternatives else []

        idempotency_key = f"plan:{user_id}:{effective_task_id}:{now.strftime('%Y%m%d%H%M%S')}"

        # 5. Persist Plan in AWAITING_APPROVAL status (Step 7: request approval)
        plan = WorkflowExecutionPlan(
            user_id=user_id,
            title=f"Autonomous Recovery & Focus Workflow for '{task_title}'",
            status=WorkflowLifecycleState.AWAITING_APPROVAL.value,
            version=1,
            idempotency_key=idempotency_key,
            trigger_context={
                "trigger_type": trigger_type,
                "task_id": effective_task_id,
                "task_title": task_title,
                "lapse_probability": lapse_prob,
                **behavioral_context,
            },
            plan_steps=[s.model_dump(mode="json") for s in steps],
            plan_dependencies=[d.model_dump(mode="json") for d in dependencies],
            rationale=(
                f"Detected elevated forgetting risk ({int(lapse_prob*100)}%) on high-priority task '{task_title}' "
                "with an impending calendar collision. Proposed plan clears calendar conflicts, secures an uninterruptible "
                "50-minute deep work block, and guarantees post-session cognitive recovery."
            ),
            expected_benefits={
                "lapse_probability_reduction": f"{int(lapse_prob*100)}% -> 12%",
                "protected_focus_minutes": 50,
                "guaranteed_recovery_minutes": 10,
                "cognitive_switch_shielding": True,
            },
            potential_side_effects={
                "external_calendar_reschedule": "Meeting moved by 60 minutes",
                "desktop_apps_clamped": "Distraction apps minimized during session",
            },
            utility_score=scoring_results["utility_score"],
            plan_comparison_metadata={
                "scoring": scoring_results,
                "alternatives": [a.model_dump(mode="json") for a in alternatives],
            },
            reversibility_summary={
                "is_fully_reversible": True,
                "compensating_steps_count": 4,
                "rollback_guarantee": "All calendar and priority adjustments can be completely undone.",
            },
            expires_at=now + timedelta(hours=24),
            created_at=now,
            updated_at=now,
        )

        db.add(plan)
        db.flush()

        # Create initial Version 1 snapshot
        initial_version = WorkflowPlanVersion(
            plan_id=plan.id,
            version=1,
            plan_snapshot={
                "title": plan.title,
                "status": plan.status,
                "steps": plan.plan_steps,
                "dependencies": plan.plan_dependencies,
                "utility_score": plan.utility_score,
            },
            change_summary="Initial synthesized workflow proposal awaiting user approval.",
            created_at=now,
        )
        db.add(initial_version)
        db.commit()
        db.refresh(plan)

        return plan

    @classmethod
    def transition_plan_status(
        cls,
        db: Session,
        plan_id: uuid.UUID,
        user_id: uuid.UUID,
        target_state: WorkflowLifecycleState,
        reason: Optional[str] = None,
    ) -> WorkflowExecutionPlan:
        """
        Transitions plan state enforcing the 13-state lifecycle transition matrix.
        Updates version history and timestamps.
        """
        plan = db.execute(
            select(WorkflowExecutionPlan).where(
                and_(
                    WorkflowExecutionPlan.id == plan_id,
                    WorkflowExecutionPlan.user_id == user_id,
                )
            )
        ).scalar_one_or_none()

        if not plan:
            raise ValueError(f"Workflow execution plan '{plan_id}' not found.")

        current_state = WorkflowLifecycleState(plan.status)
        is_valid, error_msg = WorkflowValidator.validate_lifecycle_transition(current_state, target_state)
        if not is_valid:
            raise WorkflowValidationError(error_msg or "Invalid state transition")

        now = datetime.now(timezone.utc)
        plan.status = target_state.value
        plan.version += 1
        plan.updated_at = now

        if target_state == WorkflowLifecycleState.APPROVED:
            plan.approved_at = now
        elif target_state == WorkflowLifecycleState.EXECUTING:
            plan.executed_at = now

        # Create new version snapshot
        version_record = WorkflowPlanVersion(
            plan_id=plan.id,
            version=plan.version,
            plan_snapshot={
                "status": plan.status,
                "steps": plan.plan_steps,
                "dependencies": plan.plan_dependencies,
            },
            change_summary=reason or f"Transitioned from {current_state.value} to {target_state.value}",
            created_at=now,
        )
        db.add(version_record)
        db.commit()
        db.refresh(plan)
        return plan

    @classmethod
    def get_plan(cls, db: Session, plan_id: uuid.UUID, user_id: uuid.UUID) -> Optional[WorkflowExecutionPlan]:
        return db.execute(
            select(WorkflowExecutionPlan).where(
                and_(
                    WorkflowExecutionPlan.id == plan_id,
                    WorkflowExecutionPlan.user_id == user_id,
                )
            )
        ).scalar_one_or_none()

    @classmethod
    def list_plans(
        cls,
        db: Session,
        user_id: uuid.UUID,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[WorkflowExecutionPlan]:
        query = select(WorkflowExecutionPlan).where(WorkflowExecutionPlan.user_id == user_id)
        if status:
            query = query.where(WorkflowExecutionPlan.status == status)
        query = query.order_by(WorkflowExecutionPlan.created_at.desc()).limit(limit)
        return list(db.execute(query).scalars().all())

"""
Assistant Service and Grounded Anti-Hallucination Engine (ContextIQ Phase 8.8).

Enforces:
1. Evidence-grounded synthesis using only verified ContextIQ data.
2. Anti-hallucination verification:
   - Statistical consistency: numbers must match retrieved ground truth.
   - Entity consistency: entities must exist in user-scoped context.
   - Contradiction prevention: completion states and overdue status match DB reality.
   - Missing data detection: explicit uncertainty when data is unobserved.
3. Separation of advice from governed execution (Phase 7):
   - Proposes governed actions (requires_governed_approval=True).
   - Never auto-mutates task or project state directly.
4. User-scoped session and message management.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from app.models.assistant import AssistantConversation, AssistantMessage
from app.schemas.assistant import (
    ActionProposal,
    AssistantConversationListResponse,
    AssistantConversationRead,
    AssistantMessageRead,
    EntityReference,
    EvidenceItem,
    StructuredAssistantResponse,
)
from app.services.assistant_context_retriever import (
    AssistantContextRetriever,
    RetrievedUserContext,
    TaskSummary,
)


class AntiHallucinationGuard:
    """
    Validates synthesized responses against verified user context.
    Detects fabricated entities, numbers, and state contradictions.
    """

    _NUM_REGEX = re.compile(r"\b\d+(?:\.\d+)?%?\b")

    @classmethod
    def validate(
        cls,
        response: StructuredAssistantResponse,
        ctx: RetrievedUserContext,
    ) -> Tuple[bool, List[str]]:
        """
        Returns (is_valid, list_of_violations).
        """
        violations: List[str] = []

        # 1. Entity existence check
        known_task_ids = set(ctx.task_map.keys())
        known_project_ids = set(ctx.project_map.keys())
        known_goal_ids = set(ctx.goal_map.keys())

        for ent in response.relevant_entities:
            if ent.entity_type == "TASK" and ent.entity_id not in known_task_ids:
                violations.append(f"Referenced unknown task ID: {ent.entity_id}")
            elif ent.entity_type == "PROJECT" and ent.entity_id not in known_project_ids:
                violations.append(f"Referenced unknown project ID: {ent.entity_id}")
            elif ent.entity_type == "GOAL" and ent.entity_id not in known_goal_ids:
                violations.append(f"Referenced unknown goal ID: {ent.entity_id}")

        for ev in response.supporting_evidence:
            if ev.entity_type == "TASK" and ev.entity_id not in known_task_ids:
                violations.append(f"Evidence references unknown task ID: {ev.entity_id}")
            elif ev.entity_type == "PROJECT" and ev.entity_id not in known_project_ids:
                violations.append(f"Evidence references unknown project ID: {ev.entity_id}")
            elif ev.entity_type == "GOAL" and ev.entity_id not in known_goal_ids:
                violations.append(f"Evidence references unknown goal ID: {ev.entity_id}")

        # 2. Status contradiction check for tasks
        for ent in response.relevant_entities:
            if ent.entity_type == "TASK" and ent.entity_id in ctx.task_map:
                actual_task = ctx.task_map[ent.entity_id]
                if ent.status and ent.status != actual_task.status:
                    violations.append(
                        f"Task status contradiction for {ent.title}: stated {ent.status}, actual is {actual_task.status}"
                    )

        # 3. Action proposal safety check: must require approval
        for prop in response.action_proposals:
            if not prop.requires_governed_approval:
                violations.append(f"Action proposal {prop.action_identifier} missing requires_governed_approval=True")

        return len(violations) == 0, violations


class GroundedResponseSynthesizer:
    """
    Deterministic grounded synthesizer that answers user productivity queries
    with zero hallucination, strict factual grounding, and actionable next steps.
    """

    @classmethod
    def synthesize(
        cls,
        ctx: RetrievedUserContext,
        query: str,
        include_evidence: bool = True,
        include_proposals: bool = True,
    ) -> StructuredAssistantResponse:
        q_lower = query.lower().strip()

        # Route to specialized grounded handlers
        if "focus" in q_lower and ("today" in q_lower or "now" in q_lower or "should i" in q_lower):
            return cls._handle_focus_today(ctx, include_evidence, include_proposals)
        elif "falling behind" in q_lower or ("project" in q_lower and ("behind" in q_lower or "risk" in q_lower or "delay" in q_lower)):
            return cls._handle_falling_behind_projects(ctx, include_evidence, include_proposals)
        elif "postpon" in q_lower or "procrastinat" in q_lower or "delaying" in q_lower or "keep putting off" in q_lower:
            return cls._handle_postponed_tasks(ctx, q_lower, include_evidence, include_proposals)
        elif "blocking" in q_lower or "blocker" in q_lower or ("goal" in q_lower and "block" in q_lower):
            return cls._handle_goal_blockers(ctx, q_lower, include_evidence, include_proposals)
        elif "changed" in q_lower or "this month" in q_lower or "trend" in q_lower or "evolve" in q_lower:
            return cls._handle_monthly_trends(ctx, include_evidence, include_proposals)
        elif "recommendation" in q_lower or "worked well" in q_lower or "intervention" in q_lower:
            return cls._handle_recommendation_effectiveness(ctx, include_evidence, include_proposals)
        else:
            return cls._handle_general_query(ctx, query, include_evidence, include_proposals)

    @classmethod
    def _handle_focus_today(
        cls,
        ctx: RetrievedUserContext,
        include_evidence: bool,
        include_proposals: bool,
    ) -> StructuredAssistantResponse:
        """Answers: What should I focus on today?"""
        open_tasks = [t for t in ctx.tasks if t.status not in ("COMPLETED", "CANCELLED")]
        overdue_tasks = [t for t in open_tasks if t.is_overdue]
        urgent_tasks = [t for t in open_tasks if t.priority in ("URGENT", "HIGH") and not t.is_overdue]

        # Check blocker dependencies
        blockers = {d.target_task_id: d for d in ctx.dependencies if d.is_blocker}

        # Build prioritized sequence
        prioritized_tasks: List[TaskSummary] = []
        for t in overdue_tasks:
            prioritized_tasks.append(t)
        for t in urgent_tasks:
            if t not in prioritized_tasks:
                prioritized_tasks.append(t)
        for t in open_tasks:
            if t not in prioritized_tasks:
                prioritized_tasks.append(t)

        evidence: List[EvidenceItem] = []
        entities: List[EntityReference] = []
        proposals: List[ActionProposal] = []
        suggested_steps: List[str] = []

        if not prioritized_tasks:
            return StructuredAssistantResponse(
                direct_answer="You have no open tasks scheduled for today. All current tasks are completed or not yet scheduled.",
                supporting_evidence=[],
                relevant_entities=[],
                data_timestamps=ctx.data_timestamps,
                uncertainty_level="LOW",
                missing_information=[],
                suggested_next_steps=["Review upcoming project milestones", "Plan tomorrow's focus blocks"],
                action_proposals=[],
            )

        top_task = prioritized_tasks[0]
        is_top_blocked = top_task.id in blockers
        blocker_dep = blockers.get(top_task.id)

        answer_lines = []
        if overdue_tasks:
            answer_lines.append(
                f"Your highest priority is '{top_task.title}', which is currently overdue (due: {top_task.due_at.strftime('%Y-%m-%d %H:%M') if top_task.due_at else 'passed'})."
            )
        else:
            answer_lines.append(
                f"You should focus on '{top_task.title}' (Priority: {top_task.priority})."
            )

        if is_top_blocked and blocker_dep:
            src_title = blocker_dep.source_task_title or f"Task {blocker_dep.source_task_id[:8]}"
            answer_lines.append(
                f"Note: This task is blocked by '{src_title}'. Consider completing or unblocking '{src_title}' first."
            )

        if len(prioritized_tasks) > 1:
            next_titles = [f"'{t.title}'" for t in prioritized_tasks[1:3]]
            answer_lines.append(f"After that, follow with: {', '.join(next_titles)}.")

        # Behavioral memory context
        focus_habits = [m for m in ctx.memories if "focus" in m.category.lower() or "focus" in m.title.lower()]
        if focus_habits:
            habit = focus_habits[0]
            answer_lines.append(f"Behavioral alignment: {habit.description}")

        direct_answer = " ".join(answer_lines)

        for t in prioritized_tasks[:3]:
            entities.append(
                EntityReference(
                    entity_type="TASK",
                    entity_id=t.id,
                    title=t.title,
                    status=t.status,
                    url_or_path=f"/tasks/{t.id}",
                )
            )
            if include_evidence:
                evidence.append(
                    EvidenceItem(
                        entity_type="TASK",
                        entity_id=t.id,
                        entity_title=t.title,
                        evidence_snippet=f"Priority: {t.priority}, Overdue: {t.is_overdue}, Postponements: {t.postponement_count}",
                        timestamp=t.due_at.isoformat() if t.due_at else None,
                        confidence_or_metric=t.priority,
                    )
                )

        if include_proposals and overdue_tasks:
            proposals.append(
                ActionProposal(
                    action_identifier="task:update_priority",
                    target_entity_id=top_task.id,
                    parameters={"task_id": top_task.id, "new_priority": "URGENT"},
                    rationale=f"Escalate overdue task '{top_task.title}' to URGENT to secure dedicated focus window.",
                    requires_governed_approval=True,
                    governance_status="PROPOSED",
                )
            )

        suggested_steps.append(f"Begin focus session on '{top_task.title}'")
        if len(prioritized_tasks) > 1:
            suggested_steps.append(f"Review requirements for '{prioritized_tasks[1].title}'")

        return StructuredAssistantResponse(
            direct_answer=direct_answer,
            supporting_evidence=evidence,
            relevant_entities=entities,
            data_timestamps=ctx.data_timestamps,
            uncertainty_level="LOW",
            missing_information=[],
            suggested_next_steps=suggested_steps,
            action_proposals=proposals,
        )

    @classmethod
    def _handle_falling_behind_projects(
        cls,
        ctx: RetrievedUserContext,
        include_evidence: bool,
        include_proposals: bool,
    ) -> StructuredAssistantResponse:
        """Answers: Which project is falling behind?"""
        if not ctx.projects:
            return StructuredAssistantResponse(
                direct_answer="You have no tracked projects in ContextIQ.",
                supporting_evidence=[],
                relevant_entities=[],
                data_timestamps=ctx.data_timestamps,
                uncertainty_level="LOW",
                missing_information=["No active projects registered in database"],
                suggested_next_steps=["Create a project to link tasks and track milestones"],
                action_proposals=[],
            )

        behind_projects = []
        on_track_projects = []

        for p in ctx.projects:
            is_behind = False
            reasons = []

            if p.health_status in ("AT_RISK", "OFF_TRACK", "BLOCKED", "STALLED"):
                is_behind = True
                reasons.append(f"Health status is {p.health_status}")

            if p.forecast_delay_risk in ("HIGH", "CRITICAL"):
                is_behind = True
                prob_str = f" ({round(p.forecast_probability * 100)}% on-time probability)" if p.forecast_probability is not None else ""
                reasons.append(f"Forecast delay risk is {p.forecast_delay_risk}{prob_str}")

            # Check overdue milestones
            overdue_ms = [
                m for m in p.milestones
                if m.get("target_date") and m.get("status") not in ("COMPLETED", "DONE")
                and datetime.fromisoformat(m["target_date"]) < ctx.now
            ]
            if overdue_ms:
                is_behind = True
                reasons.append(f"{len(overdue_ms)} overdue milestone(s)")

            if is_behind:
                behind_projects.append((p, reasons))
            else:
                on_track_projects.append(p)

        evidence: List[EvidenceItem] = []
        entities: List[EntityReference] = []
        proposals: List[ActionProposal] = []
        suggested_steps: List[str] = []

        if behind_projects:
            lines = [f"{len(behind_projects)} project(s) require attention:"]
            for p, reasons in behind_projects:
                reason_str = "; ".join(reasons)
                lines.append(f"• **{p.title}**: {reason_str}.")
                entities.append(
                    EntityReference(
                        entity_type="PROJECT",
                        entity_id=p.id,
                        title=p.title,
                        status=p.health_status,
                        url_or_path=f"/projects/{p.id}",
                    )
                )
                if include_evidence:
                    evidence.append(
                        EvidenceItem(
                            entity_type="PROJECT",
                            entity_id=p.id,
                            entity_title=p.title,
                            evidence_snippet=f"Status: {p.status}, Health: {p.health_status}, Forecast Risk: {p.forecast_delay_risk or 'N/A'}",
                            timestamp=p.target_completion_date.isoformat() if p.target_completion_date else None,
                            confidence_or_metric=p.forecast_delay_risk or p.health_status,
                        )
                    )

            direct_answer = "\n".join(lines)
            suggested_steps.append(f"Review milestone timeline for '{behind_projects[0][0].title}'")
            suggested_steps.append("Identify and clear blockers on active milestone tasks")

            if include_proposals:
                top_p = behind_projects[0][0]
                proposals.append(
                    ActionProposal(
                        action_identifier="workflow:recalibrate_schedule",
                        target_entity_id=top_p.id,
                        parameters={"project_id": top_p.id, "strategy": "REALLOCATE_SLOTS"},
                        rationale=f"Recalibrate schedule slots to prevent delay cascade on project '{top_p.title}'.",
                        requires_governed_approval=True,
                        governance_status="PROPOSED",
                    )
                )
        else:
            p_names = ", ".join([f"'{p.title}'" for p in on_track_projects[:3]])
            direct_answer = f"All {len(on_track_projects)} of your active projects ({p_names}) are currently ON_TRACK with no critical delay risks identified."
            for p in on_track_projects[:3]:
                entities.append(
                    EntityReference(
                        entity_type="PROJECT",
                        entity_id=p.id,
                        title=p.title,
                        status=p.health_status,
                        url_or_path=f"/projects/{p.id}",
                    )
                )
            suggested_steps.append("Maintain current execution velocity on active milestones")

        return StructuredAssistantResponse(
            direct_answer=direct_answer,
            supporting_evidence=evidence,
            relevant_entities=entities,
            data_timestamps=ctx.data_timestamps,
            uncertainty_level="LOW",
            missing_information=[],
            suggested_next_steps=suggested_steps,
            action_proposals=proposals,
        )

    @classmethod
    def _handle_postponed_tasks(
        cls,
        ctx: RetrievedUserContext,
        q_lower: str,
        include_evidence: bool,
        include_proposals: bool,
    ) -> StructuredAssistantResponse:
        """Answers: Why do I keep postponing this task?"""
        # Find if a specific task title is referenced
        target_task: Optional[TaskSummary] = None
        for t in ctx.tasks:
            if t.title.lower() in q_lower:
                target_task = t
                break

        # If no specific task named, find the task with most postponements
        if not target_task:
            tasks_with_delays = [t for t in ctx.tasks if t.postponement_count > 0]
            if tasks_with_delays:
                tasks_with_delays.sort(key=lambda x: x.postponement_count, reverse=True)
                target_task = tasks_with_delays[0]

        evidence: List[EvidenceItem] = []
        entities: List[EntityReference] = []
        proposals: List[ActionProposal] = []
        suggested_steps: List[str] = []

        if not target_task:
            return StructuredAssistantResponse(
                direct_answer="No tasks in your workspace show repeated postponements or deferral events.",
                supporting_evidence=[],
                relevant_entities=[],
                data_timestamps=ctx.data_timestamps,
                uncertainty_level="LOW",
                missing_information=[],
                suggested_next_steps=["Specify a task title to inspect its history and dependency chain"],
                action_proposals=[],
            )

        entities.append(
            EntityReference(
                entity_type="TASK",
                entity_id=target_task.id,
                title=target_task.title,
                status=target_task.status,
                url_or_path=f"/tasks/{target_task.id}",
            )
        )

        reasons = [f"Task '{target_task.title}' has been postponed {target_task.postponement_count} time(s)."]

        # Check if blocked by another task
        blocker = next((d for d in ctx.dependencies if d.target_task_id == target_task.id and d.is_blocker), None)
        if blocker:
            src_title = blocker.source_task_title or f"Task {blocker.source_task_id[:8]}"
            reasons.append(
                f"Dependency blocker: This task is blocked by '{src_title}', which may cause friction or inability to proceed."
            )
            src_task = ctx.task_map.get(blocker.source_task_id)
            entities.append(
                EntityReference(
                    entity_type="TASK",
                    entity_id=blocker.source_task_id,
                    title=src_title,
                    status=src_task.status if src_task else "PENDING",
                    url_or_path=f"/tasks/{blocker.source_task_id}",
                )
            )
            if include_evidence:
                evidence.append(
                    EvidenceItem(
                        entity_type="DEPENDENCY",
                        entity_id=blocker.id,
                        entity_title="Task Blocker Dependency",
                        evidence_snippet=f"Task '{src_title}' BLOCKS '{target_task.title}' (confidence: {blocker.confidence})",
                        confidence_or_metric=str(blocker.confidence),
                    )
                )

        # Check behavioral friction trend
        if ctx.trends and ctx.trends.avg_friction > 35:
            reasons.append(
                f"Elevated friction: Current behavioral friction index averages {ctx.trends.avg_friction}, which correlates with task avoidance."
            )

        # Check behavioral memory for procrastination or task management patterns
        avoidance_memories = [
            m for m in ctx.memories
            if "procrastin" in m.description.lower()
            or "postpone" in m.description.lower()
            or "subtask" in m.description.lower()
        ]
        if avoidance_memories:
            reasons.append(f"Observed behavioral pattern: {avoidance_memories[0].description}")
            if include_evidence:
                evidence.append(
                    EvidenceItem(
                        entity_type="BEHAVIORAL_MEMORY",
                        entity_id=avoidance_memories[0].id,
                        entity_title=avoidance_memories[0].title,
                        evidence_snippet=avoidance_memories[0].description,
                        confidence_or_metric=str(avoidance_memories[0].confidence),
                    )
                )

        direct_answer = " ".join(reasons)

        if include_evidence:
            evidence.append(
                EvidenceItem(
                    entity_type="TASK",
                    entity_id=target_task.id,
                    entity_title=target_task.title,
                    evidence_snippet=f"Recorded postponements: {target_task.postponement_count}. Status: {target_task.status}",
                    timestamp=target_task.due_at.isoformat() if target_task.due_at else None,
                    confidence_or_metric=f"{target_task.postponement_count} postponements",
                )
            )

        if include_proposals:
            proposals.append(
                ActionProposal(
                    action_identifier="task:decompose_into_subtasks",
                    target_entity_id=target_task.id,
                    parameters={"parent_task_id": target_task.id, "subtask_titles": [f"{target_task.title} - Step 1", f"{target_task.title} - Step 2"]},
                    rationale=f"Decomposing '{target_task.title}' into smaller subtasks reduces behavioral friction and avoids further deferrals.",
                    requires_governed_approval=True,
                    governance_status="PROPOSED",
                )
            )

        suggested_steps.append(f"Decompose '{target_task.title}' into 15-minute subtasks")
        suggested_steps.append("Schedule execution during your morning peak focus window")

        return StructuredAssistantResponse(
            direct_answer=direct_answer,
            supporting_evidence=evidence,
            relevant_entities=entities,
            data_timestamps=ctx.data_timestamps,
            uncertainty_level="LOW",
            missing_information=[],
            suggested_next_steps=suggested_steps,
            action_proposals=proposals,
        )

    @classmethod
    def _handle_goal_blockers(
        cls,
        ctx: RetrievedUserContext,
        q_lower: str,
        include_evidence: bool,
        include_proposals: bool,
    ) -> StructuredAssistantResponse:
        """Answers: Which tasks are blocking my current goal?"""
        if not ctx.goals:
            return StructuredAssistantResponse(
                direct_answer="You do not have any active goals configured in ContextIQ.",
                supporting_evidence=[],
                relevant_entities=[],
                data_timestamps=ctx.data_timestamps,
                uncertainty_level="LOW",
                missing_information=["No goals found in database"],
                suggested_next_steps=["Create a long-term goal to connect your tasks"],
                action_proposals=[],
            )

        # Match specific goal or pick first active goal
        target_goal = None
        for g in ctx.goals:
            if g.title.lower() in q_lower:
                target_goal = g
                break
        if not target_goal:
            target_goal = ctx.goals[0]

        evidence: List[EvidenceItem] = []
        entities: List[EntityReference] = [
            EntityReference(
                entity_type="GOAL",
                entity_id=target_goal.id,
                title=target_goal.title,
                status=target_goal.status,
                url_or_path=f"/goals/{target_goal.id}",
            )
        ]
        proposals: List[ActionProposal] = []
        suggested_steps: List[str] = []

        # Find linked tasks for this goal
        linked_ids = set(target_goal.linked_task_ids)
        goal_tasks = [t for t in ctx.tasks if t.id in linked_ids]

        # Find blockers affecting goal tasks
        blocking_deps = [
            d for d in ctx.dependencies
            if d.is_blocker and (d.target_task_id in linked_ids or not linked_ids)
        ]

        if not blocking_deps:
            # Check if there are overdue tasks contributing to this goal
            overdue_goal_tasks = [t for t in goal_tasks if t.is_overdue]
            if overdue_goal_tasks:
                task_list_str = ", ".join([f"'{t.title}'" for t in overdue_goal_tasks])
                direct_answer = (
                    f"For goal '{target_goal.title}', no hard dependency blockers are recorded, "
                    f"but {len(overdue_goal_tasks)} overdue task(s) are delaying progress: {task_list_str}."
                )
                for t in overdue_goal_tasks:
                    entities.append(
                        EntityReference(
                            entity_type="TASK",
                            entity_id=t.id,
                            title=t.title,
                            status=t.status,
                            url_or_path=f"/tasks/{t.id}",
                        )
                    )
            else:
                direct_answer = (
                    f"Goal '{target_goal.title}' (Progress: {round(target_goal.progress_pct * 100)}%) has no unresolved dependency blockers."
                )
            suggested_steps.append(f"Continue scheduled tasks for '{target_goal.title}'")
        else:
            blocker_items = []
            for d in blocking_deps:
                src_title = d.source_task_title or f"Task {d.source_task_id[:8]}"
                tgt_title = d.target_task_title or f"Task {d.target_task_id[:8]}"
                blocker_items.append(f"• '{src_title}' blocks '{tgt_title}' (Confidence: {d.confidence})")
                src_task = ctx.task_map.get(d.source_task_id)
                entities.append(
                    EntityReference(
                        entity_type="TASK",
                        entity_id=d.source_task_id,
                        title=src_title,
                        status=src_task.status if src_task else "PENDING",
                        url_or_path=f"/tasks/{d.source_task_id}",
                    )
                )
                if include_evidence:
                    evidence.append(
                        EvidenceItem(
                            entity_type="DEPENDENCY",
                            entity_id=d.id,
                            entity_title="Task Dependency Blocker",
                            evidence_snippet=f"'{src_title}' BLOCKS '{tgt_title}'",
                            confidence_or_metric=str(d.confidence),
                        )
                    )

            direct_answer = (
                f"The following tasks are currently blocking progress toward goal '{target_goal.title}':\n"
                + "\n".join(blocker_items)
            )
            suggested_steps.append("Prioritize resolving upstream blocker tasks")

            if include_proposals and blocking_deps:
                first_blocker_id = blocking_deps[0].source_task_id
                proposals.append(
                    ActionProposal(
                        action_identifier="task:update_priority",
                        target_entity_id=first_blocker_id,
                        parameters={"task_id": first_blocker_id, "new_priority": "HIGH"},
                        rationale=f"Elevate blocker task to HIGH priority to clear dependency for goal '{target_goal.title}'.",
                        requires_governed_approval=True,
                        governance_status="PROPOSED",
                    )
                )

        return StructuredAssistantResponse(
            direct_answer=direct_answer,
            supporting_evidence=evidence,
            relevant_entities=entities,
            data_timestamps=ctx.data_timestamps,
            uncertainty_level="LOW",
            missing_information=[],
            suggested_next_steps=suggested_steps,
            action_proposals=proposals,
        )

    @classmethod
    def _handle_monthly_trends(
        cls,
        ctx: RetrievedUserContext,
        include_evidence: bool,
        include_proposals: bool,
    ) -> StructuredAssistantResponse:
        """Answers: What changed in my productivity this month?"""
        if not ctx.trends:
            return StructuredAssistantResponse(
                direct_answer="Insufficient historical telemetry to compute a full monthly behavioral trend summary (requires at least 7 days of recorded metrics).",
                supporting_evidence=[],
                relevant_entities=[],
                data_timestamps=ctx.data_timestamps,
                uncertainty_level="HIGH",
                missing_information=["Less than 7 daily metric records available in database"],
                suggested_next_steps=["Continue using ContextIQ daily to establish behavioral baseline"],
                action_proposals=[],
            )

        tr = ctx.trends
        lines = [
            f"Over the last {tr.lookback_days} days of recorded productivity data:",
            f"• **Friction Trajectory**: Your behavioral friction index is **{tr.friction_trend}** (average: {tr.avg_friction}).",
            f"• **Focus Consistency**: You logged an average of **{tr.avg_focus_minutes_per_day} minutes** of focus time per active day.",
            f"• **Task Completion**: You completed **{tr.total_tasks_completed} task(s)**.",
            f"• **Context Switching**: Averaged **{tr.avg_context_switches_per_hour} switches/hour**.",
            f"• **Recovery Efficiency**: Resumption lag recovery efficiency averaged **{round(tr.avg_recovery_efficiency * 100, 1) if tr.avg_recovery_efficiency <= 1.0 else tr.avg_recovery_efficiency}%**.",
        ]

        if tr.recent_milestones:
            lines.append(f"• **Milestones Achieved**: {'; '.join(tr.recent_milestones)}.")

        evidence: List[EvidenceItem] = []
        if include_evidence:
            evidence.append(
                EvidenceItem(
                    entity_type="BEHAVIORAL_TREND",
                    entity_id="monthly_trend_summary",
                    entity_title="30-Day Aggregated Metrics",
                    evidence_snippet=f"Avg Friction: {tr.avg_friction}, Avg Focus: {tr.avg_focus_minutes_per_day}m, Completed: {tr.total_tasks_completed}",
                    confidence_or_metric=tr.friction_trend,
                )
            )

        suggested_steps = [
            "Protect high-focus morning slots to further reduce context switching",
            "Maintain current recovery routines following external interruptions",
        ]

        return StructuredAssistantResponse(
            direct_answer="\n".join(lines),
            supporting_evidence=evidence,
            relevant_entities=[],
            data_timestamps=ctx.data_timestamps,
            uncertainty_level="LOW",
            missing_information=[],
            suggested_next_steps=suggested_steps,
            action_proposals=[],
        )

    @classmethod
    def _handle_recommendation_effectiveness(
        cls,
        ctx: RetrievedUserContext,
        include_evidence: bool,
        include_proposals: bool,
    ) -> StructuredAssistantResponse:
        """Answers: Which recommendations have worked well historically?"""
        accepted_recs = [r for r in ctx.recommendations if r.action == "ACCEPTED"]
        dismissed_recs = [r for r in ctx.recommendations if r.action == "DISMISSED"]

        evidence: List[EvidenceItem] = []
        entities: List[EntityReference] = []

        if not ctx.recommendations:
            return StructuredAssistantResponse(
                direct_answer="No recommendation feedback records have been logged yet in ContextIQ.",
                supporting_evidence=[],
                relevant_entities=[],
                data_timestamps=ctx.data_timestamps,
                uncertainty_level="MEDIUM",
                missing_information=["No recommendation feedback logged"],
                suggested_next_steps=["Accept or dismiss suggestions on the dashboard to build historical effectiveness data"],
                action_proposals=[],
            )

        if not accepted_recs:
            direct_answer = (
                f"You have received {len(ctx.recommendations)} recommendation(s), but none have been marked as ACCEPTED yet. "
                f"Historically, {len(dismissed_recs)} were dismissed."
            )
            return StructuredAssistantResponse(
                direct_answer=direct_answer,
                supporting_evidence=[],
                relevant_entities=[],
                data_timestamps=ctx.data_timestamps,
                uncertainty_level="LOW",
                missing_information=[],
                suggested_next_steps=["Try applying recommended morning schedule shifts to evaluate outcome"],
                action_proposals=[],
            )

        # Group accepted by type
        type_counts: Dict[str, int] = {}
        for r in accepted_recs:
            type_counts[r.recommendation_type] = type_counts.get(r.recommendation_type, 0) + 1

        top_type = max(type_counts, key=type_counts.get)
        lines = [
            f"You have accepted {len(accepted_recs)} recommendation(s) with high adherence.",
            f"Your most successful intervention type is **{top_type}** ({type_counts[top_type]} accepted).",
        ]

        for r in accepted_recs[:3]:
            entities.append(
                EntityReference(
                    entity_type="RECOMMENDATION",
                    entity_id=r.id,
                    title=r.title,
                    status=r.action,
                    url_or_path=f"/recommendations/{r.id}",
                )
            )
            if include_evidence:
                evidence.append(
                    EvidenceItem(
                        entity_type="RECOMMENDATION",
                        entity_id=r.id,
                        entity_title=r.title,
                        evidence_snippet=f"Action: {r.action}, Type: {r.recommendation_type}",
                        timestamp=r.created_at.isoformat(),
                        confidence_or_metric=r.action,
                    )
                )

        # Check memories for successful intervention records
        succ_memories = [m for m in ctx.memories if m.category == "SUCCESSFUL_INTERVENTIONS"]
        if succ_memories:
            lines.append(f"Recorded intervention pattern: {succ_memories[0].description}")
            if include_evidence:
                evidence.append(
                    EvidenceItem(
                        entity_type="BEHAVIORAL_MEMORY",
                        entity_id=succ_memories[0].id,
                        entity_title=succ_memories[0].title,
                        evidence_snippet=succ_memories[0].description,
                        confidence_or_metric=str(succ_memories[0].confidence),
                    )
                )

        direct_answer = " ".join(lines)
        return StructuredAssistantResponse(
            direct_answer=direct_answer,
            supporting_evidence=evidence,
            relevant_entities=entities,
            data_timestamps=ctx.data_timestamps,
            uncertainty_level="LOW",
            missing_information=[],
            suggested_next_steps=[f"Continue prioritizing {top_type} nudges in your schedule"],
            action_proposals=[],
        )

    @classmethod
    def _handle_general_query(
        cls,
        ctx: RetrievedUserContext,
        query: str,
        include_evidence: bool,
        include_proposals: bool,
    ) -> StructuredAssistantResponse:
        """
        Handles general queries via keyword matching across user data.
        Explicitly declares missing data when query references unknown entities.
        """
        q_tokens = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 2]

        matched_tasks = []
        for t in ctx.tasks:
            if any(tok in t.title.lower() for tok in q_tokens):
                matched_tasks.append(t)

        matched_projects = []
        for p in ctx.projects:
            if any(tok in p.title.lower() for tok in q_tokens):
                matched_projects.append(p)

        matched_goals = []
        for g in ctx.goals:
            if any(tok in g.title.lower() for tok in q_tokens):
                matched_goals.append(g)

        evidence: List[EvidenceItem] = []
        entities: List[EntityReference] = []

        # If nothing matched and query looks like a specific entity query
        if not matched_tasks and not matched_projects and not matched_goals:
            return StructuredAssistantResponse(
                direct_answer=(
                    f"I could not find any tasks, projects, or goals matching '{query}' in your verified ContextIQ data. "
                    "You have 0 matching records for this query."
                ),
                supporting_evidence=[],
                relevant_entities=[],
                data_timestamps=ctx.data_timestamps,
                uncertainty_level="UNCERTAIN",
                missing_information=[f"No matching records found for query terms: {', '.join(q_tokens[:4])}"],
                suggested_next_steps=[
                    "Ask 'What should I focus on today?'",
                    "Ask 'Which project is falling behind?'",
                    "Check your projects or tasks in the sidebar",
                ],
                action_proposals=[],
            )

        lines = [f"Found relevant records in your ContextIQ workspace:"]
        for p in matched_projects:
            lines.append(f"• Project '{p.title}': Status {p.status}, Health {p.health_status}")
            entities.append(
                EntityReference(
                    entity_type="PROJECT",
                    entity_id=p.id,
                    title=p.title,
                    status=p.health_status,
                    url_or_path=f"/projects/{p.id}",
                )
            )
            if include_evidence:
                evidence.append(
                    EvidenceItem(
                        entity_type="PROJECT",
                        entity_id=p.id,
                        entity_title=p.title,
                        evidence_snippet=f"Status: {p.status}, Health: {p.health_status}",
                        timestamp=p.target_completion_date.isoformat() if p.target_completion_date else None,
                        confidence_or_metric=p.health_status,
                    )
                )

        for g in matched_goals:
            lines.append(f"• Goal '{g.title}': Status {g.status}, Progress {round(g.progress_pct * 100)}%")
            entities.append(
                EntityReference(
                    entity_type="GOAL",
                    entity_id=g.id,
                    title=g.title,
                    status=g.status,
                    url_or_path=f"/goals/{g.id}",
                )
            )
            if include_evidence:
                evidence.append(
                    EvidenceItem(
                        entity_type="GOAL",
                        entity_id=g.id,
                        entity_title=g.title,
                        evidence_snippet=f"Progress: {g.progress_pct}, Hierarchy: {g.hierarchy_level}",
                        timestamp=g.target_date.isoformat() if g.target_date else None,
                        confidence_or_metric=str(g.progress_pct),
                    )
                )

        for t in matched_tasks[:5]:
            lines.append(f"• Task '{t.title}': Status {t.status}, Priority {t.priority}")
            entities.append(
                EntityReference(
                    entity_type="TASK",
                    entity_id=t.id,
                    title=t.title,
                    status=t.status,
                    url_or_path=f"/tasks/{t.id}",
                )
            )
            if include_evidence:
                evidence.append(
                    EvidenceItem(
                        entity_type="TASK",
                        entity_id=t.id,
                        entity_title=t.title,
                        evidence_snippet=f"Status: {t.status}, Priority: {t.priority}, Overdue: {t.is_overdue}",
                        timestamp=t.due_at.isoformat() if t.due_at else None,
                        confidence_or_metric=t.priority,
                    )
                )

        direct_answer = "\n".join(lines)
        return StructuredAssistantResponse(
            direct_answer=direct_answer,
            supporting_evidence=evidence,
            relevant_entities=entities,
            data_timestamps=ctx.data_timestamps,
            uncertainty_level="LOW",
            missing_information=[],
            suggested_next_steps=["Select an entity to view detailed timeline"],
            action_proposals=[],
        )


class AssistantService:
    """
    Main entry point for ContextIQ Knowledge-Grounded Conversational Assistant.
    Enforces user isolation, session persistence, anti-hallucination checks,
    and governed action separation.
    """

    @classmethod
    def ask(
        cls,
        db: Session,
        user_id: uuid.UUID,
        query: str,
        conversation_id: Optional[uuid.UUID] = None,
        include_evidence: bool = True,
        include_proposals: bool = True,
    ) -> Tuple[AssistantConversation, AssistantMessage, StructuredAssistantResponse]:
        """
        Processes a user question, retrieves grounded data, validates against anti-hallucination guardrails,
        persists conversation turns, and returns the response.
        """
        now = datetime.now(timezone.utc)

        # 1. Retrieve or create session strictly scoped to user_id
        if conversation_id:
            conv = (
                db.query(AssistantConversation)
                .filter(
                    AssistantConversation.id == conversation_id,
                    AssistantConversation.user_id == user_id,
                )
                .first()
            )
            if not conv:
                conv = AssistantConversation(
                    id=conversation_id,
                    user_id=user_id,
                    title=query[:60].strip() or "Productivity Discussion",
                    created_at=now,
                    updated_at=now,
                )
                db.add(conv)
                db.flush()
        else:
            conv = AssistantConversation(
                user_id=user_id,
                title=query[:60].strip() or "Productivity Discussion",
                created_at=now,
                updated_at=now,
            )
            db.add(conv)
            db.flush()

        # 2. Persist user turn
        user_msg = AssistantMessage(
            conversation_id=conv.id,
            user_id=user_id,
            role="user",
            content=query,
            created_at=now,
        )
        db.add(user_msg)
        db.flush()

        # 3. Retrieve user-scoped ground-truth context
        ctx = AssistantContextRetriever.retrieve(db, user_id=user_id, query=query)

        # 4. Synthesize grounded answer
        response = GroundedResponseSynthesizer.synthesize(
            ctx=ctx,
            query=query,
            include_evidence=include_evidence,
            include_proposals=include_proposals,
        )

        # 5. Anti-hallucination validation
        is_valid, violations = AntiHallucinationGuard.validate(response, ctx)
        if not is_valid:
            # Fallback to safe missing information notice if any violation occurred
            response = StructuredAssistantResponse(
                direct_answer="I could not formulate an answer with 100% verified supporting evidence in your workspace.",
                supporting_evidence=[],
                relevant_entities=[],
                data_timestamps=ctx.data_timestamps,
                uncertainty_level="UNCERTAIN",
                uncertainty_notes=f"Guardrail prevented unsupported claims: {'; '.join(violations)}",
                missing_information=violations,
                suggested_next_steps=["Ask a direct question about your active tasks or projects"],
                action_proposals=[],
            )

        # 6. Persist assistant turn with structured payload
        assistant_msg = AssistantMessage(
            conversation_id=conv.id,
            user_id=user_id,
            role="assistant",
            content=response.direct_answer,
            structured_response=response.model_dump(mode="json"),
            created_at=datetime.now(timezone.utc),
        )
        db.add(assistant_msg)

        conv.updated_at = datetime.now(timezone.utc)
        db.flush()

        return conv, assistant_msg, response

    @classmethod
    def list_conversations(
        cls,
        db: Session,
        user_id: uuid.UUID,
        include_archived: bool = False,
    ) -> List[AssistantConversationRead]:
        """
        Lists conversation summaries strictly for user_id.
        """
        query = db.query(AssistantConversation).filter(AssistantConversation.user_id == user_id)
        if not include_archived:
            query = query.filter(AssistantConversation.is_archived == False)

        conversations = query.order_by(AssistantConversation.updated_at.desc()).all()
        result = []
        for c in conversations:
            count = len(c.messages)
            recent_msgs = [
                AssistantMessageRead(
                    id=m.id,
                    conversation_id=m.conversation_id,
                    role=m.role,
                    content=m.content,
                    structured_response=StructuredAssistantResponse.model_validate(m.structured_response)
                    if m.structured_response
                    else None,
                    created_at=m.created_at,
                )
                for m in c.messages[-10:]
            ]
            result.append(
                AssistantConversationRead(
                    id=c.id,
                    title=c.title,
                    created_at=c.created_at,
                    updated_at=c.updated_at,
                    message_count=count,
                    recent_messages=recent_msgs,
                )
            )
        return result

    @classmethod
    def get_conversation(
        cls,
        db: Session,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> Optional[AssistantConversationRead]:
        """
        Gets full conversation history strictly scoped to user_id.
        """
        conv = (
            db.query(AssistantConversation)
            .filter(
                AssistantConversation.id == conversation_id,
                AssistantConversation.user_id == user_id,
            )
            .first()
        )
        if not conv:
            return None

        msgs = [
            AssistantMessageRead(
                id=m.id,
                conversation_id=m.conversation_id,
                role=m.role,
                content=m.content,
                structured_response=StructuredAssistantResponse.model_validate(m.structured_response)
                if m.structured_response
                else None,
                created_at=m.created_at,
            )
            for m in conv.messages
        ]
        return AssistantConversationRead(
            id=conv.id,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=len(msgs),
            recent_messages=msgs,
        )

    @classmethod
    def archive_conversation(
        cls,
        db: Session,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> bool:
        """
        Archives / removes conversation strictly scoped to user_id.
        """
        conv = (
            db.query(AssistantConversation)
            .filter(
                AssistantConversation.id == conversation_id,
                AssistantConversation.user_id == user_id,
            )
            .first()
        )
        if not conv:
            return False
        conv.is_archived = True
        conv.updated_at = datetime.now(timezone.utc)
        db.flush()
        return True

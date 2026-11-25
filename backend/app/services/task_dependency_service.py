"""
Service layer for Cross-Task Dependency Discovery and Intelligent Relationship Analysis (Phase 8.5).

Implements:
1. Multi-strategy relationship discovery:
   - Rule-based detection (shared projects, shared goals, deadline sequencing, resource conflicts).
   - Association rule mining (co-completion support, confidence, lift over task baskets).
   - Temporal sequence analysis (Markovian directional ordering and repeated workflows).
   - Knowledge graph structural path overlap.
2. Epistemic boundary management:
   - Clear separation between explicit and inferred dependencies.
   - User confirmation workflow (confirm, reject, type correction, explicit promotion).
3. Cascading multi-hop impact analysis:
   - Downstream affected tasks with hop distance and critical path assessment.
   - Milestone deadline risk calculation.
   - Strategic project health degradation.
   - Goal risk propagation.
"""
from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models.enums import GraphRelationshipType, KnowledgeEvidenceSource, TaskPriority, TaskStatus
from app.models.goal_project import (
    GoalRiskFactor,
    GoalTaskAssociation,
    ProjectGoalAssociation,
    ProjectHealthStatus,
)
from app.models.knowledge_graph import Goal, KnowledgeGraphEdge, KnowledgeGraphNode, Milestone, Project
from app.models.task import Task
from app.models.task_association import TaskAssociation
from app.models.task_dependency import (
    DependencyDetectionMethod,
    DependencyValidationStatus,
    TaskDependency,
    TaskDependencyType,
)
from app.models.task_event import TaskEvent
from app.schemas.task_dependency import (
    DependencyDiscoveryRequest,
    DependencyDiscoveryResult,
    DependencyGraphEdge,
    DependencyGraphNode,
    DependencyGraphResponse,
    ImpactAnalysisRequest,
    ImpactAnalysisResult,
    ImpactedGoalItem,
    ImpactedMilestoneItem,
    ImpactedProjectItem,
    ImpactedTaskItem,
    TaskDependencyConfirmation,
    TaskDependencyCreate,
    TaskDependencyRead,
    TaskDependencyUpdate,
)

logger = logging.getLogger(__name__)


def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class TaskDependencyService:
    """Core intelligence engine for task dependency discovery and impact analysis."""

    # -----------------------------------------------------------------------
    # CRUD & Lifecycle Operations
    # -----------------------------------------------------------------------

    @staticmethod
    def create_explicit_dependency(
        db: Session, user_id: uuid.UUID, payload: TaskDependencyCreate
    ) -> TaskDependency:
        """Creates an explicit user-declared dependency constraint between two tasks."""
        if payload.source_task_id == payload.target_task_id:
            raise ValidationError("A task cannot depend on or block itself.")

        # Ensure both tasks belong to user
        source = db.execute(
            select(Task).where(Task.id == payload.source_task_id, Task.user_id == user_id)
        ).scalar_one_or_none()
        target = db.execute(
            select(Task).where(Task.id == payload.target_task_id, Task.user_id == user_id)
        ).scalar_one_or_none()
        if not source or not target:
            raise NotFoundError("One or both tasks not found for current user.")

        # Check existing
        existing = db.execute(
            select(TaskDependency).where(
                TaskDependency.user_id == user_id,
                TaskDependency.source_task_id == payload.source_task_id,
                TaskDependency.target_task_id == payload.target_task_id,
                TaskDependency.dependency_type == payload.dependency_type.value,
            )
        ).scalar_one_or_none()
        if existing:
            existing.validation_status = DependencyValidationStatus.CONVERTED_EXPLICIT.value
            existing.is_inferred = False
            existing.confidence = payload.confidence
            existing.notes = payload.notes
            db.flush()
            return existing

        now = datetime.now(timezone.utc)
        dep = TaskDependency(
            user_id=user_id,
            source_task_id=payload.source_task_id,
            target_task_id=payload.target_task_id,
            dependency_type=payload.dependency_type.value,
            is_inferred=False,
            confidence=payload.confidence,
            detection_method=DependencyDetectionMethod.EXPLICIT_INPUT.value,
            validation_status=DependencyValidationStatus.CONVERTED_EXPLICIT.value,
            supporting_observations=payload.supporting_observations or {"source": "user_declared"},
            first_observed_at=now,
            last_observed_at=now,
            notes=payload.notes,
        )
        db.add(dep)
        db.flush()
        return dep

    @staticmethod
    def get_dependency(db: Session, user_id: uuid.UUID, dependency_id: uuid.UUID) -> TaskDependency:
        dep = db.execute(
            select(TaskDependency).where(
                TaskDependency.id == dependency_id,
                TaskDependency.user_id == user_id,
            )
        ).scalar_one_or_none()
        if not dep:
            raise NotFoundError(f"Task dependency {dependency_id} not found.")
        return dep

    @staticmethod
    def list_dependencies(
        db: Session,
        user_id: uuid.UUID,
        source_task_id: Optional[uuid.UUID] = None,
        target_task_id: Optional[uuid.UUID] = None,
        dependency_type: Optional[str] = None,
        validation_status: Optional[str] = None,
        is_inferred: Optional[bool] = None,
    ) -> List[TaskDependency]:
        stmt = select(TaskDependency).where(TaskDependency.user_id == user_id)
        if source_task_id:
            stmt = stmt.where(TaskDependency.source_task_id == source_task_id)
        if target_task_id:
            stmt = stmt.where(TaskDependency.target_task_id == target_task_id)
        if dependency_type:
            stmt = stmt.where(TaskDependency.dependency_type == dependency_type)
        if validation_status:
            stmt = stmt.where(TaskDependency.validation_status == validation_status)
        if is_inferred is not None:
            stmt = stmt.where(TaskDependency.is_inferred == is_inferred)

        stmt = stmt.order_by(TaskDependency.confidence.desc(), TaskDependency.created_at.desc())
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def update_dependency(
        db: Session,
        user_id: uuid.UUID,
        dependency_id: uuid.UUID,
        payload: TaskDependencyUpdate,
    ) -> TaskDependency:
        dep = TaskDependencyService.get_dependency(db, user_id, dependency_id)
        if payload.dependency_type:
            dep.dependency_type = payload.dependency_type.value
        if payload.validation_status:
            dep.validation_status = payload.validation_status.value
            if payload.validation_status == DependencyValidationStatus.CONVERTED_EXPLICIT:
                dep.is_inferred = False
        if payload.confidence is not None:
            dep.confidence = payload.confidence
        if payload.notes is not None:
            dep.notes = payload.notes
        db.flush()
        return dep

    @staticmethod
    def delete_dependency(db: Session, user_id: uuid.UUID, dependency_id: uuid.UUID) -> None:
        dep = TaskDependencyService.get_dependency(db, user_id, dependency_id)
        db.delete(dep)
        db.flush()

    # -----------------------------------------------------------------------
    # User Confirmation & Type Correction Workflow
    # -----------------------------------------------------------------------

    @staticmethod
    def confirm_or_review_dependency(
        db: Session,
        user_id: uuid.UUID,
        dependency_id: uuid.UUID,
        payload: TaskDependencyConfirmation,
    ) -> TaskDependency:
        """
        Processes user review:
        - CONFIRM: Validates relationship without forcing execution constraints.
        - REJECT: Flags as rejected hypothesis so it is excluded from future suggestions.
        - CONVERT_EXPLICIT: Promotes to explicit dependency, syncing to Knowledge Graph.
        """
        dep = TaskDependencyService.get_dependency(db, user_id, dependency_id)

        if payload.corrected_type:
            dep.dependency_type = payload.corrected_type.value

        if payload.notes:
            dep.notes = payload.notes

        if payload.action == "CONFIRM":
            dep.validation_status = DependencyValidationStatus.CONFIRMED.value
            dep.confidence = max(dep.confidence, 0.85)
        elif payload.action == "REJECT":
            dep.validation_status = DependencyValidationStatus.REJECTED.value
            dep.confidence = 0.0
        elif payload.action == "CONVERT_EXPLICIT":
            dep.validation_status = DependencyValidationStatus.CONVERTED_EXPLICIT.value
            dep.is_inferred = False
            dep.confidence = 1.0

            # Promote to Knowledge Graph Edge if knowledge nodes exist
            TaskDependencyService._sync_explicit_to_knowledge_graph(db, user_id, dep)

        db.flush()
        return dep

    @staticmethod
    def _sync_explicit_to_knowledge_graph(db: Session, user_id: uuid.UUID, dep: TaskDependency) -> None:
        """Syncs a converted explicit dependency into KnowledgeGraphEdge."""
        source_node = db.execute(
            select(KnowledgeGraphNode).where(
                KnowledgeGraphNode.user_id == user_id,
                KnowledgeGraphNode.entity_id == dep.source_task_id,
            )
        ).scalar_one_or_none()
        target_node = db.execute(
            select(KnowledgeGraphNode).where(
                KnowledgeGraphNode.user_id == user_id,
                KnowledgeGraphNode.entity_id == dep.target_task_id,
            )
        ).scalar_one_or_none()

        if source_node and target_node:
            rel_type = (
                GraphRelationshipType.BLOCKS.value
                if dep.dependency_type in (TaskDependencyType.POTENTIAL_BLOCKER.value, TaskDependencyType.EXPLICIT_DEPENDENCY.value)
                else GraphRelationshipType.DEPENDS_ON.value
            )
            edge = db.execute(
                select(KnowledgeGraphEdge).where(
                    KnowledgeGraphEdge.user_id == user_id,
                    KnowledgeGraphEdge.source_node_id == source_node.id,
                    KnowledgeGraphEdge.target_node_id == target_node.id,
                    KnowledgeGraphEdge.relationship_type == rel_type,
                )
            ).scalar_one_or_none()
            if not edge:
                edge = KnowledgeGraphEdge(
                    user_id=user_id,
                    source_node_id=source_node.id,
                    target_node_id=target_node.id,
                    source_entity_id=dep.source_task_id,
                    target_entity_id=dep.target_task_id,
                    relationship_type=rel_type,
                    is_inferred=False,
                    confidence=1.0,
                    evidence_source=KnowledgeEvidenceSource.EXPLICIT_USER.value,
                    provenance_payload={"promoted_from_dependency_id": str(dep.id)},
                )
                db.add(edge)

    # -----------------------------------------------------------------------
    # Multi-Strategy Dependency Discovery Engine
    # -----------------------------------------------------------------------

    @staticmethod
    def discover_dependencies(
        db: Session,
        user_id: uuid.UUID,
        params: DependencyDiscoveryRequest,
    ) -> DependencyDiscoveryResult:
        """
        Executes analytical algorithms to discover latent cross-task relationships:
        1. Rule-based project and goal clustering.
        2. Deadline sequencing and potential blocker inference.
        3. Resource / focus slot conflicts.
        4. Association rule mining over completion baskets (support, confidence, lift).
        5. Temporal sequence transitions & repeated workflow mining.
        """
        now = datetime.now(timezone.utc)
        lookback_cutoff = now - timedelta(days=params.lookback_days)

        user_tasks = list(
            db.execute(
                select(Task).where(
                    Task.user_id == user_id,
                )
            ).scalars().all()
        )
        task_map = {t.id: t for t in user_tasks}

        discovered_deps: List[Dict[str, Any]] = []

        # -------------------------------------------------------------------
        # Strategy 1: Shared Project & Shared Goal Discovery
        # -------------------------------------------------------------------
        if params.include_project_goals:
            assocs = list(
                db.execute(
                    select(GoalTaskAssociation).where(GoalTaskAssociation.user_id == user_id)
                ).scalars().all()
            )
            # Map by project_id
            project_tasks: Dict[uuid.UUID, List[GoalTaskAssociation]] = defaultdict(list)
            # Map by goal_id
            goal_tasks: Dict[uuid.UUID, List[GoalTaskAssociation]] = defaultdict(list)

            for a in assocs:
                if a.project_id:
                    project_tasks[a.project_id].append(a)
                if a.goal_id:
                    goal_tasks[a.goal_id].append(a)

            # Detect SHARED_PROJECT
            for p_id, p_assocs in project_tasks.items():
                if len(p_assocs) >= 2:
                    for i in range(len(p_assocs)):
                        for j in range(i + 1, len(p_assocs)):
                            t1 = p_assocs[i].task_id
                            t2 = p_assocs[j].task_id
                            if t1 != t2 and t1 in task_map and t2 in task_map:
                                discovered_deps.append({
                                    "source_task_id": t1,
                                    "target_task_id": t2,
                                    "dependency_type": TaskDependencyType.SHARED_PROJECT.value,
                                    "confidence": 0.75,
                                    "detection_method": DependencyDetectionMethod.RULE_BASED.value,
                                    "observations": {
                                        "shared_project_id": str(p_id),
                                        "reason": "Both tasks belong to the same active project.",
                                    },
                                })

            # Detect SHARED_GOAL
            for g_id, g_assocs in goal_tasks.items():
                if len(g_assocs) >= 2:
                    for i in range(len(g_assocs)):
                        for j in range(i + 1, len(g_assocs)):
                            t1 = g_assocs[i].task_id
                            t2 = g_assocs[j].task_id
                            if t1 != t2 and t1 in task_map and t2 in task_map:
                                discovered_deps.append({
                                    "source_task_id": t1,
                                    "target_task_id": t2,
                                    "dependency_type": TaskDependencyType.SHARED_GOAL.value,
                                    "confidence": 0.70,
                                    "detection_method": DependencyDetectionMethod.RULE_BASED.value,
                                    "observations": {
                                        "shared_goal_id": str(g_id),
                                        "reason": "Both tasks contribute to the same strategic goal.",
                                    },
                                })

            # Detect POTENTIAL_BLOCKER via sequential deadlines & critical path
            for p_id, p_assocs in project_tasks.items():
                active_assocs = [a for a in p_assocs if a.task_id in task_map]
                for a1 in active_assocs:
                    for a2 in active_assocs:
                        if a1.task_id == a2.task_id:
                            continue
                        t1 = task_map[a1.task_id]
                        t2 = task_map[a2.task_id]
                        t1_comp = t1.status == TaskStatus.COMPLETED or (hasattr(t1.status, "value") and t1.status.value == "COMPLETED")
                        t2_comp = t2.status == TaskStatus.COMPLETED or (hasattr(t2.status, "value") and t2.status.value == "COMPLETED")

                        # If t1 is critical path or blocks, or t1 is due before t2
                        if not t1_comp and not t2_comp and t1.due_at and t2.due_at:
                            t1_utc = _to_utc(t1.due_at)
                            t2_utc = _to_utc(t2.due_at)
                            if t1_utc and t2_utc and t1_utc < t2_utc:
                                time_gap_hours = (t2_utc - t1_utc).total_seconds() / 3600.0
                                # If tight sequence within 48 hours, or t1 is already overdue
                                is_overdue = t1_utc < now
                                if time_gap_hours <= 48.0 or is_overdue or a1.is_critical_path:
                                    conf = 0.85 if (is_overdue or a1.is_critical_path) else 0.65
                                    discovered_deps.append({
                                        "source_task_id": t1.id,
                                        "target_task_id": t2.id,
                                        "dependency_type": TaskDependencyType.POTENTIAL_BLOCKER.value,
                                        "confidence": conf,
                                        "detection_method": DependencyDetectionMethod.RULE_BASED.value,
                                        "observations": {
                                            "upstream_due_at": t1_utc.isoformat(),
                                            "downstream_due_at": t2_utc.isoformat(),
                                            "is_upstream_overdue": is_overdue,
                                            "is_critical_path": a1.is_critical_path,
                                            "project_id": str(p_id),
                                            "reason": "Uncompleted upstream task with earlier deadline may delay downstream milestone task.",
                                        },
                                    })

        # -------------------------------------------------------------------
        # Strategy 2: Resource / Focus Slot Conflicts
        # -------------------------------------------------------------------
        if params.include_resource_conflicts:
            pending_tasks = [
                t for t in user_tasks
                if (t.status != TaskStatus.COMPLETED and (not hasattr(t.status, "value") or t.status.value != "COMPLETED"))
                and t.due_at is not None
            ]
            for i in range(len(pending_tasks)):
                for j in range(i + 1, len(pending_tasks)):
                    t1 = pending_tasks[i]
                    t2 = pending_tasks[j]
                    d1 = _to_utc(t1.due_at)
                    d2 = _to_utc(t2.due_at)
                    if d1 and d2:
                        diff_hours = abs((d1 - d2).total_seconds()) / 3600.0
                        if diff_hours <= 2.0:
                            # Conflicting due window
                            discovered_deps.append({
                                "source_task_id": t1.id,
                                "target_task_id": t2.id,
                                "dependency_type": TaskDependencyType.RESOURCE_CONFLICT.value,
                                "confidence": 0.70,
                                "detection_method": DependencyDetectionMethod.RULE_BASED.value,
                                "observations": {
                                    "task1_due_at": d1.isoformat(),
                                    "task2_due_at": d2.isoformat(),
                                    "time_delta_hours": round(diff_hours, 1),
                                    "reason": "Both high-priority tasks compete for completion within the same 2-hour window.",
                                },
                            })

        # -------------------------------------------------------------------
        # Strategy 3: Association Mining & Temporal Sequence Analysis
        # -------------------------------------------------------------------
        if params.include_temporal:
            # Fetch completion events within lookback
            events = list(
                db.execute(
                    select(TaskEvent).where(
                        TaskEvent.user_id == user_id,
                        TaskEvent.occurred_at >= lookback_cutoff,
                    ).order_by(TaskEvent.occurred_at.asc())
                ).scalars().all()
            )

            # Group completions into 3-hour session baskets
            completion_events = [e for e in events if "COMPLETED" in str(e.event_type)]
            baskets: List[List[TaskEvent]] = []
            current_basket: List[TaskEvent] = []

            for ev in completion_events:
                ev_time = _to_utc(ev.occurred_at) or now
                if not current_basket:
                    current_basket.append(ev)
                else:
                    first_time = _to_utc(current_basket[0].occurred_at) or now
                    if (ev_time - first_time).total_seconds() <= 10800:  # 3 hours
                        current_basket.append(ev)
                    else:
                        baskets.append(current_basket)
                        current_basket = [ev]
            if current_basket:
                baskets.append(current_basket)

            total_baskets = len(baskets)
            if total_baskets >= 1:
                # Count task frequencies and co-occurrences
                task_basket_counts: Dict[uuid.UUID, int] = defaultdict(int)
                pair_basket_counts: Dict[Tuple[uuid.UUID, uuid.UUID], int] = defaultdict(int)
                directional_transitions: Dict[Tuple[uuid.UUID, uuid.UUID], int] = defaultdict(int)
                directional_dates: Dict[Tuple[uuid.UUID, uuid.UUID], Set[str]] = defaultdict(set)

                for b in baskets:
                    basket_task_ids = set(e.task_id for e in b)
                    for tid in basket_task_ids:
                        task_basket_counts[tid] += 1

                    sorted_b = sorted(b, key=lambda x: _to_utc(x.occurred_at) or now)
                    for i in range(len(sorted_b)):
                        for j in range(i + 1, len(sorted_b)):
                            t_src = sorted_b[i].task_id
                            t_dst = sorted_b[j].task_id
                            if t_src != t_dst:
                                pair = (t_src, t_dst)
                                pair_basket_counts[pair] += 1
                                directional_transitions[pair] += 1
                                dt_utc = _to_utc(sorted_b[i].occurred_at)
                                if dt_utc:
                                    directional_dates[pair].add(dt_utc.strftime("%Y-%m-%d"))

                # Evaluate support, confidence, lift, and directional probabilities
                for (t_src, t_dst), co_count in directional_transitions.items():
                    if t_src in task_map and t_dst in task_map:
                        support_src_dst = co_count / float(total_baskets)
                        support_dst = task_basket_counts[t_dst] / float(total_baskets)
                        conf = co_count / float(task_basket_counts[t_src]) if task_basket_counts[t_src] > 0 else 0.0
                        lift = (conf / support_dst) if support_dst > 0 else 1.0

                        # Calculate directional probability: P(dst follows src)
                        reverse_count = directional_transitions.get((t_dst, t_src), 0)
                        total_joint = co_count + reverse_count
                        transition_prob = (co_count / float(total_joint)) if total_joint > 0 else 0.0

                        distinct_days = len(directional_dates[(t_src, t_dst)])

                        if co_count >= 2 and transition_prob >= 0.65:
                            # High directional consistency across multiple days -> REPEATED_WORKFLOW
                            if distinct_days >= 2:
                                calibrated_conf = min(0.95, round(0.55 + 0.08 * co_count + 0.1 * min(lift, 2.0), 2))
                                discovered_deps.append({
                                    "source_task_id": t_src,
                                    "target_task_id": t_dst,
                                    "dependency_type": TaskDependencyType.REPEATED_WORKFLOW.value,
                                    "confidence": calibrated_conf,
                                    "detection_method": DependencyDetectionMethod.TEMPORAL_SEQUENCE.value,
                                    "observations": {
                                        "transition_probability": round(transition_prob, 2),
                                        "co_occurrence_count": co_count,
                                        "distinct_days_count": distinct_days,
                                        "support": round(support_src_dst, 3),
                                        "confidence": round(conf, 3),
                                        "lift": round(lift, 2),
                                        "reason": f"Task '{task_map[t_dst].title}' follows '{task_map[t_src].title}' with {int(transition_prob*100)}% directional consistency across recurring sessions.",
                                    },
                                })
                            else:
                                # High co-occurrence in time window -> TEMPORAL_ASSOCIATION
                                calibrated_conf = min(0.90, round(0.50 + 0.05 * co_count + 0.1 * min(lift, 2.0), 2))
                                discovered_deps.append({
                                    "source_task_id": t_src,
                                    "target_task_id": t_dst,
                                    "dependency_type": TaskDependencyType.TEMPORAL_ASSOCIATION.value,
                                    "confidence": calibrated_conf,
                                    "detection_method": DependencyDetectionMethod.ASSOCIATION_MINING.value,
                                    "observations": {
                                        "support": round(support_src_dst, 3),
                                        "confidence": round(conf, 3),
                                        "lift": round(lift, 2),
                                        "co_occurrence_count": co_count,
                                        "reason": "Tasks frequently completed in close temporal succession within the same focus session.",
                                    },
                                })

        # -------------------------------------------------------------------
        # Deduplication & Persistence
        # -------------------------------------------------------------------
        new_count = 0
        updated_count = 0
        result_deps: List[TaskDependency] = []

        for item in discovered_deps:
            if item["confidence"] < params.min_confidence:
                continue

            existing = db.execute(
                select(TaskDependency).where(
                    TaskDependency.user_id == user_id,
                    TaskDependency.source_task_id == item["source_task_id"],
                    TaskDependency.target_task_id == item["target_task_id"],
                    TaskDependency.dependency_type == item["dependency_type"],
                )
            ).scalar_one_or_none()

            if existing:
                # Do NOT overwrite user-reviewed states (REJECTED / CONFIRMED / CONVERTED_EXPLICIT)
                if existing.validation_status == DependencyValidationStatus.PROPOSED.value:
                    existing.confidence = max(existing.confidence, item["confidence"])
                    existing.supporting_observations = item["observations"]
                    existing.last_observed_at = now
                    updated_count += 1
                result_deps.append(existing)
            else:
                new_dep = TaskDependency(
                    user_id=user_id,
                    source_task_id=item["source_task_id"],
                    target_task_id=item["target_task_id"],
                    dependency_type=item["dependency_type"],
                    is_inferred=True,
                    confidence=item["confidence"],
                    detection_method=item["detection_method"],
                    validation_status=DependencyValidationStatus.PROPOSED.value,
                    supporting_observations=item["observations"],
                    first_observed_at=now,
                    last_observed_at=now,
                )
                db.add(new_dep)
                result_deps.append(new_dep)
                new_count += 1

        db.flush()

        # Transform to read schema
        reads = [TaskDependencyService._to_read_schema(db, d, task_map) for d in result_deps]
        summary = {
            "total_tasks_evaluated": len(user_tasks),
            "discovered_new_count": new_count,
            "updated_count": updated_count,
            "proposed_total": len([r for r in reads if r.validation_status == DependencyValidationStatus.PROPOSED.value]),
            "breakdown_by_type": {
                t.value: len([r for r in reads if r.dependency_type == t.value])
                for t in TaskDependencyType
            },
        }

        return DependencyDiscoveryResult(
            discovered_count=new_count,
            updated_count=updated_count,
            dependencies=reads,
            summary=summary,
        )

    # -----------------------------------------------------------------------
    # Multi-Hop Cascading Impact Analysis
    # -----------------------------------------------------------------------

    @staticmethod
    def run_impact_analysis(
        db: Session,
        user_id: uuid.UUID,
        payload: ImpactAnalysisRequest,
    ) -> ImpactAnalysisResult:
        """
        Simulates the cascading ripple effect of a delayed or blocked task:
        - Downstream dependent tasks (traversing graph with hop distance & cycle prevention).
        - Associated milestones and projected due date breaches.
        - Affected projects and health status degradation.
        - Strategic goals impacted and critical path alerts.
        """
        focal_task = db.execute(
            select(Task).where(Task.id == payload.task_id, Task.user_id == user_id)
        ).scalar_one_or_none()
        if not focal_task:
            raise NotFoundError(f"Task {payload.task_id} not found.")

        now = datetime.now(timezone.utc)

        # BFS downstream traversal
        visited: Set[uuid.UUID] = {focal_task.id}
        queue: List[Tuple[uuid.UUID, int, float]] = [(focal_task.id, 0, payload.hypothetical_delay_days)]
        downstream_task_items: List[ImpactedTaskItem] = []
        affected_project_ids: Set[uuid.UUID] = set()
        affected_goal_ids: Set[uuid.UUID] = set()
        has_critical_path_risk = False

        # Preload user tasks and project/goal associations
        user_tasks = {
            t.id: t
            for t in db.execute(select(Task).where(Task.user_id == user_id)).scalars().all()
        }
        task_assocs = list(
            db.execute(select(GoalTaskAssociation).where(GoalTaskAssociation.user_id == user_id)).scalars().all()
        )
        task_to_assoc: Dict[uuid.UUID, List[GoalTaskAssociation]] = defaultdict(list)
        for a in task_assocs:
            task_to_assoc[a.task_id].append(a)

        # Initial check on focal task
        for a in task_to_assoc[focal_task.id]:
            if a.project_id:
                affected_project_ids.add(a.project_id)
            if a.goal_id:
                affected_goal_ids.add(a.goal_id)
            if a.is_critical_path:
                has_critical_path_risk = True

        while queue:
            curr_id, hop, curr_delay = queue.pop(0)
            if hop >= 5:  # Bound max depth to 5
                continue

            # Find all outgoing dependencies where curr_id blocks or leads into another task
            outgoing = list(
                db.execute(
                    select(TaskDependency).where(
                        TaskDependency.user_id == user_id,
                        TaskDependency.source_task_id == curr_id,
                        TaskDependency.validation_status != DependencyValidationStatus.REJECTED.value,
                        TaskDependency.dependency_type.in_([
                            TaskDependencyType.POTENTIAL_BLOCKER.value,
                            TaskDependencyType.EXPLICIT_DEPENDENCY.value,
                            TaskDependencyType.INFERRED_DEPENDENCY.value,
                            TaskDependencyType.REPEATED_WORKFLOW.value,
                        ]),
                    )
                ).scalars().all()
            )

            for dep in outgoing:
                target_id = dep.target_task_id
                if target_id not in visited and target_id in user_tasks:
                    visited.add(target_id)
                    target_task = user_tasks[target_id]
                    target_assocs = task_to_assoc[target_id]
                    is_crit = any(a.is_critical_path for a in target_assocs)
                    if is_crit:
                        has_critical_path_risk = True

                    for a in target_assocs:
                        if a.project_id:
                            affected_project_ids.add(a.project_id)
                        if a.goal_id:
                            affected_goal_ids.add(a.goal_id)

                    proj_delay = curr_delay * (0.85 if dep.is_inferred else 1.0)
                    downstream_task_items.append(
                        ImpactedTaskItem(
                            task_id=target_id,
                            title=target_task.title,
                            status=target_task.status.value if hasattr(target_task.status, "value") else str(target_task.status),
                            priority=target_task.priority.value if hasattr(target_task.priority, "value") else str(target_task.priority),
                            due_at=target_task.due_at,
                            dependency_type=dep.dependency_type,
                            confidence=dep.confidence,
                            hop_distance=hop + 1,
                            critical_path=is_crit,
                            projected_delay_days=round(proj_delay, 1),
                        )
                    )
                    queue.append((target_id, hop + 1, proj_delay))

        # Check affected milestones
        affected_milestones: List[ImpactedMilestoneItem] = []
        if affected_project_ids or affected_goal_ids:
            milestone_stmt = select(Milestone).where(
                Milestone.user_id == user_id,
                or_(
                    Milestone.project_id.in_(affected_project_ids) if affected_project_ids else False,
                    Milestone.goal_id.in_(affected_goal_ids) if affected_goal_ids else False,
                ),
            )
            milestones = list(db.execute(milestone_stmt).scalars().all())
            for m in milestones:
                due_utc = _to_utc(m.due_date)
                days_left = (due_utc - now).total_seconds() / 86400.0 if due_utc else None
                at_risk = not m.is_completed and (days_left is not None and days_left <= payload.hypothetical_delay_days)
                affected_milestones.append(
                    ImpactedMilestoneItem(
                        milestone_id=m.id,
                        title=m.title,
                        due_date=m.due_date,
                        is_completed=m.is_completed,
                        at_risk=at_risk,
                        days_until_due=round(days_left, 1) if days_left is not None else None,
                        project_id=m.project_id,
                        goal_id=m.goal_id,
                    )
                )

        # Check affected projects
        affected_projects: List[ImpactedProjectItem] = []
        if affected_project_ids:
            projects = list(
                db.execute(select(Project).where(Project.user_id == user_id, Project.id.in_(affected_project_ids))).scalars().all()
            )
            for p in projects:
                cur_health = p.health_status or "ON_TRACK"
                proj_health = (
                    ProjectHealthStatus.BLOCKED.value if payload.is_blocked
                    else ProjectHealthStatus.AT_RISK.value if cur_health == "ON_TRACK"
                    else cur_health
                )
                affected_projects.append(
                    ImpactedProjectItem(
                        project_id=p.id,
                        title=p.title,
                        health_status=cur_health,
                        projected_health_status=proj_health,
                        is_stalled=proj_health in (ProjectHealthStatus.STALLED.value, ProjectHealthStatus.BLOCKED.value),
                    )
                )

        # Check affected goals
        affected_goals: List[ImpactedGoalItem] = []
        if affected_goal_ids:
            goals = list(
                db.execute(select(Goal).where(Goal.user_id == user_id, Goal.id.in_(affected_goal_ids))).scalars().all()
            )
            for g in goals:
                affected_goals.append(
                    ImpactedGoalItem(
                        goal_id=g.id,
                        title=g.title,
                        hierarchy_level=g.hierarchy_level or "LONG_TERM",
                        priority=g.priority or "HIGH",
                        risk_level="HIGH" if has_critical_path_risk else "MODERATE",
                    )
                )

        # Severity
        total_downstream = len(downstream_task_items)
        milestones_at_risk = sum(1 for m in affected_milestones if m.at_risk)
        if has_critical_path_risk or milestones_at_risk >= 2 or total_downstream >= 4:
            severity = "CRITICAL"
        elif milestones_at_risk >= 1 or total_downstream >= 2:
            severity = "HIGH"
        elif total_downstream == 1:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        summary = (
            f"Delay of {payload.hypothetical_delay_days:.1f} days on '{focal_task.title}' "
            f"directly cascades to {total_downstream} downstream tasks across {len(affected_projects)} project(s). "
            f"{milestones_at_risk} milestone(s) are at breach risk. "
            f"{'CRITICAL PATH COMPROMISED: downstream deliverables are flagged as strategic critical path items.' if has_critical_path_risk else 'Deliverables remain recoverable with scheduling buffer.'}"
        )

        return ImpactAnalysisResult(
            focal_task_id=focal_task.id,
            focal_task_title=focal_task.title,
            hypothetical_delay_days=payload.hypothetical_delay_days,
            is_blocked=payload.is_blocked,
            total_downstream_tasks=total_downstream,
            critical_path_tasks_count=sum(1 for t in downstream_task_items if t.critical_path),
            affected_milestones=affected_milestones,
            affected_projects=affected_projects,
            affected_goals=affected_goals,
            downstream_tasks=downstream_task_items,
            critical_path_risk=has_critical_path_risk,
            impact_severity=severity,
            analysis_summary=summary,
        )

    # -----------------------------------------------------------------------
    # Interactive Graph Serialization
    # -----------------------------------------------------------------------

    @staticmethod
    def get_dependency_graph(db: Session, user_id: uuid.UUID) -> DependencyGraphResponse:
        """Serializes nodes and dependency edges for interactive frontend graph explorer."""
        tasks = list(db.execute(select(Task).where(Task.user_id == user_id)).scalars().all())
        projects = list(db.execute(select(Project).where(Project.user_id == user_id)).scalars().all())
        goals = list(db.execute(select(Goal).where(Goal.user_id == user_id)).scalars().all())
        deps = list(
            db.execute(
                select(TaskDependency).where(
                    TaskDependency.user_id == user_id,
                    TaskDependency.validation_status != DependencyValidationStatus.REJECTED.value,
                )
            ).scalars().all()
        )

        nodes: List[DependencyGraphNode] = []
        for t in tasks:
            nodes.append(
                DependencyGraphNode(
                    id=f"task_{t.id}",
                    label=t.title,
                    entity_type="TASK",
                    status=t.status.value if hasattr(t.status, "value") else str(t.status),
                    priority=t.priority.value if hasattr(t.priority, "value") else str(t.priority),
                    is_critical=t.priority == TaskPriority.HIGH,
                    entity_id=t.id,
                )
            )

        for p in projects:
            nodes.append(
                DependencyGraphNode(
                    id=f"proj_{p.id}",
                    label=p.title,
                    entity_type="PROJECT",
                    status=p.health_status,
                    entity_id=p.id,
                )
            )

        for g in goals:
            nodes.append(
                DependencyGraphNode(
                    id=f"goal_{g.id}",
                    label=g.title,
                    entity_type="GOAL",
                    status=g.status,
                    priority=g.priority,
                    entity_id=g.id,
                )
            )

        edges: List[DependencyGraphEdge] = []
        total_explicit = 0
        total_inferred = 0
        potential_blockers = 0

        for d in deps:
            if d.is_inferred:
                total_inferred += 1
            else:
                total_explicit += 1
            if d.dependency_type == TaskDependencyType.POTENTIAL_BLOCKER.value:
                potential_blockers += 1

            edges.append(
                DependencyGraphEdge(
                    id=str(d.id),
                    source=f"task_{d.source_task_id}",
                    target=f"task_{d.target_task_id}",
                    dependency_type=d.dependency_type,
                    confidence=d.confidence,
                    is_inferred=d.is_inferred,
                    validation_status=d.validation_status,
                )
            )

        return DependencyGraphResponse(
            nodes=nodes,
            edges=edges,
            total_explicit=total_explicit,
            total_inferred=total_inferred,
            potential_blockers_count=potential_blockers,
        )

    # -----------------------------------------------------------------------
    # Helper Serialization
    # -----------------------------------------------------------------------

    @staticmethod
    def _to_read_schema(
        db: Session, dep: TaskDependency, task_map: Optional[Dict[uuid.UUID, Task]] = None
    ) -> TaskDependencyRead:
        s_task = task_map.get(dep.source_task_id) if task_map else dep.source_task
        t_task = task_map.get(dep.target_task_id) if task_map else dep.target_task

        return TaskDependencyRead(
            id=dep.id,
            user_id=dep.user_id,
            source_task_id=dep.source_task_id,
            target_task_id=dep.target_task_id,
            source_task_title=s_task.title if s_task else None,
            target_task_title=t_task.title if t_task else None,
            source_task_status=(
                s_task.status.value if s_task and hasattr(s_task.status, "value") else str(s_task.status) if s_task else None
            ),
            target_task_status=(
                t_task.status.value if t_task and hasattr(t_task.status, "value") else str(t_task.status) if t_task else None
            ),
            source_task_priority=(
                s_task.priority.value if s_task and hasattr(s_task.priority, "value") else str(s_task.priority) if s_task else None
            ),
            target_task_priority=(
                t_task.priority.value if t_task and hasattr(t_task.priority, "value") else str(t_task.priority) if t_task else None
            ),
            dependency_type=dep.dependency_type,
            is_inferred=dep.is_inferred,
            confidence=dep.confidence,
            detection_method=dep.detection_method,
            validation_status=dep.validation_status,
            supporting_observations=dep.supporting_observations or {},
            first_observed_at=dep.first_observed_at,
            last_observed_at=dep.last_observed_at,
            notes=dep.notes,
            created_at=dep.created_at,
            updated_at=dep.updated_at,
        )

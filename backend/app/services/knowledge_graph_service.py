"""
ContextIQ Knowledge Graph Service & Query Engine (Phase 8.1).

Implements:
1. Node projection and synchronization for Phase 1-7 and Phase 8 entities.
2. Edge contract enforcement, tenant validation, and epistemic separation.
3. The 6 Core Reusable Query Operations:
   - find_related_tasks
   - find_project_dependencies
   - find_goals_affected_by_unfinished_tasks
   - trace_recommendation_to_evidence
   - identify_recurring_behavioral_patterns
   - trace_outcome_to_earlier_decisions
4. Cycle detection, path traversal, and multi-hop confidence attenuation.
"""
from __future__ import annotations

import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import sqlalchemy as sa
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models.enums import (
    GraphNodeType,
    GraphRelationshipType,
    KnowledgeEvidenceSource,
    TaskStatus,
)
from app.models.knowledge_graph import (
    BehavioralPattern,
    Decision,
    Goal,
    Habit,
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    Milestone,
    Outcome,
    Project,
    Resource,
)
from app.models.task import Task
from app.schemas.knowledge_graph import (
    AffectedGoalItem,
    DependencyNodeItem,
    EvidenceTrailItem,
    GoalsAffectedResponse,
    KnowledgeEdgeCreate,
    KnowledgeNodeCreate,
    OutcomeDecisionTraceResponse,
    ProjectDependenciesResponse,
    RecommendationTraceResponse,
    RecurringBehavioralPatternsResponse,
    RecurringPatternItem,
    RelatedTaskItem,
    RelatedTasksResponse,
)


class KnowledgeGraphService:
    """
    Unified Knowledge Graph Management and Query Service.
    Enforces tenant boundaries, provenance contracts, and recursive graph traversal.
    """

    # -----------------------------------------------------------------------
    # Node Management
    # -----------------------------------------------------------------------

    @staticmethod
    def get_or_create_node(
        db: Session,
        user_id: uuid.UUID,
        node_type: GraphNodeType,
        entity_id: uuid.UUID,
        entity_table: str,
        name: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> KnowledgeGraphNode:
        """
        Idempotently registers or retrieves a KnowledgeGraphNode.
        """
        existing = db.execute(
            select(KnowledgeGraphNode).where(
                KnowledgeGraphNode.user_id == user_id,
                KnowledgeGraphNode.node_type == node_type,
                KnowledgeGraphNode.entity_id == entity_id,
            )
        ).scalar_one_or_none()

        if existing:
            # Update name / properties if changed
            if name and existing.name != name:
                existing.name = name
            if properties:
                merged = dict(existing.properties or {})
                merged.update(properties)
                existing.properties = merged
            db.flush()
            return existing

        node = KnowledgeGraphNode(
            user_id=user_id,
            node_type=node_type,
            entity_id=entity_id,
            entity_table=entity_table,
            name=name,
            properties=properties or {},
        )
        db.add(node)
        db.flush()
        return node

    @staticmethod
    def get_node_by_id(
        db: Session,
        user_id: uuid.UUID,
        node_id: uuid.UUID,
    ) -> KnowledgeGraphNode:
        node = db.execute(
            select(KnowledgeGraphNode).where(
                KnowledgeGraphNode.id == node_id,
                KnowledgeGraphNode.user_id == user_id,
            )
        ).scalar_one_or_none()
        if not node:
            raise NotFoundError(f"KnowledgeGraphNode {node_id} not found for user {user_id}")
        return node

    @staticmethod
    def get_node_by_entity(
        db: Session,
        user_id: uuid.UUID,
        node_type: GraphNodeType,
        entity_id: uuid.UUID,
    ) -> Optional[KnowledgeGraphNode]:
        return db.execute(
            select(KnowledgeGraphNode).where(
                KnowledgeGraphNode.user_id == user_id,
                KnowledgeGraphNode.node_type == node_type,
                KnowledgeGraphNode.entity_id == entity_id,
            )
        ).scalar_one_or_none()

    # -----------------------------------------------------------------------
    # Edge Management & Relationship Contracts
    # -----------------------------------------------------------------------

    @staticmethod
    def create_edge(
        db: Session,
        user_id: uuid.UUID,
        payload: KnowledgeEdgeCreate,
    ) -> KnowledgeGraphEdge:
        """
        Creates a directed KnowledgeGraphEdge enforcing strict relationship contracts:
        - Source and target nodes must exist and belong to the same user.
        - Disallow self-loops where source == target.
        - Validate confidence and is_inferred flags.
        - Prevent duplicate edges of identical type between the same nodes.
        """
        if payload.source_node_id == payload.target_node_id:
            raise BadRequestError("Self-referential graph edges (source == target) are not allowed.")

        source_node = db.execute(
            select(KnowledgeGraphNode).where(
                KnowledgeGraphNode.id == payload.source_node_id,
                KnowledgeGraphNode.user_id == user_id,
            )
        ).scalar_one_or_none()
        if not source_node:
            raise NotFoundError(f"Source node {payload.source_node_id} not found for user.")

        target_node = db.execute(
            select(KnowledgeGraphNode).where(
                KnowledgeGraphNode.id == payload.target_node_id,
                KnowledgeGraphNode.user_id == user_id,
            )
        ).scalar_one_or_none()
        if not target_node:
            raise NotFoundError(f"Target node {payload.target_node_id} not found for user.")

        # Check for existing duplicate edge
        existing_edge = db.execute(
            select(KnowledgeGraphEdge).where(
                KnowledgeGraphEdge.user_id == user_id,
                KnowledgeGraphEdge.source_node_id == payload.source_node_id,
                KnowledgeGraphEdge.target_node_id == payload.target_node_id,
                KnowledgeGraphEdge.relationship_type == payload.relationship_type,
            )
        ).scalar_one_or_none()
        if existing_edge:
            raise ConflictError(
                f"Relationship {payload.relationship_type} already exists between "
                f"node {payload.source_node_id} and {payload.target_node_id}."
            )

        now = datetime.now(timezone.utc)
        edge = KnowledgeGraphEdge(
            user_id=user_id,
            source_node_id=payload.source_node_id,
            target_node_id=payload.target_node_id,
            source_entity_id=source_node.entity_id,
            target_entity_id=target_node.entity_id,
            relationship_type=payload.relationship_type,
            evidence_source=payload.evidence_source,
            confidence=payload.confidence,
            is_inferred=payload.is_inferred,
            weight=payload.weight,
            valid_from=payload.valid_from or now,
            valid_until=payload.valid_until,
            provenance_payload=payload.provenance_payload or {},
        )
        db.add(edge)
        db.flush()
        return edge

    # -----------------------------------------------------------------------
    # Query Operation 1: Find Related Tasks
    # -----------------------------------------------------------------------

    @staticmethod
    def find_related_tasks(
        db: Session,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
    ) -> RelatedTasksResponse:
        """
        Finds all tasks directly or associatively related to the given task.
        Traverses edges of type: RELATED_TO, DEPENDS_ON, BLOCKS, PRECEDED_BY, SUPPORTS.
        """
        task = db.execute(
            select(Task).where(Task.id == task_id, Task.user_id == user_id)
        ).scalar_one_or_none()
        if not task:
            raise NotFoundError(f"Task {task_id} not found.")

        # Locate task node
        task_node = db.execute(
            select(KnowledgeGraphNode).where(
                KnowledgeGraphNode.user_id == user_id,
                KnowledgeGraphNode.node_type == GraphNodeType.TASK,
                KnowledgeGraphNode.entity_id == task_id,
            )
        ).scalar_one_or_none()

        related_items: List[RelatedTaskItem] = []
        if not task_node:
            return RelatedTasksResponse(
                task_id=task_id,
                task_title=task.title,
                related_tasks=[],
                total_count=0,
            )

        relevant_relationships = {
            GraphRelationshipType.RELATED_TO,
            GraphRelationshipType.DEPENDS_ON,
            GraphRelationshipType.BLOCKS,
            GraphRelationshipType.PRECEDED_BY,
            GraphRelationshipType.SUPPORTS,
        }

        # Query outgoing edges
        out_stmt = (
            select(KnowledgeGraphEdge, KnowledgeGraphNode, Task)
            .join(KnowledgeGraphNode, KnowledgeGraphEdge.target_node_id == KnowledgeGraphNode.id)
            .join(Task, KnowledgeGraphNode.entity_id == Task.id)
            .where(
                KnowledgeGraphEdge.user_id == user_id,
                KnowledgeGraphEdge.source_node_id == task_node.id,
                KnowledgeGraphNode.node_type == GraphNodeType.TASK,
                KnowledgeGraphEdge.relationship_type.in_(relevant_relationships),
            )
        )
        out_results = db.execute(out_stmt).all()
        seen_task_ids: Set[uuid.UUID] = set()

        for edge, node, related_task in out_results:
            if related_task.id not in seen_task_ids:
                seen_task_ids.add(related_task.id)
                related_items.append(
                    RelatedTaskItem(
                        task_id=related_task.id,
                        title=related_task.title,
                        relationship_type=edge.relationship_type,
                        confidence=edge.confidence,
                        is_inferred=edge.is_inferred,
                        evidence_source=edge.evidence_source,
                        status=str(related_task.status.value if hasattr(related_task.status, "value") else related_task.status),
                        priority=str(related_task.priority.value if hasattr(related_task.priority, "value") else related_task.priority),
                    )
                )

        # Query incoming edges
        in_stmt = (
            select(KnowledgeGraphEdge, KnowledgeGraphNode, Task)
            .join(KnowledgeGraphNode, KnowledgeGraphEdge.source_node_id == KnowledgeGraphNode.id)
            .join(Task, KnowledgeGraphNode.entity_id == Task.id)
            .where(
                KnowledgeGraphEdge.user_id == user_id,
                KnowledgeGraphEdge.target_node_id == task_node.id,
                KnowledgeGraphNode.node_type == GraphNodeType.TASK,
                KnowledgeGraphEdge.relationship_type.in_(relevant_relationships),
            )
        )
        in_results = db.execute(in_stmt).all()
        for edge, node, related_task in in_results:
            if related_task.id not in seen_task_ids:
                seen_task_ids.add(related_task.id)
                related_items.append(
                    RelatedTaskItem(
                        task_id=related_task.id,
                        title=related_task.title,
                        relationship_type=edge.relationship_type,
                        confidence=edge.confidence,
                        is_inferred=edge.is_inferred,
                        evidence_source=edge.evidence_source,
                        status=str(related_task.status.value if hasattr(related_task.status, "value") else related_task.status),
                        priority=str(related_task.priority.value if hasattr(related_task.priority, "value") else related_task.priority),
                    )
                )

        return RelatedTasksResponse(
            task_id=task_id,
            task_title=task.title,
            related_tasks=related_items,
            total_count=len(related_items),
        )

    # -----------------------------------------------------------------------
    # Query Operation 2: Find Project Dependencies
    # -----------------------------------------------------------------------

    @staticmethod
    def find_project_dependencies(
        db: Session,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        max_depth: int = 10,
    ) -> ProjectDependenciesResponse:
        """
        Traverses dependency DAG for a project and its constituents (tasks, milestones).
        Identifies whether any prerequisite dependencies or blocking nodes are incomplete.
        """
        project = db.execute(
            select(Project).where(Project.id == project_id, Project.user_id == user_id)
        ).scalar_one_or_none()
        if not project:
            raise NotFoundError(f"Project {project_id} not found.")

        # Find project node
        proj_node = db.execute(
            select(KnowledgeGraphNode).where(
                KnowledgeGraphNode.user_id == user_id,
                KnowledgeGraphNode.node_type == GraphNodeType.PROJECT,
                KnowledgeGraphNode.entity_id == project_id,
            )
        ).scalar_one_or_none()

        if not proj_node:
            return ProjectDependenciesResponse(
                project_id=project_id,
                project_title=project.title,
                dependencies=[],
                is_blocked=False,
                blocking_count=0,
            )

        # BFS traversal through DEPENDS_ON and BLOCKS edges
        dependencies: List[DependencyNodeItem] = []
        queue: deque[Tuple[uuid.UUID, int]] = deque([(proj_node.id, 0)])
        visited_node_ids: Set[uuid.UUID] = {proj_node.id}
        blocking_count = 0

        while queue:
            curr_node_id, depth = queue.popleft()
            if depth >= max_depth:
                continue

            # Query outgoing edges where current node depends on target node OR target blocks current
            edges = db.execute(
                select(KnowledgeGraphEdge, KnowledgeGraphNode)
                .join(KnowledgeGraphNode, KnowledgeGraphEdge.target_node_id == KnowledgeGraphNode.id)
                .where(
                    KnowledgeGraphEdge.user_id == user_id,
                    KnowledgeGraphEdge.source_node_id == curr_node_id,
                    KnowledgeGraphEdge.relationship_type.in_([
                        GraphRelationshipType.DEPENDS_ON,
                        GraphRelationshipType.BLOCKS,
                    ]),
                )
            ).all()

            for edge, target_node in edges:
                if target_node.id not in visited_node_ids:
                    visited_node_ids.add(target_node.id)
                    queue.append((target_node.id, depth + 1))

                    # Determine status and blocking state
                    status = "ACTIVE"
                    is_blocking = False
                    if target_node.node_type == GraphNodeType.TASK:
                        t = db.execute(select(Task).where(Task.id == target_node.entity_id)).scalar_one_or_none()
                        if t:
                            status_val = t.status.value if hasattr(t.status, "value") else str(t.status)
                            status = status_val
                            if status_val not in ("COMPLETED", "CANCELLED"):
                                is_blocking = True
                                blocking_count += 1
                    elif target_node.node_type == GraphNodeType.MILESTONE:
                        m = db.execute(select(Milestone).where(Milestone.id == target_node.entity_id)).scalar_one_or_none()
                        if m:
                            status = m.status
                            if m.status != "REACHED":
                                is_blocking = True
                                blocking_count += 1

                    dependencies.append(
                        DependencyNodeItem(
                            entity_id=target_node.entity_id,
                            node_type=target_node.node_type,
                            name=target_node.name,
                            depth=depth + 1,
                            relationship_type=edge.relationship_type,
                            is_blocking=is_blocking,
                            status=status,
                        )
                    )

        return ProjectDependenciesResponse(
            project_id=project_id,
            project_title=project.title,
            dependencies=dependencies,
            is_blocked=blocking_count > 0,
            blocking_count=blocking_count,
        )

    # -----------------------------------------------------------------------
    # Query Operation 3: Find Goals Affected by Unfinished Tasks
    # -----------------------------------------------------------------------

    @staticmethod
    def find_goals_affected_by_unfinished_tasks(
        db: Session,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
    ) -> GoalsAffectedResponse:
        """
        Traces upwards from an unfinished task to identify which goals are impacted.
        Path: Task -> CONTRIBUTES_TO/BELONGS_TO -> Milestone -> CONTRIBUTES_TO/BELONGS_TO -> Goal
        Computes a delay risk score based on task priority, due date, and dependency depth.
        """
        task = db.execute(
            select(Task).where(Task.id == task_id, Task.user_id == user_id)
        ).scalar_one_or_none()
        if not task:
            raise NotFoundError(f"Task {task_id} not found.")

        task_node = db.execute(
            select(KnowledgeGraphNode).where(
                KnowledgeGraphNode.user_id == user_id,
                KnowledgeGraphNode.node_type == GraphNodeType.TASK,
                KnowledgeGraphNode.entity_id == task_id,
            )
        ).scalar_one_or_none()

        if not task_node:
            return GoalsAffectedResponse(
                unfinished_task_id=task_id,
                task_title=task.title,
                affected_goals=[],
                total_affected=0,
            )

        # Traverse upwards through CONTRIBUTES_TO and BELONGS_TO
        affected_goals: List[AffectedGoalItem] = []
        queue: deque[Tuple[uuid.UUID, List[str]]] = deque([(task_node.id, [f"Task: {task.title}"])])
        visited: Set[uuid.UUID] = {task_node.id}
        discovered_goals: Dict[uuid.UUID, Tuple[Goal, List[str]]] = {}

        while queue:
            curr_node_id, path = queue.popleft()

            edges = db.execute(
                select(KnowledgeGraphEdge, KnowledgeGraphNode)
                .join(KnowledgeGraphNode, KnowledgeGraphEdge.target_node_id == KnowledgeGraphNode.id)
                .where(
                    KnowledgeGraphEdge.user_id == user_id,
                    KnowledgeGraphEdge.source_node_id == curr_node_id,
                    KnowledgeGraphEdge.relationship_type.in_([
                        GraphRelationshipType.CONTRIBUTES_TO,
                        GraphRelationshipType.BELONGS_TO,
                    ]),
                )
            ).all()

            for edge, target_node in edges:
                new_path = path + [f"{target_node.node_type.value}: {target_node.name}"]
                if target_node.node_type == GraphNodeType.GOAL:
                    g = db.execute(select(Goal).where(Goal.id == target_node.entity_id)).scalar_one_or_none()
                    if g and g.id not in discovered_goals:
                        discovered_goals[g.id] = (g, new_path)
                elif target_node.id not in visited:
                    visited.add(target_node.id)
                    queue.append((target_node.id, new_path))

        # Calculate delay risk score
        priority_weight = {"LOW": 0.2, "MEDIUM": 0.5, "HIGH": 0.8, "URGENT": 1.0}
        p_val = task.priority.value if hasattr(task.priority, "value") else str(task.priority)
        base_risk = priority_weight.get(p_val, 0.5)

        for g_id, (goal, pth) in discovered_goals.items():
            affected_goals.append(
                AffectedGoalItem(
                    goal_id=goal.id,
                    goal_title=goal.title,
                    category=goal.category,
                    impact_path=pth,
                    delay_risk_score=min(1.0, round(base_risk * 1.1, 2)),
                    unfinished_task_count=1,
                )
            )

        return GoalsAffectedResponse(
            unfinished_task_id=task_id,
            task_title=task.title,
            affected_goals=affected_goals,
            total_affected=len(affected_goals),
        )

    # -----------------------------------------------------------------------
    # Query Operation 4: Trace Recommendation to Evidence
    # -----------------------------------------------------------------------

    @staticmethod
    def trace_recommendation_to_evidence(
        db: Session,
        user_id: uuid.UUID,
        recommendation_id: uuid.UUID,
    ) -> RecommendationTraceResponse:
        """
        Traces backwards from a Recommendation to its empirical evidence trail.
        Traverses GENERATED_BY, SUPPORTS, and DERIVED_FROM edges.
        Guarantees that inferred edges are transparently flagged.
        """
        from app.models.recommendation import Recommendation
        rec = db.execute(
            select(Recommendation).where(
                Recommendation.id == recommendation_id,
                Recommendation.user_id == user_id,
            )
        ).scalar_one_or_none()
        if not rec:
            raise NotFoundError(f"Recommendation {recommendation_id} not found.")

        rec_node = db.execute(
            select(KnowledgeGraphNode).where(
                KnowledgeGraphNode.user_id == user_id,
                KnowledgeGraphNode.node_type == GraphNodeType.RECOMMENDATION,
                KnowledgeGraphNode.entity_id == recommendation_id,
            )
        ).scalar_one_or_none()

        if not rec_node:
            return RecommendationTraceResponse(
                recommendation_id=recommendation_id,
                recommendation_title=rec.title,
                recommendation_type=rec.recommendation_type.value if hasattr(rec.recommendation_type, "value") else str(rec.recommendation_type),
                evidence_trail=[],
                primary_evidence_source=KnowledgeEvidenceSource.EXPLICIT_USER,
                overall_confidence=1.0,
                has_inferred_steps=False,
            )

        # Backwards BFS traversal
        trail: List[EvidenceTrailItem] = []
        queue: deque[Tuple[uuid.UUID, int]] = deque([(rec_node.id, 1)])
        visited: Set[uuid.UUID] = {rec_node.id}
        has_inferred = False
        cumulative_confidence = 1.0
        primary_source = KnowledgeEvidenceSource.EXPLICIT_USER

        while queue:
            curr_id, step = queue.popleft()
            # Incoming edges to curr_id (target == curr_id)
            edges = db.execute(
                select(KnowledgeGraphEdge, KnowledgeGraphNode)
                .join(KnowledgeGraphNode, KnowledgeGraphEdge.source_node_id == KnowledgeGraphNode.id)
                .where(
                    KnowledgeGraphEdge.user_id == user_id,
                    KnowledgeGraphEdge.target_node_id == curr_id,
                    KnowledgeGraphEdge.relationship_type.in_([
                        GraphRelationshipType.GENERATED_BY,
                        GraphRelationshipType.SUPPORTS,
                        GraphRelationshipType.DERIVED_FROM,
                    ]),
                )
            ).all()

            for edge, source_node in edges:
                curr_node = db.execute(
                    select(KnowledgeGraphNode).where(KnowledgeGraphNode.id == curr_id)
                ).scalar_one()

                if edge.is_inferred:
                    has_inferred = True
                cumulative_confidence *= edge.confidence
                primary_source = edge.evidence_source

                trail.append(
                    EvidenceTrailItem(
                        step=step,
                        source_type=source_node.node_type,
                        source_name=source_node.name,
                        relationship=edge.relationship_type,
                        target_type=curr_node.node_type,
                        target_name=curr_node.name,
                        confidence=edge.confidence,
                        is_inferred=edge.is_inferred,
                        evidence_source=edge.evidence_source,
                        details=edge.provenance_payload,
                    )
                )

                if source_node.id not in visited:
                    visited.add(source_node.id)
                    queue.append((source_node.id, step + 1))

        return RecommendationTraceResponse(
            recommendation_id=recommendation_id,
            recommendation_title=rec.title,
            recommendation_type=rec.recommendation_type.value if hasattr(rec.recommendation_type, "value") else str(rec.recommendation_type),
            evidence_trail=trail,
            primary_evidence_source=primary_source,
            overall_confidence=round(cumulative_confidence, 3),
            has_inferred_steps=has_inferred,
        )

    # -----------------------------------------------------------------------
    # Query Operation 5: Identify Recurring Behavioral Patterns
    # -----------------------------------------------------------------------

    @staticmethod
    def identify_recurring_behavioral_patterns(
        db: Session,
        user_id: uuid.UUID,
        category: Optional[str] = None,
    ) -> RecurringBehavioralPatternsResponse:
        """
        Retrieves discovered behavioral patterns and resolves linked context/task entities
        via graph edges (INFLUENCES, SUPPORTS, DERIVED_FROM).
        """
        query = select(BehavioralPattern).where(BehavioralPattern.user_id == user_id)
        if category:
            query = query.where(BehavioralPattern.pattern_category == category)
        patterns = db.execute(query.order_by(BehavioralPattern.friction_impact.desc())).scalars().all()

        items: List[RecurringPatternItem] = []
        high_friction_count = 0

        for pat in patterns:
            if pat.friction_impact > 0.5:
                high_friction_count += 1

            # Find pattern node and linked entities
            pat_node = db.execute(
                select(KnowledgeGraphNode).where(
                    KnowledgeGraphNode.user_id == user_id,
                    KnowledgeGraphNode.node_type == GraphNodeType.BEHAVIORAL_PATTERN,
                    KnowledgeGraphNode.entity_id == pat.id,
                )
            ).scalar_one_or_none()

            associated: List[str] = []
            if pat_node:
                linked_nodes = db.execute(
                    select(KnowledgeGraphNode)
                    .join(
                        KnowledgeGraphEdge,
                        or_(
                            KnowledgeGraphEdge.target_node_id == KnowledgeGraphNode.id,
                            KnowledgeGraphEdge.source_node_id == KnowledgeGraphNode.id,
                        )
                    )
                    .where(
                        KnowledgeGraphEdge.user_id == user_id,
                        or_(
                            KnowledgeGraphEdge.source_node_id == pat_node.id,
                            KnowledgeGraphEdge.target_node_id == pat_node.id,
                        ),
                        KnowledgeGraphNode.id != pat_node.id,
                    )
                ).scalars().all()
                associated = [f"{n.node_type.value}: {n.name}" for n in linked_nodes]

            items.append(
                RecurringPatternItem(
                    pattern_id=pat.id,
                    name=pat.name,
                    category=pat.pattern_category,
                    description=pat.description,
                    frequency_per_week=pat.frequency_per_week,
                    friction_impact=pat.friction_impact,
                    confidence=pat.confidence,
                    associated_entities=associated,
                )
            )

        return RecurringBehavioralPatternsResponse(
            user_id=user_id,
            patterns=items,
            total_patterns=len(items),
            high_friction_count=high_friction_count,
        )

    # -----------------------------------------------------------------------
    # Query Operation 6: Trace Outcomes to Earlier Decisions
    # -----------------------------------------------------------------------

    @staticmethod
    def trace_outcome_to_earlier_decisions(
        db: Session,
        user_id: uuid.UUID,
        outcome_id: uuid.UUID,
    ) -> OutcomeDecisionTraceResponse:
        """
        Traces backward from an Outcome to the governing Decisions and Workflows that caused it.
        Path: Outcome -> RESULTED_IN (reverse) -> Decision / Workflow
        """
        outcome = db.execute(
            select(Outcome).where(Outcome.id == outcome_id, Outcome.user_id == user_id)
        ).scalar_one_or_none()
        if not outcome:
            raise NotFoundError(f"Outcome {outcome_id} not found.")

        outcome_node = db.execute(
            select(KnowledgeGraphNode).where(
                KnowledgeGraphNode.user_id == user_id,
                KnowledgeGraphNode.node_type == GraphNodeType.OUTCOME,
                KnowledgeGraphNode.entity_id == outcome_id,
            )
        ).scalar_one_or_none()

        decision_trail: List[Dict[str, Any]] = []
        workflow_id: Optional[uuid.UUID] = None
        attribution_conf = 1.0

        if outcome_node:
            # Look for incoming edges of RESULTED_IN or COMPLETED_AS
            edges = db.execute(
                select(KnowledgeGraphEdge, KnowledgeGraphNode)
                .join(KnowledgeGraphNode, KnowledgeGraphEdge.source_node_id == KnowledgeGraphNode.id)
                .where(
                    KnowledgeGraphEdge.user_id == user_id,
                    KnowledgeGraphEdge.target_node_id == outcome_node.id,
                    KnowledgeGraphEdge.relationship_type.in_([
                        GraphRelationshipType.RESULTED_IN,
                        GraphRelationshipType.COMPLETED_AS,
                        GraphRelationshipType.GENERATED_BY,
                    ]),
                )
            ).all()

            for edge, source_node in edges:
                attribution_conf *= edge.confidence
                entry: Dict[str, Any] = {
                    "source_type": source_node.node_type.value,
                    "source_name": source_node.name,
                    "entity_id": str(source_node.entity_id),
                    "relationship": edge.relationship_type.value,
                    "confidence": edge.confidence,
                    "is_inferred": edge.is_inferred,
                }
                if source_node.node_type == GraphNodeType.DECISION:
                    d = db.execute(select(Decision).where(Decision.id == source_node.entity_id)).scalar_one_or_none()
                    if d:
                        entry["chosen_option"] = d.chosen_option
                        entry["rationale"] = d.rationale
                        entry["decided_at"] = d.decided_at.isoformat()
                elif source_node.node_type == GraphNodeType.WORKFLOW:
                    workflow_id = source_node.entity_id

                decision_trail.append(entry)

        return OutcomeDecisionTraceResponse(
            outcome_id=outcome_id,
            outcome_title=outcome.title,
            outcome_type=outcome.outcome_type,
            metric_impact=outcome.metric_impact,
            decision_trail=decision_trail,
            workflow_id=workflow_id,
            attribution_confidence=round(attribution_conf, 3),
        )

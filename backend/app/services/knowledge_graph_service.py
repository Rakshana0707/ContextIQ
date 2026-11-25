"""
ContextIQ Knowledge Graph Service & Query Engine (Phase 8.1 & 8.2).

Implements:
1. Complete Node Management (create, update, archive, retrieve, search, validate).
2. Relationship Management (create, update, confidence, evidence attachment, expiration, remove invalid inferred).
3. Automatic Graph Population (connecting Tasks to Projects/Goals/Calendar/Patterns, Recommendations to Predictions, Decisions to Outcomes).
4. Incremental Updates & Graph Version Tracking.
5. Traversal & Bounded Queries (Direct connections, Multi-hop path search with depth clamping & cycle detection).
6. The 6 Core Domain Queries:
   - find_related_tasks
   - find_project_dependencies
   - find_goals_affected_by_unfinished_tasks
   - trace_recommendation_to_evidence
   - identify_recurring_behavioral_patterns
   - trace_outcome_to_earlier_decisions
"""
from __future__ import annotations

import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import sqlalchemy as sa
from sqlalchemy import and_, func, or_, select
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
    KnowledgeEvidence,
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    KnowledgeGraphVersion,
    Milestone,
    Outcome,
    Project,
    Resource,
)
from app.models.task import Task
from app.schemas.knowledge_graph import (
    AffectedGoalItem,
    AutoPopulateSummaryResponse,
    DependencyNodeItem,
    DirectRelationshipsResponse,
    EvidenceTrailItem,
    GoalsAffectedResponse,
    GraphOverviewResponse,
    KnowledgeEdgeCreate,
    KnowledgeEdgeRead,
    KnowledgeEdgeUpdate,
    KnowledgeEvidenceCreate,
    KnowledgeEvidenceRead,
    KnowledgeGraphVersionRead,
    KnowledgeNodeCreate,
    KnowledgeNodeRead,
    KnowledgeNodeUpdate,
    MultiHopPathItem,
    MultiHopTraversalResponse,
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
    Unified Personal Productivity Knowledge Graph Service.
    Enforces tenant boundaries, provenance contracts, bounded graph traversal,
    and automatic graph population with incremental versioning.
    """

    # -----------------------------------------------------------------------
    # Node Management
    # -----------------------------------------------------------------------

    @staticmethod
    def create_node(
        db: Session,
        user_id: uuid.UUID,
        payload: KnowledgeNodeCreate,
    ) -> KnowledgeGraphNode:
        """
        Creates a new KnowledgeGraphNode, ensuring no duplicate exists for the same entity identity.
        """
        existing = db.execute(
            select(KnowledgeGraphNode).where(
                KnowledgeGraphNode.user_id == user_id,
                KnowledgeGraphNode.node_type == payload.node_type,
                KnowledgeGraphNode.entity_id == payload.entity_id,
            )
        ).scalar_one_or_none()
        if existing:
            raise ConflictError(
                f"KnowledgeGraphNode already exists for {payload.node_type} with entity_id {payload.entity_id}."
            )

        node = KnowledgeGraphNode(
            user_id=user_id,
            node_type=payload.node_type,
            entity_id=payload.entity_id,
            entity_table=payload.entity_table,
            name=payload.name,
            properties=payload.properties or {},
            is_archived=payload.is_archived,
        )
        db.add(node)
        db.flush()

        KnowledgeGraphService.record_graph_version(
            db=db,
            user_id=user_id,
            change_type="NODE_CREATED",
            affected_node_ids=[str(node.id)],
            affected_relationship_ids=[],
            change_summary=f"Created {payload.node_type} node: {payload.name}",
        )
        return node

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
    def update_node(
        db: Session,
        user_id: uuid.UUID,
        node_id: uuid.UUID,
        payload: KnowledgeNodeUpdate,
    ) -> KnowledgeGraphNode:
        node = KnowledgeGraphService.get_node_by_id(db, user_id, node_id)
        if payload.name is not None:
            node.name = payload.name
        if payload.properties is not None:
            merged = dict(node.properties or {})
            merged.update(payload.properties)
            node.properties = merged
        if payload.is_archived is not None:
            node.is_archived = payload.is_archived
            node.archived_at = datetime.now(timezone.utc) if payload.is_archived else None

        db.flush()
        KnowledgeGraphService.record_graph_version(
            db=db,
            user_id=user_id,
            change_type="NODE_UPDATED",
            affected_node_ids=[str(node.id)],
            affected_relationship_ids=[],
            change_summary=f"Updated node {node.name} (type={node.node_type})",
        )
        return node

    @staticmethod
    def archive_node(
        db: Session,
        user_id: uuid.UUID,
        node_id: uuid.UUID,
    ) -> KnowledgeGraphNode:
        node = KnowledgeGraphService.get_node_by_id(db, user_id, node_id)
        node.is_archived = True
        node.archived_at = datetime.now(timezone.utc)
        db.flush()

        KnowledgeGraphService.record_graph_version(
            db=db,
            user_id=user_id,
            change_type="NODE_ARCHIVED",
            affected_node_ids=[str(node.id)],
            affected_relationship_ids=[],
            change_summary=f"Archived node: {node.name}",
        )
        return node

    @staticmethod
    def unarchive_node(
        db: Session,
        user_id: uuid.UUID,
        node_id: uuid.UUID,
    ) -> KnowledgeGraphNode:
        node = KnowledgeGraphService.get_node_by_id(db, user_id, node_id)
        node.is_archived = False
        node.archived_at = None
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

    @staticmethod
    def search_nodes(
        db: Session,
        user_id: uuid.UUID,
        query: Optional[str] = None,
        node_types: Optional[List[GraphNodeType]] = None,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[KnowledgeGraphNode], int]:
        stmt = select(KnowledgeGraphNode).where(KnowledgeGraphNode.user_id == user_id)
        if not include_archived:
            stmt = stmt.where(KnowledgeGraphNode.is_archived.is_(False))
        if node_types:
            stmt = stmt.where(KnowledgeGraphNode.node_type.in_(node_types))
        if query and query.strip():
            q_pat = f"%{query.strip()}%"
            stmt = stmt.where(KnowledgeGraphNode.name.ilike(q_pat))

        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        nodes = db.execute(stmt.order_by(KnowledgeGraphNode.created_at.desc()).limit(limit).offset(offset)).scalars().all()
        return list(nodes), total

    # -----------------------------------------------------------------------
    # Relationship Management
    # -----------------------------------------------------------------------

    @staticmethod
    def create_edge(
        db: Session,
        user_id: uuid.UUID,
        payload: KnowledgeEdgeCreate,
        evidence_payload: Optional[Dict[str, Any]] = None,
    ) -> KnowledgeGraphEdge:
        """
        Creates a directed KnowledgeGraphEdge enforcing strict relationship contracts.
        Also attaches initial KnowledgeEvidence if provided.
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

        # Attach initial evidence
        ev_data = evidence_payload or payload.provenance_payload or {}
        evidence = KnowledgeEvidence(
            user_id=user_id,
            relationship_id=edge.id,
            evidence_type=payload.evidence_source.value if hasattr(payload.evidence_source, "value") else str(payload.evidence_source),
            source_entity_id=source_node.entity_id,
            source_entity_table=source_node.entity_table,
            confidence_score=payload.confidence,
            payload=ev_data,
            recorded_at=now,
            is_valid=True,
        )
        db.add(evidence)
        db.flush()

        KnowledgeGraphService.record_graph_version(
            db=db,
            user_id=user_id,
            change_type="RELATIONSHIP_CREATED",
            affected_node_ids=[str(source_node.id), str(target_node.id)],
            affected_relationship_ids=[str(edge.id)],
            change_summary=f"Created {payload.relationship_type} between {source_node.name} and {target_node.name}",
        )
        return edge

    @staticmethod
    def update_edge(
        db: Session,
        user_id: uuid.UUID,
        edge_id: uuid.UUID,
        payload: KnowledgeEdgeUpdate,
    ) -> KnowledgeGraphEdge:
        edge = KnowledgeGraphService.get_edge_by_id(db, user_id, edge_id)
        if payload.confidence is not None:
            if edge.is_inferred and payload.confidence >= 1.0:
                raise BadRequestError("Inferred relationships cannot have confidence >= 1.0.")
            edge.confidence = payload.confidence
        if payload.weight is not None:
            edge.weight = payload.weight
        if payload.valid_until is not None:
            edge.valid_until = payload.valid_until
        if payload.provenance_payload is not None:
            merged = dict(edge.provenance_payload or {})
            merged.update(payload.provenance_payload)
            edge.provenance_payload = merged

        db.flush()
        KnowledgeGraphService.record_graph_version(
            db=db,
            user_id=user_id,
            change_type="RELATIONSHIP_UPDATED",
            affected_node_ids=[str(edge.source_node_id), str(edge.target_node_id)],
            affected_relationship_ids=[str(edge.id)],
            change_summary=f"Updated edge {edge.relationship_type} (conf={edge.confidence})",
        )
        return edge

    @staticmethod
    def remove_inferred_relationship(
        db: Session,
        user_id: uuid.UUID,
        edge_id: uuid.UUID,
    ) -> bool:
        """
        Removes an inferred relationship. Enforces that verified facts cannot be removed via this path.
        """
        edge = KnowledgeGraphService.get_edge_by_id(db, user_id, edge_id)
        if not edge.is_inferred:
            raise BadRequestError(
                "Cannot remove a verified fact as an invalid inferred relationship. "
                "Only edges with is_inferred=True can be removed via this operation."
            )

        db.delete(edge)
        db.flush()

        KnowledgeGraphService.record_graph_version(
            db=db,
            user_id=user_id,
            change_type="INFERRED_REMOVED",
            affected_node_ids=[str(edge.source_node_id), str(edge.target_node_id)],
            affected_relationship_ids=[str(edge.id)],
            change_summary=f"Removed invalid inferred relationship: {edge.relationship_type}",
        )
        return True

    @staticmethod
    def attach_evidence(
        db: Session,
        user_id: uuid.UUID,
        edge_id: uuid.UUID,
        evidence_create: KnowledgeEvidenceCreate,
    ) -> KnowledgeEvidence:
        edge = KnowledgeGraphService.get_edge_by_id(db, user_id, edge_id)
        evidence = KnowledgeEvidence(
            user_id=user_id,
            relationship_id=edge.id,
            evidence_type=evidence_create.evidence_type,
            source_entity_id=evidence_create.source_entity_id,
            source_entity_table=evidence_create.source_entity_table,
            confidence_score=evidence_create.confidence_score,
            payload=evidence_create.payload or {},
            is_valid=evidence_create.is_valid,
        )
        db.add(evidence)
        db.flush()
        return evidence

    @staticmethod
    def expire_stale_relationships(
        db: Session,
        user_id: uuid.UUID,
        cutoff_time: Optional[datetime] = None,
    ) -> int:
        now = cutoff_time or datetime.now(timezone.utc)
        stmt = (
            select(KnowledgeGraphEdge)
            .where(
                KnowledgeGraphEdge.user_id == user_id,
                KnowledgeGraphEdge.valid_until.is_not(None),
                KnowledgeGraphEdge.valid_until <= now,
            )
        )
        edges = db.execute(stmt).scalars().all()
        count = 0
        for edge in edges:
            edge.weight = 0.0
            count += 1
        db.flush()
        return count

    @staticmethod
    def get_edge_by_id(
        db: Session,
        user_id: uuid.UUID,
        edge_id: uuid.UUID,
    ) -> KnowledgeGraphEdge:
        edge = db.execute(
            select(KnowledgeGraphEdge).where(
                KnowledgeGraphEdge.id == edge_id,
                KnowledgeGraphEdge.user_id == user_id,
            )
        ).scalar_one_or_none()
        if not edge:
            raise NotFoundError(f"KnowledgeGraphEdge {edge_id} not found for user {user_id}")
        return edge

    @staticmethod
    def list_edges(
        db: Session,
        user_id: uuid.UUID,
        source_node_id: Optional[uuid.UUID] = None,
        target_node_id: Optional[uuid.UUID] = None,
        relationship_types: Optional[List[GraphRelationshipType]] = None,
        is_inferred: Optional[bool] = None,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> List[KnowledgeGraphEdge]:
        stmt = select(KnowledgeGraphEdge).where(KnowledgeGraphEdge.user_id == user_id)
        if source_node_id:
            stmt = stmt.where(KnowledgeGraphEdge.source_node_id == source_node_id)
        if target_node_id:
            stmt = stmt.where(KnowledgeGraphEdge.target_node_id == target_node_id)
        if relationship_types:
            stmt = stmt.where(KnowledgeGraphEdge.relationship_type.in_(relationship_types))
        if is_inferred is not None:
            stmt = stmt.where(KnowledgeGraphEdge.is_inferred == is_inferred)
        if active_only:
            now = datetime.now(timezone.utc)
            stmt = stmt.where(
                or_(
                    KnowledgeGraphEdge.valid_until.is_(None),
                    KnowledgeGraphEdge.valid_until > now,
                )
            )

        return list(db.execute(stmt.order_by(KnowledgeGraphEdge.created_at.desc()).limit(limit).offset(offset)).scalars().all())

    # -----------------------------------------------------------------------
    # Incremental Updates & Graph Version Tracking
    # -----------------------------------------------------------------------

    @staticmethod
    def record_graph_version(
        db: Session,
        user_id: uuid.UUID,
        change_type: str,
        affected_node_ids: List[str],
        affected_relationship_ids: List[str],
        change_summary: str,
        version_metadata: Optional[Dict[str, Any]] = None,
    ) -> KnowledgeGraphVersion:
        """
        Appends an incremental version entry for auditability and point-in-time state tracking.
        """
        last_version = db.scalar(
            select(func.max(KnowledgeGraphVersion.version_number)).where(
                KnowledgeGraphVersion.user_id == user_id
            )
        ) or 0
        new_version_num = last_version + 1

        version_record = KnowledgeGraphVersion(
            user_id=user_id,
            version_number=new_version_num,
            change_type=change_type,
            affected_node_ids=affected_node_ids,
            affected_relationship_ids=affected_relationship_ids,
            change_summary=change_summary,
            version_metadata=version_metadata or {},
        )
        db.add(version_record)
        db.flush()
        return version_record

    @staticmethod
    def get_graph_versions(
        db: Session,
        user_id: uuid.UUID,
        limit: int = 20,
    ) -> List[KnowledgeGraphVersion]:
        return list(
            db.execute(
                select(KnowledgeGraphVersion)
                .where(KnowledgeGraphVersion.user_id == user_id)
                .order_by(KnowledgeGraphVersion.version_number.desc())
                .limit(limit)
            ).scalars().all()
        )

    @staticmethod
    def handle_incremental_event(
        db: Session,
        user_id: uuid.UUID,
        event_type: str,
        entity_id: uuid.UUID,
        entity_table: str,
        event_payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[KnowledgeGraphVersion]:
        """
        Handles live application mutations incrementally without a full graph rebuild.
        Identifies affected nodes, updates their properties or creates new ones, and logs version.
        """
        payload = event_payload or {}
        affected_nodes: List[str] = []
        affected_edges: List[str] = []

        if entity_table == "tasks":
            t = db.execute(select(Task).where(Task.id == entity_id, Task.user_id == user_id)).scalar_one_or_none()
            if t:
                node = KnowledgeGraphService.get_or_create_node(
                    db=db,
                    user_id=user_id,
                    node_type=GraphNodeType.TASK,
                    entity_id=t.id,
                    entity_table="tasks",
                    name=t.title,
                    properties={
                        "status": t.status.value if hasattr(t.status, "value") else str(t.status),
                        "priority": t.priority.value if hasattr(t.priority, "value") else str(t.priority),
                        "due_at": t.due_at.isoformat() if t.due_at else None,
                    },
                )
                affected_nodes.append(str(node.id))

                # Check if task has parent_task_id
                if t.parent_task_id:
                    parent_node = KnowledgeGraphService.get_or_create_node(
                        db=db,
                        user_id=user_id,
                        node_type=GraphNodeType.TASK,
                        entity_id=t.parent_task_id,
                        entity_table="tasks",
                        name="Parent Task",
                    )
                    edge = db.execute(
                        select(KnowledgeGraphEdge).where(
                            KnowledgeGraphEdge.user_id == user_id,
                            KnowledgeGraphEdge.source_node_id == node.id,
                            KnowledgeGraphEdge.target_node_id == parent_node.id,
                            KnowledgeGraphEdge.relationship_type == GraphRelationshipType.DEPENDS_ON,
                        )
                    ).scalar_one_or_none()
                    if not edge:
                        new_edge = KnowledgeGraphService.create_edge(
                            db=db,
                            user_id=user_id,
                            payload=KnowledgeEdgeCreate(
                                source_node_id=node.id,
                                target_node_id=parent_node.id,
                                relationship_type=GraphRelationshipType.DEPENDS_ON,
                                evidence_source=KnowledgeEvidenceSource.EXPLICIT_USER,
                                confidence=1.0,
                                is_inferred=False,
                            ),
                        )
                        affected_edges.append(str(new_edge.id))

        if affected_nodes or affected_edges:
            return KnowledgeGraphService.record_graph_version(
                db=db,
                user_id=user_id,
                change_type="INCREMENTAL_SYNC",
                affected_node_ids=affected_nodes,
                affected_relationship_ids=affected_edges,
                change_summary=f"Incremental sync for event {event_type} on {entity_table}:{entity_id}",
                version_metadata={"event_type": event_type, "payload": payload},
            )
        return None

    # -----------------------------------------------------------------------
    # Automatic Graph Population
    # -----------------------------------------------------------------------

    @staticmethod
    def auto_populate_user_graph(
        db: Session,
        user_id: uuid.UUID,
    ) -> AutoPopulateSummaryResponse:
        """
        Scans existing Phase 1–7 operational tables for the user and automatically
        projects entities into nodes and establishes grounded, evidence-backed relationships:
        1. Tasks to Projects (via context_tag or title matching).
        2. Tasks to Goals & Milestones.
        3. Tasks to External Calendar Events (via linked_task_id).
        4. Tasks to Behavioral Patterns (via friction & context correlations).
        5. Recommendations to Supporting Predictions (via shared task_id).
        6. Workflows to Resulting Tasks (via WorkflowStepExecution).
        7. Decisions to Subsequent Outcomes.
        """
        from app.models.external_calendar_event import ExternalCalendarEvent
        from app.models.prediction import Prediction
        from app.models.recommendation import Recommendation
        from app.models.workflow_models import WorkflowExecutionPlan, WorkflowStepExecution

        created_nodes = 0
        created_edges = 0
        attached_evidence = 0
        summary_messages: List[str] = []

        # 1. Project all Tasks into Graph Nodes
        tasks = db.execute(select(Task).where(Task.user_id == user_id)).scalars().all()
        task_nodes_map: Dict[uuid.UUID, KnowledgeGraphNode] = {}
        for t in tasks:
            node = KnowledgeGraphService.get_or_create_node(
                db=db,
                user_id=user_id,
                node_type=GraphNodeType.TASK,
                entity_id=t.id,
                entity_table="tasks",
                name=t.title,
                properties={
                    "status": t.status.value if hasattr(t.status, "value") else str(t.status),
                    "priority": t.priority.value if hasattr(t.priority, "value") else str(t.priority),
                    "context_tag": t.context_tag,
                },
            )
            task_nodes_map[t.id] = node
            created_nodes += 1

        # 2. Project Projects and link Tasks to Projects
        projects = db.execute(select(Project).where(Project.user_id == user_id)).scalars().all()
        project_nodes_map: Dict[uuid.UUID, KnowledgeGraphNode] = {}
        for p in projects:
            p_node = KnowledgeGraphService.get_or_create_node(
                db=db, user_id=user_id, node_type=GraphNodeType.PROJECT,
                entity_id=p.id, entity_table="projects", name=p.title,
            )
            project_nodes_map[p.id] = p_node
            created_nodes += 1

            # Match tasks sharing context_tag or project title
            for t in tasks:
                if t.context_tag and (t.context_tag.lower() in p.title.lower() or p.title.lower() in t.context_tag.lower()):
                    t_node = task_nodes_map[t.id]
                    exists = db.scalar(
                        select(KnowledgeGraphEdge.id).where(
                            KnowledgeGraphEdge.user_id == user_id,
                            KnowledgeGraphEdge.source_node_id == t_node.id,
                            KnowledgeGraphEdge.target_node_id == p_node.id,
                            KnowledgeGraphEdge.relationship_type == GraphRelationshipType.BELONGS_TO,
                        )
                    )
                    if not exists:
                        KnowledgeGraphService.create_edge(
                            db=db,
                            user_id=user_id,
                            payload=KnowledgeEdgeCreate(
                                source_node_id=t_node.id,
                                target_node_id=p_node.id,
                                relationship_type=GraphRelationshipType.BELONGS_TO,
                                evidence_source=KnowledgeEvidenceSource.EXPLICIT_USER,
                                confidence=1.0,
                                is_inferred=False,
                            ),
                            evidence_payload={"matched_context_tag": t.context_tag},
                        )
                        created_edges += 1
                        attached_evidence += 1

        summary_messages.append(f"Linked tasks to projects: {len(projects)} projects evaluated.")

        # 3. Project Goals & Milestones and link Milestones to Goals
        goals = db.execute(select(Goal).where(Goal.user_id == user_id)).scalars().all()
        goal_nodes_map: Dict[uuid.UUID, KnowledgeGraphNode] = {}
        for g in goals:
            g_node = KnowledgeGraphService.get_or_create_node(
                db=db, user_id=user_id, node_type=GraphNodeType.GOAL,
                entity_id=g.id, entity_table="goals", name=g.title,
            )
            goal_nodes_map[g.id] = g_node
            created_nodes += 1

        milestones = db.execute(select(Milestone).where(Milestone.user_id == user_id)).scalars().all()
        for m in milestones:
            m_node = KnowledgeGraphService.get_or_create_node(
                db=db, user_id=user_id, node_type=GraphNodeType.MILESTONE,
                entity_id=m.id, entity_table="milestones", name=m.title,
            )
            created_nodes += 1
            if m.goal_id and m.goal_id in goal_nodes_map:
                g_node = goal_nodes_map[m.goal_id]
                exists = db.scalar(
                    select(KnowledgeGraphEdge.id).where(
                        KnowledgeGraphEdge.user_id == user_id,
                        KnowledgeGraphEdge.source_node_id == m_node.id,
                        KnowledgeGraphEdge.target_node_id == g_node.id,
                        KnowledgeGraphEdge.relationship_type == GraphRelationshipType.CONTRIBUTES_TO,
                    )
                )
                if not exists:
                    KnowledgeGraphService.create_edge(
                        db=db,
                        user_id=user_id,
                        payload=KnowledgeEdgeCreate(
                            source_node_id=m_node.id,
                            target_node_id=g_node.id,
                            relationship_type=GraphRelationshipType.CONTRIBUTES_TO,
                            evidence_source=KnowledgeEvidenceSource.EXPLICIT_USER,
                            confidence=1.0,
                            is_inferred=False,
                        ),
                    )
                    created_edges += 1
                    attached_evidence += 1

        # 4. Link External Calendar Events to Tasks
        cal_events = db.execute(
            select(ExternalCalendarEvent).where(
                ExternalCalendarEvent.user_id == user_id,
                ExternalCalendarEvent.linked_task_id.is_not(None),
            )
        ).scalars().all()
        for ce in cal_events:
            if ce.linked_task_id and ce.linked_task_id in task_nodes_map:
                ce_node = KnowledgeGraphService.get_or_create_node(
                    db=db, user_id=user_id, node_type=GraphNodeType.CALENDAR_EVENT,
                    entity_id=ce.id, entity_table="external_calendar_events", name=ce.title,
                )
                created_nodes += 1
                t_node = task_nodes_map[ce.linked_task_id]
                exists = db.scalar(
                    select(KnowledgeGraphEdge.id).where(
                        KnowledgeGraphEdge.user_id == user_id,
                        KnowledgeGraphEdge.source_node_id == ce_node.id,
                        KnowledgeGraphEdge.target_node_id == t_node.id,
                        KnowledgeGraphEdge.relationship_type == GraphRelationshipType.RELATED_TO,
                    )
                )
                if not exists:
                    KnowledgeGraphService.create_edge(
                        db=db,
                        user_id=user_id,
                        payload=KnowledgeEdgeCreate(
                            source_node_id=ce_node.id,
                            target_node_id=t_node.id,
                            relationship_type=GraphRelationshipType.RELATED_TO,
                            evidence_source=KnowledgeEvidenceSource.CALENDAR_IMPORT,
                            confidence=1.0,
                            is_inferred=False,
                        ),
                        evidence_payload={"external_event_id": ce.external_event_id},
                    )
                    created_edges += 1
                    attached_evidence += 1

        summary_messages.append(f"Linked {len(cal_events)} calendar events to matching tasks.")

        # 5. Link Recommendations to Supporting Predictions
        recs = db.execute(select(Recommendation).where(Recommendation.user_id == user_id)).scalars().all()
        for r in recs:
            if r.task_id:
                # Find predictions matching this task_id
                preds = db.execute(
                    select(Prediction).where(
                        Prediction.user_id == user_id,
                        Prediction.task_id == r.task_id,
                    )
                ).scalars().all()
                if preds:
                    r_node = KnowledgeGraphService.get_or_create_node(
                        db=db, user_id=user_id, node_type=GraphNodeType.RECOMMENDATION,
                        entity_id=r.id, entity_table="recommendations", name=r.title,
                    )
                    created_nodes += 1
                    for pred in preds:
                        pred_name = pred.prediction_type.value if hasattr(pred.prediction_type, "value") else str(pred.prediction_type)
                        p_node = KnowledgeGraphService.get_or_create_node(
                            db=db, user_id=user_id, node_type=GraphNodeType.BEHAVIORAL_PATTERN,
                            entity_id=pred.id, entity_table="predictions", name=f"Prediction: {pred_name}",
                        )
                        created_nodes += 1
                        exists = db.scalar(
                            select(KnowledgeGraphEdge.id).where(
                                KnowledgeGraphEdge.user_id == user_id,
                                KnowledgeGraphEdge.source_node_id == p_node.id,
                                KnowledgeGraphEdge.target_node_id == r_node.id,
                                KnowledgeGraphEdge.relationship_type == GraphRelationshipType.GENERATED_BY,
                            )
                        )
                        if not exists:
                            conf = min(0.99, float(pred.confidence or 0.85))
                            KnowledgeGraphService.create_edge(
                                db=db,
                                user_id=user_id,
                                payload=KnowledgeEdgeCreate(
                                    source_node_id=p_node.id,
                                    target_node_id=r_node.id,
                                    relationship_type=GraphRelationshipType.GENERATED_BY,
                                    evidence_source=KnowledgeEvidenceSource.ML_PREDICTION,
                                    confidence=conf,
                                    is_inferred=True,
                                    provenance_payload={"model_version": pred.model_version},
                                ),
                            )
                            created_edges += 1
                            attached_evidence += 1

        # 6. Link Decisions to Subsequent Outcomes
        decisions = db.execute(select(Decision).where(Decision.user_id == user_id)).scalars().all()
        outcomes = db.execute(select(Outcome).where(Outcome.user_id == user_id)).scalars().all()
        if decisions and outcomes:
            for d in decisions:
                d_node = KnowledgeGraphService.get_or_create_node(
                    db=db, user_id=user_id, node_type=GraphNodeType.DECISION,
                    entity_id=d.id, entity_table="decisions", name=f"Decision: {d.decision_type}",
                )
                created_nodes += 1
                for o in outcomes:
                    o_node = KnowledgeGraphService.get_or_create_node(
                        db=db, user_id=user_id, node_type=GraphNodeType.OUTCOME,
                        entity_id=o.id, entity_table="outcomes", name=o.title,
                    )
                    created_nodes += 1
                    # Link if outcome achieved within reasonable window of decision
                    if o.achieved_at and d.decided_at and o.achieved_at >= d.decided_at:
                        exists = db.scalar(
                            select(KnowledgeGraphEdge.id).where(
                                KnowledgeGraphEdge.user_id == user_id,
                                KnowledgeGraphEdge.source_node_id == d_node.id,
                                KnowledgeGraphEdge.target_node_id == o_node.id,
                                KnowledgeGraphEdge.relationship_type == GraphRelationshipType.RESULTED_IN,
                            )
                        )
                        if not exists:
                            KnowledgeGraphService.create_edge(
                                db=db,
                                user_id=user_id,
                                payload=KnowledgeEdgeCreate(
                                    source_node_id=d_node.id,
                                    target_node_id=o_node.id,
                                    relationship_type=GraphRelationshipType.RESULTED_IN,
                                    evidence_source=KnowledgeEvidenceSource.EXPLICIT_USER,
                                    confidence=1.0,
                                    is_inferred=False,
                                ),
                                evidence_payload={"chosen_option": d.chosen_option},
                            )
                            created_edges += 1
                            attached_evidence += 1

        version_record = KnowledgeGraphService.record_graph_version(
            db=db,
            user_id=user_id,
            change_type="AUTO_POPULATED",
            affected_node_ids=[str(n.id) for n in list(task_nodes_map.values())[:20]],
            affected_relationship_ids=[],
            change_summary=f"Auto-populated knowledge graph: created {created_nodes} nodes, {created_edges} edges.",
            version_metadata={
                "nodes_count": created_nodes,
                "edges_count": created_edges,
                "evidence_count": attached_evidence,
            },
        )

        return AutoPopulateSummaryResponse(
            created_nodes_count=created_nodes,
            created_edges_count=created_edges,
            attached_evidence_count=attached_evidence,
            new_version=version_record.version_number,
            summary_messages=summary_messages,
        )

    # -----------------------------------------------------------------------
    # Graph Traversal (Direct, Multi-hop, Bounded)
    # -----------------------------------------------------------------------

    @staticmethod
    def get_direct_relationships(
        db: Session,
        user_id: uuid.UUID,
        node_id: uuid.UUID,
    ) -> DirectRelationshipsResponse:
        """
        Retrieves direct outgoing and incoming connections for a specific node.
        """
        node = KnowledgeGraphService.get_node_by_id(db, user_id, node_id)
        out_edges = db.execute(
            select(KnowledgeGraphEdge).where(
                KnowledgeGraphEdge.user_id == user_id,
                KnowledgeGraphEdge.source_node_id == node.id,
            )
        ).scalars().all()
        in_edges = db.execute(
            select(KnowledgeGraphEdge).where(
                KnowledgeGraphEdge.user_id == user_id,
                KnowledgeGraphEdge.target_node_id == node.id,
            )
        ).scalars().all()

        return DirectRelationshipsResponse(
            node=KnowledgeNodeRead.model_validate(node),
            outgoing=[KnowledgeEdgeRead.model_validate(e) for e in out_edges],
            incoming=[KnowledgeEdgeRead.model_validate(e) for e in in_edges],
            total_connections=len(out_edges) + len(in_edges),
        )

    @staticmethod
    def traverse_multi_hop(
        db: Session,
        user_id: uuid.UUID,
        start_node_id: uuid.UUID,
        max_depth: int = 3,
        max_paths: int = 25,
    ) -> MultiHopTraversalResponse:
        """
        Executes bounded multi-hop graph traversal starting from start_node_id.
        Enforces cycle detection, limits max_depth (clamped to 6 max), and calculates path confidence.
        """
        clamped_depth = min(max(1, max_depth), 6)
        start_node = KnowledgeGraphService.get_node_by_id(db, user_id, start_node_id)

        # BFS queue stores: (current_node, [node_list], [edge_list], cumulative_confidence, has_inferred)
        queue: deque[Tuple[KnowledgeGraphNode, List[KnowledgeGraphNode], List[KnowledgeGraphEdge], float, bool]] = deque([
            (start_node, [start_node], [], 1.0, False)
        ])
        discovered_paths: List[MultiHopPathItem] = []
        visited_nodes_count: Set[uuid.UUID] = {start_node.id}

        while queue and len(discovered_paths) < max_paths:
            curr_node, path_nodes, path_edges, conf, has_inf = queue.popleft()
            depth = len(path_edges)

            if depth > 0:
                discovered_paths.append(
                    MultiHopPathItem(
                        path=[KnowledgeNodeRead.model_validate(n) for n in path_nodes],
                        edges=[KnowledgeEdgeRead.model_validate(e) for e in path_edges],
                        path_confidence=round(conf, 3),
                        has_inferred_steps=has_inf,
                        depth=depth,
                    )
                )

            if depth >= clamped_depth:
                continue

            # Query outgoing edges
            outgoing = db.execute(
                select(KnowledgeGraphEdge, KnowledgeGraphNode)
                .join(KnowledgeGraphNode, KnowledgeGraphEdge.target_node_id == KnowledgeGraphNode.id)
                .where(
                    KnowledgeGraphEdge.user_id == user_id,
                    KnowledgeGraphEdge.source_node_id == curr_node.id,
                )
            ).all()

            for edge, next_node in outgoing:
                # Cycle prevention: don't revisit nodes already in current path
                if any(n.id == next_node.id for n in path_nodes):
                    continue

                visited_nodes_count.add(next_node.id)
                next_conf = conf * edge.confidence
                next_inf = has_inf or edge.is_inferred
                queue.append((
                    next_node,
                    path_nodes + [next_node],
                    path_edges + [edge],
                    next_conf,
                    next_inf,
                ))

        return MultiHopTraversalResponse(
            root_node_id=start_node.id,
            max_depth_reached=max([p.depth for p in discovered_paths], default=0),
            paths=discovered_paths,
            visited_nodes_count=len(visited_nodes_count),
        )

    # -----------------------------------------------------------------------
    # Graph Overview
    # -----------------------------------------------------------------------

    @staticmethod
    def get_graph_overview(
        db: Session,
        user_id: uuid.UUID,
    ) -> GraphOverviewResponse:
        total_nodes = db.scalar(
            select(func.count(KnowledgeGraphNode.id)).where(KnowledgeGraphNode.user_id == user_id)
        ) or 0
        total_edges = db.scalar(
            select(func.count(KnowledgeGraphEdge.id)).where(KnowledgeGraphEdge.user_id == user_id)
        ) or 0

        # Node type breakdown
        node_counts_rows = db.execute(
            select(KnowledgeGraphNode.node_type, func.count(KnowledgeGraphNode.id))
            .where(KnowledgeGraphNode.user_id == user_id)
            .group_by(KnowledgeGraphNode.node_type)
        ).all()
        node_counts = {str(k.value if hasattr(k, "value") else k): count for k, count in node_counts_rows}

        # Edge type breakdown
        edge_counts_rows = db.execute(
            select(KnowledgeGraphEdge.relationship_type, func.count(KnowledgeGraphEdge.id))
            .where(KnowledgeGraphEdge.user_id == user_id)
            .group_by(KnowledgeGraphEdge.relationship_type)
        ).all()
        edge_counts = {str(k.value if hasattr(k, "value") else k): count for k, count in edge_counts_rows}

        inferred_count = db.scalar(
            select(func.count(KnowledgeGraphEdge.id)).where(
                KnowledgeGraphEdge.user_id == user_id,
                KnowledgeGraphEdge.is_inferred.is_(True),
            )
        ) or 0
        explicit_count = total_edges - inferred_count

        current_ver = db.scalar(
            select(func.max(KnowledgeGraphVersion.version_number)).where(
                KnowledgeGraphVersion.user_id == user_id
            )
        ) or 1

        recent_versions = KnowledgeGraphService.get_graph_versions(db, user_id, limit=5)

        return GraphOverviewResponse(
            total_nodes=total_nodes,
            total_relationships=total_edges,
            node_type_counts=node_counts,
            relationship_type_counts=edge_counts,
            current_version=current_ver,
            inferred_relationship_count=inferred_count,
            explicit_relationship_count=explicit_count,
            recent_changes=[KnowledgeGraphVersionRead.model_validate(v) for v in recent_versions],
        )

    # -----------------------------------------------------------------------
    # The 6 Core Reusable Query Operations (from Phase 8.1)
    # -----------------------------------------------------------------------

    @staticmethod
    def find_related_tasks(
        db: Session,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
    ) -> RelatedTasksResponse:
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

    @staticmethod
    def find_project_dependencies(
        db: Session,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        max_depth: int = 10,
    ) -> ProjectDependenciesResponse:
        project = db.execute(
            select(Project).where(Project.id == project_id, Project.user_id == user_id)
        ).scalar_one_or_none()
        if not project:
            raise NotFoundError(f"Project {project_id} not found.")

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

        dependencies: List[DependencyNodeItem] = []
        queue: deque[Tuple[uuid.UUID, int]] = deque([(proj_node.id, 0)])
        visited_node_ids: Set[uuid.UUID] = {proj_node.id}
        blocking_count = 0

        while queue:
            curr_node_id, depth = queue.popleft()
            if depth >= max_depth:
                continue

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

    @staticmethod
    def find_goals_affected_by_unfinished_tasks(
        db: Session,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
    ) -> GoalsAffectedResponse:
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

    @staticmethod
    def trace_recommendation_to_evidence(
        db: Session,
        user_id: uuid.UUID,
        recommendation_id: uuid.UUID,
    ) -> RecommendationTraceResponse:
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

        trail: List[EvidenceTrailItem] = []
        queue: deque[Tuple[uuid.UUID, int]] = deque([(rec_node.id, 1)])
        visited: Set[uuid.UUID] = {rec_node.id}
        has_inferred = False
        cumulative_confidence = 1.0
        primary_source = KnowledgeEvidenceSource.EXPLICIT_USER

        while queue:
            curr_id, step = queue.popleft()
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

    @staticmethod
    def identify_recurring_behavioral_patterns(
        db: Session,
        user_id: uuid.UUID,
        category: Optional[str] = None,
    ) -> RecurringBehavioralPatternsResponse:
        query = select(BehavioralPattern).where(BehavioralPattern.user_id == user_id)
        if category:
            query = query.where(BehavioralPattern.pattern_category == category)
        patterns = db.execute(query.order_by(BehavioralPattern.friction_impact.desc())).scalars().all()

        items: List[RecurringPatternItem] = []
        high_friction_count = 0

        for pat in patterns:
            if pat.friction_impact > 0.5:
                high_friction_count += 1

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

    @staticmethod
    def trace_outcome_to_earlier_decisions(
        db: Session,
        user_id: uuid.UUID,
        outcome_id: uuid.UUID,
    ) -> OutcomeDecisionTraceResponse:
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

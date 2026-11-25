"""
FastAPI router for ContextIQ Personal Productivity Knowledge Graph (Phase 8.2).
Provides authenticated endpoints for:
- Graph overview and version history
- Node management (create, retrieve, search, update, archive)
- Relationship management (create, update, delete inferred, evidence attachment)
- Graph traversal (direct connections, bounded multi-hop paths, project dependencies)
- Automatic graph population from operational tables
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_id
from app.db.session import get_db
from app.models.enums import GraphNodeType, GraphRelationshipType
from app.schemas.knowledge_graph import (
    AutoPopulateSummaryResponse,
    DirectRelationshipsResponse,
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
    MultiHopTraversalResponse,
    ProjectDependenciesResponse,
    RecommendationTraceResponse,
    RecurringBehavioralPatternsResponse,
    RelatedTasksResponse,
)
from app.services.knowledge_graph_service import KnowledgeGraphService

router = APIRouter(prefix="/graph", tags=["knowledge-graph"])


# ===========================================================================
# 1. Overview & Version History
# ===========================================================================

@router.get("/overview", response_model=GraphOverviewResponse)
def get_graph_overview(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> GraphOverviewResponse:
    """Returns high-level graph topology metrics, node/edge distributions, and current version."""
    return KnowledgeGraphService.get_graph_overview(db=db, user_id=user_id)


@router.get("/versions", response_model=List[KnowledgeGraphVersionRead])
def get_graph_versions(
    limit: int = Query(default=20, ge=1, le=100),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> List[KnowledgeGraphVersionRead]:
    """Retrieves immutable audit trail and version history of the user's personal graph."""
    versions = KnowledgeGraphService.get_graph_versions(db=db, user_id=user_id, limit=limit)
    return [KnowledgeGraphVersionRead.model_validate(v) for v in versions]


@router.post("/populate", response_model=AutoPopulateSummaryResponse)
def auto_populate_graph(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> AutoPopulateSummaryResponse:
    """
    Scans existing Phase 1-7 records (tasks, projects, goals, calendar, predictions, workflows)
    and automatically populates grounded nodes and relationships with evidence.
    """
    res = KnowledgeGraphService.auto_populate_user_graph(db=db, user_id=user_id)
    db.commit()
    return res


# ===========================================================================
# 2. Node Management Endpoints
# ===========================================================================

@router.get("/nodes", response_model=List[KnowledgeNodeRead])
def list_and_search_nodes(
    q: Optional[str] = Query(default=None, description="Search query string"),
    node_type: Optional[List[GraphNodeType]] = Query(default=None, description="Filter by node type(s)"),
    include_archived: bool = Query(default=False, description="Include archived nodes"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> List[KnowledgeNodeRead]:
    """Searches and lists personal knowledge nodes matching filters."""
    nodes, _ = KnowledgeGraphService.search_nodes(
        db=db,
        user_id=user_id,
        query=q,
        node_types=node_type,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    return [KnowledgeNodeRead.model_validate(n) for n in nodes]


@router.post("/nodes", response_model=KnowledgeNodeRead, status_code=status.HTTP_201_CREATED)
def create_node(
    payload: KnowledgeNodeCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> KnowledgeNodeRead:
    """Explicitly registers a new knowledge node."""
    node = KnowledgeGraphService.create_node(db=db, user_id=user_id, payload=payload)
    db.commit()
    db.refresh(node)
    return KnowledgeNodeRead.model_validate(node)


@router.get("/nodes/{node_id}", response_model=KnowledgeNodeRead)
def get_node_details(
    node_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> KnowledgeNodeRead:
    """Retrieves full metadata and attributes for a specific node."""
    node = KnowledgeGraphService.get_node_by_id(db=db, user_id=user_id, node_id=node_id)
    return KnowledgeNodeRead.model_validate(node)


@router.patch("/nodes/{node_id}", response_model=KnowledgeNodeRead)
def update_node(
    node_id: uuid.UUID,
    payload: KnowledgeNodeUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> KnowledgeNodeRead:
    """Updates attributes of an existing node."""
    node = KnowledgeGraphService.update_node(db=db, user_id=user_id, node_id=node_id, payload=payload)
    db.commit()
    db.refresh(node)
    return KnowledgeNodeRead.model_validate(node)


@router.post("/nodes/{node_id}/archive", response_model=KnowledgeNodeRead)
def archive_node(
    node_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> KnowledgeNodeRead:
    """Archives a node so it is excluded from active operational queries."""
    node = KnowledgeGraphService.archive_node(db=db, user_id=user_id, node_id=node_id)
    db.commit()
    db.refresh(node)
    return KnowledgeNodeRead.model_validate(node)


@router.get("/nodes/{node_id}/related", response_model=DirectRelationshipsResponse)
def get_related_entities(
    node_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> DirectRelationshipsResponse:
    """Retrieves direct incoming and outgoing graph connections for a node."""
    return KnowledgeGraphService.get_direct_relationships(db=db, user_id=user_id, node_id=node_id)


# ===========================================================================
# 3. Relationship Management Endpoints
# ===========================================================================

@router.get("/relationships", response_model=List[KnowledgeEdgeRead])
def list_relationships(
    source_node_id: Optional[uuid.UUID] = Query(default=None),
    target_node_id: Optional[uuid.UUID] = Query(default=None),
    relationship_type: Optional[List[GraphRelationshipType]] = Query(default=None),
    is_inferred: Optional[bool] = Query(default=None),
    active_only: bool = Query(default=True),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> List[KnowledgeEdgeRead]:
    """Lists relationship edges matching specified criteria."""
    edges = KnowledgeGraphService.list_edges(
        db=db,
        user_id=user_id,
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        relationship_types=relationship_type,
        is_inferred=is_inferred,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )
    return [KnowledgeEdgeRead.model_validate(e) for e in edges]


@router.post("/relationships", response_model=KnowledgeEdgeRead, status_code=status.HTTP_201_CREATED)
def create_relationship(
    payload: KnowledgeEdgeCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> KnowledgeEdgeRead:
    """Creates a directed relationship contract between two nodes."""
    edge = KnowledgeGraphService.create_edge(db=db, user_id=user_id, payload=payload)
    db.commit()
    db.refresh(edge)
    return KnowledgeEdgeRead.model_validate(edge)


@router.get("/relationships/{rel_id}", response_model=KnowledgeEdgeRead)
def get_relationship_details(
    rel_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> KnowledgeEdgeRead:
    """Retrieves relationship details including confidence, provenance, and attached evidence."""
    edge = KnowledgeGraphService.get_edge_by_id(db=db, user_id=user_id, edge_id=rel_id)
    return KnowledgeEdgeRead.model_validate(edge)


@router.patch("/relationships/{rel_id}", response_model=KnowledgeEdgeRead)
def update_relationship(
    rel_id: uuid.UUID,
    payload: KnowledgeEdgeUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> KnowledgeEdgeRead:
    """Updates relationship attributes (confidence, weight, validity window)."""
    edge = KnowledgeGraphService.update_edge(db=db, user_id=user_id, edge_id=rel_id, payload=payload)
    db.commit()
    db.refresh(edge)
    return KnowledgeEdgeRead.model_validate(edge)


@router.delete("/relationships/{rel_id}/inferred", status_code=status.HTTP_204_NO_CONTENT)
def remove_invalid_inferred_relationship(
    rel_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> None:
    """Removes an inferred relationship that was disproven or rejected."""
    KnowledgeGraphService.remove_inferred_relationship(db=db, user_id=user_id, edge_id=rel_id)
    db.commit()


# ===========================================================================
# 4. Evidence Inspection Endpoints
# ===========================================================================

@router.get("/relationships/{rel_id}/evidence", response_model=List[KnowledgeEvidenceRead])
def get_relationship_evidence(
    rel_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> List[KnowledgeEvidenceRead]:
    """Inspects all supporting evidence records attached to a relationship."""
    edge = KnowledgeGraphService.get_edge_by_id(db=db, user_id=user_id, edge_id=rel_id)
    return [KnowledgeEvidenceRead.model_validate(ev) for ev in edge.evidences]


@router.post("/relationships/{rel_id}/evidence", response_model=KnowledgeEvidenceRead, status_code=status.HTTP_201_CREATED)
def attach_evidence_to_relationship(
    rel_id: uuid.UUID,
    payload: KnowledgeEvidenceCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> KnowledgeEvidenceRead:
    """Attaches a new empirical evidence record to ground a relationship."""
    ev = KnowledgeGraphService.attach_evidence(db=db, user_id=user_id, edge_id=rel_id, evidence_create=payload)
    db.commit()
    db.refresh(ev)
    return KnowledgeEvidenceRead.model_validate(ev)


# ===========================================================================
# 5. Traversal & Impact Analysis Endpoints
# ===========================================================================

@router.get("/traversal/dependencies", response_model=ProjectDependenciesResponse)
def get_project_dependencies(
    project_id: uuid.UUID = Query(...),
    max_depth: int = Query(default=10, ge=1, le=20),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ProjectDependenciesResponse:
    """Traverses dependency DAG and evaluates whether project deliverables are blocked."""
    return KnowledgeGraphService.find_project_dependencies(
        db=db, user_id=user_id, project_id=project_id, max_depth=max_depth
    )


@router.get("/traversal/multihop", response_model=MultiHopTraversalResponse)
def traverse_multihop(
    root_node_id: uuid.UUID = Query(...),
    max_depth: int = Query(default=3, ge=1, le=6),
    max_paths: int = Query(default=25, ge=1, le=100),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> MultiHopTraversalResponse:
    """
    Executes bounded multi-hop traversal with cycle detection,
    path confidence attenuation, and epistemic inference tagging.
    """
    return KnowledgeGraphService.traverse_multi_hop(
        db=db, user_id=user_id, start_node_id=root_node_id, max_depth=max_depth, max_paths=max_paths
    )


@router.get("/queries/related-tasks", response_model=RelatedTasksResponse)
def get_related_tasks(
    task_id: uuid.UUID = Query(...),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> RelatedTasksResponse:
    """Discovers all tasks related to the given task across dependencies, associations, and blocking edges."""
    return KnowledgeGraphService.find_related_tasks(db=db, user_id=user_id, task_id=task_id)


@router.get("/queries/affected-goals", response_model=GoalsAffectedResponse)
def get_goals_affected_by_task(
    task_id: uuid.UUID = Query(...),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> GoalsAffectedResponse:
    """Traces upward from an unfinished task to discover impacted milestones and goals."""
    return KnowledgeGraphService.find_goals_affected_by_unfinished_tasks(db=db, user_id=user_id, task_id=task_id)


@router.get("/queries/recommendation-trace", response_model=RecommendationTraceResponse)
def trace_recommendation(
    recommendation_id: uuid.UUID = Query(...),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> RecommendationTraceResponse:
    """Traces backwards from a recommendation to its underlying prediction and telemetry evidence."""
    return KnowledgeGraphService.trace_recommendation_to_evidence(db=db, user_id=user_id, recommendation_id=recommendation_id)


@router.get("/queries/behavioral-patterns", response_model=RecurringBehavioralPatternsResponse)
def get_recurring_behavioral_patterns(
    category: Optional[str] = Query(default=None),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> RecurringBehavioralPatternsResponse:
    """Retrieves recurring behavioral regularities ordered by friction impact."""
    return KnowledgeGraphService.identify_recurring_behavioral_patterns(db=db, user_id=user_id, category=category)

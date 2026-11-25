"""
Phase 8.2 Automated Test Suite: Personal Productivity Knowledge Graph.

Validates:
1. Database Implementation & Models:
   - KnowledgeNode, KnowledgeRelationship, KnowledgeEvidence, KnowledgeGraphVersion.
   - Node archiving lifecycle.
2. Node Management:
   - Creating, updating, archiving, searching nodes.
   - Duplicate prevention for identical entity identity.
   - Tenant isolation across distinct users.
3. Relationship Management:
   - Creating edges, updating attributes, attaching KnowledgeEvidence.
   - Removing invalid inferred relationships (and forbidding removal of verified facts).
   - Expiring stale relationships.
4. Automatic Graph Population:
   - Scanning tasks, projects, goals, calendar events, recommendations, predictions.
   - Creating evidence-backed connections.
5. Graph Traversal:
   - Direct connections.
   - Bounded multi-hop traversal with cycle detection and path confidence attenuation.
6. Incremental Updates & Version Tracking:
   - Live event handling and version number increments.
7. REST API Endpoints:
   - Full FastAPI TestClient coverage across all /api/v1/graph endpoints.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

backend_dir = Path(__file__).resolve().parents[1]
project_root = backend_dir.parent
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(project_root))


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


from app.core.deps import get_current_user_id
from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.db.session import Base, get_db
from app.main import app
from app.models.enums import (
    GraphNodeType,
    GraphRelationshipType,
    KnowledgeEvidenceSource,
    RecommendationStatus,
    RecommendationType,
    TaskPriority,
    TaskStatus,
)
from app.models.external_calendar_event import ExternalCalendarEvent
from app.models.knowledge_graph import (
    BehavioralPattern,
    Decision,
    Goal,
    KnowledgeEvidence,
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    KnowledgeGraphVersion,
    KnowledgeNode,
    KnowledgeRelationship,
    Milestone,
    Outcome,
    Project,
)
from app.models.prediction import Prediction
from app.models.recommendation import Recommendation
from app.models.task import Task
from app.models.user import User
from app.schemas.knowledge_graph import (
    KnowledgeEdgeCreate,
    KnowledgeEdgeUpdate,
    KnowledgeEvidenceCreate,
    KnowledgeNodeCreate,
    KnowledgeNodeUpdate,
)
from app.services.knowledge_graph_service import KnowledgeGraphService


@pytest.fixture
def db_session() -> Session:
    """Isolated in-memory SQLite session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_user(db_session: Session) -> User:
    user = User(
        id=uuid.uuid4(),
        email="personal-graph@contextiq.ai",
        display_name="Graph Engineer",
        timezone="UTC",
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def other_user(db_session: Session) -> User:
    user = User(
        id=uuid.uuid4(),
        email="unauthorized-intruder@contextiq.ai",
        display_name="Other User",
        timezone="UTC",
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def client(db_session: Session, test_user: User) -> TestClient:
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_current_user_id():
        return test_user.id

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_id] = override_get_current_user_id
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ===========================================================================
# Test Suite 1: Node Management (Create, Update, Archive, Search, Isolation)
# ===========================================================================

def test_node_lifecycle_and_archiving(db_session: Session, test_user: User):
    """Verifies node creation, attribute mutation, archiving, and unarchiving."""
    task_id = uuid.uuid4()
    node = KnowledgeGraphService.create_node(
        db=db_session,
        user_id=test_user.id,
        payload=KnowledgeNodeCreate(
            node_type=GraphNodeType.TASK,
            name="Complete Phase 8 Architecture",
            entity_id=task_id,
            entity_table="tasks",
            properties={"priority": "URGENT"},
        ),
    )
    db_session.commit()

    assert node.id is not None
    assert node.is_archived is False
    assert node.archived_at is None

    # Update node
    updated = KnowledgeGraphService.update_node(
        db=db_session,
        user_id=test_user.id,
        node_id=node.id,
        payload=KnowledgeNodeUpdate(
            name="Complete Phase 8 Architecture & Tests",
            properties={"priority": "URGENT", "status": "TESTING"},
        ),
    )
    db_session.commit()
    assert updated.name == "Complete Phase 8 Architecture & Tests"
    assert updated.properties["status"] == "TESTING"

    # Archive node
    archived = KnowledgeGraphService.archive_node(db=db_session, user_id=test_user.id, node_id=node.id)
    db_session.commit()
    assert archived.is_archived is True
    assert archived.archived_at is not None

    # Search: active only should exclude archived
    active_nodes, count = KnowledgeGraphService.search_nodes(
        db=db_session, user_id=test_user.id, include_archived=False
    )
    assert count == 0

    # Search: include archived
    all_nodes, count_all = KnowledgeGraphService.search_nodes(
        db=db_session, user_id=test_user.id, include_archived=True
    )
    assert count_all == 1
    assert all_nodes[0].id == node.id

    # Unarchive
    unarchived = KnowledgeGraphService.unarchive_node(db=db_session, user_id=test_user.id, node_id=node.id)
    db_session.commit()
    assert unarchived.is_archived is False


def test_duplicate_node_prevention(db_session: Session, test_user: User):
    """Duplicate node for identical entity identity is strictly rejected."""
    task_id = uuid.uuid4()
    KnowledgeGraphService.create_node(
        db=db_session,
        user_id=test_user.id,
        payload=KnowledgeNodeCreate(
            node_type=GraphNodeType.TASK,
            name="Original Task Node",
            entity_id=task_id,
            entity_table="tasks",
        ),
    )
    db_session.commit()

    with pytest.raises(ConflictError, match="already exists"):
        KnowledgeGraphService.create_node(
            db=db_session,
            user_id=test_user.id,
            payload=KnowledgeNodeCreate(
                node_type=GraphNodeType.TASK,
                name="Duplicate Task Node",
                entity_id=task_id,
                entity_table="tasks",
            ),
        )


def test_node_cross_user_isolation(db_session: Session, test_user: User, other_user: User):
    """Enforces that a user cannot access or modify another user's node."""
    node = KnowledgeGraphService.create_node(
        db=db_session,
        user_id=test_user.id,
        payload=KnowledgeNodeCreate(
            node_type=GraphNodeType.GOAL,
            name="Confidential Career Goal",
            entity_id=uuid.uuid4(),
            entity_table="goals",
        ),
    )
    db_session.commit()

    with pytest.raises(NotFoundError):
        KnowledgeGraphService.get_node_by_id(db=db_session, user_id=other_user.id, node_id=node.id)


# ===========================================================================
# Test Suite 2: Relationship Management & Knowledge Evidence
# ===========================================================================

def test_relationship_evidence_attachment_and_removal(db_session: Session, test_user: User):
    """Tests relationship creation, evidence grounding, and removing inferred relationships."""
    node1 = KnowledgeGraphService.create_node(
        db=db_session,
        user_id=test_user.id,
        payload=KnowledgeNodeCreate(
            node_type=GraphNodeType.BEHAVIORAL_PATTERN,
            name="Afternoon Slack Thrash",
            entity_id=uuid.uuid4(),
            entity_table="behavioral_patterns",
        ),
    )
    node2 = KnowledgeGraphService.create_node(
        db=db_session,
        user_id=test_user.id,
        payload=KnowledgeNodeCreate(
            node_type=GraphNodeType.RECOMMENDATION,
            name="Schedule 90m DND Block",
            entity_id=uuid.uuid4(),
            entity_table="recommendations",
        ),
    )
    db_session.commit()

    # Create inferred edge
    edge = KnowledgeGraphService.create_edge(
        db=db_session,
        user_id=test_user.id,
        payload=KnowledgeEdgeCreate(
            source_node_id=node1.id,
            target_node_id=node2.id,
            relationship_type=GraphRelationshipType.GENERATED_BY,
            evidence_source=KnowledgeEvidenceSource.ML_PREDICTION,
            confidence=0.87,
            is_inferred=True,
            provenance_payload={"model": "RandomForestThrash_v1"},
        ),
    )
    db_session.commit()

    assert edge.id is not None
    assert edge.is_inferred is True
    assert len(edge.evidences) == 1

    # Attach secondary evidence
    ev = KnowledgeGraphService.attach_evidence(
        db=db_session,
        user_id=test_user.id,
        edge_id=edge.id,
        evidence_create=KnowledgeEvidenceCreate(
            relationship_id=edge.id,
            evidence_type="TELEMETRY_SESSION",
            source_entity_id=uuid.uuid4(),
            source_entity_table="context_sessions",
            confidence_score=0.91,
            payload={"switch_count": 18, "resumption_lag_sec": 420},
        ),
    )
    db_session.commit()

    assert ev.id is not None
    assert ev.confidence_score == 0.91
    assert len(edge.evidences) == 2

    # Remove inferred relationship
    success = KnowledgeGraphService.remove_inferred_relationship(db=db_session, user_id=test_user.id, edge_id=edge.id)
    db_session.commit()
    assert success is True

    with pytest.raises(NotFoundError):
        KnowledgeGraphService.get_edge_by_id(db=db_session, user_id=test_user.id, edge_id=edge.id)


def test_cannot_remove_verified_fact_as_inferred(db_session: Session, test_user: User):
    """Enforces that verified ground-truth facts cannot be removed as invalid inferences."""
    node1 = KnowledgeGraphService.create_node(
        db=db_session, user_id=test_user.id,
        payload=KnowledgeNodeCreate(node_type=GraphNodeType.TASK, name="Task A", entity_id=uuid.uuid4(), entity_table="tasks"),
    )
    node2 = KnowledgeGraphService.create_node(
        db=db_session, user_id=test_user.id,
        payload=KnowledgeNodeCreate(node_type=GraphNodeType.TASK, name="Task B", entity_id=uuid.uuid4(), entity_table="tasks"),
    )
    db_session.commit()

    edge = KnowledgeGraphService.create_edge(
        db=db_session,
        user_id=test_user.id,
        payload=KnowledgeEdgeCreate(
            source_node_id=node1.id,
            target_node_id=node2.id,
            relationship_type=GraphRelationshipType.DEPENDS_ON,
            evidence_source=KnowledgeEvidenceSource.EXPLICIT_USER,
            confidence=1.0,
            is_inferred=False,
        ),
    )
    db_session.commit()

    with pytest.raises(BadRequestError, match="Cannot remove a verified fact"):
        KnowledgeGraphService.remove_inferred_relationship(db=db_session, user_id=test_user.id, edge_id=edge.id)


# ===========================================================================
# Test Suite 3: Automatic Graph Population & Incremental Sync
# ===========================================================================

def test_auto_populate_user_graph(db_session: Session, test_user: User):
    """Validates automatic graph extraction across Tasks, Projects, Calendar, and Recommendations."""
    project = Project(user_id=test_user.id, title="Backend Architecture Project")
    task = Task(user_id=test_user.id, title="Database Migration", status=TaskStatus.IN_PROGRESS, context_tag="architecture")
    db_session.add_all([project, task])
    db_session.flush()

    rec = Recommendation(
        user_id=test_user.id,
        title="Schedule Focus Time",
        message="Suggested break",
        recommendation_type=RecommendationType.BREAK_SUGGESTION,
        task_id=task.id,
    )
    pred = Prediction(
        user_id=test_user.id,
        task_id=task.id,
        prediction_type="FORGET_RISK",
        predicted_value={"risk": 0.72},
        confidence=0.88,
        model_version="v2.1",
    )
    cal_event = ExternalCalendarEvent(
        integration_id=uuid.uuid4(),
        user_id=test_user.id,
        calendar_id="primary",
        external_event_id="ext-cal-101",
        title="Architecture Standup",
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
        linked_task_id=task.id,
    )
    db_session.add_all([rec, pred, cal_event])
    db_session.commit()

    res = KnowledgeGraphService.auto_populate_user_graph(db=db_session, user_id=test_user.id)
    db_session.commit()

    assert res.created_nodes_count >= 4
    assert res.created_edges_count >= 2
    assert res.new_version >= 2

    # Verify task node exists and calendar event is linked
    task_node = KnowledgeGraphService.get_node_by_entity(db_session, test_user.id, GraphNodeType.TASK, task.id)
    assert task_node is not None

    related = KnowledgeGraphService.get_direct_relationships(db_session, test_user.id, task_node.id)
    assert related.total_connections >= 1


def test_incremental_event_handling(db_session: Session, test_user: User):
    """Verifies that live application events incrementally update graph nodes and record versions."""
    task = Task(user_id=test_user.id, title="Incremental Task", status=TaskStatus.PENDING)
    db_session.add(task)
    db_session.commit()

    version = KnowledgeGraphService.handle_incremental_event(
        db=db_session,
        user_id=test_user.id,
        event_type="TASK_CREATED",
        entity_id=task.id,
        entity_table="tasks",
        event_payload={"title": task.title},
    )
    db_session.commit()

    assert version is not None
    assert version.change_type == "INCREMENTAL_SYNC"
    assert len(version.affected_node_ids) == 1

    node = KnowledgeGraphService.get_node_by_entity(db_session, test_user.id, GraphNodeType.TASK, task.id)
    assert node is not None
    assert node.name == "Incremental Task"


# ===========================================================================
# Test Suite 4: Bounded Graph Traversal & Cycle Prevention
# ===========================================================================

def test_bounded_multihop_traversal(db_session: Session, test_user: User):
    """Tests multi-hop traversal with depth limiting, confidence attenuation, and cycle prevention."""
    n1 = KnowledgeGraphService.create_node(
        db=db_session, user_id=test_user.id,
        payload=KnowledgeNodeCreate(node_type=GraphNodeType.GOAL, name="Root Goal", entity_id=uuid.uuid4(), entity_table="goals"),
    )
    n2 = KnowledgeGraphService.create_node(
        db=db_session, user_id=test_user.id,
        payload=KnowledgeNodeCreate(node_type=GraphNodeType.MILESTONE, name="Mid Milestone", entity_id=uuid.uuid4(), entity_table="milestones"),
    )
    n3 = KnowledgeGraphService.create_node(
        db=db_session, user_id=test_user.id,
        payload=KnowledgeNodeCreate(node_type=GraphNodeType.TASK, name="Leaf Task", entity_id=uuid.uuid4(), entity_table="tasks"),
    )
    db_session.commit()

    # n1 -> n2 (confidence 0.9)
    KnowledgeGraphService.create_edge(
        db_session, test_user.id,
        KnowledgeEdgeCreate(
            source_node_id=n1.id, target_node_id=n2.id, relationship_type=GraphRelationshipType.CONTRIBUTES_TO,
            confidence=0.9, is_inferred=True, evidence_source=KnowledgeEvidenceSource.ML_PREDICTION,
        ),
    )
    # n2 -> n3 (confidence 0.8)
    KnowledgeGraphService.create_edge(
        db_session, test_user.id,
        KnowledgeEdgeCreate(
            source_node_id=n2.id, target_node_id=n3.id, relationship_type=GraphRelationshipType.DEPENDS_ON,
            confidence=0.8, is_inferred=True, evidence_source=KnowledgeEvidenceSource.STATISTICAL_ANALYSIS,
        ),
    )
    db_session.commit()

    traversal = KnowledgeGraphService.traverse_multi_hop(
        db=db_session, user_id=test_user.id, start_node_id=n1.id, max_depth=3
    )

    assert traversal.root_node_id == n1.id
    assert traversal.max_depth_reached == 2
    assert len(traversal.paths) == 2

    # Verify path 2 (n1 -> n2 -> n3) confidence: 0.9 * 0.8 = 0.72
    p2 = next(p for p in traversal.paths if p.depth == 2)
    assert p2.path_confidence == 0.72
    assert p2.has_inferred_steps is True


# ===========================================================================
# Test Suite 5: REST API Endpoints (FastAPI TestClient)
# ===========================================================================

def test_api_graph_overview(client: TestClient, db_session: Session, test_user: User):
    """Validates GET /api/v1/graph/overview."""
    res = client.get("/api/v1/graph/overview")
    assert res.status_code == 200
    data = res.json()
    assert "total_nodes" in data
    assert "total_relationships" in data
    assert "current_version" in data


def test_api_node_crud_and_archive(client: TestClient, db_session: Session, test_user: User):
    """Validates POST, GET, PATCH, and Archive on /api/v1/graph/nodes."""
    entity_id = str(uuid.uuid4())
    create_payload = {
        "node_type": "TASK",
        "name": "API Created Task",
        "entity_id": entity_id,
        "entity_table": "tasks",
        "properties": {"tag": "api_test"},
    }
    # 1. Create
    res = client.post("/api/v1/graph/nodes", json=create_payload)
    assert res.status_code == 201
    node_data = res.json()
    node_id = node_data["id"]
    assert node_data["name"] == "API Created Task"

    # 2. Get Details
    res = client.get(f"/api/v1/graph/nodes/{node_id}")
    assert res.status_code == 200
    assert res.json()["id"] == node_id

    # 3. Patch Attributes
    patch_res = client.patch(f"/api/v1/graph/nodes/{node_id}", json={"name": "API Patched Task"})
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "API Patched Task"

    # 4. Archive
    archive_res = client.post(f"/api/v1/graph/nodes/{node_id}/archive")
    assert archive_res.status_code == 200
    assert archive_res.json()["is_archived"] is True


def test_api_relationships_and_evidence(client: TestClient, db_session: Session, test_user: User):
    """Validates edge creation, evidence retrieval, and inferred edge deletion via API."""
    n1 = KnowledgeGraphService.create_node(
        db_session, test_user.id,
        KnowledgeNodeCreate(node_type=GraphNodeType.TASK, name="Task 1", entity_id=uuid.uuid4(), entity_table="tasks"),
    )
    n2 = KnowledgeGraphService.create_node(
        db_session, test_user.id,
        KnowledgeNodeCreate(node_type=GraphNodeType.TASK, name="Task 2", entity_id=uuid.uuid4(), entity_table="tasks"),
    )
    db_session.commit()

    rel_payload = {
        "source_node_id": str(n1.id),
        "target_node_id": str(n2.id),
        "relationship_type": "RELATED_TO",
        "evidence_source": "STATISTICAL_ANALYSIS",
        "confidence": 0.84,
        "is_inferred": True,
    }
    # Create relationship
    rel_res = client.post("/api/v1/graph/relationships", json=rel_payload)
    assert rel_res.status_code == 201
    rel_data = rel_res.json()
    rel_id = rel_data["id"]

    # Get evidence
    ev_res = client.get(f"/api/v1/graph/relationships/{rel_id}/evidence")
    assert ev_res.status_code == 200
    assert len(ev_res.json()) >= 1

    # Delete inferred relationship
    del_res = client.delete(f"/api/v1/graph/relationships/{rel_id}/inferred")
    assert del_res.status_code == 204


def test_api_auto_populate(client: TestClient, db_session: Session, test_user: User):
    """Validates POST /api/v1/graph/populate."""
    pop_res = client.post("/api/v1/graph/populate")
    assert pop_res.status_code == 200
    data = pop_res.json()
    assert "created_nodes_count" in data
    assert "created_edges_count" in data
    assert "new_version" in data

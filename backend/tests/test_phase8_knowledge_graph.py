"""
Phase 8.1 Automated Test Suite: Knowledge Graph Architecture and Intelligence Audit.

Validates:
1. Node registry idempotency and projection across Phase 1-7 and Phase 8 entities.
2. Relationship contract enforcement:
   - Multi-tenant isolation (cross-user links strictly rejected).
   - Epistemic boundary: inferred facts must have confidence < 1.0 and valid evidence source.
   - Ground truth facts must have confidence == 1.0 and non-inferred flag.
   - Rejection of self-loops.
3. The 6 Reusable Query Operations:
   - Query 1: Find related tasks across diverse relationship types.
   - Query 2: Find project dependencies and detect blocking unfinished tasks.
   - Query 3: Find goals affected by unfinished tasks with risk scoring.
   - Query 4: Trace recommendation to its evidence trail with confidence attenuation.
   - Query 5: Identify recurring behavioral patterns and high-friction regularities.
   - Query 6: Trace outcomes to earlier decisions and workflow plans.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
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


from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.db.session import Base
from app.models.enums import (
    GraphNodeType,
    GraphRelationshipType,
    KnowledgeEvidenceSource,
    RecommendationStatus,
    RecommendationType,
    TaskPriority,
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
from app.models.recommendation import Recommendation
from app.models.task import Task
from app.models.user import User
from app.schemas.knowledge_graph import KnowledgeEdgeCreate
from app.services.knowledge_graph_service import KnowledgeGraphService


@pytest.fixture
def db_session() -> Session:
    """In-memory SQLite session with full model schema."""
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
        email="kg-architect@contextiq.ai",
        display_name="KG Test User",
        timezone="UTC",
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def second_user(db_session: Session) -> User:
    user = User(
        id=uuid.uuid4(),
        email="other-user@contextiq.ai",
        display_name="Other User",
        timezone="UTC",
    )
    db_session.add(user)
    db_session.commit()
    return user


# ===========================================================================
# Test Suite 1: Node Projection and Registry Idempotency
# ===========================================================================

def test_node_registration_and_idempotency(db_session: Session, test_user: User):
    """Verifies that nodes can be registered and subsequent calls return existing nodes without duplication."""
    task_id = uuid.uuid4()
    node1 = KnowledgeGraphService.get_or_create_node(
        db=db_session,
        user_id=test_user.id,
        node_type=GraphNodeType.TASK,
        entity_id=task_id,
        entity_table="tasks",
        name="Implement Knowledge Graph Schema",
        properties={"status": "IN_PROGRESS"},
    )
    db_session.commit()

    assert node1.id is not None
    assert node1.name == "Implement Knowledge Graph Schema"

    # Re-register same entity with updated properties
    node2 = KnowledgeGraphService.get_or_create_node(
        db=db_session,
        user_id=test_user.id,
        node_type=GraphNodeType.TASK,
        entity_id=task_id,
        entity_table="tasks",
        name="Implement Knowledge Graph Schema v2",
        properties={"status": "COMPLETED", "priority": "HIGH"},
    )
    db_session.commit()

    assert node1.id == node2.id
    assert node2.name == "Implement Knowledge Graph Schema v2"
    assert node2.properties["status"] == "COMPLETED"
    assert node2.properties["priority"] == "HIGH"


# ===========================================================================
# Test Suite 2: Relationship Contract Enforcement and Epistemic Guardrails
# ===========================================================================

def test_relationship_contract_rejects_self_loop(db_session: Session, test_user: User):
    """Self-referential edges where source == target must be rejected."""
    node = KnowledgeGraphService.get_or_create_node(
        db=db_session,
        user_id=test_user.id,
        node_type=GraphNodeType.TASK,
        entity_id=uuid.uuid4(),
        entity_table="tasks",
        name="Self Task",
    )
    db_session.commit()

    payload = KnowledgeEdgeCreate(
        source_node_id=node.id,
        target_node_id=node.id,
        relationship_type=GraphRelationshipType.DEPENDS_ON,
        evidence_source=KnowledgeEvidenceSource.EXPLICIT_USER,
        confidence=1.0,
        is_inferred=False,
    )
    with pytest.raises(BadRequestError, match="Self-referential"):
        KnowledgeGraphService.create_edge(db_session, test_user.id, payload)


def test_relationship_contract_rejects_cross_user_edges(
    db_session: Session, test_user: User, second_user: User
):
    """Enforces strict tenant isolation: edges between nodes of different users are rejected."""
    user1_node = KnowledgeGraphService.get_or_create_node(
        db=db_session,
        user_id=test_user.id,
        node_type=GraphNodeType.TASK,
        entity_id=uuid.uuid4(),
        entity_table="tasks",
        name="User 1 Task",
    )
    user2_node = KnowledgeGraphService.get_or_create_node(
        db=db_session,
        user_id=second_user.id,
        node_type=GraphNodeType.TASK,
        entity_id=uuid.uuid4(),
        entity_table="tasks",
        name="User 2 Task",
    )
    db_session.commit()

    payload = KnowledgeEdgeCreate(
        source_node_id=user1_node.id,
        target_node_id=user2_node.id,
        relationship_type=GraphRelationshipType.RELATED_TO,
        evidence_source=KnowledgeEvidenceSource.EXPLICIT_USER,
        confidence=1.0,
        is_inferred=False,
    )
    with pytest.raises(NotFoundError):
        KnowledgeGraphService.create_edge(db_session, test_user.id, payload)


def test_epistemic_guardrail_rejects_unsupported_facts(db_session: Session, test_user: User):
    """
    Inferred relationships cannot be presented as verified facts (confidence must be < 1.0).
    ML/statistical inferences must have is_inferred=True.
    """
    node1 = KnowledgeGraphService.get_or_create_node(
        db=db_session, user_id=test_user.id, node_type=GraphNodeType.TASK,
        entity_id=uuid.uuid4(), entity_table="tasks", name="T1"
    )
    node2 = KnowledgeGraphService.get_or_create_node(
        db=db_session, user_id=test_user.id, node_type=GraphNodeType.TASK,
        entity_id=uuid.uuid4(), entity_table="tasks", name="T2"
    )
    db_session.commit()

    # Violation 1: ML prediction claiming is_inferred=False with 1.0 confidence
    with pytest.raises(ValueError, match="must be flagged as is_inferred=True"):
        KnowledgeEdgeCreate(
            source_node_id=node1.id,
            target_node_id=node2.id,
            relationship_type=GraphRelationshipType.INFLUENCES,
            evidence_source=KnowledgeEvidenceSource.ML_PREDICTION,
            confidence=1.0,
            is_inferred=False,
        )

    # Violation 2: Inferred relationship claiming 1.0 confidence
    with pytest.raises(ValueError, match="cannot claim absolute certainty"):
        KnowledgeEdgeCreate(
            source_node_id=node1.id,
            target_node_id=node2.id,
            relationship_type=GraphRelationshipType.INFLUENCES,
            evidence_source=KnowledgeEvidenceSource.ML_PREDICTION,
            confidence=1.0,
            is_inferred=True,
        )

    # Violation 3: Explicit user input flagged as inferred
    with pytest.raises(ValueError, match="Explicit user relationships cannot be marked as is_inferred=True"):
        KnowledgeEdgeCreate(
            source_node_id=node1.id,
            target_node_id=node2.id,
            relationship_type=GraphRelationshipType.DEPENDS_ON,
            evidence_source=KnowledgeEvidenceSource.EXPLICIT_USER,
            confidence=0.85,
            is_inferred=True,
        )


# ===========================================================================
# Test Suite 3: Query 1 - Find Related Tasks
# ===========================================================================

def test_query_find_related_tasks(db_session: Session, test_user: User):
    """Tests discovery of related tasks across multiple relationship types."""
    t1 = Task(user_id=test_user.id, title="Main Architecture Task", status=TaskStatus.IN_PROGRESS, priority=TaskPriority.HIGH)
    t2 = Task(user_id=test_user.id, title="Dependency Task", status=TaskStatus.COMPLETED, priority=TaskPriority.MEDIUM)
    t3 = Task(user_id=test_user.id, title="Associated Basket Task", status=TaskStatus.PENDING, priority=TaskPriority.LOW)
    db_session.add_all([t1, t2, t3])
    db_session.commit()

    n1 = KnowledgeGraphService.get_or_create_node(db_session, test_user.id, GraphNodeType.TASK, t1.id, "tasks", t1.title)
    n2 = KnowledgeGraphService.get_or_create_node(db_session, test_user.id, GraphNodeType.TASK, t2.id, "tasks", t2.title)
    n3 = KnowledgeGraphService.get_or_create_node(db_session, test_user.id, GraphNodeType.TASK, t3.id, "tasks", t3.title)

    # Edge 1: t1 DEPENDS_ON t2 (explicit user fact)
    KnowledgeGraphService.create_edge(
        db_session, test_user.id,
        KnowledgeEdgeCreate(
            source_node_id=n1.id,
            target_node_id=n2.id,
            relationship_type=GraphRelationshipType.DEPENDS_ON,
            evidence_source=KnowledgeEvidenceSource.EXPLICIT_USER,
            confidence=1.0,
            is_inferred=False,
        )
    )

    # Edge 2: t1 RELATED_TO t3 (statistical association rule)
    KnowledgeGraphService.create_edge(
        db_session, test_user.id,
        KnowledgeEdgeCreate(
            source_node_id=n1.id,
            target_node_id=n3.id,
            relationship_type=GraphRelationshipType.RELATED_TO,
            evidence_source=KnowledgeEvidenceSource.STATISTICAL_ANALYSIS,
            confidence=0.82,
            is_inferred=True,
        )
    )
    db_session.commit()

    response = KnowledgeGraphService.find_related_tasks(db_session, test_user.id, t1.id)
    assert response.total_count == 2
    assert {r.title for r in response.related_tasks} == {"Dependency Task", "Associated Basket Task"}
    
    # Check that inferred metadata is preserved
    inferred_task = next(r for r in response.related_tasks if r.title == "Associated Basket Task")
    assert inferred_task.is_inferred is True
    assert inferred_task.confidence == 0.82
    assert inferred_task.evidence_source == KnowledgeEvidenceSource.STATISTICAL_ANALYSIS


# ===========================================================================
# Test Suite 4: Query 2 - Find Project Dependencies and Blocking Detection
# ===========================================================================

def test_query_find_project_dependencies(db_session: Session, test_user: User):
    """Tests multi-level project dependency resolution and blocking task identification."""
    project = Project(user_id=test_user.id, title="ContextIQ Phase 8")
    task_done = Task(user_id=test_user.id, title="Phase 8.1 Schema", status=TaskStatus.COMPLETED)
    task_blocked = Task(user_id=test_user.id, title="Phase 8.2 Execution", status=TaskStatus.PENDING)
    db_session.add_all([project, task_done, task_blocked])
    db_session.commit()

    p_node = KnowledgeGraphService.get_or_create_node(db_session, test_user.id, GraphNodeType.PROJECT, project.id, "projects", project.title)
    t1_node = KnowledgeGraphService.get_or_create_node(db_session, test_user.id, GraphNodeType.TASK, task_done.id, "tasks", task_done.title)
    t2_node = KnowledgeGraphService.get_or_create_node(db_session, test_user.id, GraphNodeType.TASK, task_blocked.id, "tasks", task_blocked.title)

    # Project depends on t1
    KnowledgeGraphService.create_edge(
        db_session, test_user.id,
        KnowledgeEdgeCreate(
            source_node_id=p_node.id,
            target_node_id=t1_node.id,
            relationship_type=GraphRelationshipType.DEPENDS_ON,
        )
    )
    # Project depends on t2 (which is PENDING)
    KnowledgeGraphService.create_edge(
        db_session, test_user.id,
        KnowledgeEdgeCreate(
            source_node_id=p_node.id,
            target_node_id=t2_node.id,
            relationship_type=GraphRelationshipType.DEPENDS_ON,
        )
    )
    db_session.commit()

    response = KnowledgeGraphService.find_project_dependencies(db_session, test_user.id, project.id)
    assert len(response.dependencies) == 2
    assert response.is_blocked is True
    assert response.blocking_count == 1
    blocking_dep = next(d for d in response.dependencies if d.is_blocking)
    assert blocking_dep.name == "Phase 8.2 Execution"


# ===========================================================================
# Test Suite 5: Query 3 - Find Goals Affected by Unfinished Tasks
# ===========================================================================

def test_query_find_goals_affected_by_unfinished_tasks(db_session: Session, test_user: User):
    """Tests upward transitive traversal: Task -> Milestone -> Goal with delay risk."""
    goal = Goal(user_id=test_user.id, title="Publish ContextIQ v2", category="RESEARCH")
    milestone = Milestone(user_id=test_user.id, title="Complete Intelligence Layer", goal_id=goal.id)
    task = Task(user_id=test_user.id, title="Train Dynamic Hazard Model", priority=TaskPriority.HIGH, status=TaskStatus.IN_PROGRESS)
    db_session.add_all([goal, milestone, task])
    db_session.commit()

    g_node = KnowledgeGraphService.get_or_create_node(db_session, test_user.id, GraphNodeType.GOAL, goal.id, "goals", goal.title)
    m_node = KnowledgeGraphService.get_or_create_node(db_session, test_user.id, GraphNodeType.MILESTONE, milestone.id, "milestones", milestone.title)
    t_node = KnowledgeGraphService.get_or_create_node(db_session, test_user.id, GraphNodeType.TASK, task.id, "tasks", task.title)

    # Task CONTRIBUTES_TO Milestone
    KnowledgeGraphService.create_edge(
        db_session, test_user.id,
        KnowledgeEdgeCreate(
            source_node_id=t_node.id,
            target_node_id=m_node.id,
            relationship_type=GraphRelationshipType.CONTRIBUTES_TO,
        )
    )
    # Milestone CONTRIBUTES_TO Goal
    KnowledgeGraphService.create_edge(
        db_session, test_user.id,
        KnowledgeEdgeCreate(
            source_node_id=m_node.id,
            target_node_id=g_node.id,
            relationship_type=GraphRelationshipType.CONTRIBUTES_TO,
        )
    )
    db_session.commit()

    response = KnowledgeGraphService.find_goals_affected_by_unfinished_tasks(db_session, test_user.id, task.id)
    assert response.total_affected == 1
    affected = response.affected_goals[0]
    assert affected.goal_title == "Publish ContextIQ v2"
    assert affected.category == "RESEARCH"
    assert affected.delay_risk_score > 0.5
    assert len(affected.impact_path) == 3


# ===========================================================================
# Test Suite 6: Query 4 - Trace Recommendation to Evidence
# ===========================================================================

def test_query_trace_recommendation_to_evidence(db_session: Session, test_user: User):
    """Tests backward explainability: Recommendation <- GENERATED_BY <- Prediction <- SUPPORTS <- Pattern."""
    rec = Recommendation(
        user_id=test_user.id,
        title="Block afternoon calendar for recovery",
        message="Frequent afternoon thrashing detected.",
        recommendation_type=RecommendationType.BREAK_SUGGESTION,
        status=RecommendationStatus.PENDING,
    )
    pattern = BehavioralPattern(
        user_id=test_user.id,
        name="Afternoon Slack Thrash",
        pattern_category="FRICTION",
        description="High context switching after 2 PM",
        friction_impact=0.75,
        confidence=0.88,
    )
    db_session.add_all([rec, pattern])
    db_session.commit()

    rec_node = KnowledgeGraphService.get_or_create_node(
        db_session, test_user.id, GraphNodeType.RECOMMENDATION, rec.id, "recommendations", rec.title
    )
    pat_node = KnowledgeGraphService.get_or_create_node(
        db_session, test_user.id, GraphNodeType.BEHAVIORAL_PATTERN, pattern.id, "behavioral_patterns", pattern.name
    )

    # Edge: Pattern GENERATED_BY Recommendation (or Recommendation GENERATED_BY Pattern)
    # Target = rec_node, Source = pat_node
    KnowledgeGraphService.create_edge(
        db_session, test_user.id,
        KnowledgeEdgeCreate(
            source_node_id=pat_node.id,
            target_node_id=rec_node.id,
            relationship_type=GraphRelationshipType.GENERATED_BY,
            evidence_source=KnowledgeEvidenceSource.ML_PREDICTION,
            confidence=0.88,
            is_inferred=True,
            provenance_payload={"model": "RandomForestThrashDetector", "version": "2.4"},
        )
    )
    db_session.commit()

    trace = KnowledgeGraphService.trace_recommendation_to_evidence(db_session, test_user.id, rec.id)
    assert trace.recommendation_title == "Block afternoon calendar for recovery"
    assert len(trace.evidence_trail) == 1
    step = trace.evidence_trail[0]
    assert step.source_name == "Afternoon Slack Thrash"
    assert step.relationship == GraphRelationshipType.GENERATED_BY
    assert step.is_inferred is True
    assert trace.has_inferred_steps is True
    assert trace.overall_confidence == 0.88


# ===========================================================================
# Test Suite 7: Query 5 - Identify Recurring Behavioral Patterns
# ===========================================================================

def test_query_identify_recurring_behavioral_patterns(db_session: Session, test_user: User):
    """Tests discovery and friction-ranking of behavioral regularities."""
    p1 = BehavioralPattern(
        user_id=test_user.id,
        name="Deep Work Morning Momentum",
        pattern_category="FOCUS_OPTIMAL",
        description="Consistently achieves 90min uninterrupted flow before 11 AM",
        frequency_per_week=4.5,
        friction_impact=0.1,
        confidence=0.92,
    )
    p2 = BehavioralPattern(
        user_id=test_user.id,
        name="Post-Meeting Resumption Lag",
        pattern_category="FRICTION",
        description="Average 24 minute micro-delay after Zoom meetings",
        frequency_per_week=6.0,
        friction_impact=0.82,
        confidence=0.85,
    )
    db_session.add_all([p1, p2])
    db_session.commit()

    response = KnowledgeGraphService.identify_recurring_behavioral_patterns(db_session, test_user.id)
    assert response.total_patterns == 2
    assert response.high_friction_count == 1
    assert response.patterns[0].name == "Post-Meeting Resumption Lag"
    assert response.patterns[0].friction_impact == 0.82


# ===========================================================================
# Test Suite 8: Query 6 - Trace Outcomes to Earlier Decisions
# ===========================================================================

def test_query_trace_outcome_to_earlier_decisions(db_session: Session, test_user: User):
    """Tests causal outcome attribution back to earlier user decisions."""
    decision = Decision(
        user_id=test_user.id,
        decision_type="WORKFLOW_APPROVAL",
        chosen_option="APPROVE_SCHEDULE_SHIFT",
        alternative_options=["DISMISS", "DEFER"],
        rationale="Calendar clear in morning; shift complex task to morning focus window",
        confidence=1.0,
    )
    outcome = Outcome(
        user_id=test_user.id,
        outcome_type="TASK_COMPLETED",
        title="Completed Deep Work Ahead of Deadline",
        metric_impact={"delay_minutes_reduced": 45, "bfi_improvement": 0.3},
    )
    db_session.add_all([decision, outcome])
    db_session.commit()

    d_node = KnowledgeGraphService.get_or_create_node(
        db_session, test_user.id, GraphNodeType.DECISION, decision.id, "decisions", "Approve Schedule Shift"
    )
    o_node = KnowledgeGraphService.get_or_create_node(
        db_session, test_user.id, GraphNodeType.OUTCOME, outcome.id, "outcomes", outcome.title
    )

    KnowledgeGraphService.create_edge(
        db_session, test_user.id,
        KnowledgeEdgeCreate(
            source_node_id=d_node.id,
            target_node_id=o_node.id,
            relationship_type=GraphRelationshipType.RESULTED_IN,
            evidence_source=KnowledgeEvidenceSource.EXPLICIT_USER,
            confidence=1.0,
            is_inferred=False,
        )
    )
    db_session.commit()

    res = KnowledgeGraphService.trace_outcome_to_earlier_decisions(db_session, test_user.id, outcome.id)
    assert res.outcome_title == "Completed Deep Work Ahead of Deadline"
    assert len(res.decision_trail) == 1
    d_trail = res.decision_trail[0]
    assert d_trail["chosen_option"] == "APPROVE_SCHEDULE_SHIFT"
    assert d_trail["rationale"] == "Calendar clear in morning; shift complex task to morning focus window"
    assert res.attribution_confidence == 1.0

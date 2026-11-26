# Knowledge Graph Architecture & Developer Guide

## 1. Overview

The ContextIQ Productivity Knowledge Graph provides an entity-relationship graph connecting a user's productivity universe. Rather than maintaining isolated records for tasks, projects, calendar events, focus sessions, and behavioral friction, the graph maps these relationships with explicit confidence scoring, evidence provenance, and version tracking.

---

## 2. Graph Schema & Core Entities

The Knowledge Graph is implemented in PostgreSQL using SQLAlchemy models:

- **[KnowledgeNode](file:///e:/Downloads 🔃/ContextIQ-main/ContextIQ-main/backend/app/models/knowledge_graph.py#L45)**: Represents entities such as `TASK`, `PROJECT`, `GOAL`, `BEHAVIORAL_PATTERN`, `FOCUS_SESSION`, `INTERVENTION`, `DECISION`, or `OUTCOME`.
  - `entity_type`: Category of the node.
  - `entity_id`: UUID of the backing source record (e.g., Task UUID).
  - `properties`: Flexible JSONB dictionary of domain attributes.
  - `is_archived`: Soft-deletion flag.
- **[KnowledgeRelationship](file:///e:/Downloads 🔃/ContextIQ-main/ContextIQ-main/backend/app/models/knowledge_graph.py#L90)**: Directed edge connecting a source node to a target node.
  - `relationship_type`: Semantic relationship (e.g. `BLOCKS`, `CONTRIBUTES_TO`, `CAUSES_FRICTION`, `ASSOCIATED_WITH`, `RESOLVED_BY`).
  - `is_inferred`: Boolean flag distinguishing explicit user relationships from mined inferences.
  - `confidence`: Float between 0.0 and 1.0.
  - `expires_at`: Optional timestamp for temporal expiration of inferred connections.
- **[KnowledgeEvidence](file:///e:/Downloads 🔃/ContextIQ-main/ContextIQ-main/backend/app/models/knowledge_graph.py#L140)**: Provenance records linking a relationship to historical observations, logs, or metrics.
- **[KnowledgeGraphVersion](file:///e:/Downloads 🔃/ContextIQ-main/ContextIQ-main/backend/app/models/knowledge_graph.py#L180)**: Versioning metadata tracking graph population checkpoints.

---

## 3. Node Deduplication & Ownership

To prevent duplicate nodes representing the same real-world entity:
1. Every node maintains a unique index on `(user_id, entity_type, entity_id)`.
2. Graph population utilities use `upsert` semantics to update node attributes without creating redundant nodes.
3. Node queries always filter by `user_id` to strictly guarantee tenant isolation.

---

## 4. Relationship Lifecycle & Confidence Scoring

Relationships adhere to an explicit lifecycle:
1. **Explicit Creation**: Manually asserted by the user (confidence $= 1.0$, `is_inferred = False`).
2. **Automated Inference**: Discovered by association mining or dependency engines (confidence calculated from evidence weight, `is_inferred = True`).
3. **Decay & Invalidation**: Inferred relationships with stale evidence or user contradictions have their confidence decayed or are marked expired via `expires_at <= now()`.

---

## 5. API Endpoints

- `GET /api/v1/knowledge-graph/nodes`: Query and search graph nodes by type or keyword.
- `GET /api/v1/knowledge-graph/nodes/{node_id}/subgraph`: Retrieve adjacent nodes and edges up to depth $N$.
- `POST /api/v1/knowledge-graph/relationships`: Create an explicit relationship.
- `DELETE /api/v1/knowledge-graph/relationships/{id}`: Invalidate or remove an edge.
- `POST /api/v1/knowledge-graph/sync`: Trigger automated graph sync from tasks, goals, and behavioral logs.

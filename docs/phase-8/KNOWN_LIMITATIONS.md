# Phase 8: Known Limitations & Future Enhancements

## 1. Overview

While Phase 8 achieves full end-to-end functionality across all specified requirements, this document outlines known operational boundaries, mathematical assumptions, and recommended future roadmap improvements.

---

## 2. Documented Limitations & Operational Boundaries

### 2.1 Cold-Start & Data Sufficiency Requirements
- **Forecasting & Monte Carlo Simulation**: Project forecasts require at least 5 completed tasks and 14 days of telemetry before transitioning from `DATA_INSUFFICIENT` to `DATA_SUFFICIENT`. When data is insufficient, forecasts report wide uncertainty spreads ($> 20$ days) and emit epistemic disclaimers.
- **Behavioral Trend Analysis**: Mann-Kendall trend tests and changepoint detection require a minimum of 7 consecutive daily metric snapshots to establish statistical significance ($p < 0.05$).

### 2.2 In-Memory vs. Distributed Graph Scale
- **Graph Storage**: The Knowledge Graph is currently hosted on PostgreSQL using indexed adjacency tables (`KnowledgeNode`, `KnowledgeRelationship`).
- **Scale Ceiling**: Traversal queries perform optimally up to depth $N \le 3$ for single users ($< 50,000$ edges). For multi-tenant organizations scaling beyond 1,000,000 nodes per tenant, an external graph database engine (such as Neo4j or Amazon Neptune) or recursive CTE optimization should be evaluated.

### 2.3 Dependency Inference Heuristics
- **Rule-Based & Sequential Inferences**: Cross-task dependencies rely on temporal sequencing and shared goal associations. In rare edge cases where a user alternates rapidly between unrelated tasks, inferred blockers may generate false positives until confirmed or rejected by the user.

### 2.4 LLM Provider Dependency in Natural-Language Analytics
- **Query Planner Fallback**: While the query planner uses deterministic keyword matching and AST construction for canonical productivity queries, complex compound questions fallback to the multi-provider LLM abstraction. In offline or mock environments, queries outside the canonical dictionary return generalized semantic matches.

---

## 3. Recommended Future Roadmap

1. **Active Learning Feedback Loop**: Implement active learning algorithms to re-rank dependency candidates based on explicit user confirmation and rejection patterns.
2. **Calendar Conflict Bi-Directional Sync**: Integrate direct CalDAV / Google Calendar bi-directional schedule adjustments for proposed counterfactual focus blocks.
3. **Federated Behavioral Privacy**: Enable local client-side embedding computation for sensitive task descriptions before synchronizing graph node metadata.

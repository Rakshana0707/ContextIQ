# ContextIQ Architectural Boundaries & Known Limitations
## Phase 7 Production Baseline

This document transparently records current architectural boundaries, scale ceilings, and non-blocking limitations for ContextIQ Phase 7.

---

## 1. Concurrency & Rate Limiting Boundaries

1. **In-Memory Rate Limiting**:
   - The token-bucket rate limiter (`RateLimiterMiddleware`) tracks client request tokens in local application memory.
   - *Impact*: In a multi-replica horizontal cluster behind an NGINX round-robin load balancer, the effective rate limit scales proportionally with the number of replicas (e.g. 60 req/min * 3 instances = 180 req/min cluster-wide).
   - *Phase 8 Migration*: Migrate token buckets to shared Redis instances (`redis-py` with sliding window script).

2. **In-Memory Circuit Breakers**:
   - The circuit breaker states for external calendar providers (`calendar_sync`, `google_oauth`, `llm_inference`) are held in process memory.
   - *Impact*: A circuit tripping in Instance A does not immediately trip in Instance B until Instance B also encounters consecutive failures.

---

## 2. Execution Engine Limitations

1. **Synchronous Action Dispatch**:
   - Registered actions (e.g., `calendar:insert_focus_block`, `task:update_priority`) execute synchronously inside worker threads.
   - *Boundary*: Recommended maximum steps per workflow plan is 20 steps. Workflow plans exceeding 20 steps should be decomposed into multiple sequenced child workflows.

2. **Calendar Timezone Assumption**:
   - External calendar event rescheduling calculations currently assume the user's primary calendar operates in UTC unless an explicit IANA timezone string is passed in `user.timezone_preference`.

3. **Compensation Stack Boundaries**:
   - Irreversible actions (such as sending an external email or push notification) cannot be unwound via inverse compensation. These actions are explicitly marked `is_reversible=False` in `ActionRegistry` and require user confirmation prior to execution.

---

## 3. Behavioral Telemetry & Event Constraints

1. **Out-of-Order Event Window**:
   - Delayed and offline events are accepted up to 24 hours into the past. Telemetry events timestamped > 24 hours prior are ingested and stored in `StandardEventRecord` but do not retroactively trigger real-time proactive notification feeds.

2. **Conformal Uncertainty Bounds**:
   - Empirical intervals for behavioral friction index (BFI) and forgetting risk use an inductive split-conformal calibration set. On users with fewer than 10 logged tasks, intervals default to a conservative baseline interval of `[55%-95%]`.

---

## 4. Phase 8 Evolution Roadmap

| Item | Current Implementation | Phase 8 Target |
| :--- | :--- | :--- |
| Rate Limiting | In-Memory Token Bucket | Redis Sliding-Window Token Bucket |
| Calendar Integration | Polling Sync (5m interval) | Webhook Subscriptions (Google/Graph Push) |
| Audit Storage | Append-Only PostgreSQL Table | Cross-Region WORM Object Storage |
| Workflow Actions | Synchronous In-Process Dispatch | Distributed Celery / Temporal Orchestrator |
| Privacy Erasure | Soft-Delete + Anonymization | Automated Cryptographic Erasure (Zero-Knowledge) |

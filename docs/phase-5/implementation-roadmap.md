# Phase 5 Implementation Roadmap: External Ecosystem Integration & Cross-Platform Intelligence

## 1. Executive Roadmap Overview

Phase 5 transitions ContextIQ from an isolated single-device platform into a connected, cross-platform cognitive co-pilot. To ensure engineering excellence, strict data ownership, and uninterrupted stability for existing Phases 1–4 capabilities, Phase 5 is structured into eight disciplined subphases.

```mermaid
gantt
    title ContextIQ Phase 5 Engineering Roadmap
    dateFormat  YYYY-MM-DD
    section Architecture
    Phase 5.1: Architecture Audit & Design Specifications       :done,    des1, 2026-11-24, 2026-11-25
    section Data & Security Core
    Phase 5.2: Relational Schema & Alembic Migrations          :active,  mig1, 2026-11-26, 2026-12-03
    Phase 5.3: Core Provider Abstraction & Token Vault         :         sec1, 2026-12-04, 2026-12-12
    section Synchronization
    Phase 5.4: Calendar Connectors & Delta Webhooks            :         cal1, 2026-12-13, 2026-12-23
    Phase 5.5: Cross-Device Sync & Multi-Platform Ingestion    :         sync1, 2026-12-24, 2027-01-05
    section Mobile & Edge
    Phase 5.6: Mobile Companion Clients (Android & iOS)        :         mob1, 2027-01-06, 2027-01-20
    Phase 5.7: Location Intelligence & Geofence Pipeline       :         loc1, 2027-01-21, 2027-01-30
    section UI & Validation
    Phase 5.8: Frontend Integration Portal & Verification      :         ui1,  2027-01-31, 2027-02-12
```

---

## 2. Detailed Subphase Specifications

### Phase 5.1: Architecture Audit & Design Specifications (Current Deliverable)
- **Status**: Completed.
- **Objectives**: Complete repository audit, design unified provider abstraction, formalize cross-device event contracts, establish security/OAuth architecture, define data ownership invariants, and author comprehensive documentation suite in `docs/phase-5/`.
- **Deliverables**: Complete documentation package in `docs/phase-5/`.

---

### Phase 5.2: Relational Schema & Alembic Migrations
- **Objective**: Introduce database foundations for external integrations, normalized calendar events, and edge device registries without disrupting existing tables.
- **Key Tasks**:
  1. Author Alembic migration script `h8i9j0k1l2m3_add_phase5_external_integrations.py`.
  2. Implement SQLAlchemy ORM models in `backend/app/models/`:
     - `external_integration.py` (`ExternalIntegration`)
     - `external_calendar_event.py` (`ExternalCalendarEvent`)
     - `user_device.py` (`UserDevice`)
  3. Configure table indexes, unique constraints, and cascading foreign keys.
  4. Ensure full Row-Level Security (RLS) policy compatibility for tenant isolation.
- **Testing Criteria**: 100% migration upgrade and downgrade test coverage.

---

### Phase 5.3: Core Provider Abstraction & Cryptographic Token Vault
- **Objective**: Build the backend token management layer, AES-256-GCM vault, and base provider interfaces.
- **Key Tasks**:
  1. Implement `TokenVault` in `backend/app/core/token_vault.py` with HKDF key derivation and AES-256-GCM authenticated cipher.
  2. Implement abstract base classes `IntegrationProvider` and `CalendarProvider` in `backend/app/integrations/base.py`.
  3. Implement `ProviderRegistry` and dynamic adapter factory.
  4. Build OAuth 2.0 PKCE helper utilities and state parameter signing routines.
- **Testing Criteria**: Cryptographic unit tests verifying token sealing, tampering rejection, and key derivation reproducibility.

---

### Phase 5.4: Calendar Connectors (Google & Microsoft) & Delta Webhooks
- **Objective**: Implement production drivers for Google Calendar API v3 and Microsoft Graph Calendar API.
- **Key Tasks**:
  1. Build `GoogleCalendarProvider` (`backend/app/integrations/google/`):
     - `initial_sync()` and incremental sync via `syncToken`.
     - Push notification channel registration via Google Watch.
  2. Build `MicrosoftOutlookProvider` (`backend/app/integrations/microsoft/`):
     - Delta queries on `/me/calendarView/delta`.
     - Webhook subscription and handshake validation.
  3. Build webhook ingestion controller in `backend/app/api/v1/integrations/webhooks.py`.
  4. Wire calendar meeting blackouts into `UserFocusWindow` and `NotificationIntelligenceManager`.
- **Testing Criteria**: Mocked HTTP integration tests validating delta token recovery upon HTTP 410 Gone.

---

### Phase 5.5: Cross-Device Synchronization & Multi-Platform Ingestion
- **Objective**: Extend telemetry ingestion to support multi-device streams, causal ordering, and session stitching.
- **Key Tasks**:
  1. Upgrade `POST /api/v1/telemetry/events/batch` to accept cross-device schema v2.0.0.
  2. Implement device enrollment endpoint: `POST /api/v1/devices/enroll`.
  3. Implement Lamport logical clock tracking and client clock skew compensation.
  4. Extend Session Reconstruction Engine (`backend/app/services/session_reconstruction_engine.py`) to stitch desktop and mobile sessions.
- **Testing Criteria**: Concurrency testing verifying idempotent deduplication of identical event IDs across parallel requests.

---

### Phase 5.6: Mobile Companion Applications (Android & iOS)
- **Objective**: Develop native companion background agents for Android and iOS devices.
- **Key Tasks**:
  1. **Android Client**:
     - `UsageStatsManager` foreground monitoring worker.
     - Screen on/off `BroadcastReceiver`.
     - Room SQLite buffer and `WorkManager` batch sync.
     - FCM push notification handling with actionable buttons.
  2. **iOS Client**:
     - `BGAppRefreshTask` and `BGProcessingTask` handlers.
     - APNs interactive push notification receiver.
     - Local SQLite offline persistence.
- **Testing Criteria**: Battery benchmarking verifying $< 2\%$ battery consumption over a 24-hour period.

---

### Phase 5.7: Location Intelligence & Geofence Pipeline
- **Objective**: Implement battery-preserving OS geofencing and departure contextual triggers.
- **Key Tasks**:
  1. Implement mobile geofence registration pipeline against `GET /api/v1/locations`.
  2. Implement Android `GeofencingClient` and iOS `CLCircularRegion` listeners.
  3. Wire `location_exited` and `location_entered` events into the Contextual Bandit Engine (`arm_3_one_more_thing`).
  4. Build commute mode detection heuristics.
- **Testing Criteria**: Boundary simulation tests validating departure nudge firing within 30 seconds of region exit.

---

### Phase 5.8: Frontend Integration Center & End-to-End Validation
- **Objective**: Deliver user-facing integration controls in Next.js 16 and conduct comprehensive security audits.
- **Key Tasks**:
  1. Build `/integrations` management portal in Next.js 16:
     - Calendar connection cards (Google Calendar, Outlook).
     - Connected device manager (active devices, last sync time, revoke button).
     - Geofence visualization and location manager.
  2. End-to-end load and performance testing.
  3. Security penetration audit (PKCE compliance, zero credential leakage validation).
- **Testing Criteria**: End-to-end user journey test from OAuth authorization to calendar sync and mobile push notification delivery.

---

## 3. Risk Management & Mitigation Strategies

| Risk Factor | Likelihood | Impact | Architectural Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| **Provider Rate Limiting (429s)** | Medium | High | Exponential backoff with randomized jitter; delta tokens minimize query volume; webhooks eliminate polling. |
| **Delta Token Invalidation (410 Gone)** | Low | Medium | Automatic detection and graceful fallback to full resynchronization without duplicating existing event IDs. |
| **Mobile Battery Drain** | High | Critical | Zero continuous GPS; OS-level geofences; usage sampling occurs only during active screen-on intervals; Wi-Fi preferred uploads. |
| **Clock Skew Across Edge Devices** | High | Medium | Server-side skew compensation via `X-Client-Timestamp` headers combined with Lamport logical clock causal ordering. |
| **User Data Overwrite Accusations** | Low | Catastrophic | Strict data ownership rules: ContextIQ never edits external meeting times/attendees; cooperative focus blocks adapt to external user moves. |

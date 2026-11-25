# Phase 5 System Architecture: External Ecosystem & Cross-Platform Intelligence

## 1. Architectural Overview

ContextIQ Phase 5 introduces a modular, cross-platform architecture designed to bridge desktop telemetry, mobile activity, and enterprise cloud calendar services into a unified cognitive intelligence engine.

```mermaid
flowchart TB
    subgraph Client Tier
        DA["Desktop Telemetry Agent<br/>(PyQt6 / Win32 Hooks)"]
        RN["Mobile Companion<br/>(React Native / Expo)"]
        WEB["Next.js 16 Web Dashboard<br/>(Tailwind CSS / Lucide)"]
    end

    subgraph API Gateway & Ingestion
        GW["FastAPI Core Gateway (:8000)"]
        AUTH["OAuth 2.0 PKCE / JWT Auth"]
        RATE["Rate Limiter & Request Validator"]
    end

    subgraph Integration Core
        PR["Provider Registry"]
        TV["AES-256-GCM Token Vault"]
        G_ADP["Google Calendar Adapter"]
        M_ADP["Microsoft Graph Adapter"]
    end

    subgraph Intelligence & Analytics Tier
        SE["Scheduling Engine<br/>(Availability & Fatigue)"]
        TR["Session Reconstruction<br/>(Cross-Device Stitching)"]
        LI["Location Intelligence<br/>(Apriori Association Engine)"]
        NI["Notification Intelligence<br/>(Quiet Hours & Focus Gating)"]
    end

    subgraph Persistence Tier
        PG[("PostgreSQL 16 DB<br/>Row-Level Security")]
        SQ[("Mobile SQLite Cache<br/>Offline Mutex Queue")]
    end

    DA -->|HTTP Telemetry Stream| GW
    RN <-->|REST API / Secure Store| GW
    RN <-->|Offline Synchronization| SQ
    WEB <-->|React Query / Server Actions| GW

    GW --> AUTH
    GW --> RATE
    GW --> PR
    GW --> SE
    GW --> TR
    GW --> LI
    GW --> NI

    PR <--> G_ADP
    PR <--> M_ADP
    PR <--> TV
    TV <--> PG

    G_ADP <-->|Google Calendar v3 API| G_EXT[("Google Cloud")]
    M_ADP <-->|Microsoft Graph v1.0| M_EXT[("Microsoft Entra")]

    SE <--> PG
    TR <--> PG
    LI <--> PG
    NI <--> PG
```

---

## 2. Component Subsystems

### A. Core Integration Framework
- **`ProviderRegistry`**: Dynamic provider registry managing lifecycles of `GoogleCalendarProvider` and `MicrosoftCalendarProvider`. Supports runtime lookup, credential validation, and health diagnostics.
- **`TokenVault`**: Cryptographic storage leveraging PBKDF2/HKDF key derivation with AES-256-GCM authenticated encryption. Access tokens, refresh tokens, and synchronization states (`syncToken`, `deltaLink`) are sealed before persisting to PostgreSQL.

### B. Intelligent Scheduling Subsystem
- **Availability Matrix Calculation**: Integrates user working hours, external calendar events (`busy` / `tentative`), existing task commitments, and cognitive recovery buffers.
- **Micro-Delay & Fatigue Buffers**: Injects dynamic rest buffers ($\Delta t_{\text{recovery}}$) between high-cognitive-load blocks and preceding meetings.
- **Approval Gating**: Prevents automated external calendar modifications without explicit user consent.

### C. Cross-Device Synchronization Engine
- **Unified Event Schema**: Normalizes desktop active window events, mobile app actions, calendar appointments, and manual check-ins with platform metadata (`WINDOWS`, `ANDROID`, `IOS`, `WEB`, `GOOGLE_CALENDAR`, `MICROSOFT_CALENDAR`).
- **Device Registry**: Manages device lifecycle, tracking `device_id`, platform, application version, registration timestamp, last active timestamp, and revocation status.
- **Cross-Device Session Reconstruction**: Synthesizes multi-device interactions into coherent work episodes, accounting for clock skew and device transitions.

### D. Location-Aware Context Engine
- **Discrete Geofencing Pipeline**: Coarse circular geofences (minimum 100m radius) evaluated on-device. Client only transmits `GEOFENCE_ENTER`, `GEOFENCE_EXIT`, or `MANUAL` check-in events.
- **Context Association Mining**: Adapts Apriori and FP-Growth rule mining to correlate task completions with specific physical contexts, categorizing associations into `EXPLICIT`, `STATISTICALLY_OBSERVED`, and `LOW_CONFIDENCE` tiers.
- **Fatigue & Focus Protection**: Smart reminders are automatically suppressed between 22:00 and 08:00 or when an active focus session is detected.

---

## 3. Relational Schema Architecture (PostgreSQL)

Phase 5 introduced five dedicated database tables and extended two existing models via Alembic migrations:

```mermaid
erDiagram
    USERS ||--o{ CALENDAR_INTEGRATIONS : owns
    USERS ||--o{ EXTERNAL_CALENDAR_EVENTS : syncs
    USERS ||--o{ SCHEDULE_PROPOSALS : reviews
    USERS ||--o{ USER_DEVICES : registers
    USERS ||--o{ LOCATIONS : creates
    LOCATIONS ||--o{ LOCATION_CHECKINS : tracks
    LOCATIONS ||--o{ LOCATION_ROUTINE_ASSOCIATIONS : associates

    CALENDAR_INTEGRATIONS {
        uuid id PK
        uuid user_id FK
        string provider
        string encrypted_access_token
        string encrypted_refresh_token
        datetime token_expires_at
        jsonb granted_scopes
        string sync_token
        datetime last_sync_at
        string sync_status
    }

    EXTERNAL_CALENDAR_EVENTS {
        uuid id PK
        uuid user_id FK
        uuid integration_id FK
        string provider_event_id
        string title
        datetime start_time
        datetime end_time
        string timezone
        boolean is_all_day
        string availability
        boolean is_private
        jsonb raw_payload
    }

    SCHEDULE_PROPOSALS {
        uuid id PK
        uuid user_id FK
        uuid task_id FK
        datetime proposed_start
        datetime proposed_end
        float confidence_score
        string scheduling_rationale
        string status
        boolean written_to_external
    }

    USER_DEVICES {
        uuid id PK
        uuid user_id FK
        string device_id UK
        string device_type
        string platform
        string device_name
        string app_version
        datetime last_seen_at
        boolean is_revoked
    }

    LOCATIONS {
        uuid id PK
        uuid user_id FK
        string name
        string location_type
        float latitude
        float longitude
        int radius_meters
        boolean reminders_enabled
        boolean arrival_reminder_enabled
        boolean departure_reminder_enabled
    }

    LOCATION_CHECKINS {
        uuid id PK
        uuid user_id FK
        uuid location_id FK
        string check_in_type
        datetime occurred_at
        jsonb context_metadata
    }

    LOCATION_ROUTINE_ASSOCIATIONS {
        uuid id PK
        uuid user_id FK
        uuid location_id FK
        uuid task_id FK
        string trigger_type
        string association_source
        float confidence_score
        float support_score
    }
```

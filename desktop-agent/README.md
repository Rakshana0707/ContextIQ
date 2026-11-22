# ContextIQ Windows Desktop Behavioral Activity Collector

The **ContextIQ Desktop Agent** is a lightweight, privacy-preserving Windows background agent that passively collects behavioral activity metadata (foreground application transitions, active focus durations, and aggregate user inactivity).

All collection integrates with the ContextIQ backend and session reconstruction engine while adhering strictly to the **ContextIQ Anti-Surveillance Manifesto**.

---

## 1. Core Capabilities & Architecture

```
desktop-agent/
    app/
        main.py                  # CLI and Windows process lifecycle management
        config.py                # Agent configuration and device ID resolution
        agent.py                 # Core DesktopAgent orchestrator
        collectors/
            foreground_window.py # Low-level Win32 foreground process inspection
            application_activity.py # Focus intervals, monotonic durations & transitions
            idle_detector.py     # Aggregate inactivity detection via GetLastInputInfo
        events/
            event_builder.py     # Canonical envelope builder (UUIDv7, timestamps)
            event_queue.py       # Thread-safe in-memory buffer
        privacy/
            consent_checker.py   # Strict opt-in & zero secret buffering guard
            exclusion_manager.py # Process denylist & user application exclusions
        sync/
            api_client.py        # Backend REST API client
            sync_worker.py       # Background batch synchronization with backoff
        storage/
            local_database.py    # Persistent SQLite buffer (WAL mode)
        monitoring/
            health.py            # Process CPU, RSS memory & heartbeat monitor
    tests/                       # Mocked deterministic automated tests
    requirements.txt             # Agent dependencies
    README.md                    # Module documentation
```

---

## 2. Privacy & Anti-Surveillance Invariants

- **Zero Keystrokes & Clicks**: No low-level keyboard hooks (`WH_KEYBOARD_LL`) or mouse hooks (`WH_MOUSE_LL`).
- **No Screenshots**: No screen recording, video capture, or OCR.
- **Window Titles Omitted by Default**: Window titles are strictly omitted (`None`) to protect confidential documents and private messages.
- **Zero Secret Buffering**: When monitoring is paused or consent is revoked, the agent **immediately halts collection and does NOT secretly buffer events**.
- **Global Security Denylist**: Password managers (`1password.exe`, `keepass.exe`, `bitwarden.exe`, etc.) and system utilities (`regedit.exe`, `taskmgr.exe`) are masked/suppressed at the OS boundary.

---

## 3. Command Line Interface (CLI)

The agent provides a clean command-line interface via `app/main.py` or `scripts/run_desktop_agent.ps1`:

### Run in Foreground (Interactive / Debug)
```powershell
python app/main.py run --grant-consent -v
```

### Start in Background (Detached)
```powershell
python app/main.py start --grant-consent
```

### Check Status & Metrics
```powershell
python app/main.py status
```
Outputs:
```text
================ ContextIQ Desktop Agent Status ================
 Agent Process State   : RUNNING (PID: 12480)
 Target User ID        : 00000000-0000-0000-0000-000000000001
 Device Hardware ID    : e3b0c44298fc1c14...
 Backend Endpoint      : http://localhost:8000/api/v1
 Polling Sample Rate   : 0.5s
 Idle Threshold        : 120.0s
 Total Buffered Events : 42
 Pending Sync Events   : 0
 Successfully Synced   : 42
 Failed Sync Events    : 0
================================================================
```

### Stop Background Agent
```powershell
python app/main.py stop
```

### Windows Startup Integration (Optional)
Requires explicit user authorization flag (`--confirm`):
```powershell
# Enable startup at user login
python app/main.py autostart --enable --confirm

# Disable startup
python app/main.py autostart --disable
```

---

## 4. Configuration

Configurable via environment variables prefixed with `CONTEXTIQ_AGENT_`:

| Environment Variable | Default | Description |
| :--- | :--- | :--- |
| `CONTEXTIQ_AGENT_BACKEND_URL` | `http://localhost:8000/api/v1` | ContextIQ backend REST endpoint |
| `CONTEXTIQ_AGENT_USER_ID` | `00000000-0000-0000-0000-000000000001` | Target user UUID |
| `CONTEXTIQ_AGENT_POLLING_INTERVAL_SECONDS` | `0.5` | Sampling loop sleep interval |
| `CONTEXTIQ_AGENT_IDLE_THRESHOLD_SECONDS` | `120.0` | Inactivity threshold before idle event |
| `CONTEXTIQ_AGENT_SYNC_INTERVAL_SECONDS` | `10.0` | Server synchronization batch interval |
| `CONTEXTIQ_AGENT_DB_PATH` | `data/agent_buffer.db` | Local SQLite WAL persistence path |
| `CONTEXTIQ_AGENT_CAPTURE_WINDOW_TITLES` | `False` | Strictly False by default |

---

## 5. Automated Tests

Run the full deterministic unit test suite with mocked OS APIs:
```powershell
pytest desktop-agent/tests -v
```

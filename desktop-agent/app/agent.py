"""Core DesktopAgent orchestrator coordinating collectors, privacy, storage, and sync."""
import logging
import signal
import sys
import threading
import time
from typing import Any

from app.collectors.application_activity import ApplicationActivityTracker
from app.collectors.foreground_window import ForegroundWindowCollector, NativeWin32Provider
from app.collectors.idle_detector import IdleDetector, IdleTimeProvider
from app.config import AgentConfig
from app.events.event_builder import EventBuilder
from app.events.event_queue import EventQueue
from app.monitoring.health import HealthMonitor
from app.privacy.consent_checker import ConsentChecker
from app.privacy.exclusion_manager import ExclusionManager
from app.storage.local_database import LocalDatabase
from app.sync.api_client import ContextIQApiClient
from app.sync.sync_worker import SyncWorker

logger = logging.getLogger(__name__)


class DesktopAgent:
    """Production-grade Windows desktop behavioral activity collector."""

    def __init__(
        self,
        config: AgentConfig | None = None,
        win32_provider: NativeWin32Provider | None = None,
        idle_provider: IdleTimeProvider | None = None,
        api_client: ContextIQApiClient | None = None,
    ):
        self.config = config or AgentConfig()

        # Core components
        self.event_builder = EventBuilder(
            user_id=self.config.user_id,
            device_id=self.config.device_id,
        )
        self.event_queue = EventQueue(max_size=self.config.max_queue_size)

        db_path = self.config.get_absolute_db_path()
        self.local_db = LocalDatabase(db_path=db_path)

        self.consent_checker = ConsentChecker()
        self.exclusion_manager = ExclusionManager()

        self.foreground_collector = ForegroundWindowCollector(
            provider=win32_provider,
            capture_window_titles=self.config.capture_window_titles,
        )
        self.activity_tracker = ApplicationActivityTracker(
            event_builder=self.event_builder,
            rapid_switch_threshold_seconds=self.config.rapid_switch_threshold_seconds,
        )
        self.idle_detector = IdleDetector(
            event_builder=self.event_builder,
            idle_threshold_seconds=self.config.idle_threshold_seconds,
            provider=idle_provider,
        )

        self.health_monitor = HealthMonitor(
            event_builder=self.event_builder,
            local_db=self.local_db,
        )

        self.api_client = api_client or ContextIQApiClient(
            base_url=self.config.backend_url,
            api_token=self.config.api_token,
        )
        self.sync_worker = SyncWorker(
            local_db=self.local_db,
            api_client=self.api_client,
            consent_checker=self.consent_checker,
            exclusion_manager=self.exclusion_manager,
            health_monitor=self.health_monitor,
            user_id=self.config.user_id,
            device_id=self.config.device_id,
            sync_interval_seconds=self.config.sync_interval_seconds,
            batch_size=self.config.batch_size,
            max_retries=self.config.max_retries,
        )

        self._stop_event = threading.Event()
        self._is_running = False

    def setup_signal_handlers(self) -> None:
        """Register handlers for graceful shutdown on SIGINT and SIGTERM."""
        def _handle_signal(signum: int, frame: Any) -> None:
            logger.info("Received termination signal (%d); initiating graceful shutdown...", signum)
            self.stop()

        try:
            signal.signal(signal.SIGINT, _handle_signal)
            signal.signal(signal.SIGTERM, _handle_signal)
        except (ValueError, AttributeError):
            # May occur in non-main threads
            pass

    def step(self) -> list[dict[str, Any]]:
        """Single sampling step for testing or polling loop execution.

        Returns list of newly constructed events.
        """
        generated_events: list[dict[str, Any]] = []

        # 1. Strict Consent Check
        # If monitoring is not allowed (consent revoked, missing, or paused),
        # STOP collection immediately and DO NOT buffer secretly.
        if not self.consent_checker.is_collection_allowed():
            # Reset trackers cleanly so resumed collection doesn't report stale interval
            self.activity_tracker.reset()
            self.idle_detector.reset()
            return []

        # 2. Collect Foreground Application
        try:
            app_info = self.foreground_collector.get_foreground_app()
            app_id = app_info.application_identifier

            # 3. Application Exclusion & Denylist check
            if self.exclusion_manager.is_excluded(app_id):
                # If currently active app switched into an excluded app, flush previous app deactivation
                deact_event = self.activity_tracker.flush_current_activity(transition_trigger="SWITCHED_TO_EXCLUDED")
                if deact_event and self.consent_checker.is_collection_allowed("app_transitions"):
                    self.event_queue.put(deact_event)
                    generated_events.append(deact_event)
            else:
                # App is permitted; track transitions if category is consented
                if self.consent_checker.is_collection_allowed("app_transitions"):
                    act_events = self.activity_tracker.process_foreground_sample(app_info)
                    for ev in act_events:
                        self.event_queue.put(ev)
                        generated_events.append(ev)

            # 4. Inactivity & Idle Detection
            if self.consent_checker.is_collection_allowed("inactivity_detection"):
                # Pass current app identifier only if not excluded
                active_app_for_idle = None if self.exclusion_manager.is_excluded(app_id) else app_id
                idle_events = self.idle_detector.check_idle_state(current_app_id=active_app_for_idle)
                for ev in idle_events:
                    self.event_queue.put(ev)
                    generated_events.append(ev)

            # 5. Periodic Heartbeat
            now_mono = time.monotonic()
            if now_mono - self.health_monitor.last_heartbeat_time >= self.config.heartbeat_interval_seconds:
                hb = self.health_monitor.create_heartbeat_event()
                self.event_queue.put(hb)
                generated_events.append(hb)

        except Exception as e:
            logger.error("Error in agent sampling step: %s", e, exc_info=True)

        # 6. Flush in-memory queue to persistent local SQLite buffer
        self._flush_queue_to_storage()

        return generated_events

    def _flush_queue_to_storage(self) -> None:
        """Drain in-memory queue and persist to SQLite buffer."""
        batch = self.event_queue.get_batch(max_items=self.config.batch_size)
        if batch and self.consent_checker.is_collection_allowed("local_storage"):
            self.local_db.insert_events_batch(batch)

    def run(self) -> None:
        """Run the agent background loop continuously until stopped."""
        self._is_running = True
        self._stop_event.clear()
        self.setup_signal_handlers()

        logger.info("ContextIQ Desktop Agent starting (User=%s, Device=%s)", self.config.user_id, self.config.device_id)

        # Initial policy fetch from backend
        self._initial_backend_sync()

        # Emit agent_started event if consented
        if self.consent_checker.is_collection_allowed():
            started_ev = self.event_builder.build_agent_started()
            self.event_queue.put(started_ev)
            self._flush_queue_to_storage()

        # Start background sync worker
        self.sync_worker.start()

        # Main polling loop
        logger.info("Entering main collection loop (polling interval=%.2fs)...", self.config.polling_interval_seconds)
        while not self._stop_event.is_set():
            try:
                self.step()
            except Exception as e:
                logger.error("Unhandled exception in agent loop: %s", e, exc_info=True)

            self._stop_event.wait(timeout=self.config.polling_interval_seconds)

        self._shutdown()

    def pause_telemetry(self, duration_seconds: float | None = None, reason: str = "USER_REQUEST") -> None:
        """Pause telemetry collection and emit telemetry_paused event."""
        if self.consent_checker.is_collection_allowed():
            paused_ev = self.event_builder.build_telemetry_paused(duration_seconds=duration_seconds, reason=reason)
            self.event_queue.put(paused_ev)
            self._flush_queue_to_storage()
        self.consent_checker.pause(duration_seconds=duration_seconds)

    def resume_telemetry(self) -> None:
        """Resume telemetry collection and emit telemetry_resumed event."""
        self.consent_checker.resume()
        if self.consent_checker.is_collection_allowed():
            resumed_ev = self.event_builder.build_telemetry_resumed()
            self.event_queue.put(resumed_ev)
            self._flush_queue_to_storage()

    def stop(self) -> None:
        """Request agent shutdown."""
        self._stop_event.set()

    def _shutdown(self) -> None:
        """Execute orderly shutdown sequence."""
        logger.info("Executing graceful shutdown...")
        self._is_running = False

        # Stop sync worker
        self.sync_worker.stop()

        # Flush any remaining transition
        if self.consent_checker.is_collection_allowed("app_transitions"):
            last_deact = self.activity_tracker.flush_current_activity(transition_trigger="AGENT_SHUTDOWN")
            if last_deact:
                self.event_queue.put(last_deact)

        # Emit agent_stopped event if consented
        if self.consent_checker.is_collection_allowed():
            stopped_ev = self.event_builder.build_agent_stopped(
                uptime_seconds=time.monotonic() - self.health_monitor.start_time_monotonic
            )
            self.event_queue.put(stopped_ev)

        # Flush all remaining events to SQLite
        while not self.event_queue.is_empty():
            self._flush_queue_to_storage()

        self.local_db.close()
        logger.info("ContextIQ Desktop Agent terminated cleanly.")

    def _initial_backend_sync(self) -> None:
        """Query server for initial consent, settings, and exclusions."""
        try:
            settings = self.api_client.get_privacy_settings(self.config.user_id)
            consent = self.api_client.get_active_consent(self.config.user_id)
            if settings is not None:
                self.consent_checker.update_from_backend(settings, consent)
                logger.info(
                    "Initial consent loaded: enabled=%s, paused=%s",
                    self.consent_checker.is_telemetry_enabled,
                    self.consent_checker.is_paused,
                )

            exclusions = self.api_client.get_app_exclusions(self.config.user_id)
            if exclusions:
                self.exclusion_manager.update_from_backend(exclusions)
        except Exception as e:
            logger.debug("Initial backend synchronization failed (will operate offline): %s", e)

"""Configuration settings for ContextIQ Windows Desktop Behavioral Activity Collector."""
import hashlib
import os
import platform
import uuid
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings


def get_default_device_id() -> str:
    """Generate deterministic device identifier based on machine characteristics."""
    raw_id = f"{platform.node()}-{uuid.getnode()}-{platform.machine()}"
    return hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:32]


class AgentConfig(BaseSettings):
    """Desktop Agent runtime configuration settings."""

    # Server connection
    backend_url: str = Field(
        default="http://localhost:8000/api/v1",
        description="ContextIQ backend REST API base URL",
    )
    api_token: str | None = Field(
        default=None,
        description="Optional Bearer token for server authentication",
    )
    user_id: str = Field(
        default="00000000-0000-0000-0000-000000000001",
        description="ContextIQ user UUID",
    )
    device_id: str = Field(
        default_factory=get_default_device_id,
        description="Unique device hardware hash",
    )
    device_name: str = Field(
        default_factory=platform.node,
        description="Local computer name",
    )

    # Polling & timing configuration
    polling_interval_seconds: float = Field(
        default=0.5,
        ge=0.1,
        le=5.0,
        description="Sampling loop sleep interval in seconds",
    )
    idle_threshold_seconds: float = Field(
        default=120.0,
        ge=10.0,
        description="Inactivity duration in seconds before user_idle_started is emitted",
    )
    rapid_switch_threshold_seconds: float = Field(
        default=0.2,
        ge=0.05,
        description="Transitions shorter than this duration are flagged as rapid switches",
    )

    # Local buffer database
    db_path: str = Field(
        default="data/agent_buffer.db",
        description="Relative or absolute path to SQLite persistence database",
    )
    max_queue_size: int = Field(
        default=1000,
        description="Maximum in-memory queue capacity before dropping or blocking",
    )

    # Synchronization
    sync_interval_seconds: float = Field(
        default=10.0,
        ge=1.0,
        description="Frequency of background batch sync in seconds",
    )
    batch_size: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum events dispatched per sync request",
    )
    max_retries: int = Field(
        default=5,
        description="Maximum retry attempts before marking event as permanently failed",
    )

    # Monitoring & health
    heartbeat_interval_seconds: float = Field(
        default=60.0,
        ge=5.0,
        description="Interval for health heartbeat telemetry emission",
    )

    # Privacy configuration (Strict anti-surveillance defaults)
    capture_window_titles: bool = Field(
        default=False,
        description="Strictly False: window titles are omitted by default to protect message/document privacy",
    )

    class Config:
        env_prefix = "CONTEXTIQ_AGENT_"
        case_sensitive = False

    def get_absolute_db_path(self, base_dir: Path | None = None) -> Path:
        """Resolve database path relative to agent root or absolute."""
        p = Path(self.db_path)
        if p.is_absolute():
            return p
        if base_dir is None:
            base_dir = Path(__file__).resolve().parent.parent
        return (base_dir / p).resolve()

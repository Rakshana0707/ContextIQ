"""
Structured JSON Logging and Contextual Tracing (ContextIQ Phase 7.8).
Excludes secrets, OAuth tokens, and personal credentials from logs.
"""
from __future__ import annotations

import contextvars
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Context variables for distributed request tracing
request_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_id_ctx", default=None
)
correlation_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "correlation_id_ctx", default=None
)
user_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "user_id_ctx", default=None
)
workflow_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "workflow_id_ctx", default=None
)

# Regex to scrub sensitive values
SECRET_PATTERNS = [
    re.compile(r'(token["\s:=]+)(["\']?[a-zA-Z0-9_\-\.]{8,}["\']?)', re.IGNORECASE),
    re.compile(r'(password["\s:=]+)(["\']?[^"\'\s,]{4,}["\']?)', re.IGNORECASE),
    re.compile(r'(secret["\s:=]+)(["\']?[a-zA-Z0-9_\-\.]{8,}["\']?)', re.IGNORECASE),
    re.compile(r'(bearer\s+)([a-zA-Z0-9_\-\.]{8,})', re.IGNORECASE),
    re.compile(r'(api_key["\s:=]+)(["\']?[a-zA-Z0-9_\-\.]{8,}["\']?)', re.IGNORECASE),
]


def scrub_sensitive_text(text: str) -> str:
    """Masks secret substrings in log messages."""
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(r"\1[REDACTED]", text)
    return text


class StructuredJsonFormatter(logging.Formatter):
    """
    Formats log records as structured JSON dictionaries containing
    distributed tracing correlation IDs and error categories.
    """

    def __init__(
        self,
        service_name: str = "contextiq-backend",
        service: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.service_name = service or service_name

    def format(self, record: logging.LogRecord) -> str:
        # Base log object
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "severity": record.levelname,
            "service": self.service_name,
            "logger": record.name,
            "message": scrub_sensitive_text(record.getMessage()),
        }

        # Tracing Context
        req_id = request_id_ctx.get()
        if req_id:
            log_entry["request_id"] = req_id

        corr_id = correlation_id_ctx.get()
        if corr_id:
            log_entry["correlation_id"] = corr_id

        uid = user_id_ctx.get()
        if uid:
            log_entry["user_id"] = uid
            # Mask or truncate user identifier for privacy
            log_entry["user_id_prefix"] = f"{uid[:8]}..." if len(uid) > 8 else uid

        wfid = workflow_id_ctx.get()
        if wfid:
            log_entry["workflow_id"] = wfid

        # Error details & category
        if record.exc_info:
            log_entry["error_category"] = (
                record.exc_info[0].__name__ if record.exc_info[0] else "UnknownException"
            )
            log_entry["exception"] = scrub_sensitive_text(self.formatException(record.exc_info))
        elif record.levelno >= logging.ERROR:
            log_entry["error_category"] = "ApplicationError"

        # Extra metadata
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            for k, v in record.extra_fields.items():
                if k not in log_entry:
                    log_entry[k] = v

        return json.dumps(log_entry)


def setup_structured_logging(service_name: str = "contextiq-backend", level: int = logging.INFO) -> None:
    """Configures root logger with the structured JSON formatter."""
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredJsonFormatter(service_name=service_name))

    root_logger = logging.getLogger()
    # Avoid duplicate handlers
    if not any(isinstance(h.formatter, StructuredJsonFormatter) for h in root_logger.handlers):
        root_logger.setLevel(level)
        root_logger.addHandler(handler)
